"""
AgentService
============
Agent 服务编排层（重构后精简版）。

本文件职责：
  - 初始化并组装各子模块（ConfigLoader、ToolPolicyEngine、ToolExecutor、ReActLoop、PostHandler）
  - 编排 chat() 主流程（约 150 行）
  - 保留少量不便迁移的辅助方法（反思、主动观察、Prompt 预览、Pet 状态读取）

子模块说明：
  _config_loader.py   → LLM/反思/MCP 配置加载
  _tool_policy.py     → 工具发现与策略过滤
  _tool_executor.py   → Function Calling 执行分发
  _react_loop.py      → ReAct 推理-行动主循环
  _post_handler.py    → 日志持久化、Scorer、梦境调度
  _background_tasks.py→ 后台异步任务（TTS/梦境/Scorer）
"""

import asyncio
import uuid
from typing import Any, AsyncIterable, Dict, List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.component_container import ComponentContainer
from core.nit_manager import get_nit_manager
from interfaces.core import (
    IPostprocessorManager,
    IPreprocessorManager,
    IPromptManager,
)
from models import ConversationLog, PetState, ScheduledTask
from nit_core.security import NITSecurityManager
from nit_core.tools.core.WindowsOps.windows_ops import get_active_windows
from services.agent._config_loader import AgentConfigLoader
from services.agent._post_handler import AgentPostHandler
from services.agent._react_loop import ReActLoop
from services.agent._tool_executor import AgentToolExecutor
from services.agent._tool_policy import ToolPolicyEngine
from services.agent.task_manager import task_manager
from services.core.llm_service import LLMService
from services.core.nsfw_detector import is_nsfw
from services.core.session_service import set_current_session_context
from services.memory.memory_service import MemoryService
from services.memory.scorer_service import ScorerService


