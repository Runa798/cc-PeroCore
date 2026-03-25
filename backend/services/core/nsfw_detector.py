"""Lightweight NSFW content detector for provider routing.

Scans the last user message for Chinese/English sexual keywords.
Returns True when the conversation is likely NSFW so the router
can switch away from providers that refuse explicit content.
"""

import re
from typing import Any, Dict, List

# ── 关键词库（命中任意一个即判定 NSFW） ──

_ZH_KEYWORDS = frozenset({
    # 身体部位
    "鸡巴", "肉棒", "巨物", "巨根", "大屌", "龟头", "阴茎",
    "乳房", "奶子", "乳头", "乳尖", "酥胸",
    "阴道", "蜜穴", "小穴", "骚逼", "阴蒂", "阴唇",
    "屁眼", "菊花", "肛门",
    # 状态 / 动作
    "勃起", "射精", "精液", "潮吹", "高潮", "内射",
    "抽插", "插入", "口交", "深喉", "颜射",
    "做爱", "性交", "操我", "干我", "肏",
    # 场景描述
    "破处", "开苞", "轮奸", "强奸", "调教", "捆绑",
    "自慰", "手淫", "打飞机",
    # 衣着 / 暗示
    "脱光", "全裸", "裸体", "内裤湿",
})

_EN_KEYWORDS = frozenset({
    "blowjob", "handjob", "creampie", "gangbang", "anal",
    "orgasm", "ejaculate", "cum inside", "fuck me",
    "pussy", "cock", "dick", "clit",
    "deepthroat", "bondage", "hentai",
})

# 组合短语（需要正则匹配的模式）
_PATTERNS = [
    re.compile(r"(写|来).{0,6}(nsfw|色情|黄色|肉|h)\s*(场景|内容|文|段)", re.I),
    re.compile(r"(脱|解开).{0,4}(衣服|内衣|裙子|裤子|胸罩)", re.I),
    re.compile(r"舔.{0,2}(下面|那里|私处)", re.I),
    re.compile(r"(用力|狠狠|使劲).{0,4}(操|干|插|顶|肏)", re.I),
]


def _extract_last_user_text(messages: List[Dict[str, Any]]) -> str:
    """Extract the text from the last user message."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts)
    return ""


def is_nsfw(messages: List[Dict[str, Any]]) -> bool:
    """Check whether the conversation's latest user turn contains NSFW content."""
    text = _extract_last_user_text(messages).lower()
    if not text:
        return False

    # 关键词命中
    for kw in _ZH_KEYWORDS:
        if kw in text:
            return True
    for kw in _EN_KEYWORDS:
        if kw in text:
            return True

    # 正则模式命中
    for pat in _PATTERNS:
        if pat.search(text):
            return True

    return False
