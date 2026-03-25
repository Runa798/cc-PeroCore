import asyncio
import base64
import json
import logging
import os
import re
import time
import uuid
from typing import Optional

from sqlmodel import select

# from services.agent.agent_service import AgentService # Moved to local import to avoid circular dependency
from database import get_session
from models import AIModelConfig, Config
from peroproto import perolink_pb2
from services.core.gateway_client import gateway_client
from services.core.gateway_hub import gateway_hub
from services.interaction.tts_service import get_tts_service
from services.perception.asr_service import get_asr_service

# 配置日志
logger = logging.getLogger(__name__)


class RealtimeSessionManager:
    """
    实时会话管理器 (原 VoiceManager)
    - 接收前端音频流/文本流
    - VAD 检测 (目前由前端做，这里只接收分片)
    - 语音转文字 (ASR)
    - 文本对话 (Agent)
    - 文字转语音 (TTS)
    - 推送音频流/文本流回前端
    """

    def __init__(self):
        self.asr_service = get_asr_service()
        self.tts_service = get_tts_service()
        self.current_task: Optional[asyncio.Task] = None
        self.pending_confirmations: dict[str, asyncio.Future] = {}
        self.active_commands: dict[int, asyncio.Event] = {}

    def initialize(self):
        """初始化网关监听器"""
        gateway_client.on("stream", self.handle_stream)
        gateway_client.on("action:voice_interaction", self.handle_voice_interaction)
        gateway_client.on("action:confirm", self.handle_confirmation_response_action)
        logger.info("实时会话管理器已使用 GatewayClient 初始化")

    async def handle_stream(self, envelope):
        """处理传入的音频流"""
        # 目前我们期望客户端完成 VAD，接收完整的语音片段？
        # 还是原始流？
        # 如果 stream_id 暗示一个会话。
        # 目前，假设客户端发送的一个流代表一个“语音结束”等价物或原始块。
        # 但查看之前的逻辑：“speech_end”事件包含 base64 数据。
        # DataStream 负载包含字节。

        # 如果它是完整的音频文件（模拟流）：
        if envelope.stream.is_end:
            # 作为语音轮次处理
            await self._process_voice_turn_gateway(
                envelope.source_id, envelope.stream.data, envelope.trace_id
            )

    async def handle_voice_interaction(self, envelope):
        """处理语音控制消息（文本、状态等）"""
        req = envelope.request
        msg_type = req.params.get("type")

        if msg_type == "text":
            # 处理等同于语音的文本输入
            pass  # 待办事项

    async def handle_confirmation_response_action(self, envelope):
        """通过 ActionRequest 处理确认响应"""
        req = envelope.request
        req_id = req.params.get("id")
        approved = req.params.get("approved") == "true"

        if req_id in self.pending_confirmations:
            future = self.pending_confirmations[req_id]
            if not future.done():
                future.set_result(approved)
        else:
            logger.warning(f"收到未知请求的确认: {req_id}")

    # ... existing methods ...

    def register_skippable_command(self, pid: int, event: asyncio.Event):
        """注册一个可跳过等待的命令"""
        self.active_commands[pid] = event

    def unregister_skippable_command(self, pid: int):
        """注销命令"""
        if pid in self.active_commands:
            del self.active_commands[pid]

    def skip_command(self, pid: int) -> bool:
        """触发跳过命令等待"""
        if pid in self.active_commands:
            logger.info(f"跳过 PID {pid} 的命令等待")
            self.active_commands[pid].set()
            return True
        return False

    async def broadcast_gateway(self, message: dict):
        """通过网关广播消息"""
        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = gateway_client.device_id
        envelope.target_id = "broadcast"
        envelope.timestamp = int(time.time() * 1000)

        envelope.request.action_name = "voice_update"
        for k, v in message.items():
            envelope.request.params[k] = str(v)

        await gateway_hub.broadcast_envelope(envelope)

    async def broadcast(self, message: dict):
        """[已弃用] 将旧版广播调用转发到网关"""
        await self.broadcast_gateway(message)

    async def send_audio_stream_gateway(
        self, target_id: str, trace_id: str, audio_path: str
    ):
        """通过网关以 DataStream 发送音频文件"""
        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = gateway_client.device_id
            envelope.target_id = target_id
            envelope.timestamp = int(time.time() * 1000)
            envelope.trace_id = trace_id

            # 使用 DataStream
            envelope.stream.stream_id = str(uuid.uuid4())
            envelope.stream.data = audio_data
            envelope.stream.is_end = True
            envelope.stream.content_type = "audio/mp3"  # 或基于文件的 wav

            await gateway_hub.broadcast_envelope(envelope)
        except Exception as e:
            logger.error(f"通过网关发送音频流失败: {e}")

    async def _process_voice_turn_gateway(
        self, source_id: str, audio_bytes: bytes, trace_id: str
    ):
        """通过网关处理语音轮次"""
        import time

        start_turn_time = time.time()

        # 1. 保存临时文件
        temp_audio_path = f"temp_voice_gw_{source_id}_{int(time.time())}.wav"
        try:
            print("\n" + "=" * 60)
            print(f"[Gateway Voice] 开始对话轮次 {time.strftime('%H:%M:%S')}")
            print("=" * 60)

            with open(temp_audio_path, "wb") as f:
                f.write(audio_bytes)

            # 2. ASR
            print("[ASR] 正在转录...")
            await self.broadcast_gateway({"type": "status", "content": "listening"})

            asr_start = time.time()
            try:
                user_text = await self.asr_service.transcribe(temp_audio_path)
            except Exception as e:
                error_msg = f"ASR 失败: {str(e)}"
                logger.error(error_msg)
                await self.broadcast_gateway(
                    {"type": "text_response", "content": f"[{error_msg}]"}
                )
                await self.broadcast_gateway({"type": "status", "content": "idle"})
                return

            asr_duration = time.time() - asr_start

            if not user_text or not user_text.strip():
                print(f"[ASR] 未检测到语音 ({asr_duration:.2f}s).")
                await self.broadcast_gateway({"type": "status", "content": "idle"})
                return

            print(f'[ASR] 用户: "{user_text}" ({asr_duration:.2f}s)')
            await self.broadcast_gateway(
                {"type": "transcription", "content": user_text}
            )

            # 重置陪伴计时器
            try:
                from services.agent.companion_service import companion_service

                companion_service.update_activity()
            except Exception as e:
                logger.warning(f"更新活动失败: {e}")

            # 3. 助手
            print("[Agent] 正在生成回复...")

            session_id = "voice_session"

            async def report_status(status_type: str, content: str):
                from services.agent.task_manager import task_manager

                turn_count = 0
                if session_id:
                    turn_count = task_manager.get_turn_count(session_id)

                await self.broadcast_gateway(
                    {
                        "type": "status",
                        "content": status_type,
                        "message": content,
                        "turn_count": turn_count,
                    }
                )

            await self.broadcast_gateway({"type": "status", "content": "thinking"})

            agent_start = time.time()
            async for session in get_session():
                # 检查原生语音输入
                enable_voice_input = False
                try:
                    config_obj = (
                        await session.exec(
                            select(Config).where(Config.key == "current_model_id")
                        )
                    ).first()
                    if config_obj and config_obj.value:
                        model_id_db = int(config_obj.value)
                        model_config = await session.get(AIModelConfig, model_id_db)
                        if model_config and model_config.enable_voice:
                            enable_voice_input = True
                except Exception:
                    pass

                messages_payload = [{"role": "user", "content": user_text}]
                if enable_voice_input:
                    try:
                        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                        messages_payload = [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"[User speaking (ASR: {user_text})]",
                                    },
                                    {
                                        "type": "input_audio",
                                        "input_audio": {
                                            "data": audio_b64,
                                            "format": "wav",
                                        },
                                    },
                                ],
                            }
                        ]
                    except Exception as e:
                        print(f"准备音频负载失败: {e}")

                from services.agent.agent_service import AgentService

                agent = AgentService(session)
                full_response = ""
                generation_error = None

                try:
                    last_broadcasted_ui_text = ""
                    async for chunk in agent.chat(
                        messages_payload,
                        source="gateway",
                        session_id="voice_session",
                        on_status=report_status,
                        is_voice_mode=True,
                        user_text_override=user_text,
                    ):
                        if chunk:
                            # 过滤掉 SSE 事件（内部信号）
                            if chunk.startswith("data:"):
                                continue

                            full_response += chunk

                            # [增量广播]
                            # 尝试清理文本以查看是否有可显示的内容
                            current_ui_text = self._clean_text(
                                full_response, for_tts=False
                            )
                            # 仅当内容存在且已更改时才广播
                            if (
                                current_ui_text
                                and current_ui_text != last_broadcasted_ui_text
                            ):
                                await self.broadcast_gateway(
                                    {
                                        "type": "text_response",
                                        "content": current_ui_text,
                                    }
                                )
                                last_broadcasted_ui_text = current_ui_text

                except Exception as e:
                    print(f"生成错误: {e}")
                    generation_error = str(e)

                agent_duration = time.time() - agent_start
                print(
                    f"[Agent] 回复已生成 ({len(full_response)} 字符, {agent_duration:.2f}s)"
                )

                # 4. 处理响应和 TTS
                ui_response = self._clean_text(full_response, for_tts=False)
                tts_response = self._clean_text(full_response, for_tts=True)

                if not ui_response:
                    if generation_error:
                        ui_response = f"(错误: {generation_error})"
                        tts_response = "哎呀，出错了。"
                    elif full_response.strip():
                        ui_response = "(Pero 执行了动作...)"
                    else:
                        ui_response = "..."
                if not tts_response:
                    tts_response = "..."

                # 发送文本
                await self.broadcast_gateway({"type": "status", "content": "speaking"})
                await self.broadcast_gateway(
                    {"type": "text_response", "content": ui_response}
                )

                # TTS
                target_voice, target_rate, target_pitch = self._get_voice_params(
                    full_response
                )
                print(f"[TTS] 正在合成 {target_voice}...")
                tts_start = time.time()
                audio_path = await self.tts_service.synthesize(
                    tts_response,
                    voice=target_voice,
                    rate=target_rate,
                    pitch=target_pitch,
                )
                tts_duration = time.time() - tts_start

                if audio_path:
                    print(f"[TTS] 音频就绪 ({tts_duration:.2f}s). 正在发送流.")
                    await self.send_audio_stream_gateway(
                        source_id, trace_id, audio_path
                    )
                else:
                    print("❌ TTS 失败.")

                total_duration = time.time() - start_turn_time
                print(f"🏁 [Gateway Voice] 对话轮次结束 ({total_duration:.2f}s)\n")

                await self.broadcast_gateway({"type": "status", "content": "idle"})
                break

        except Exception as e:
            logger.error(f"Gateway 语音错误: {e}")
            await self.broadcast_gateway({"type": "error", "content": str(e)})
        finally:
            if os.path.exists(temp_audio_path):
                import contextlib

                with contextlib.suppress(Exception):
                    os.remove(temp_audio_path)

    async def request_user_confirmation(
        self, command: str, risk_info: dict = None, is_high_risk: bool = False
    ) -> bool:
        """
        向前端发送确认请求，并等待用户响应。
        返回 True (同意) 或 False (拒绝)。
        :param command: 指令内容
        :param risk_info: 详细的风险审计信息 {level, reason, highlight}
        :param is_high_risk: (兼容旧参数) 是否高风险，如果 risk_info 存在，优先使用 risk_info['level'] >= 2 判断
        """
        import uuid

        request_id = str(uuid.uuid4())

        # 创建 Future 以等待响应
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_confirmations[request_id] = future

        # 兼容处理
        if risk_info is None:
            risk_info = {
                "level": 2 if is_high_risk else 1,
                "reason": "检测到高风险操作" if is_high_risk else "常规操作",
                "highlight": None,
            }

        try:
            # 广播请求
            payload = {
                "type": "confirmation_request",
                "id": request_id,
                "command": command,
                "risk_info": json.dumps(risk_info),  # Gateway 参数必须为字符串
                "is_high_risk": str(risk_info["level"] >= 2),
            }
            await self.broadcast_gateway(payload)
            # 旧版广播已移除

            # 等待响应 (设置超时，例如 5 分钟)
            result = await asyncio.wait_for(future, timeout=300)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"确认请求 {request_id} 超时。")
            return False
        finally:
            if request_id in self.pending_confirmations:
                del self.pending_confirmations[request_id]

    def _clean_text(self, text: str, for_tts: bool = True) -> str:
        """清洗文本，移除标签、动作描述等不应朗读的内容"""
        if not text:
            return ""

        cleaned = text

        # 1. 移除 XML 标签 (包括内容)
        cleaned = re.sub(r"<[^>]+>.*?</[^>]+>", "", cleaned, flags=re.DOTALL)

        # 2. 移除 NIT 调用块
        from nit_core.dispatcher import remove_nit_tags

        cleaned = remove_nit_tags(cleaned)

        if for_tts:
            # [重要] 优先移除 Markdown 代码块，避免朗读代码内容
            # 匹配 ```...``` (多行) 和 `...` (单行)
            cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
            cleaned = re.sub(r"`[^`\n]+`", " ", cleaned)

            # [重要] 移除 URL 链接
            cleaned = re.sub(r"https?://\S+", " ", cleaned)

            # [特性] 智能 ReAct 过滤器
            # 目标：只朗读最终回复，忽略 思考/计划/行动/观察 (Thinking/Plan/Action/Observation) 的历史记录。

            # 0. 全局移除思考 (Thinking) 和 碎碎念 (Monologue)
            # 无论是否检测到 Final Answer，这些内容都绝对不应该朗读
            cleaned = re.sub(
                r"【(?:Thinking|Monologue).*?】",
                "",
                cleaned,
                flags=re.DOTALL | re.IGNORECASE,
            )
            cleaned = re.sub(
                r"\[(?:Thinking|Monologue).*?\]",
                "",
                cleaned,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # 策略 1：如果存在 "Final Answer" (最终回答) 标记，则提取其后的所有内容。
            final_marker = re.search(
                r"(?:Final Answer|最终回答|回复)[:：]?\s*(.*)",
                cleaned,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if final_marker:
                cleaned = final_marker.group(1)
            else:
                # 策略 2：通过已知的 ReAct 块标题进行分割，并提取最后一块。
                # 这假设回复总是在最后。

                # 标准化换行符
                cleaned = cleaned.replace("\r\n", "\n")

                # 识别最后一个 "技术标题" 并提取其后的内容
                # 标题包括：Plan:, Action:, Observation:, Result:, Thought:
                # 我们查找这些标题在行首的最后一次出现
                headers_pattern = r"(?m)^(?:Plan|计划|Action|Action Input|Observation|Result|Thought|Prompt)[:：]"

                matches = list(re.finditer(headers_pattern, cleaned))
                if matches:
                    last_match = matches[-1]
                    # 从最后一个标题之后的行开始
                    # 等等，如果最后一个标题是 "Plan:"，我们也想跳过计划内容。
                    # 计划内容通常在下一个标题或双换行符处结束。
                    # 既然我们找到了最后一个标题，那么它之后的内容要么是该标题的内容，要么是最终回复。

                    cleaned[last_match.start() :]

                    # 启发式规则：如果是 Observation/Result/Action，我们要么不读它。
                    # 但如果它是剩下的唯一内容，也许我们什么都不应该读？
                    # 然而，通常在技术块之后会有文本。

                    # 让我们尝试移除与最后一个块关联的 *行*，如果它们看起来像技术内容。
                    # 但更简单的方法：最终回复通常不以关键字开头。
                    # 所以如果我们有 `Observation: ... \n Hello`，我们要的是 `Hello`。

                    # 让我们使用一个 "块剥离器" (Block Stripper) 来移除所有已知的技术块。
                    # 正则表达式匹配技术块：标题 -> 内容 -> 下一个标题/结尾

                    block_pattern = r"(?m)^(?:Plan|计划|Action|Action Input|Observation|Result|Thought|Prompt)[:：][\s\S]*?(?=(?:^(?:Plan|计划|Action|Action Input|Observation|Result|Thought|Prompt|Final Answer|最终回答|回复)[:：])|\Z)"
                    cleaned = re.sub(block_pattern, "", cleaned)

        # 4. 移除动作描述 *...* 或 (动作) 或 （动作）
        if for_tts:
            cleaned = re.sub(r"\*.*?\*", "", cleaned)
            cleaned = re.sub(r"\(.*?\)", "", cleaned)  # 移除半角括号内的动作或备注
            cleaned = re.sub(r"（.*?）", "", cleaned)  # 移除全角括号内的动作或备注

        # 5. 移除 Markdown 标记
        if for_tts:
            cleaned = re.sub(r"#+\s+", "", cleaned)  # 移除标题符号
            cleaned = re.sub(
                r"\[(.*?)\]\(.*?\)", r"\1", cleaned
            )  # 移除链接，只保留文字
            cleaned = re.sub(r"[*_~]", "", cleaned)  # 移除粗体、斜体、删除线等标记

        # 6. 移除 Emoji 和特殊符号 (仅针对 TTS)
        if for_tts:
            # 移除常见 Emoji
            cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)
            # 移除特定颜文字或符号
            cleaned = re.sub(
                r"[^\w\s\u4e00-\u9fa5，。！？；：“”（）\n\.,!\?\-]", "", cleaned
            )
            # 进一步清洗可能残留的连续标点或无意义字符
            cleaned = re.sub(r"[\-_]{2,}", " ", cleaned)

        # 7. 移除多余空白
        cleaned = re.sub(r"\n+", "\n", cleaned).strip()

        return cleaned

    def _get_voice_params(self, full_response: str):
        """鲁棒地根据回复中的心情标签 (XML 或 NIT) 或内容，动态调整语音参数"""
        # 统一使用晓伊音色，作为全局默认基础值
        voice = "zh-CN-XiaoyiNeural"
        rate = "+15%"
        pitch = "+5Hz"

        # 尝试提取心情关键词
        mood_text = ""

        # 方案 A: 从回复内容中寻找心情暗示 (简单的关键词匹配)
        mood_keywords = {
            "happy": ["开心", "高兴", "兴奋", "乐"],
            "sad": ["伤心", "难过", "哭", "委屈"],
            "angry": ["生气", "愤怒", "火大", "恼"],
            "neutral": ["好吧", "知道", "哦", "嗯"],
        }

        for mood, keywords in mood_keywords.items():
            if any(k in full_response for k in keywords):
                mood_text = mood
                break

        # 方案 B: 尝试正则匹配 <PEROCUE> 标签 (旧版兼容)
        if not mood_text:
            perocue_match = re.search(r"<PEROCUE>(.*?)</PEROCUE>", full_response, re.S)
            if perocue_match:
                raw_content = perocue_match.group(1).strip()
                try:
                    data = json.loads(raw_content)
                    mood_text = str(data.get("mood", ""))
                except Exception:
                    mood_match = re.search(
                        r'["\']mood["\']\s*:\s*["\']([^"\']+)["\']', raw_content
                    )
                    if mood_match:
                        mood_text = mood_match.group(1)

        # 方案 C: 如果标签解析彻底失败，就在整个文本中搜索“心情”相关的词（最后的保底）
        if not mood_text:
            mood_text = full_response

        # 情绪微调逻辑 (在晓伊的基础上进行微调)
        if any(
            word in mood_text
            for word in ["兴奋", "开心", "喜悦", "激昂", "嘿嘿", "太棒了"]
        ):
            # 保持巅峰状态
            rate = "+20%"
            pitch = "+7Hz"
        elif any(
            word in mood_text for word in ["难过", "低落", "委屈", "疲惫", "唔", "呜"]
        ):
            # 稍微沉稳一点，但依然保留晓伊的底色
            rate = "+5%"
            pitch = "+2Hz"
        elif any(word in mood_text for word in ["生气", "愤怒", "哼"]):
            # 语速加快，音调变冲
            rate = "+25%"
            pitch = "+4Hz"
        elif any(word in mood_text for word in ["温馨", "温情", "爱", "主人"]):
            # 稍微慢一点，显得乖巧
            rate = "+10%"
            pitch = "+5Hz"

        return voice, rate, pitch

    def _extract_triggers(self, text: str) -> dict:
        """
        [已弃用] 从 LLM 回复中提取交互类触发器标签。
        现已由 NIT 协议下的 UpdateStatusPlugin 统一处理。
        """
        return {}


# 单例
realtime_session_manager = RealtimeSessionManager()
