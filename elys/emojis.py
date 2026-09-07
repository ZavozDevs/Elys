# © ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import contextlib
import logging
import os
import re
import sys
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

        for entries in data.values():
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

# Regex to find <tg-emoji> and other custom emoji tag representations
CONVERT_TG_EMOJI_RE = re.compile(
    r"""<(?P<tag>tg-emoji|emoji|e)\b[^>]*\b(?:emoji[-_]?id|document[-_]?id|id)=["']?(?P<id>\d+)["']?[^>]*>(?P<text>.*?)</(?P=tag)>""",
    flags=re.IGNORECASE | re.DOTALL,
)

# Regex to find <a href="tg://emoji?id=..."> representations
CONVERT_A_EMOJI_RE = re.compile(
    r"""<a\b[^>]*\bhref=["']?tg://emoji\?id=(?P<id>\d+)["']?[^>]*>(?P<text>.*?)</a>""",
    flags=re.IGNORECASE | re.DOTALL,
)

_ALT_EMOJI_FORMAT: bool | None = None


def set_alt_emoji_format(enabled: bool) -> None:
    """Set the state of the experimental alternative emoji format (<a href="tg://emoji?id=...">)."""
    global _ALT_EMOJI_FORMAT
    _ALT_EMOJI_FORMAT = bool(enabled)


def is_alt_emoji_format() -> bool:
    """
    Checks if alternative <a href="tg://emoji?id=..."> format is enabled.
    Falls back to environment variables and database config.
    """
    if _ALT_EMOJI_FORMAT is not None:
        return _ALT_EMOJI_FORMAT

    env_val = os.environ.get("Settings.alt_emoji_format") or os.environ.get(
        "ELYS_ALT_EMOJI_FORMAT"
    )
    if env_val is not None:
        return env_val.strip().lower() in ("true", "1", "yes", "y", "on")

    with contextlib.suppress(Exception):
        main_mod = sys.modules.get("elys.main")
        if main_mod and hasattr(main_mod, "elys") and hasattr(main_mod.elys, "clients"):
            for client in main_mod.elys.clients:
                if hasattr(client, "elys_db") and client.elys_db:
                    for mod_name in ("Settings", "ElysConfigMod", "ElysConfig"):
                        val = client.elys_db.get(mod_name, "__config__", {}).get(
                            "alt_emoji_format"
                        )
                        if val is not None:
                            return bool(val)

    return False


def convert_to_alt_emoji(text: str) -> str:
    """
    Converts <tg-emoji emoji-id="...">...</tg-emoji> to <a href="tg://emoji?id=...">...</a>
    """
    if not isinstance(text, str):
        return text
    return CONVERT_TG_EMOJI_RE.sub(
        r'<a href="tg://emoji?id=\g<id>">\g<text></a>', text
    )


def convert_to_tg_emoji(text: str) -> str:
    """
    Converts <a href="tg://emoji?id=...">...</a> to <tg-emoji emoji-id="...">...</tg-emoji>
    """
    if not isinstance(text, str):
        return text
    return CONVERT_A_EMOJI_RE.sub(
        r'<tg-emoji emoji-id="\g<id>">\g<text></tg-emoji>', text
    )


def format_custom_emoji(
    emoji_id: str | int,
    fallback: str,
    alt_format: bool | None = None,
) -> str:
    """
    Formats a custom emoji tag according to the active format setting.
    """
    use_alt = is_alt_emoji_format() if alt_format is None else alt_format
    if use_alt:
        return f'<a href="tg://emoji?id={emoji_id}">{fallback}</a>'
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def get_emoji(
    name: str, use_custom: bool = True, alt_format: bool | None = None
) -> str:
    """
    Returns HTML custom emoji tag or fallback unicode character for a given alias name.
    Example: get_emoji('star') -> '<tg-emoji emoji-id="5237836252400626980">⭐</tg-emoji>'
    or '<a href="tg://emoji?id=5237836252400626980">⭐</a>' when alt_format is True
    """
    data = EMOJI_REGISTRY.get(name.lower())
    if not data:
        return f"{{e:{name}}}"
    eid, fb = data
    if use_custom and eid:
        return format_custom_emoji(eid, fb, alt_format=alt_format)
    return fb


def render_emojis(
    text: typing.Any, use_custom: bool = True, alt_format: bool | None = None
) -> typing.Any:
    """
    Renders all {e:name} and {emoji:name} tokens in the given text into Telegram custom emoji tags.
    Also converts existing <tg-emoji> tags if alt_format is enabled.
    """
    if not isinstance(text, str):
        return text

    use_alt = is_alt_emoji_format() if alt_format is None else alt_format

    if "{e:" not in text and "{emoji:" not in text:
        if use_alt and ("<tg-emoji" in text.lower() or "<emoji" in text.lower()):
            return convert_to_alt_emoji(text)
        return text

    def _replace(match: re.Match) -> str:
        token = match.group(1).lower()
        if token in EMOJI_REGISTRY:
            eid, fb = EMOJI_REGISTRY[token]
            if use_custom and eid:
                if use_alt:
                    return f'<a href="tg://emoji?id={eid}">{fb}</a>'
                return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
            return fb
        return match.group(0)

    res = EMOJI_TOKEN_RE.sub(_replace, text)
    if use_alt and ("<tg-emoji" in res.lower() or "<emoji" in res.lower()):
        res = convert_to_alt_emoji(res)
    return res


def clean_emojis(text: str) -> str:
    """
    Strips both {e:name} tokens, <tg-emoji> and <a href="tg://emoji?id=..."> tags to plain unicode emojis.
    """
    if not isinstance(text, str):
        return text

    text = render_emojis(text, use_custom=False)
    text = re.sub(
        r"""<(?P<tag>tg-emoji|emoji|e)\b[^>]*>(.*?)</(?P=tag)>""",
        r"\2",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return CONVERT_A_EMOJI_RE.sub(r"\g<text>", text)


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
