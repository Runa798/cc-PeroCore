import asyncio
import base64
import json
from typing import Any, AsyncIterable, Dict, List, Optional

import anthropic
import httpx
from google import genai
from google.genai import types

from services.core.gateway_client import gateway_client
from services.core.moderation_service import moderation_service
from services.core.claude_code_provider import chat_claude_code, chat_claude_code_stream

# 默认 API Base URL 配置 (用户未提供时使用)
DEFAULT_API_BASES = {
    "openai": "https://api.openai.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "deepseek": "https://api.deepseek.com",
    "moonshot": "https://api.moonshot.cn/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "groq": "https://api.groq.com/openai/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "minimax": "https://api.minimax.chat/v1",
    "mistral": "https://api.mistral.ai/v1",
    "yi": "https://api.lingyiwanwu.com/v1",
    "xai": "https://api.x.ai/v1",
    "stepfun": "https://api.stepfun.com/v1",
    "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1",
    "ollama": "http://localhost:11434/v1",
}

ERROR_MAPPING = {
    400: "请求参数错误 (400) - 请检查模型配置或输入内容",
    401: "认证失败 (401) - API Key 无效或过期",
    403: "禁止访问 (403) - 余额不足或无权限",
    404: "模型不存在 (404) - URL 错误或模型名称错误",
    429: "请求过于频繁 (429) - 触发速率限制，请稍后再试",
    500: "服务商内部错误 (500) - 远程服务崩溃",
    502: "网关错误 (502) - 网络连接不稳定",
    503: "服务不可用 (503) - 服务器超载或维护中",
    504: "网关超时 (504) - 响应时间过长",
}


