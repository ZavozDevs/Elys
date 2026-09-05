# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""The ``utils`` package MCUB modules import, mapped onto Elys's own utils.

MCUB modules do ``import utils`` / ``from utils import answer, Strings`` and
then reach for helpers that Elys mostly already has under different names.
Anything Elys lacks is implemented here rather than vendored, because these
functions are thin and need Elys objects to work.
"""

from __future__ import annotations

import datetime
import logging

from .. import utils as elys_utils
from ._vendor.arg_parser import (  # noqa: F401  (re-exported)
    ArgumentParser,
    extract_command,
    parse_arguments,
    parse_kwargs,
    split_args,
)
from ._vendor.html_parser import (  # noqa: F401  (re-exported)
    format_message,
    parse_html,
    telegram_to_html,
)
from ._vendor.strings import Strings  # noqa: F401  (re-exported)

logger = logging.getLogger(__name__)


def _unwrap(event):
    """Return the underlying Elys ``Message`` for an MCUB event wrapper."""
    raw = getattr(event, "raw_message", None)
    return raw if raw is not None else event


# ---------------------------------------------------------------------------
# arguments
# ---------------------------------------------------------------------------


def get_args(event) -> list[str]:
    return elys_utils.get_args(_unwrap(event))


def get_args_raw(event) -> str:
    return elys_utils.get_args_raw(_unwrap(event))


def get_args_html(event) -> str:
    return elys_utils.get_args_html(_unwrap(event))


def get_prefix(target=None) -> str:
    prefix = getattr(target, "custom_prefix", None)
    return prefix if isinstance(prefix, str) and prefix else "."


def get_lang(target=None, default: str = "ru") -> str:
    config = getattr(target, "config", None)
    getter = getattr(config, "get", None)
    if callable(getter):
        return getter("language", default) or default
    return default


# ---------------------------------------------------------------------------
# messaging
# ---------------------------------------------------------------------------


async def answer(
    event,
    text,
    *,
    reply_markup=None,
    file=None,
    caption=None,
    as_html: bool = False,
    as_emoji: bool = False,
    kernel=None,
    **kwargs,
):
    """MCUB's ``utils.answer``: edit-or-reply with HTML defaults."""
    from .buttons import to_elys_markup

    message = _unwrap(event)

    if reply_markup is not None:
        kwargs["reply_markup"] = to_elys_markup(reply_markup)
    if file is not None:
        kwargs["file"] = file
    if caption is not None:
        text = caption if text is None else text

    # `as_html`/`as_emoji` are MCUB switches; Elys already parses HTML by
    # default on this path, so they only need to not blow up.
    kwargs.pop("as_html", None)
    kwargs.pop("as_emoji", None)

    return await elys_utils.answer(message, text, **kwargs)


async def answer_file(event, file, caption=None, *, as_html: bool = False, **kwargs):
    return await elys_utils.answer_file(_unwrap(event), file, caption, **kwargs)


async def edit_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    return await answer(event, html_text, as_html=True, **kwargs)


async def reply_with_html(kernel, event, html_text: str, truncate: bool = True, **kwargs):
    message = _unwrap(event)
    return await message.reply(html_text, parse_mode="html", **kwargs)


async def send_with_html(kernel, client, chat_id, html_text: str, truncate: bool = True, **kwargs):
    return await client.send_message(chat_id, html_text, parse_mode="html", **kwargs)


async def send_file_with_html(kernel, client, chat_id, html_text, file, truncate=True, **kwargs):
    return await client.send_file(
        chat_id, file, caption=html_text, parse_mode="html", **kwargs
    )


def clean_html_fallback(html_text: str) -> str:
    return elys_utils.remove_html(html_text)


# ---------------------------------------------------------------------------
# text / entities
# ---------------------------------------------------------------------------


def escape_html(text: str) -> str:
    return elys_utils.escape_html(text)


def escape_quotes(text: str) -> str:
    return elys_utils.escape_quotes(text)


def relocate_entities(entities, offset: int, text: str | None = None):
    return elys_utils.relocate_entities(entities, offset, text)


