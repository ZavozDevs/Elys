# © ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging
import re
import typing
from pathlib import Path
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

EMOJI_YML_PATH = Path(__file__).parent / "emojis.yml"

# Registry: alias -> (emoji_id, fallback_unicode)
EMOJI_REGISTRY: dict[str, tuple[str, str]] = {}
# Reverse lookup: clean unicode symbol -> primary alias
SYMBOL_TO_ALIAS: dict[str, str] = {}


def _load_registry() -> None:
    global EMOJI_REGISTRY, SYMBOL_TO_ALIAS
    EMOJI_REGISTRY.clear()
    SYMBOL_TO_ALIAS.clear()

    if not EMOJI_YML_PATH.exists():
        logger.warning("emojis.yml not found at %s", EMOJI_YML_PATH)
        return

    try:
        yaml = YAML(typ="safe")
        data = yaml.load(EMOJI_YML_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return

        for _category, entries in data.items():
            if not isinstance(entries, dict):
                continue
            for primary_alias, info in entries.items():
                if not isinstance(info, dict):
                    continue
                eid = str(info.get("id") or "")
                fb = str(info.get("fallback") or "")
                aliases = [primary_alias] + list(info.get("aliases") or [])

                for a in aliases:
                    EMOJI_REGISTRY[a.lower()] = (eid, fb)

                clean_fb = fb.replace("\ufe0f", "")
                if clean_fb and clean_fb not in SYMBOL_TO_ALIAS:
                    SYMBOL_TO_ALIAS[clean_fb] = primary_alias
                if fb and fb not in SYMBOL_TO_ALIAS:
                    SYMBOL_TO_ALIAS[fb] = primary_alias

    except Exception:
        logger.exception("Failed to load emojis.yml")


_load_registry()

# Regex to find {e:name} and {emoji:name}
EMOJI_TOKEN_RE = re.compile(r"\{(?:e|emoji):([a-zA-Z0-9_]+)\}")


def get_emoji(name: str, use_custom: bool = True) -> str:
    """
    Returns HTML custom emoji tag or fallback unicode character for a given alias name.
    Example: get_emoji('star') -> '<tg-emoji emoji-id="5237836252400626980">⭐</tg-emoji>'
    """
    data = EMOJI_REGISTRY.get(name.lower())
    if not data:
        return f"{{e:{name}}}"
    eid, fb = data
    if use_custom and eid:
        return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
    return fb


def render_emojis(text: typing.Any, use_custom: bool = True) -> typing.Any:
    """
    Renders all {e:name} and {emoji:name} tokens in the given text into Telegram custom emoji tags.
    Fast path: returns original object immediately if text has no tokens.
    """
    if not isinstance(text, str):
        return text

    if "{e:" not in text and "{emoji:" not in text:
        return text

    def _replace(match: re.Match) -> str:
        token = match.group(1).lower()
        if token in EMOJI_REGISTRY:
            eid, fb = EMOJI_REGISTRY[token]
            if use_custom and eid:
                return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
            return fb
        return match.group(0)

    return EMOJI_TOKEN_RE.sub(_replace, text)


def clean_emojis(text: str) -> str:
    """
    Strips both {e:name} tokens and <tg-emoji> tags to plain unicode emojis.
    """
    if not isinstance(text, str):
        return text

    text = render_emojis(text, use_custom=False)
    return re.sub(r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", r"\1", text)


class _EmojiAccessor:
    """
    Convenient attribute-based access to emoji tags in Python code:
    e.g. E.star, E.stop, E.check, E.warn
    """
    def __getattr__(self, name: str) -> str:
        name_clean = name.lower()
        if name_clean in EMOJI_REGISTRY:
            return get_emoji(name_clean)
        raise AttributeError(f"No emoji alias registered with name '{name}'")

    def __getitem__(self, name: str) -> str:
        return self.__getattr__(name)


E = _EmojiAccessor()