class LLMService:
    def __init__(
        self, api_key: str, api_base: str, model: str, provider: str = "openai"
    ):
        self.api_key = api_key.strip() if api_key else ""
        self.provider = provider or "openai"
        self.model = model

        # 清洗 api_base: 去空格, 去末尾斜杠
        base = api_base.strip().rstrip("/") if api_base else ""

        # 如果未提供 api_base，尝试使用默认值
        if not base:
            base = DEFAULT_API_BASES.get(self.provider, "https://api.openai.com")

        self.api_base = base

    def _get_url(self, endpoint: str) -> str:
        """根据 endpoint 自动拼接正确的 URL (用于通用 OpenAI 兼容接口)"""
        # 特殊处理：如果是 OpenAI 兼容但不需要 /v1 (极少数情况)，或者用户输入了完整 URL
        # 这里假设 self.api_base 已经是基础路径 (如 https://api.deepseek.com)

        # 为了兼容性，如果 api_base 已经包含 /v1，则不重复添加
        # 如果 endpoint 是 chat/completions

        suffix = ""
        if endpoint == "chat":
            suffix = "/chat/completions"
        elif endpoint == "models":
            suffix = "/models"
        else:
            suffix = endpoint

        # 检查是否已经以 /v1 结尾
        if self.api_base.endswith("/v1"):
            return f"{self.api_base}{suffix.replace('/v1', '')}"  # 避免重复

        # 检查 suffix 是否自带 /v1 (通常不会，但在 _get_url 调用时要注意)
        return (
            f"{self.api_base}{suffix}"
            if "/v1" in self.api_base
            else f"{self.api_base}/v1{suffix}"
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: List[Dict] = None,
        response_format: Optional[Dict] = None,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        # Claude Code CLI (本地子进程，完整 shell 权限)
        if self.provider == "claude_code":
            return await chat_claude_code(messages, temperature, tools, model=self.model)

        # 智能纠错：若模型为 Gemini 但 Provider 误设为 Anthropic，强制回退到 OpenAI 兼容模式
        if self.provider in ["claude", "anthropic"] and "gemini" in self.model.lower():
            print(
                f"[LLMService] 检测到 Gemini 模型 '{self.model}' 使用 Anthropic 提供商。强制回退到 OpenAI 兼容协议。"
            )
        elif self.provider == "gemini":
            return await self._chat_gemini(messages, temperature, tools)
        elif self.provider in ["claude", "anthropic"]:
            return await self._chat_anthropic(messages, temperature, tools)

        # 默认使用 OpenAI 兼容协议 (支持 SiliconFlow, DeepSeek, DashScope 等)
        return await self._chat_openai_compatible(
            messages, temperature, tools, response_format, timeout
        )

    async def _chat_openai_compatible(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        tools: List[Dict] = None,
        response_format: Optional[Dict] = None,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """通用 OpenAI 兼容接口调用"""

        # 构造 URL：如果是 v1 结尾的 base，直接拼接；否则加 v1
        # 但有些 provider 可能不需要 v1 (如 Ollama 有时)，这里主要针对公有云 API
        if self.api_base.endswith("/v1"):
            url = f"{self.api_base}/chat/completions"
        else:
            url = f"{self.api_base}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        if response_format:
            payload["response_format"] = response_format

        # 调试输出
        self._debug_print_payload(payload)

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    self._handle_http_error(response)
                return response.json()
            except Exception as e:
                print(f"[LLM] 请求异常: {e}")

                # 识别常见连接错误
                err_msg = str(e)
                title = "LLM 请求异常"
                if "ConnectError" in err_msg or "ConnectTimeout" in err_msg:
                    title = "LLM 连接失败"
                    err_msg = "无法连接到 API 服务器，请检查网络或 API Base 设置。"
                elif "ReadTimeout" in err_msg:
                    title = "LLM 响应超时"
                    err_msg = "模型响应时间过长，请稍后再试。"

                asyncio.create_task(
                    gateway_client.broadcast_error(
                        message=f"{err_msg}", title=title, error_type="error"
                    )
                )
                raise

    def _debug_print_payload(self, payload):
        """调试：打印 payload 结构（不包含大型 base64 数据）"""
        try:
            # 仅在开发环境或显式开启 DEBUG 时打印完整 payload
            # 为了减少日志噪音，默认仅打印摘要

            debug_payload = json.loads(json.dumps(payload))
            messages = debug_payload.get("messages", [])

            summary = {
                "model": debug_payload.get("model"),
                "message_count": len(messages),
                "messages_preview": [],
            }

            for msg in messages:
                content = msg.get("content")
                role = msg.get("role")

                preview_content = "..."
                if isinstance(content, str):
                    # 移除所有截断，显示完整内容
                    preview_content = content
                elif isinstance(content, list):
                    # 尝试提取列表中的完整文本内容
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "image_url":
                                text_parts.append("[Image]")
                            else:
                                text_parts.append(f"[{item.get('type', 'unknown')}]")

                    full_text = " ".join(text_parts)
                    preview_content = full_text or f"[{len(content)} items (No Text)]"

                summary["messages_preview"].append(f"[{role}] {preview_content}")

            print(
                f"[LLM] 请求摘要 ({self.provider}): {json.dumps(summary, indent=2, ensure_ascii=False)}"
            )

            # 原有的完整打印逻辑 (已注释，需要时取消注释)
            # print(
            #     f"[LLM] 请求 Payload ({self.provider}): {json.dumps(debug_payload, indent=2, ensure_ascii=False)}"
            # )
        except Exception:
            pass

    def _handle_http_error(self, response):
        try:
            # 尝试解析 JSON 错误信息
            data = response.json()
            if "error" in data:
                if isinstance(data["error"], dict) and "message" in data["error"]:
                    error_text = data["error"]["message"]
                else:
                    error_text = json.dumps(data["error"], ensure_ascii=False)
            else:
                error_text = response.text
        except Exception:
            error_text = response.text

        # 清洗 HTML 错误
        if "<html" in error_text.lower() or "<!doctype" in error_text.lower():
            import re

            title_match = re.search(r"<title>(.*?)</title>", error_text, re.IGNORECASE)
            if title_match:
                error_text = (
                    f"网络错误 ({response.status_code}): {title_match.group(1)}"
                )
            else:
                error_text = f"网络错误 ({response.status_code}): HTML 响应"

        # 中文友好映射
        friendly_msg = ERROR_MAPPING.get(response.status_code)
        if friendly_msg:
            error_text = f"{friendly_msg}\n详细信息: {error_text}"

        # 广播错误通知
        asyncio.create_task(
            gateway_client.broadcast_error(
                message=error_text[:200] + ("..." if len(error_text) > 200 else ""),
                title=f"LLM API 错误 ({response.status_code})",
                error_type="error",
            )
        )

        print(f"[LLM] 错误响应: {error_text}")
        raise Exception(f"LLM 错误: {response.status_code} - {error_text}")

    async def _chat_gemini(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: List[Dict] = None,
    ) -> Dict[str, Any]:
        """Gemini 原生 API 调用 (使用 google-genai SDK)"""
        try:
            client = genai.Client(api_key=self.api_key)
            contents = self._convert_to_genai_contents(messages)

            system_instruction = None
            history = []
            for content in contents:
                if content.role == "system":
                    system_instruction = content.parts[0].text
                else:
                    history.append(content)

            genai_tools = self._convert_tools_to_genai(tools)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                tools=genai_tools,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                ],
            )

            response = await client.aio.models.generate_content(
                model=self.model, contents=history, config=config
            )

            content_text = ""
            import contextlib

            with contextlib.suppress(Exception):
                content_text = response.text

            message = {"role": "assistant", "content": content_text}

            # 检查 function call
            if response.candidates and response.candidates[0].content.parts:
                tool_calls = []
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        import uuid

                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        tool_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": json.dumps(part.function_call.args),
                                },
                            }
                        )
                if tool_calls:
                    message["tool_calls"] = tool_calls
                    if not message["content"]:
                        message["content"] = None

            return {"choices": [{"message": message}]}
        except Exception as e:
            print(f"[Gemini] 错误: {e}")
            asyncio.create_task(
                gateway_client.broadcast_error(
                    message=f"Gemini API 调用失败: {str(e)}",
                    title="Gemini 错误",
                    error_type="error",
                )
            )
            raise

    async def _chat_anthropic(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: List[Dict] = None,
    ) -> Dict[str, Any]:
        """Anthropic 原生 API 调用 (使用 anthropic SDK)"""
        try:
            client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=(
                    self.api_base
                    if self.api_base != "https://api.openai.com" and self.api_base
                    else None
                ),
            )

            system_prompt, anthropic_messages = self._convert_to_anthropic_format(
                messages
            )
            anthropic_tools = self._convert_tools_to_anthropic(tools)

            kwargs = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": 4096,
                "temperature": temperature,
                "system": system_prompt,
            }

            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            print(f"[Anthropic SDK] 发送请求: {self.model}")

            response = await client.messages.create(**kwargs)

            # 转换响应为 OpenAI 格式
            content_text = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            },
                        }
                    )

            message = {
                "role": "assistant",
                "content": content_text if content_text else None,
            }

            if tool_calls:
                message["tool_calls"] = tool_calls

            return {
                "choices": [{"message": message, "finish_reason": response.stop_reason}]
            }

        except Exception as e:
            print(f"[Anthropic] SDK 错误: {e}")
            asyncio.create_task(
                gateway_client.broadcast_error(
                    message=f"Anthropic SDK 调用失败: {str(e)}",
                    title="Anthropic 错误",
                    error_type="error",
                )
            )
            raise

    # ... (保留辅助方法如 _convert_to_genai_contents 等 - 将在下面复制) ...

    def _convert_to_genai_contents(
        self, messages: List[Dict[str, Any]]
    ) -> List[types.Content]:
        """将 OpenAI 消息格式转换为 Gemini GenAI Content 格式"""
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "assistant":
                role = "model"
            elif role == "tool":
                role = "user"

            parts = []

            # 1. 工具调用
            if role == "model" and "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    func = tc.get("function", {})
                    if func:
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except Exception:
                            args = {}
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=func.get("name"), args=args
                                )
                            )
                        )

            # 2. 内容
            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    parts.append(types.Part(text=content))
                elif isinstance(content, list):
                    for item in content:
                        if item["type"] == "text":
                            parts.append(types.Part(text=item["text"]))
                        elif item["type"] == "input_audio":
                            try:
                                audio_data = item["input_audio"]["data"]
                                parts.append(
                                    types.Part(
                                        inline_data=types.Blob(
                                            mime_type=f"audio/{item['input_audio']['format']}",
                                            data=base64.b64decode(audio_data),
                                        )
                                    )
                                )
                            except Exception as e:
                                print(f"[Gemini] 音频解码错误: {e}")
                        elif item["type"] == "image_url":
                            try:
                                url = item["image_url"]["url"]
                                if url.startswith("data:"):
                                    header, data = url.split(",", 1)
                                    mime_type = header.split(";")[0].split(":")[1]
                                    parts.append(
                                        types.Part(
                                            inline_data=types.Blob(
                                                mime_type=mime_type,
                                                data=base64.b64decode(data),
                                            )
                                        )
                                    )
                            except Exception as e:
                                print(f"[Gemini] 图片解码错误: {e}")

            # 3. 工具响应
            if msg["role"] == "tool":
                tool_name = msg.get("name", "unknown_tool")
                parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name, response={"result": content}
                        )
                    )
                )

            if parts:
                contents.append(types.Content(role=role, parts=parts))
        return contents

    def _convert_tools_to_genai(self, openai_tools: List[Dict]) -> List[types.Tool]:
        if not openai_tools:
            return None
        declarations = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                declarations.append(
                    types.FunctionDeclaration(
                        name=func.get("name"),
                        description=func.get("description"),
                        parameters=func.get("parameters"),
                    )
                )
        return (
            [types.Tool(function_declarations=declarations)] if declarations else None
        )

    def _convert_to_anthropic_format(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """转换 OpenAI 消息到 Anthropic 格式"""
        system_prompt = ""
        anthropic_msgs = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_prompt += str(content) + "\n"
                continue

            if role == "tool":
                tool_call_id = msg.get("tool_call_id")
                anthropic_msgs.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": str(content),
                            }
                        ],
                    }
                )
                continue

            if role == "assistant" and msg.get("tool_calls"):
                blocks = []
                if content:
                    blocks.append({"type": "text", "text": str(content)})

                for tc in msg["tool_calls"]:
                    func = tc["function"]
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": func["name"],
                            "input": json.loads(func["arguments"]),
                        }
                    )
                anthropic_msgs.append({"role": "assistant", "content": blocks})
                continue

            anthropic_msgs.append({"role": role, "content": content})

        return system_prompt.strip(), anthropic_msgs

    def _convert_tools_to_anthropic(self, tools: List[Dict]) -> List[Dict]:
        if not tools:
            return None
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description"),
                        "input_schema": func.get("parameters"),
                    }
                )
        return anthropic_tools

    async def list_models(self) -> List[str]:
        """获取模型列表"""
        if self.provider == "gemini":
            try:
                client = genai.Client(api_key=self.api_key)
                models = await asyncio.to_thread(client.models.list)
                return [
                    m.name
                    for m in models
                    if "generateContent" in m.supported_generation_methods
                ]
            except Exception as e:
                print(f"[Gemini] 获取模型列表失败: {e}")
                return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]

        elif self.provider in ["claude", "anthropic"]:
            try:
                client = anthropic.AsyncAnthropic(api_key=self.api_key)
                models = await client.models.list()
                return sorted([m.id for m in models.data])
            except Exception as e:
                print(f"[Anthropic] 获取模型列表错误: {e}")
                return ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229"]

        # 通用 OpenAI 兼容列表获取
        # 构造 URL: 如果 base 已经包含 /v1，则去掉 /v1 加上 /models，或者直接 base/models
        # 多数兼容 API 支持 /v1/models 或 /models

        # 尝试 1: 标准 /v1/models
        url = ""
        if self.api_base.endswith("/v1"):
            url = f"{self.api_base}/models"
        else:
            url = f"{self.api_base}/v1/models"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            print(f"正在获取模型列表: {url}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                # 如果失败，尝试去掉 /v1
                if response.status_code != 200 and "/v1" in url:
                    alt_url = url.replace("/v1", "")
                    print(f"尝试备用 URL: {alt_url}")
                    response = await client.get(alt_url, headers=headers)

                if response.status_code != 200:
                    print(f"远程 API 错误: {response.status_code} - {response.text}")
                    return []

                data = response.json()
                model_list = []
                if isinstance(data, list):
                    model_list = data
                elif isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        model_list = data["data"]
                    elif "models" in data and isinstance(data["models"], list):
                        model_list = data["models"]

                ids = []
                for m in model_list:
                    if isinstance(m, str):
                        ids.append(m)
                    elif isinstance(m, dict) and "id" in m:
                        ids.append(m["id"])
                    elif isinstance(m, dict) and "name" in m:
                        ids.append(m["name"])

                return sorted(set(ids))
        except Exception as e:
            print(f"获取模型列表错误: {e}")
            return []

    async def chat_stream_deltas(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: List[Dict] = None,
        model_config: Any = None,
        stream: bool = True,
    ) -> AsyncIterable[Dict[str, Any]]:
        """流式返回 delta 对象"""
        # 获取配置
        api_key = (
            model_config.api_key
            if model_config and model_config.api_key
            else self.api_key
        )
        api_base = (
            model_config.api_base
            if model_config and model_config.api_base
            else self.api_base
        )
        model_id = model_config.model_id if model_config else self.model
        provider = (
            model_config.provider
            if hasattr(model_config, "provider")
            else self.provider
        )

        # [Debug] 打印流式模式的负载 (修复缺失日志)
        debug_payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            debug_payload["tools"] = tools

        # 如果提供商不同，临时交换以进行日志记录
        original_provider = self.provider
        if provider != self.provider:
            self.provider = provider

        self._debug_print_payload(debug_payload)

        # 恢复提供商
        self.provider = original_provider

        # 动态更新 api_base 如果需要默认值
        if not api_base and provider in DEFAULT_API_BASES:
            api_base = DEFAULT_API_BASES[provider]

        if provider == "claude_code":
            async for delta in chat_claude_code_stream(
                messages, temperature, tools, model=model_id
            ):
                yield delta
            return
        elif provider == "gemini":
            async for delta in self._chat_gemini_stream(
                messages, temperature, model_id, api_key, tools
            ):
                yield delta
            return
        elif provider in ["claude", "anthropic"]:
            async for delta in self._chat_anthropic_stream(
                messages, temperature, model_id, api_key, tools, api_base
            ):
                yield delta
            return

        # 通用 OpenAI 流式
        # 构造 URL
        if api_base.endswith("/v1"):
            url = f"{api_base}/chat/completions"
        else:
            url = f"{api_base}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    if not stream:
                        # 非流式回退
                        response = await client.post(url, headers=headers, json=payload)
                        if response.status_code != 200:
                            # 5xx 错误尝试重试
                            if response.status_code >= 500:
                                raise httpx.ConnectError(
                                    f"Server Error {response.status_code}"
                                )

                            err_msg = f"错误: {response.status_code} - {response.text}"
                            friendly_msg = ERROR_MAPPING.get(response.status_code)
                            if friendly_msg:
                                err_msg = f"{friendly_msg}\n{err_msg}"

                            asyncio.create_task(
                                gateway_client.broadcast_error(
                                    message=err_msg[:200],
                                    title=f"LLM 流式错误 ({response.status_code})",
                                )
                            )

                            yield {"content": err_msg}
                            return
                        data = response.json()
                        if data.get("choices"):
                            content = data["choices"][0]["message"].get("content", "")

                            # 审核层 (如果启用)
                            if not moderation_service.check_text(content):
                                err_msg = "内容已被拦截：涉及敏感或不安全内容。"
                                yield {"content": err_msg}
                                return

                            yield {"content": content}
                        return

                    async with client.stream(
                        "POST", url, headers=headers, json=payload
                    ) as response:
                        if response.status_code != 200:
                            # 5xx 错误尝试重试
                            if response.status_code >= 500:
                                raise httpx.ConnectError(
                                    f"Server Error {response.status_code}"
                                )

                            yield {
                                "content": f"错误: {response.status_code} - {await response.aread()}"
                            }
                            return

                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if data.get("choices"):
                                        delta = data["choices"][0].get("delta", {})
                                        content_chunk = delta.get("content", "")

                                        # 流式审核比较复杂，这里做简单处理：
                                        # 如果启用了严格审核，可能需要缓冲整个句子。
                                        # 这里仅做简单的即时关键词检测 (可能不完整)
                                        if (
                                            content_chunk
                                            and not moderation_service.check_text(
                                                content_chunk
                                            )
                                        ):
                                            yield {"content": "[拦截]"}
                                            continue

                                        yield delta
                                except Exception:
                                    continue
                    return  # 成功结束

                except (
                    httpx.ConnectError,
                    httpx.ConnectTimeout,
                    httpx.ReadTimeout,
                    httpx.PoolTimeout,
                ) as e:
                    retry_count += 1
                    print(
                        f"[LLM Stream] 连接尝试失败 ({retry_count}/{max_retries}): {e}"
                    )
                    if retry_count >= max_retries:
                        print(
                            f"[LLM Stream] 错误: 所有连接尝试在 {max_retries} 次尝试后失败。"
                        )
                        asyncio.create_task(
                            gateway_client.broadcast_error(
                                message=f"多次尝试连接 API 失败 ({max_retries}次): {str(e)}",
                                title="LLM 连接耗尽",
                            )
                        )
                        yield {
                            "content": f"\n[网络错误: 连接失败 ({max_retries}次尝试): {str(e)}]"
                        }
                        return
                    await asyncio.sleep(1 * retry_count)  # 线性退避
                except Exception as e:
                    print(f"[LLM Stream] 错误: {e}")
                    asyncio.create_task(
                        gateway_client.broadcast_error(
                            message=f"流式请求发生未知错误: {str(e)}",
                            title="LLM 流式异常",
                        )
                    )
                    yield {"content": f"\n[Error: {str(e)}]"}
                    return

    async def _chat_gemini_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        model_id: str,
        api_key: str,
        tools: List[Dict] = None,
    ) -> AsyncIterable[Dict[str, Any]]:
        """Gemini 原生 API 流式调用"""
        try:
            client = genai.Client(api_key=api_key)
            contents = self._convert_to_genai_contents(messages)

            system_instruction = None
            history = []
            for content in contents:
                if content.role == "system":
                    system_instruction = content.parts[0].text
                else:
                    history.append(content)

            genai_tools = self._convert_tools_to_genai(tools)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                tools=genai_tools,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                ],
            )

            async for chunk in client.aio.models.generate_content_stream(
                model=model_id, contents=history, config=config
            ):
                if chunk.candidates and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.function_call:
                            import uuid

                            call_id = f"call_{uuid.uuid4().hex[:8]}"
                            yield {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": call_id,
                                        "function": {
                                            "name": part.function_call.name,
                                            "arguments": json.dumps(
                                                part.function_call.args
                                            ),
                                        },
                                    }
                                ]
                            }
                try:
                    if chunk.text:
                        yield {"content": chunk.text}
                except Exception:
                    pass
        except Exception as e:
            print(f"[Gemini Stream] 错误: {e}")
            asyncio.create_task(
                gateway_client.broadcast_error(
                    message=f"Gemini 流式错误: {str(e)}", title="Gemini 异常"
                )
            )
            yield {"content": f"错误: {str(e)}"}

    async def _chat_anthropic_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        model_id: str,
        api_key: str,
        tools: List[Dict] = None,
        api_base: str = None,
    ) -> AsyncIterable[Dict[str, Any]]:
        """Anthropic 原生 API 流式调用 (使用 SDK)"""
        try:
            client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=(
                    api_base
                    if api_base and api_base != "https://api.openai.com"
                    else None
                ),
            )

            system_prompt, anthropic_messages = self._convert_to_anthropic_format(
                messages
            )
            anthropic_tools = self._convert_tools_to_anthropic(tools)

            kwargs = {
                "model": model_id,
                "messages": anthropic_messages,
                "max_tokens": 4096,
                "temperature": temperature,
                "system": system_prompt,
                "stream": True,
            }
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        yield {"content": event.delta.text}
                    # SDK 处理复杂的工具事件，但将其映射到 OpenAI delta 格式需要小心处理。目前我们专注于文本。
                    # TODO: 如果需要，实现完整的工具流映射。
        except Exception as e:
            print(f"[Anthropic Stream] 错误: {e}")
            asyncio.create_task(
                gateway_client.broadcast_error(
                    message=f"Anthropic 流式错误: {str(e)}", title="Anthropic 异常"
                )
            )
            yield {"content": f"错误: {str(e)}"}
