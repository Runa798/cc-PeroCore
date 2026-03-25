"""
AgentConfigLoader
=================
Agent 服务的配置加载层。
负责从数据库读取 LLM 配置、反思模型配置，以及 MCP 客户端列表。

将配置获取逻辑从 AgentService 中分离，使主类更专注于流程编排。
"""

import json
from typing import Any, Dict, List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import AIModelConfig, Config, MCPConfig
from services.core.mcp_service import McpClient


class AgentConfigLoader:
    """负责从数据库或配置中心加载 Agent 运行所需的各类配置。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_llm_config(self) -> Dict[str, Any]:
        """
        获取当前激活的 LLM 配置。
        优先读取 current_model_id 指向的模型卡片，回退到全局 API Key/Base 配置。
        """
        # 1. 获取全局配置
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }

        global_api_key = configs.get("global_llm_api_key", "")
        global_api_base = configs.get("global_llm_api_base", "https://api.openai.com")
        current_model_id = configs.get("current_model_id")

        # 默认回退配置
        fallback_config = {
            "api_key": global_api_key or configs.get("ppc.apiKey", ""),  # 兼容旧 key
            "api_base": global_api_base
            or configs.get("ppc.apiBase", "https://api.openai.com"),
            "model": configs.get("ppc.modelName", "gpt-3.5-turbo"),
            "provider": configs.get("global_llm_provider", "openai"),
            "temperature": 0.7,
            "enable_vision": False,
        }

        # 2. 如果没有选中模型，使用默认/回退配置
        if not current_model_id:
            return fallback_config

        # 3. 获取选中模型卡片
        try:
            model_config = await self.session.get(AIModelConfig, int(current_model_id))
            if not model_config:
                return fallback_config
        except ValueError:
            return fallback_config

        # 4. 组装最终配置
        final_api_key = (
            model_config.api_key
            if model_config.provider_type == "custom"
            else global_api_key
        )
        final_api_base = (
            model_config.api_base
            if model_config.provider_type == "custom"
            else global_api_base
        )

        return {
            "api_key": final_api_key,
            "api_base": final_api_base,
            "model": model_config.model_id,
            "provider": model_config.provider,
            "temperature": model_config.temperature,
            "enable_vision": model_config.enable_vision,
        }

    async def get_reflection_config(self) -> Optional[Dict[str, Any]]:
        """
        获取反思模型配置。
        若反思功能未启用或未配置反思模型，返回 None。
        """
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }

        if configs.get("reflection_enabled") != "true":
            return None

        reflection_model_id = configs.get("reflection_model_id")
        if not reflection_model_id:
            return None

        try:
            model_config = await self.session.get(
                AIModelConfig, int(reflection_model_id)
            )
            if not model_config:
                return None

            global_api_key = configs.get("global_llm_api_key", "")
            global_api_base = configs.get(
                "global_llm_api_base", "https://api.openai.com"
            )

            final_api_key = (
                model_config.api_key
                if model_config.provider_type == "custom"
                else global_api_key
            )
            final_api_base = (
                model_config.api_base
                if model_config.provider_type == "custom"
                else global_api_base
            )

            return {
                "api_key": final_api_key,
                "api_base": final_api_base,
                "model": model_config.model_id,
                "temperature": 0.1,  # 反思需要理性，低温
                "enable_vision": model_config.enable_vision,
            }
        except Exception as e:
            print(f"获取反思配置出错: {e}")
            return None

    async def get_mcp_clients(self) -> List[McpClient]:
        """
        获取所有已启用的 MCP 客户端。
        优先从 MCPConfig 表读取，回退到 mcp_config_json，最终回退到旧 URL 配置。
        """
        clients = []

        # 优先级 1: 通用 MCPConfig 表
        try:
            all_mcp_configs = (await self.session.exec(select(MCPConfig))).all()

            if all_mcp_configs:
                print(
                    f"[AgentConfigLoader] 在 MCPConfig 表中找到 {len(all_mcp_configs)} 个配置。以此为准。"
                )
                for mcp_config_obj in all_mcp_configs:
                    if not mcp_config_obj.enabled:
                        continue

                    print(
                        f"[AgentConfigLoader] 加载已启用的 MCP 配置: {mcp_config_obj.name}"
                    )
                    client_config = {
                        "type": mcp_config_obj.type,
                        "name": mcp_config_obj.name,
                    }

                    if mcp_config_obj.type == "stdio":
                        client_config.update(
                            {
                                "command": mcp_config_obj.command,
                                "args": json.loads(mcp_config_obj.args or "[]"),
                                "env": json.loads(mcp_config_obj.env or "{}"),
                            }
                        )
                    elif mcp_config_obj.type == "sse":
                        client_config.update({"url": mcp_config_obj.url})

                    clients.append(McpClient(config=client_config))

                return clients  # 新表有数据则以此为准
        except Exception as e:
            print(f"[AgentConfigLoader] 查询 MCPConfig 表错误: {e}")

        # 优先级 2: mcp_config_json 完整 JSON 配置
        try:
            json_config = (
                await self.session.exec(
                    select(Config).where(Config.key == "mcp_config_json")
                )
            ).first()

            if json_config and json_config.value:
                try:
                    config_data = json.loads(json_config.value)
                    if "mcpServers" in config_data:
                        for name, server_config in config_data["mcpServers"].items():
                            if not server_config.get("enabled", True):
                                print(
                                    f"[AgentConfigLoader] 跳过已禁用的 MCP JSON 配置: {name}"
                                )
                                continue
                            print(f"[AgentConfigLoader] 找到 MCP JSON 配置: {name}")
                            if "name" not in server_config:
                                server_config["name"] = name
                            clients.append(McpClient(config=server_config))
                    else:
                        print("[AgentConfigLoader] 找到直接 MCP JSON 配置")
                        clients.append(McpClient(config=config_data))
                except Exception as e:
                    print(f"[AgentConfigLoader] 加载 MCP JSON 配置失败: {e}")
        except Exception as e:
            print(f"[AgentConfigLoader] 查询 mcp_config_json 错误: {e}")

        # 优先级 3: 回退旧 URL/Key 配置
        if not clients:
            try:
                url_config = (
                    await self.session.exec(
                        select(Config).where(Config.key == "mcp_server_url")
                    )
                ).first()

                if url_config and url_config.value:
                    key_config = (
                        await self.session.exec(
                            select(Config).where(Config.key == "mcp_api_key")
                        )
                    ).first()
                    api_key = key_config.value if key_config else None

                    print(
                        f"[AgentConfigLoader] 回退到旧版 MCP URL 配置: {url_config.value}"
                    )
                    clients.append(
                        McpClient(
                            config={
                                "type": "sse",
                                "url": url_config.value,
                                "api_key": api_key,
                                "name": "Legacy-MCP",
                            }
                        )
                    )
            except Exception as e:
                print(f"[AgentConfigLoader] 查询 mcp_server_url 错误: {e}")

        return clients