# ---------------------------------------------------------------------------
# chats / peers
# ---------------------------------------------------------------------------


def get_chat_id(event) -> int:
    return elys_utils.get_chat_id(_unwrap(event))


async def get_thread_id(event):
    getter = getattr(event, "get_thread_id", None)
    if callable(getter):
        return await getter()
    return elys_utils.get_topic(_unwrap(event))


async def get_sender_info(event) -> str:
    message = _unwrap(event)
    try:
        sender = await message.get_sender()
    except Exception:
        return str(getattr(message, "sender_id", "unknown"))
    name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or ""
    username = getattr(sender, "username", None)
    return f"{name} (@{username})" if username else name or str(sender.id)


async def get_admins(event_or_client, chat_id: int | None = None) -> list[dict]:
    client = getattr(event_or_client, "client", event_or_client)
    if chat_id is None:
        chat_id = get_chat_id(event_or_client)
    admins = []
    try:
        async for user in client.iter_participants(chat_id, filter=None):
            if getattr(user, "participant", None) is not None:
                admins.append({"id": user.id, "username": user.username})
    except Exception as error:
        logger.debug("get_admins failed: %s", error)
    return admins


async def resolve_peer(client, identifier):
    try:
        entity = await client.get_entity(identifier)
        return entity.id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------


def format_time(seconds, detailed: bool = False) -> str:
    return elys_utils.formatted_uptime() if seconds is None else _format_span(seconds)


def _format_span(seconds) -> str:
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def format_date(timestamp, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if isinstance(timestamp, datetime.datetime):
        return timestamp.strftime(fmt)
    return datetime.datetime.fromtimestamp(float(timestamp)).strftime(fmt)


def format_relative_time(timestamp) -> str:
    delta = datetime.datetime.now().timestamp() - float(timestamp)
    if delta < 0:
        return "in the future"
    return f"{_format_span(delta)} ago"


# ---------------------------------------------------------------------------
# buttons
# ---------------------------------------------------------------------------


def make_button(text: str, data=None, url=None, switch=None, same_peer: bool = False):
    from elystl import Button

    if url is not None:
        return Button.url(text, url)
    if switch is not None:
        return Button.switch_inline(text, query=switch, same_peer=same_peer)
    return Button.inline(text, (data or text).encode() if isinstance(data or text, str) else data)


def make_buttons(buttons, cols: int | None = None):
    rows: list[list] = []
    flat = []
    for item in buttons:
        if isinstance(item, list):
            rows.append([make_button(**b) if isinstance(b, dict) else b for b in item])
        else:
            flat.append(make_button(**item) if isinstance(item, dict) else item)
    if flat:
        step = cols or len(flat)
        rows.extend(flat[i : i + step] for i in range(0, len(flat), step))
    return rows


# ---------------------------------------------------------------------------
# placeholders (MCUB's API over Elys's placeholder registry)
# ---------------------------------------------------------------------------


#: scope -> {key: {"callback": ..., "description": ...}}
_PLACEHOLDERS: dict[str, dict[str, dict]] = {}


def resolve_placeholders(module, template: str, data: dict | None = None, strict: bool = False) -> str:
    values = dict(data or {})
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError) as error:
        if strict:
            raise
        logger.debug("resolve_placeholders left template intact: %s", error)
        return template


def register_placeholder(
    scope: str, key: str, callback, *, timeout=None, description: str | None = None
) -> bool:
    _PLACEHOLDERS.setdefault(scope, {})[key] = {
        "callback": callback,
        "timeout": timeout,
        "description": description,
    }
    return True


def register_decorated_placeholders(scope: str, owner) -> int:
    """Register every ``@placeholders``-marked method on *owner*."""
    count = 0
    for attr in dir(owner):
        bound = getattr(owner, attr, None)
        if bound is None or not callable(bound):
            continue
        meta = getattr(bound, "_mcub_placeholders", None) or getattr(
            bound, "_placeholders", None
        )
        if not meta:
            continue
        for entry in meta if isinstance(meta, (list, tuple)) else [meta]:
            key = (entry or {}).get("key") if isinstance(entry, dict) else None
            register_placeholder(
                scope,
                key or attr,
                bound,
                description=(entry or {}).get("description")
                if isinstance(entry, dict)
                else None,
            )
            count += 1
    return count


