# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""MCUB watcher/permission tag filtering.

Ported from MCUB's ``_watcher_passes_filters`` (``core/lib/loader/register.py``)
so tag semantics match upstream exactly. One deliberate improvement: chat-kind
detection prefers Elys's ``is_private``/``is_group``/``is_channel`` properties
when present. Upstream infers them from ``event.chat``, which is ``None`` on
messages whose chat has not been fetched -- and in that case every ``only_pm``
watcher would silently never fire.
"""

from __future__ import annotations

import re
import typing


def _chat_kind(event, msg) -> tuple[bool, bool, bool]:
    """Return ``(is_pm, is_group, is_channel)``."""
    for source in (event, msg):
        private = getattr(source, "is_private", None)
        group = getattr(source, "is_group", None)
        channel = getattr(source, "is_channel", None)
        if private is not None or group is not None or channel is not None:
            return (
                bool(private),
                bool(group),
                bool(channel) and not bool(group),
            )

    chat = getattr(event, "chat", None)
    megagroup = getattr(chat, "megagroup", False)
    gigagroup = getattr(chat, "gigagroup", False)
    broadcast = getattr(chat, "broadcast", False)
    is_pm = bool(chat) and not megagroup and not broadcast and not gigagroup
    return is_pm, bool(megagroup or gigagroup), bool(broadcast)


def _media_kinds(msg) -> dict[str, bool]:
    media = getattr(msg, "media", None)
    document = getattr(media, "document", None) if media else None
    mime = getattr(document, "mime_type", "") or "" if document else ""
    attributes = getattr(document, "attributes", []) or [] if document else []

    return {
        "media": bool(media),
        "photo": bool(media and hasattr(media, "photo")),
        "video": bool(media and hasattr(media, "video")),
        "doc": bool(document),
        "audio": bool(document and mime.startswith("audio")),
        "sticker": any(
            type(attr).__name__ == "DocumentAttributeSticker" for attr in attributes
        ),
    }


def passes_filters(event, tags: typing.Mapping) -> bool:
    """True when *event* satisfies every declared tag filter."""
    if not tags:
        return True

    msg = getattr(event, "message", event)
    if isinstance(msg, str):
        # A raw Elys Message stores its text in `.message`; the MCUB event
        # adapter fixes this, but stay defensive for unwrapped inputs.
        msg = event

    if tags.get("out") and not getattr(msg, "out", False):
        return False
    if tags.get("incoming") and getattr(msg, "out", False):
        return False

    is_pm, is_group, is_channel = _chat_kind(event, msg)
    if tags.get("only_pm") and not is_pm:
        return False
    if tags.get("no_pm") and is_pm:
        return False
    if tags.get("only_groups") and not is_group:
        return False
    if tags.get("no_groups") and is_group:
        return False
    if tags.get("only_channels") and not is_channel:
        return False
    if tags.get("no_channels") and is_channel:
        return False

    kinds = _media_kinds(msg)
    for kind in ("media", "photo", "video", "audio", "doc", "sticker"):
        plural = {
            "media": "media",
            "photo": "photos",
            "video": "videos",
            "audio": "audios",
            "doc": "docs",
            "sticker": "stickers",
        }[kind]
        if tags.get(f"only_{plural}") and not kinds[kind]:
            return False
        if tags.get(f"no_{plural}") and kinds[kind]:
            return False

    forwarded = getattr(msg, "fwd_from", None)
    replied = getattr(msg, "reply_to", None)
    if tags.get("only_forwards") and not forwarded:
        return False
    if tags.get("no_forwards") and forwarded:
        return False
    if tags.get("only_reply") and not replied:
        return False
    if tags.get("no_reply") and replied:
        return False

    text = getattr(msg, "text", "") or ""
    if "regex" in tags and not re.search(tags["regex"], text):
        return False
    if "startswith" in tags and not text.startswith(tags["startswith"]):
        return False
    if "endswith" in tags and not text.endswith(tags["endswith"]):
        return False
    if "contains" in tags and tags["contains"] not in text:
        return False

    if "from_id" in tags and getattr(event, "sender_id", None) != tags["from_id"]:
        return False
    if "chat_id" in tags and getattr(event, "chat_id", None) != tags["chat_id"]:
        return False

    return True