class AgentService:
    """
    Agent 服务编排层。
    负责将预处理、工具构建、ReAct 循环、后处理各阶段串联起来。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

        # 注入 session 和 agent_id 用于工具操作
        import contextlib

        from services.agent.agent_manager import get_agent_manager

        agent_id = "pero"
        with contextlib.suppress(Exception):
            agent_id = get_agent_manager().active_agent_id

        set_current_session_context(session, agent_id)

        self.memory_service = MemoryService()
        self.scorer_service = ScorerService(session)

        self.prompt_manager = ComponentContainer.get(IPromptManager)
        self.mdp = self.prompt_manager.mdp

        self.preprocessor_manager = ComponentContainer.get(IPreprocessorManager)
        self.postprocessor_manager = ComponentContainer.get(IPostprocessorManager)

        # 初始化各子模块
        self.config_loader = AgentConfigLoader(session)
        self.tool_policy = ToolPolicyEngine(session, self.mdp)
        self.tool_executor = AgentToolExecutor(session, self.mdp)
        self.post_handler = AgentPostHandler(
            session, self.memory_service, self.postprocessor_manager
        )

    async def _get_llm_config(self) -> Dict[str, Any]:
        """兼容方法：供外部代码（预处理器等）通过 agent_service 获取 LLM 配置。"""
        return await self.config_loader.get_llm_config()

    # ─────────────────────────────────────────────
    # 主入口
    # ─────────────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        source: str = "desktop",
        session_id: str = "default",
        on_status: Optional[Any] = None,
        is_voice_mode: bool = False,
        user_text_override: str = None,
        skip_save: bool = False,
        system_trigger_instruction: str = None,
        agent_id_override: str = None,
        capabilities: List[str] = None,
        skip_system_prompt: bool = False,
        initial_variables: Dict[str, Any] = None,
    ) -> AsyncIterable[str]:
        """Agent 聊天主入口，异步生成器，流式 yield 响应文本。"""

        # ── NIT 安全 ID ──
        current_nit_id = NITSecurityManager.generate_random_id()

        # ── 通知 CompanionService 用户活动 ──
        await self._notify_companion_activity(source)

        # ── 取消待处理"反应"任务 ──
        if not system_trigger_instruction:
            await self._cancel_reaction_tasks(agent_id_override, source)

        # ── 确定当前 Agent ID ──
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        current_agent_id = agent_id_override or agent_manager.active_agent_id or "pero"

        print(
            f"[Agent] 收到聊天请求。来源: {source}, 消息数: {len(messages)}, "
            f"语音: {is_voice_mode}, Agent: {current_agent_id}"
        )

        # ── 1. 加载 LLM 配置 ──
        config = await self.config_loader.get_llm_config()

        # ── 1.5 /model 命令：手动切换模型 ──
        model_switch_reply = await self._handle_model_command(messages, config)
        if model_switch_reply is not None:
            yield model_switch_reply
            return

        # ── 2. 加载 MCP 客户端 ──
        if on_status:
            await on_status("thinking", "正在加载工具...")
        mcp_clients = []
        try:
            mcp_clients = await self.config_loader.get_mcp_clients()
            print(f"[Agent] 加载了 {len(mcp_clients)} 个 MCP 客户端")
        except Exception as e:
            print(f"[Agent] 获取 MCP 客户端失败: {e}")

        # ── 3. 构建工具列表（策略过滤）──
        (
            final_tools,
            mcp_tool_map,
            allowed_tool_names,
        ) = await self.tool_policy.build_tool_list(
            source, session_id, current_agent_id, mcp_clients, config
        )

        # ── 4. 初始化上下文 ──
        context = {
            "messages": messages,
            "source": source,
            "session_id": session_id,
            "session": self.session,
            "memory_service": self.memory_service,
            "prompt_manager": self.prompt_manager,
            "user_text_override": user_text_override,
            "is_voice_mode": is_voice_mode,
            "agent_service": self,
            "agent_id": current_agent_id,
            "variables": initial_variables or {},
            "nit_id": current_nit_id,
            "skip_system_prompt": skip_system_prompt,
            "dynamic_tools": final_tools,
            "mcp_clients": mcp_clients,
            "mcp_tool_map": mcp_tool_map,
            "allowed_tool_names": allowed_tool_names,
        }

        # ── 5. 运行预处理器管道 ──
        if on_status:
            await on_status("thinking", "正在整理记忆和思绪...")
        context = await self.preprocessor_manager.process(context)

        user_message = context.get("user_message", "")
        final_messages = context.get("final_messages", [])

        # ── 6. 注入系统触发指令 ──
        if system_trigger_instruction:
            self._inject_system_trigger(final_messages, system_trigger_instruction)
            if not user_message:
                user_message = f"【系统触发】{system_trigger_instruction}"

        # ── 7. 注入移动端来源感知 ──
        if source == "mobile":
            self._inject_mobile_context(final_messages)

        # ── 8. 注入活跃窗口信息 ──
        if source not in ["social", "mobile"]:
            self._inject_active_windows(final_messages)

        # ── 9. 工具开关判断 ──
        disable_native_tools = await self._check_native_tools_disabled()
        tools_to_pass = (
            None
            if (disable_native_tools or session_id == "companion_mode")
            else final_tools
        )

        if session_id == "companion_mode":
            print("[Agent] Companion 模式: 禁用 Function Calling (Tools=None)")
        if disable_native_tools:
            print("[Agent] 原生工具 (Function Calling) 已通过配置禁用。")

        print(f"[Agent] 通过预处理器构建 Prompt。消息数: {len(final_messages)}")

        # ── NSFW 自动路由：claude_code 不支持 NSFW，自动切到 fallback 模型 ──
        effective_config = dict(config)
        if effective_config.get("provider") == "claude_code" and is_nsfw(final_messages):
            fallback = await self._get_nsfw_fallback_config()
            if fallback:
                print(f"[Agent] NSFW 检测命中，自动切换: claude_code → {fallback['provider']}:{fallback['model']}")
                effective_config.update(fallback)

        llm = LLMService(
            api_key=effective_config.get("api_key"),
            api_base=effective_config.get("api_base"),
            model=effective_config.get("model"),
            provider=effective_config.get("provider", "openai"),
        )

        pair_id = str(uuid.uuid4())
        full_response_text = ""
        raw_full_text = ""

        # ── 10. 运行 ReAct 循环 ──
        react_loop = ReActLoop(
            llm=llm,
            session=self.session,
            mdp=self.mdp,
            postprocessor_manager=self.postprocessor_manager,
            tool_executor=self.tool_executor,
            task_manager=task_manager,
        )

        accumulated_text = []

        try:
            async for chunk in react_loop.run(
                final_messages=final_messages,
                tools_to_pass=tools_to_pass,
                context=context,
                config=config,
                on_status=on_status,
                reflection_runner=self._run_reflection,
                mcp_clients=mcp_clients,
                mcp_tool_map=mcp_tool_map,
                allowed_tool_names=allowed_tool_names,
                tool_policy_engine=self.tool_policy,
                user_message=user_message,
            ):
                accumulated_text.append(chunk)
                yield chunk

            full_response_text = "".join(accumulated_text)
            raw_full_text = full_response_text

        except Exception as e:
            import traceback

            error_msg = f"Error: {str(e)}"
            print(f"[Agent] 聊天错误: {traceback.format_exc()}")

            # 空内容错误特殊处理
            err_lower = str(e).lower()
            if (
                "no valid content" in err_lower
                or "invalid api response" in err_lower
                or "choices array is missing" in err_lower
            ):
                from services.core.gateway_client import gateway_client

                asyncio.create_task(
                    gateway_client.broadcast_error(
                        message="API 未返回有效内容，可能是模型正在思考或被截断，请重试。",
                        title="无效响应",
                        error_type="error",
                    )
                )
                return

            # 错误路径：尝试保存日志
            await self.post_handler.handle_error(
                full_response_text=full_response_text,
                error_msg=error_msg,
                user_message=user_message,
                user_text_override=user_text_override,
                source=source,
                session_id=session_id,
                pair_id=pair_id,
                current_agent_id=current_agent_id,
            )
            yield error_msg
            return

        finally:
            # 清理 MCP 客户端资源
            import contextlib

            for client in mcp_clients:
                with contextlib.suppress(Exception):
                    await client.close()

        # ── 11. 后处理（保存/Scorer/梦境）──
        try:
            await self.post_handler.handle(
                full_response_text=full_response_text,
                raw_full_text=raw_full_text,
                user_message=user_message,
                user_text_override=user_text_override,
                source=source,
                session_id=session_id,
                pair_id=pair_id,
                current_agent_id=current_agent_id,
                messages=messages,
                skip_save=skip_save,
                is_voice_mode=is_voice_mode,
                mcp_clients=mcp_clients,
            )
        except Exception as post_err:
            print(f"[Agent] 后处理失败: {post_err}")

    # ─────────────────────────────────────────────
    # 辅助方法（保留在主类）
    # ─────────────────────────────────────────────

    async def _run_reflection(
        self, task: str, history: str, screenshot_base64: str = None
    ) -> str:
        """运行反思逻辑（依赖 mdp 渲染，保留在主类）。"""
        config = await self.config_loader.get_reflection_config()
        if not config:
            return None

        print("[Reflection] 触发反思机制...")

        nit_manager = get_nit_manager()
        from nit_core.tools import plugin_manager as pm

        current_tools_defs = []

        for plugin_name, manifest in pm.plugins.items():
            category = manifest.get("_category", "plugins")
            if not nit_manager.is_category_enabled(category):
                continue
            if not nit_manager.is_plugin_enabled(plugin_name):
                continue
            caps = manifest.get("capabilities", {})
            current_tools_defs.extend(
                caps.get("invocationCommands", caps.get("toolDefinitions", []))
            )

        tools_list_str = ""
        for tool_def in current_tools_defs:
            if "function" in tool_def:
                fn = tool_def["function"]
                tools_list_str += f"- {fn.get('name', 'unknown')}: {fn.get('description', '无描述')}\n"
            elif "commandIdentifier" in tool_def:
                tools_list_str += f"- {tool_def.get('commandIdentifier', 'unknown')}: {tool_def.get('description', '无描述')}\n"
            elif "name" in tool_def:
                tools_list_str += f"- {tool_def.get('name', 'unknown')}: {tool_def.get('description', '无描述')}\n"

        is_blind = not config.get("enable_vision")
        vision_prompt_name = "vision_enabled" if not is_blind else "vision_disabled"

        system_prompt = self.mdp.render(
            "tasks/memory/reflection/reflection_ui",
            {
                "tools_list_str": tools_list_str,
                "tools_count": len(tools_list_str),
                "vision_instruction": "{{" + vision_prompt_name + "}}",
            },
        )
        user_content = f"任务目标: {task}\n\n近期操作历史:\n{history}"
        messages = [{"role": "system", "content": system_prompt}]
        content = [{"type": "text", "text": user_content}]

        if screenshot_base64 and config.get("enable_vision"):
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"},
                }
            )
            print("[Reflection] 已将截图注入反思上下文。")

        messages.append({"role": "user", "content": content})

        try:
            llm = LLMService(
                api_key=config.get("api_key"),
                api_base=config.get("api_base"),
                model=config.get("model"),
                provider=config.get("provider", "openai"),
            )
            response = await llm.chat(
                messages, temperature=config.get("temperature", 0.7)
            )
            result = response["choices"][0]["message"]["content"]
            print(f"[Reflection] 结果: {result}")
            return result
        except Exception as e:
            print(f"[Reflection] 错误: {e}")
            return None

    async def preview_prompt(
        self, session_id: str, source: str, log_id: int
    ) -> Dict[str, Any]:
        """预览特定日志完整 Prompt（系统+历史+用户），用于调试/Dashboard。"""
        log = await self.session.get(ConversationLog, log_id)
        if not log:
            return {"error": "Log not found"}

        current_msg_log = None
        history_before_id = None

        if log.role == "assistant":
            stmt = (
                select(ConversationLog)
                .where(ConversationLog.session_id == session_id)
                .where(ConversationLog.source == source)
                .where(ConversationLog.id < log_id)
                .where(ConversationLog.role == "user")
                .order_by(desc(ConversationLog.id))
                .limit(1)
            )
            current_msg_log = (await self.session.exec(stmt)).first()
            history_before_id = current_msg_log.id if current_msg_log else log_id
        else:
            current_msg_log = log
            history_before_id = log_id

        messages = []
        if current_msg_log:
            messages.append({"role": "user", "content": current_msg_log.content})

        agent_id = log.agent_id or "pero"
        context = {
            "messages": messages,
            "source": source,
            "session_id": session_id,
            "session": self.session,
            "memory_service": self.memory_service,
            "prompt_manager": self.prompt_manager,
            "agent_service": self,
            "agent_id": agent_id,
            "variables": {"history_before_id": history_before_id, "is_preview": True},
            "skip_system_prompt": False,
        }

        context = await self.preprocessor_manager.process(context)
        return {"messages": context.get("final_messages", [])}

    async def handle_proactive_observation(self, intent_description: str, score: float):
        """处理 AuraVision 主动视觉观察结果。"""
        print(f"[Agent] 收到主动观察结果: {intent_description} (评分: {score:.4f})")
        self.mdp.render(
            "tasks/perception/proactive_internal_sense",
            {"intent_description": intent_description, "score": f"{score:.4f}"},
        )
        # TODO: 触发特殊会话
        pass

    async def _get_pet_state(self) -> PetState:
        """按活跃 Agent 过滤并读取 PetState。"""
        from services.agent.agent_manager import get_agent_manager

        active_agent_id = get_agent_manager().active_agent_id
        state = (
            await self.session.exec(
                select(PetState)
                .where(PetState.agent_id == active_agent_id)
                .order_by(desc(PetState.updated_at))
                .limit(1)
            )
        ).first()

        if not state:
            state = PetState(agent_id=active_agent_id)
            self.session.add(state)
            await self.session.commit()
            await self.session.refresh(state)
        return state

    # ─────────────────────────────────────────────
    # 私有辅助（内部流程）
    # ─────────────────────────────────────────────

    async def _notify_companion_activity(self, source: str):
        """通知 CompanionService 用户活动，防止主动陪伴中断。"""
        try:
            if source not in ["social", "mobile"]:
                from services.agent.companion_service import companion_service

                companion_service.update_activity()
        except Exception as e:
            print(f"[Agent] 更新陪伴活动失败: {e}")

    async def _cancel_reaction_tasks(self, agent_id_override: str, source: str):
        """用户交互时取消待处理的"反应"任务。"""
        try:
            from services.agent.agent_manager import get_agent_manager

            current_agent_id = agent_id_override or get_agent_manager().active_agent_id
            statement = (
                select(ScheduledTask)
                .where(ScheduledTask.type == "reaction")
                .where(not ScheduledTask.is_triggered)
                .where(ScheduledTask.agent_id == current_agent_id)
            )
            tasks_to_cancel = (await self.session.exec(statement)).all()
            if tasks_to_cancel:
                print(f"[Agent] 用户交互，取消 {len(tasks_to_cancel)} 个反应任务")
                for t in tasks_to_cancel:
                    await self.session.delete(t)
                await self.session.commit()
        except Exception as e:
            print(f"[Agent] 取消反应任务失败: {e}")

    def _inject_system_trigger(self, final_messages: List[Dict], instruction: str):
        """注入系统触发指令到消息列表。"""
        print(f"[Agent] 追加系统触发指令: {instruction}")
        trigger_block = f"<System_Trigger>\n{instruction}\n</System_Trigger>"
        if final_messages and final_messages[0]["role"] == "system":
            final_messages[0]["content"] += f"\n\n{trigger_block}"
        else:
            final_messages.insert(0, {"role": "system", "content": trigger_block})

    def _inject_mobile_context(self, final_messages: List[Dict]):
        """注入移动端来源感知 Prompt。"""
        mobile_instruction = self.mdp.render("components/context/mobile")
        if final_messages and final_messages[0]["role"] == "system":
            final_messages[0]["content"] += f"\n\n{mobile_instruction}"
        else:
            final_messages.insert(0, {"role": "system", "content": mobile_instruction})
        print("[Agent] 已注入移动端来源感知。")

    def _inject_active_windows(self, final_messages: List[Dict]):
        """注入当前活跃窗口列表，防止 AI 幻觉。"""
        try:
            active_windows = get_active_windows()
            if isinstance(active_windows, list) and active_windows:
                window_list_str = "\n".join(active_windows[:20])
                if len(active_windows) > 20:
                    window_list_str += f"\n... ({len(active_windows) - 20} more)"

                state_msg = self.mdp.render(
                    "components/context/active_windows",
                    {"window_list_str": window_list_str},
                )
                if final_messages and final_messages[0]["role"] == "system":
                    final_messages[0]["content"] += f"\n\n{state_msg}"
                else:
                    final_messages.insert(0, {"role": "system", "content": state_msg})
        except Exception as e:
            print(f"[Agent] 注入活跃窗口失败: {e}")

    async def _check_native_tools_disabled(self) -> bool:
        """检查是否通过配置禁用了原生工具（Function Calling）。"""
        try:
            from models import Config

            cfg = (
                await self.session.exec(
                    select(Config).where(Config.key == "disable_native_tools")
                )
            ).first()
            return cfg.value.lower() == "true" if cfg else False
        except Exception:
            return False

    async def _handle_model_command(
        self, messages: List[Dict[str, Any]], config: Dict[str, Any]
    ) -> Optional[str]:
        """处理 /model 聊天命令。返回回复文本或 None（非命令）。

        支持:
          /model              — 列出可用模型
          /model <name>       — 切换到指定模型（持久写入 current_model_id）
        """
        import re

        last_text = ""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            c = msg.get("content", "")
            last_text = c if isinstance(c, str) else ""
            break

        last_text = last_text.strip()
        if not last_text.startswith("/model"):
            return None

        from models import AIModelConfig, Config

        # /model (no args) → list
        match = re.match(r"^/model\s*$", last_text)
        if match:
            rows = (await self.session.exec(select(AIModelConfig))).all()
            if not rows:
                return "没有配置任何模型。"
            lines = ["**可用模型：**"]
            current_provider = config.get("provider", "?")
            current_model = config.get("model", "?")
            for r in rows:
                marker = " ← 当前" if (r.provider == current_provider and r.model_id == current_model) else ""
                lines.append(f"- `{r.name}` ({r.provider}:{r.model_id}){marker}")
            return "\n".join(lines)

        # /model <name> → switch
        match = re.match(r"^/model\s+(.+)$", last_text, re.I)
        if not match:
            return None

        query = match.group(1).strip().lower()
        rows = (await self.session.exec(select(AIModelConfig))).all()
        target = None
        for r in rows:
            if query in r.name.lower() or query in (r.model_id or "").lower():
                target = r
                break

        if not target:
            names = ", ".join(f"`{r.name}`" for r in rows)
            return f"未找到匹配模型 `{query}`。可用: {names}"

        # 持久写入 current_model_id
        cfg = (
            await self.session.exec(
                select(Config).where(Config.key == "current_model_id")
            )
        ).first()
        if cfg:
            cfg.value = str(target.id)
        else:
            self.session.add(Config(key="current_model_id", value=str(target.id)))
        await self.session.commit()

        return f"已切换到 **{target.name}** (`{target.provider}:{target.model_id}`)"

    async def _get_nsfw_fallback_config(self) -> Optional[Dict[str, Any]]:
        """读取 NSFW 回退模型配置。返回 dict(api_key, api_base, model, provider) 或 None。"""
        try:
            from models import AIModelConfig, Config

            cfg = (
                await self.session.exec(
                    select(Config).where(Config.key == "nsfw_fallback_model_id")
                )
            ).first()
            if not cfg:
                return None
            model = await self.session.get(AIModelConfig, int(cfg.value))
            if not model:
                return None
            return {
                "api_key": model.api_key or "",
                "api_base": model.api_base or "",
                "model": model.model_id or "",
                "provider": model.provider or "openai",
            }
        except Exception as e:
            print(f"[Agent] NSFW fallback 配置读取失败: {e}")
            return None
