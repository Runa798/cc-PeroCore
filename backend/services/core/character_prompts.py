"""Character prompt template system for consistent image generation.

Each agent can have a `image_prompt.json` in its data directory that
locks visual traits (hair, eyes, body, outfit) for consistent generation.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Agent directories
_BUILTIN_AGENTS = Path(__file__).parent.parent / "mdp" / "agents"
_USER_AGENTS = Path(__file__).parent.parent.parent / "data" / "agents"

# Template schema example (stored as image_prompt.json per agent):
# {
#   "character": "frieren",
#   "base_tags": "1girl, silver hair, ...",
#   "sfw_outfit": "white robe, ...",
#   "nsfw_tags": "nude, ...",
#   "negative_extra": "",
#   "default_artist": "@kuroboshi kouhaku",
#   "scenes": { "bedroom": "...", "outdoor": "..." }
# }


def _find_agent_dir(agent_id: str) -> Optional[Path]:
    """Locate the agent's data directory."""
    for base in [_USER_AGENTS, _BUILTIN_AGENTS]:
        d = base / agent_id
        if d.is_dir():
            return d
    return None


def load_character_prompt(agent_id: str) -> Optional[Dict[str, Any]]:
    """Load image_prompt.json for an agent. Returns None if not found."""
    agent_dir = _find_agent_dir(agent_id)
    if not agent_dir:
        return None
    prompt_file = agent_dir / "image_prompt.json"
    if not prompt_file.exists():
        return None
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("[CharPrompt] Failed to load %s: %s", prompt_file, e)
        return None


def build_positive(
    agent_id: str,
    scene: str = "",
    extra_tags: str = "",
    nsfw: bool = False,
) -> str:
    """Build a complete positive prompt from character template.

    Args:
        agent_id: Agent ID to load template for.
        scene: Scene key (e.g., "bedroom") or free-form scene tags.
        extra_tags: Additional tags appended at the end.
        nsfw: If True, include nsfw_tags instead of sfw_outfit.

    Returns:
        Complete positive prompt string. Falls back to extra_tags if no template.
    """
    tpl = load_character_prompt(agent_id)
    if not tpl:
        return extra_tags or ""

    parts: List[str] = []

    # Base character traits (always included)
    if tpl.get("base_tags"):
        parts.append(tpl["base_tags"])

    # Outfit / NSFW
    if nsfw and tpl.get("nsfw_tags"):
        parts.append(tpl["nsfw_tags"])
    elif tpl.get("sfw_outfit"):
        parts.append(tpl["sfw_outfit"])

    # Scene
    if scene:
        # Check predefined scenes first
        scenes = tpl.get("scenes", {})
        if scene in scenes:
            parts.append(scenes[scene])
        else:
            parts.append(scene)

    # Artist style
    if tpl.get("default_artist"):
        parts.append(tpl["default_artist"])

    # Extra tags
    if extra_tags:
        parts.append(extra_tags)

    return ", ".join(parts)


def list_characters() -> List[Dict[str, str]]:
    """List all agents that have image_prompt.json."""
    results = []
    for base in [_USER_AGENTS, _BUILTIN_AGENTS]:
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if d.is_dir() and (d / "image_prompt.json").exists():
                tpl = load_character_prompt(d.name)
                results.append({
                    "agent_id": d.name,
                    "character": tpl.get("character", d.name) if tpl else d.name,
                })
    return results