def unregister_scope(scope: str) -> int:
    removed = len(_PLACEHOLDERS.get(scope, {}))
    _PLACEHOLDERS.pop(scope, None)
    return removed


def unregister_placeholder(scope: str, key: str) -> bool:
    return _PLACEHOLDERS.get(scope, {}).pop(key, None) is not None


def list_placeholder_keys(scope: str) -> list[str]:
    return sorted(_PLACEHOLDERS.get(scope, {}))


def format_placeholders(scope: str) -> str:
    return ", ".join(f"{{{key}}}" for key in list_placeholder_keys(scope))


def config_placeholders(scope: str) -> str | None:
    """Human-readable placeholder docs, following MCUB's ``str | None``.

    Deliberately backed by this shim's own registry rather than Elys's
    similarly named helper: the two take different arguments and mean different
    things, so delegating would produce confident nonsense.
    """
    if scope == "any":
        lines = [
            f"{{{key}}} - {meta.get('description') or 'No docs'} ({scope_name})"
            for scope_name, items in sorted(_PLACEHOLDERS.items())
            for key, meta in sorted(items.items())
        ]
        return "\n".join(lines) or None

    items = _PLACEHOLDERS.get(scope, {})
    if not items:
        return None
    return "\n".join(
        f"{{{key}}} - {meta.get('description') or 'No docs'}"
        for key, meta in sorted(items.items())
    )


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


async def restart_kernel(kernel, chat_id=None, message_id=None, thread_id=None):
    restart = getattr(kernel, "restart", None)
    if callable(restart):
        return await restart(chat_id=chat_id, message_id=message_id)
    return None


def get_db_path() -> str:
    from .. import main

    return str(getattr(main, "BASE_PATH", "."))


def safe_extract_zip(*args, **kwargs):
    raise NotImplementedError(
        "utils.security.safe_extract_zip is not available in the Elys MCUB"
        " compatibility layer"
    )


def safe_extract_archive(*args, **kwargs):
    raise NotImplementedError(
        "utils.security.safe_extract_archive is not available in the Elys MCUB"
        " compatibility layer"
    )


def check_trust(*args, **kwargs) -> bool:
    return True


# ---------------------------------------------------------------------------
# platform
# ---------------------------------------------------------------------------


def get_platform() -> str:
    return elys_utils.get_named_platform()


def is_termux() -> bool:
    return "termux" in get_platform().lower()


def is_wsl() -> bool:
    return "wsl" in get_platform().lower()


__all__ = [
    "ArgumentParser",
    "Strings",
    "answer",
    "answer_file",
    "check_trust",
    "clean_html_fallback",
    "config_placeholders",
    "edit_with_html",
    "escape_html",
    "escape_quotes",
    "extract_command",
    "format_date",
    "format_message",
    "format_placeholders",
    "format_relative_time",
    "format_time",
    "get_admins",
    "get_args",
    "get_args_html",
    "get_args_raw",
    "get_chat_id",
    "get_db_path",
    "get_lang",
    "get_platform",
    "get_prefix",
    "get_sender_info",
    "get_thread_id",
    "is_termux",
    "is_wsl",
    "list_placeholder_keys",
    "make_button",
    "make_buttons",
    "parse_arguments",
    "parse_html",
    "parse_kwargs",
    "register_decorated_placeholders",
    "register_placeholder",
    "relocate_entities",
    "reply_with_html",
    "resolve_peer",
    "resolve_placeholders",
    "restart_kernel",
    "safe_extract_archive",
    "safe_extract_zip",
    "send_file_with_html",
    "send_with_html",
    "split_args",
    "telegram_to_html",
    "unregister_placeholder",
    "unregister_scope",
]
