import logging
import os
import re
from typing import Any, Dict, Optional

import jinja2
import yaml

logger = logging.getLogger(__name__)


class MDPrompt:
    """
    表示一个模块化动态提示词 (MDP)。
    存储元数据 (frontmatter) 和内容。
    """

    def __init__(self, name: str, content: str, metadata: Dict[str, Any], path: str):
        self.name = name
        self.content = content
        self.metadata = metadata
        self.path = path  # 相对路径键 (例如 "tasks/scorer_summary")
        self.version = metadata.get("version", "1.0")
        self.description = metadata.get("description", "")


class MDPManager:
    """
    管理模块化动态提示词的加载、缓存和渲染。
    支持递归 Jinja2 渲染。
    """

    def __init__(self, prompt_dir: str):
        self.prompt_dir = prompt_dir
        self.prompts: Dict[str, MDPrompt] = {}
        self.jinja_env = None

        # 初始加载
        self.reload_all()

    def reload_all(self):
        """从磁盘重新加载所有提示词并初始化 Jinja2 环境。"""
        self.prompts.clear()
        prompts_content_map = {}

        if not os.path.exists(self.prompt_dir):
            logger.warning(f"MDP 提示词目录未找到: {self.prompt_dir}")
            return

        for root, _, files in os.walk(self.prompt_dir):
            for file in files:
                if file.endswith(".md") or file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    try:
                        rel_path = os.path.relpath(file_path, self.prompt_dir)
                        # 将路径分隔符规范化为正斜杠以供 Jinja2 使用
                        rel_path = rel_path.replace("\\", "/")
                        # 键是没有扩展名的路径，例如 "tasks/scorer_summary"
                        key = os.path.splitext(rel_path)[0]

                        prompt_obj = self._load_file(file_path, key)
                        self.prompts[key] = prompt_obj
                        prompts_content_map[key] = prompt_obj.content

                        # 向后兼容：如果基名唯一，也注册基名
                        basename = os.path.splitext(file)[0]
                        if basename not in self.prompts:
                            self.prompts[basename] = prompt_obj
                            prompts_content_map[basename] = prompt_obj.content

                    except Exception as e:
                        logger.error(f"加载提示词文件失败 {file_path}: {e}")

        # 初始化 Jinja2 环境
        # 使用 FileSystemLoader 以支持加载外部 Agent 目录
        loaders = [jinja2.DictLoader(prompts_content_map)]

        # 尝试加载 Agent 目录 (内置: mdp/agents, 用户: data/agents)
        try:
            # prompt_dir = .../backend/services/mdp/prompts
            # mdp_dir = .../backend/services/mdp
            mdp_dir = os.path.dirname(os.path.abspath(self.prompt_dir))
            agents_dir = os.path.join(mdp_dir, "agents")
            # 用户自定义 agent 目录: backend/data/agents
            # mdp_dir = .../backend/services/mdp → 需要上两级到 backend/
            backend_dir = os.path.dirname(os.path.dirname(mdp_dir))
            user_agents_dir = os.path.join(backend_dir, "data", "agents")

            for adir in [agents_dir, user_agents_dir]:
                if os.path.exists(adir):
                    loaders.append(jinja2.FileSystemLoader(adir))
                    logger.info(f"MDP: 已添加 Agent 目录到加载路径: {adir}")

            # 扫描所有 agent 目录下的 .md 文件并加入 prompts_content_map
            for agents_scan_dir in [agents_dir, user_agents_dir]:
              if not os.path.exists(agents_scan_dir):
                continue
              for root, _, files in os.walk(agents_scan_dir):
                    for file in files:
                        if file.endswith(".md"):
                            file_path = os.path.join(root, file)
                            try:
                                rel_path = os.path.relpath(file_path, agents_scan_dir)
                                rel_path = rel_path.replace("\\", "/")
                                # 为了避免冲突，可以给 agent 的 prompt 加个前缀，或者直接用路径
                                # 例如 pero/system_prompt
                                key = os.path.splitext(rel_path)[0]

                                # 注意：这里不解析 frontmatter，因为 agent 的 prompt 通常就是纯文本或简单的 md
                                # 但为了统一，如果需要解析也可以调用 _load_file
                                # 这里我们简单读取内容
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    # 简单的 frontmatter 剥离如果需要
                                    if content.startswith("---"):
                                        _, _, content = content.split("---", 2)

                                    # 去除 HTML 注释
                                    content = re.sub(r"<!--[\s\S]*?-->", "", content)

                                prompts_content_map[key] = content.strip()
                                logger.info(f"MDP: 已索引 Agent Prompt: {key}")

                            except Exception as e:
                                logger.warning(
                                    f"MDP: 索引 Agent Prompt 失败 {file}: {e}"
                                )

        except Exception as e:
            logger.warning(f"MDP: 无法添加 Agent 目录: {e}")

        self.jinja_env = jinja2.Environment(
            loader=jinja2.ChoiceLoader(loaders),
            autoescape=False,  # 提示词是文本，不是 HTML
            variable_start_string="{{",
            variable_end_string="}}",
            undefined=jinja2.DebugUndefined,  # 保留未定义的变量为 {{ var }} 以便调试/部分渲染
        )

        logger.info(f"从 {self.prompt_dir} 加载了 {len(self.prompts)} 个 MDP 提示词")

    def _load_file(self, file_path: str, key: str) -> MDPrompt:
        """解析带有 frontmatter 的单个文件。"""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        content = raw_content
        metadata = {}

        # 检查 YAML frontmatter 块
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_content, re.DOTALL)
        if match:
            yaml_block = match.group(1)
            content = match.group(2)
            try:
                metadata = yaml.safe_load(yaml_block) or {}
            except yaml.YAMLError as e:
                logger.error(f"文件 {file_path} 中存在 YAML 错误: {e}")
        else:
            # 回退：如果 frontmatter 缺失，尝试从 HTML 注释中解析元数据
            # 模式：注释中的 description: "..." 或 version: "..."
            desc_match = re.search(r'description:\s*["\'](.*?)["\']', raw_content)
            if desc_match:
                metadata["description"] = desc_match.group(1)

            ver_match = re.search(r'version:\s*["\'](.*?)["\']', raw_content)
            if ver_match:
                metadata["version"] = ver_match.group(1)

        # 去除 HTML 注释 (重要：这确保注释不会泄漏到提示词中)
        content = re.sub(r"<!--[\s\S]*?-->", "", content)

        return MDPrompt(key, content.strip(), metadata, key)

    def get_prompt(self, name: str) -> Optional[MDPrompt]:
        """
        获取提示词对象。
        注意：对于外部 Agent 目录中的文件，由于没有在 reload_all 中预加载到 self.prompts，
        此方法可能返回 None，但这并不代表 Jinja2 无法渲染它。
        """
        return self.prompts.get(name)

    def render(self, template_name: str, context: Dict[str, Any] = None) -> str:
        """
        使用 Jinja2 递归解析渲染提示词。
        """
        if context is None:
            context = {}

        return self._render_template(template_name, context)

    def render_blocks(
        self, template_name: str, context: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """
        渲染模版中的特定 Block (header/footer)。
        如果模版未使用 block 语法，则默认全部内容归为 header。
        """
        if context is None:
            context = {}

        if not self.jinja_env:
            return {"header": "{{Error: Jinja2 not initialized}}", "footer": ""}

        # 1. 获取 Template 对象
        target_template_name = self._resolve_template_name(template_name, context)
        try:
            template = self._get_template(target_template_name)
        except Exception as e:
            logger.error(f"Template not found: {e}")
            return {"header": f"{{{{Missing Prompt: {template_name}}}}}", "footer": ""}

        # 2. 尝试渲染 header 和 footer block
        # Jinja2 的 Template.blocks 属性包含了所有 block 的渲染函数
        # 但我们需要先渲染 context，所以必须使用 context 渲染 block

        result = {"header": "", "footer": ""}

        # 检查模版是否有 block 定义
        if not template.blocks:
            # 没有 block，全量渲染为 header
            result["header"] = self._render_template(template_name, context)
            return result

        # 辅助渲染函数：渲染 Block 并递归展开变量
        def render_block_content(block_name):
            try:
                # 渲染 block
                # 注意：Jinja2 的 render_block 方法直接返回渲染后的字符串
                block_context = template.new_context(context)
                rendered = "".join(template.blocks[block_name](block_context))
                # 递归展开 (复用 _recursive_render)
                return self._recursive_render(rendered, context)
            except Exception:
                # 如果 Block 不存在，返回空
                return ""

        if "header" in template.blocks:
            result["header"] = render_block_content("header")
        else:
            # 如果没有 header block，但有其他 block，这通常是不规范的，
            # 但我们可以尝试渲染整个模版作为 header (可能会重复包含 footer 如果 footer 也在其中)
            # 为了安全起见，如果有 footer block 但没有 header block，
            # 我们假设用户只想分离 footer，其余部分应该用其他方式获取？
            # 或者我们简单地全量渲染？
            # 最佳实践：必须成对使用 header/footer。
            # 这里做个兼容：如果没有 header block，全量渲染作为 header
            result["header"] = self._render_template(template_name, context)

        if "footer" in template.blocks:
            result["footer"] = render_block_content("footer")

        return result

    def _resolve_template_name(
        self, template_name: str, context: Dict[str, Any]
    ) -> str:
        """解析最终的模版名称 (处理 Agent 覆盖)。"""
        agent_name = context.get("agent_name")
        target_template_name = template_name

        if agent_name:
            override_name = f"{agent_name}/{template_name}"
            # 检查 override 是否存在
            try:
                self.jinja_env.get_template(override_name)
                return override_name
            except jinja2.TemplateNotFound:
                try:
                    self.jinja_env.get_template(f"{override_name}.md")
                    return f"{override_name}.md"
                except jinja2.TemplateNotFound:
                    pass
        return target_template_name

    def _get_template(self, template_name: str):
        """获取 Template 对象，支持 .md 后缀回退。"""
        try:
            return self.jinja_env.get_template(template_name)
        except jinja2.TemplateNotFound:
            return self.jinja_env.get_template(f"{template_name}.md")

    def _recursive_render(self, content: str, context: Dict[str, Any]) -> str:
        """递归展开变量。"""
        rendered = content
        max_depth = 5
        for _ in range(max_depth):
            if "{{" not in rendered:
                break

            matches = re.findall(r"\{\{\s*([a-zA-Z0-9_./]+)\s*\}\}", rendered)
            new_context = context.copy()

            for var in matches:
                if var not in new_context and var in self.prompts:
                    new_context[var] = self.prompts[var].content

            prev_rendered = rendered
            try:
                rendered = self.jinja_env.from_string(rendered).render(**new_context)
            except Exception:
                # 如果展开出错，保留原样
                break

            if rendered == prev_rendered:
                break
        return rendered

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """内部全量渲染逻辑。"""
        if not self.jinja_env:
            return "{{Error: Jinja2 not initialized}}"

        target_template_name = self._resolve_template_name(template_name, context)

        try:
            template = self._get_template(target_template_name)
            rendered = template.render(**context)
            return self._recursive_render(rendered, context)
        except Exception as e:
            logger.error(f"渲染提示词 '{template_name}' 时出错: {e}")
            return "{{Error Rendering: " + str(template_name) + "}}"


from core.path_resolver import path_resolver  # noqa: E402

# 全局单例实例
_mdp_instance = None


def get_mdp_manager() -> MDPManager:
    global _mdp_instance
    if _mdp_instance is None:
        mdp_dir = path_resolver.resolve("@app/backend/services/mdp/prompts")
        _mdp_instance = MDPManager(str(mdp_dir))
    return _mdp_instance


# 便于访问的别名
mdp = get_mdp_manager()
