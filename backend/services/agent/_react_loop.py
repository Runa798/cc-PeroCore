"""
ReActLoop
=========
Agent 的 ReAct（Reason + Act）主循环。

从 AgentService.chat() 中分离出来，独立管理：
1. 轮次控制（MAX_TURNS、陪伴/社交模式单轮限制）
2. 任务暂停检测（TaskManager）
3. 流式 LLM 调用与 delta 收集
4. 后处理器流式管道
5. 无工具调用时：NIT 文本模式解析、截图注入 Observation
6. 有工具调用时：委托 AgentToolExecutor 执行，处理反思、熔断机制
7. finish_task 终止逻辑
"""

import contextlib
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from services.agent._tool_executor import AgentToolExecutor


class ReActLoop:
    """ReAct 推理-行动主循环，以 AsyncGenerator 形式向外 yield 流式内容。"""

    MAX_TURNS_DEFAULT = 30
    MAX_TURNS_SOCIAL = 2
    MAX_TURNS_COMPANION = 1

    def __init__(
        self,
        llm,
        session,
        mdp,
        postprocessor_manager,
        tool_executor: AgentToolExecutor,
        task_manager,
    ):
        self.llm = llm
        self.session = session
        self.mdp = mdp
        self.postprocessor_manager = postprocessor_manager
        self.tool_executor = tool_executor
        self.task_manager = task_manager

    async def run(
        self,
        final_messages: List[Dict],
        tools_to_pass: Optional[List],
        context: Dict[str, Any],
        config: Dict[str, Any],
        on_status: Optional[Callable],
        reflection_runner: Optional[Callable] = None,
        mcp_clients: Optional[List] = None,
        mcp_tool_map: Optional[Dict] = None,
        allowed_tool_names: Optional[List[str]] = None,
        tool_policy_engine=None,
        user_message: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        执行 ReAct 循环，yield 流式文本给调用方。

        Args:
            final_messages      : 当前对话历史（可在循环中追加）
            tools_to_pass       : 传给 LLM 的工具列表（None=禁用 Function Calling）
            context             : 预处理器生成的上下文字典
            config              : LLM 配置
            on_status           : 状态更新回调
            reflection_runner   : 反思函数 async (task, history, screenshot) -> str
            mcp_clients         : MCP 客户端列表
            mcp_tool_map        : tool_name -> client 映射
            allowed_tool_names  : NIT 安全白名单
            tool_policy_engine  : 工具策略引擎（用于辅助分析）
            user_message        : 提取好的用户消息文本

        Yields:
            str: 流式文本片段、SSE 数据帧、UI 标签等
        """
        source = context.get("source", "desktop")
        session_id = context.get("session_id", "default")
        current_nit_id = context.get("nit_id")
        temperature = config.get("temperature", 0.7)
        enable_vision = config.get("enable_vision", False)

        # --- 循环参数配置 ---
        MAX_TURNS = self._resolve_max_turns(source, session_id)
        turn_count = 0
        consecutive_error_count = 0
        full_response_text = ""
        accumulated_full_response = ""

        if session_id:
            self.task_manager.register(session_id)

        try:
            while turn_count < MAX_TURNS:
                # ── 暂停检测 ──
                if session_id:
                    await self.task_manager.check_pause(session_id)
                    injected = self.task_manager.get_injected_instruction(session_id)
                    if injected:
                        print(f"[ReActLoop] 检测到注入指令: {injected}")
                        final_messages.append(
                            {"role": "user", "content": f"【主人即时指令】: {injected}"}
                        )

                turn_count += 1
                current_turn_text = ""
                has_tool_calls_in_this_turn = False
                collected_tool_calls: List[Dict] = []

                if on_status:
                    await on_status("thinking", f"正在思考 (第 {turn_count} 轮)...")
                print(f"[ReActLoop] 开始 LLM 流 (第 {turn_count} 轮)...")

                # ── 流式 LLM 调用 ──
                async def raw_stream_source(
                    _tools=tools_to_pass,
                    _ctc=collected_tool_calls,
                ):
                    nonlocal \
                        current_turn_text, \
                        full_response_text, \
                        has_tool_calls_in_this_turn

                    async for delta in self.llm.chat_stream_deltas(
                        final_messages, temperature=temperature, tools=_tools
                    ):
                        content = delta.get("content", "")
                        if content:
                            current_turn_text += content
                            full_response_text += content
                            yield content

                        if delta.get("tool_calls"):
                            has_tool_calls_in_this_turn = True
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                while len(_ctc) <= idx:
                                    _ctc.append(
                                        {
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    )
                                target = _ctc[idx]
                                if "id" in tc_delta:
                                    target["id"] = tc_delta["id"]
                                if "function" in tc_delta:
                                    fn = tc_delta["function"]
                                    if "name" in fn:
                                        target["function"]["name"] = fn["name"]
                                    if "arguments" in fn:
                                        target["function"]["arguments"] += fn[
                                            "arguments"
                                        ]

                # ── 后处理器流式管道 ──
                processed_stream = self.postprocessor_manager.process_stream(
                    raw_stream_source(),
                    context={
                        "source": source,
                        "session_id": session_id,
                        "skip_nit_filter": (source in ["ide", "desktop"]),
                    },
                )
                async for content in processed_stream:
                    yield content

                # ── 本轮结束：无工具调用路径 ──
                if not has_tool_calls_in_this_turn:
                    # NIT 文本模式解析
                    if full_response_text and full_response_text.strip():
                        nit_results = await self.tool_executor.save_parsed_metadata(
                            full_response_text,
                            source,
                            mcp_clients,
                            execute_nit=True,
                            expected_nit_id=current_nit_id,
                            allowed_tools=allowed_tool_names,
                        )

                        if nit_results:
                            print(
                                f"[ReActLoop] 检测到 {len(nit_results)} 个 NIT 调用。继续对话循环。"
                            )
                            # 将当前回复追加历史
                            safe_text = self._truncate_safe(full_response_text)
                            final_messages.append(
                                {"role": "assistant", "content": safe_text}
                            )

                            # 构造 Observation
                            (
                                obs_text,
                                should_terminate,
                                sse_payloads,
                            ) = await self._build_nit_observation(
                                nit_results, source, config, on_status
                            )

                            # 推送 SSE
                            for payload in sse_payloads:
                                yield f"data: {payload}\n\n"
                                await self._try_broadcast(payload)

                            # 截图注入（若需要）
                            message_content = await self._maybe_inject_screenshot(
                                obs_text, nit_results, enable_vision
                            )
                            final_messages.append(
                                {"role": "user", "content": message_content}
                            )

                            # 错误熔断
                            has_error = any(r["status"] == "error" for r in nit_results)
                            (
                                consecutive_error_count,
                                tools_to_pass,
                            ) = await self._handle_error_circuit(
                                has_error,
                                consecutive_error_count,
                                tools_to_pass,
                                final_messages,
                                user_message,
                                reflection_runner,
                            )

                            # 重置轮次状态
                            accumulated_full_response += full_response_text + "\n"
                            full_response_text = ""
                            current_turn_text = ""
                            collected_tool_calls = []
                            has_tool_calls_in_this_turn = False

                            if should_terminate:
                                print("[ReActLoop] NIT 循环由 finish_task 终止。")
                                break
                            continue

                    # 空响应兜底
                    if turn_count == 1 and not full_response_text.strip():
                        print("[ReActLoop] 流结束，无任何增量。")
                        err_msg = (
                            "⚠️ AI 没有返回有效内容。请检查网络连接或 API Key 配置。"
                        )
                        full_response_text = err_msg
                        yield err_msg

                    break  # 无 NIT 调用，正常结束

                # ── 本轮结束：有工具调用路径（Function Calling）──
                safe_turn_text = (
                    self._truncate_safe(current_turn_text)
                    if current_turn_text
                    else None
                )
                final_messages.append(
                    {
                        "role": "assistant",
                        "content": safe_turn_text,
                        "tool_calls": collected_tool_calls,
                    }
                )

                intercepted_ui_data = {}
                should_terminate_loop = False

                for tool_call in collected_tool_calls:
                    function_name = tool_call["function"]["name"]

                    (
                        fn_resp,
                        should_terminate,
                        sse_payload,
                    ) = await self.tool_executor.execute_tool_call(
                        tool_call=tool_call,
                        source=source,
                        config=config,
                        mcp_tool_map=mcp_tool_map or {},
                        mcp_clients=mcp_clients or [],
                        on_status=on_status,
                        final_messages=final_messages,
                        tool_policy_engine=tool_policy_engine,
                        user_message=user_message,
                    )

                    # finish_task 的 summary text 直接 yield
                    if should_terminate:
                        summary = tool_call["function"].get("arguments", "{}")
                        try:
                            args = json.loads(summary)
                            if args.get("summary"):
                                full_response_text += args["summary"]
                                yield args["summary"]
                        except Exception:
                            pass

                    # SSE 推送
                    if sse_payload:
                        yield f"data: {sse_payload}\n\n"
                        await self._try_broadcast(sse_payload)

                    final_messages.append(
                        {
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "name": function_name,
                            "content": fn_resp,
                        }
                    )

                    if function_name == "search_files":
                        intercepted_ui_data["FILE_RESULTS"] = fn_resp

                    if should_terminate:
                        should_terminate_loop = True
                        break

                # 错误熔断（Function Calling 路径）
                last_resp = final_messages[-1].get("content", "")
                is_tool_error = (
                    "error" in str(last_resp).lower()
                    or "fail" in str(last_resp).lower()
                )

                if is_tool_error:
                    consecutive_error_count += 1
                    print(
                        f"[ReActLoop] 检测到工具错误。连续次数: {consecutive_error_count}"
                    )
                else:
                    consecutive_error_count = 0

                if consecutive_error_count >= 3:
                    print(
                        f"⚠️ [ReActLoop] 连续错误 ({consecutive_error_count}) 达到上限。强制停止。"
                    )
                    final_messages.append(
                        {
                            "role": "system",
                            "content": "【系统紧急干预】监测到你已经连续操作失败 3 次。"
                            "请立即停止任何后续的思考与工具调用，放弃当前任务，并主动向主人汇报失败原因。",
                        }
                    )
                    tools_to_pass = None

                if is_tool_error and reflection_runner:
                    print("⚠️ [ReActLoop] 检测到工具执行错误，触发反思...")
                    history_context = "\n".join(
                        [
                            f"{m['role']}: {str(m.get('content', ''))[:200]}"
                            for m in final_messages[-5:]
                        ]
                    )
                    latest_screenshot = await self._try_capture_screenshot()
                    reflection_advice = await reflection_runner(
                        user_message, history_context, latest_screenshot
                    )
                    if reflection_advice and "NORMAL" not in reflection_advice:
                        final_messages.append(
                            {
                                "role": "system",
                                "content": f"[反思助手提示]: 检测到上一步操作可能存在问题。建议参考：{reflection_advice}",
                            }
                        )

                # 追加截图结果的 UI 标签
                for tag_name, raw_json in intercepted_ui_data.items():
                    tag = f"\n<{tag_name}>{raw_json}</{tag_name}>"
                    full_response_text += tag
                    yield tag
                    print(f"[ReActLoop] 已向响应追加隐藏标签 {tag_name}。")

                if should_terminate_loop:
                    print("[ReActLoop] 循环由 finish_task 终止。")
                    break

        finally:
            if session_id:
                self.task_manager.unregister(session_id)

        # 返回值不需要，因为 caller 都是通过 async for 消费 yield 的值
        return

    # ─────────────────────────────────────────────
    # 私有辅助方法
    # ─────────────────────────────────────────────

    def _resolve_max_turns(self, source: str, session_id: str) -> int:
        """根据运行模式决定 ReAct 最大轮次。"""
        if session_id == "companion_mode":
            print("[ReActLoop] Companion 模式: 限制为单轮 (MAX_TURNS=1)")
            return self.MAX_TURNS_COMPANION
        if source in ["social", "lightweight"]:
            print(f"[ReActLoop] {source} 模式: 限制为双轮 (MAX_TURNS=2)")
            return self.MAX_TURNS_SOCIAL
        return self.MAX_TURNS_DEFAULT

    @staticmethod
    def _truncate_safe(text: str, limit: int = 50000) -> str:
        """截断过长文本以防上下文窗口爆炸。"""
        if len(text) > limit:
            truncated = text[:limit] + "\n...(truncated by system for safety)"
            print(f"⚠️ [ReActLoop] 文本已从 {len(text)} 截断为 {limit} 字符。")
            return truncated
        return text

    async def _build_nit_observation(
        self,
        nit_results: List[Dict],
        source: str,
        config: Dict,
        on_status,
    ):
        """
        根据 NIT 执行结果构造 Observation 文本。

        Returns:
            (obs_text, should_terminate, sse_payloads)
        """
        obs_text = "【系统通知：NIT工具执行反馈】\n"
        should_terminate = False
        sse_payloads = []

        for res in nit_results:
            out_str = str(res["output"])

            # 提取状态触发器（NIT 实时状态同步）
            sse = self._try_extract_trigger_sse(out_str)
            if sse:
                sse_payloads.append(sse)

            # 截断长输出
            if len(out_str) > 2000:
                out_str = out_str[:2000] + "...(truncated)"

            # 启发式判定执行结果
            is_success = self._is_nit_result_success(res, out_str)
            if not is_success:
                res["status"] = "error"

            icon = "✅" if is_success else "❌"
            status_text = "执行完成" if is_success else "执行失败"

            display_name = res["plugin"]
            if display_name == "NIT_Script" and res.get("executed_tools"):
                display_name = f"NIT 脚本: {', '.join(res['executed_tools'])}"

            log_preview = (out_str[:200] + "...") if len(out_str) > 200 else out_str
            print(
                f"[ReActLoop] {icon} 步骤: [{display_name}] -> {status_text}\n"
                f"    结果预览: {log_preview.replace(chr(10), ' ')[:100]}",
                flush=True,
            )

            obs_text += (
                f"{icon} 工具 [{display_name}] {status_text}。\n结果:\n{out_str}\n\n"
            )

            if res["plugin"] == "finish_task" or "finish_task" in res.get(
                "executed_tools", []
            ):
                should_terminate = True

        return obs_text, should_terminate, sse_payloads

    @staticmethod
    def _is_nit_result_success(res: Dict, out_str: str) -> bool:
        """判断 NIT 结果是否真正成功（启发式）。"""
        if res["status"] != "success":
            return False
        error_indicators = ["错误:", "⚠️", "未找到插件", "权限拒绝", "Error:"]
        return not (
            any(out_str.startswith(ind) for ind in error_indicators)
            or "未找到插件" in out_str
        )

    @staticmethod
    def _try_extract_trigger_sse(out_str: str) -> Optional[str]:
        """尝试从 NIT 输出中解析状态触发器，构造 SSE payload。"""
        try:
            if "triggers" in out_str or '"mood"' in out_str:
                start = out_str.find("{")
                end = out_str.rfind("}")
                if start != -1 and end != -1:
                    data = json.loads(out_str[start : end + 1])
                    triggers = (
                        data.get("triggers")
                        or data.get("state")
                        or (data if "mood" in data else None)
                    )
                    if triggers:
                        return json.dumps({"triggers": triggers}, ensure_ascii=False)
        except Exception:
            pass
        return None

    async def _maybe_inject_screenshot(
        self,
        obs_text: str,
        nit_results: List[Dict],
        enable_vision: bool,
    ) -> Any:
        """如果 NIT 结果包含截图请求且视觉开启，则注入截图到 Observation。"""
        has_screenshot_request = self._detect_screenshot_request(nit_results)

        message_content = [{"type": "text", "text": obs_text}]

        if has_screenshot_request and enable_vision:
            try:
                print("[ReActLoop] 正在为 NIT 调用注入截图...")
                from services.perception.screenshot_service import screenshot_manager

                screenshot_data = screenshot_manager.capture()
                if screenshot_data:
                    message_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_data['base64']}"
                            },
                        }
                    )
                    capture_time = screenshot_data.get(
                        "time_str",
                        datetime.now().strftime("%H:%M:%S"),
                    )
                    obs_text += f"\n[系统] 已附带最新屏幕截图 (Time: {capture_time})。"
                    message_content[0]["text"] = obs_text
                    print(f"[ReActLoop] 截图注入成功。时间: {capture_time}")
                else:
                    obs_text += "\n[系统] 尝试截图失败：无法获取图像数据。"
                    message_content[0]["text"] = obs_text
            except Exception as e:
                import traceback

                traceback.print_exc()
                obs_text += f"\n[系统] 尝试截图失败: {e}"
                message_content[0]["text"] = obs_text

        return message_content

    @staticmethod
    def _detect_screenshot_request(nit_results: List[Dict]) -> bool:
        """检测 NIT 结果中是否包含截图请求。"""
        for res in nit_results:
            plugin = res["plugin"].lower()
            if ("screenshot" in plugin or "see_screen" in plugin) and res[
                "status"
            ] == "success":
                return True
            for t in res.get("executed_tools", []):
                if ("screenshot" in t.lower() or "see_screen" in t.lower()) and res[
                    "status"
                ] == "success":
                    return True
        return False

    async def _handle_error_circuit(
        self,
        has_error: bool,
        consecutive_error_count: int,
        tools_to_pass,
        final_messages: List[Dict],
        user_message: str,
        reflection_runner: Optional[Callable],
    ):
        """处理连续错误熔断与反思触发。"""
        if has_error:
            consecutive_error_count += 1
            print(
                f"[ReActLoop] 检测到 NIT 工具错误。连续次数: {consecutive_error_count}"
            )
        else:
            consecutive_error_count = 0

        if consecutive_error_count >= 3:
            print(
                f"⚠️ [ReActLoop] NIT 连续错误 ({consecutive_error_count}) 达到上限。强制停止。"
            )
            final_messages.append(
                {
                    "role": "system",
                    "content": "【系统紧急干预】监测到你已经连续操作失败 3 次。"
                    "请立即停止任何后续的思考与工具调用，放弃当前任务，并主动向主人汇报失败原因。",
                }
            )
            tools_to_pass = None

        if has_error and reflection_runner:
            print("⚠️ [ReActLoop] 检测到 NIT 工具执行错误，触发反思...")
            history_context = "\n".join(
                [
                    f"{m['role']}: {str(m.get('content', ''))[:200]}"
                    for m in final_messages[-5:]
                ]
            )
            latest_screenshot = await ReActLoop._try_capture_screenshot()
            advice = await reflection_runner(
                user_message, history_context, latest_screenshot
            )
            if advice and "NORMAL" not in advice:
                final_messages.append(
                    {
                        "role": "system",
                        "content": f"[反思助手提示]: 检测到上一步操作可能存在问题。建议参考：{advice}",
                    }
                )

        return consecutive_error_count, tools_to_pass

    @staticmethod
    async def _try_capture_screenshot() -> Optional[str]:
        """尝试截图，返回 base64 字符串，失败返回 None。"""
        with contextlib.suppress(Exception):
            from services.perception.screenshot_service import screenshot_manager

            shot = screenshot_manager.capture()
            if shot:
                return shot["base64"]
        return None

    @staticmethod
    async def _try_broadcast(payload_json: str):
        """尝试通过 RealtimeSessionManager 广播状态更新。"""
        try:
            from services.core.realtime_session_manager import realtime_session_manager

            data = json.loads(payload_json)
            triggers = data.get("triggers")
            if triggers:
                await realtime_session_manager.broadcast(
                    {"type": "triggers", "data": triggers}
                )
        except Exception:
            pass
