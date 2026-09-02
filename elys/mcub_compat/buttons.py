# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""MCUB button construction and callback-token dispatch.

MCUB builds *real* Telethon buttons whose ``data`` is an opaque token, and
keeps a ``token -> handler`` map of its own (``kernel.inline_callback_map``).
Elys instead uses dict-shaped markup and generates ``_callback_data`` itself.

We keep MCUB's model, because it is the only one that works on both paths a
module might use (``inline.form(buttons=...)`` and a raw ``buttons=`` kwarg),
and because module code passes bare ``telethon.Button.inline(...)`` objects
around. :func:`to_elys_markup` then flattens whatever the module produced into
Elys markup dicts, preserving the token as a raw ``data`` payload so Elys
renders the button and our own dispatcher resolves the handler.
"""

from __future__ import annotations

import inspect
import logging
import threading
import time
import typing
import uuid

logger = logging.getLogger(__name__)

VALID_STYLES = frozenset({"primary", "danger", "success", "link"})
DEFAULT_TTL = 900


def _telethon_button():
    from elystl import Button

    return Button


class CallbackRegistry:
    """Process-wide ``token -> handler`` map with TTL and per-module cleanup."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, dict] = {}
        self._by_module: dict[str, list[str]] = {}

    def register(
        self,
        handler: typing.Callable,
        *,
        module_name: str,
        args: typing.Sequence = (),
        kwargs: typing.Mapping | None = None,
        data: typing.Any = None,
        ttl: int = DEFAULT_TTL,
        allow_user: typing.Any = None,
        token: str | None = None,
    ) -> str:
        token = token or uuid.uuid4().hex
        entry = {
            "handler": handler,
            "args": list(args or []),
            "kwargs": dict(kwargs or {}),
            "data": data,
            "module_name": module_name,
            "allow_user": allow_user,
            "expires_at": time.time() + ttl if ttl else None,
        }
        with self._lock:
            self._purge_locked()
            self._entries[token] = entry
            self._by_module.setdefault(module_name, []).append(token)
        return token

    def get(self, token: str) -> dict | None:
        with self._lock:
            self._purge_locked()
            return self._entries.get(token)

    def pop(self, token: str) -> dict | None:
        with self._lock:
            entry = self._entries.pop(token, None)
            if entry is not None:
                module_name = entry.get("module_name")
                tokens = self._by_module.get(module_name) if module_name else None
                if tokens is not None:
                    try:
                        tokens.remove(token)
                    except ValueError:
                        pass
            return entry

    def forget_module(self, module_name: str) -> int:
        with self._lock:
            tokens = self._by_module.pop(module_name, [])
            for token in tokens:
                self._entries.pop(token, None)
            return len(tokens)

    def put(self, token: str, entry: dict, *, module_name: str | None = None) -> None:
        """Store a pre-built entry under *token*, tracking it for unload."""
        module_name = module_name or entry.get("module_name") or ""
        stored = dict(entry)
        stored.setdefault("module_name", module_name)
        with self._lock:
            self._purge_locked()
            self._entries[token] = stored
            if module_name:
                tokens = self._by_module.setdefault(module_name, [])
                if token not in tokens:
                    tokens.append(token)

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [
            token
            for token, entry in self._entries.items()
            if entry.get("expires_at") and entry["expires_at"] < now
        ]
        for token in expired:
            self._entries.pop(token, None)
            for tokens in self._by_module.values():
                try:
                    tokens.remove(token)
                except ValueError:
                    pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


#: Single shared registry; MCUB likewise keeps one map on the kernel.
registry = CallbackRegistry()


def entry_allows_user(entry: dict, sender_id) -> bool:
    """Replicates MCUB's ``_callback_entry_allows_user`` allow-list check."""
    if entry.get("allow_all"):
        return True
    allow_user = entry.get("allow_user")
    if allow_user == "all":
        return True
    if allow_user is None:
        return False
    if isinstance(allow_user, int):
        return sender_id == allow_user
    if isinstance(allow_user, (list, tuple, set)):
        return sender_id in allow_user
    return False


def make_callback_button(
    text: str,
    handler: typing.Callable,
    *,
    module_name: str,
    args: typing.Sequence = (),
    kwargs: typing.Mapping | None = None,
    data: typing.Any = None,
    ttl: int = DEFAULT_TTL,
    allow_user: typing.Any = None,
    allow_ttl: int = 100,
    permissions=None,
    style: str | None = None,
    icon: int | None = None,
    token: str | None = None,
    _return_token: bool = False,
    **button_kwargs,
):
    """Register *handler* and return a callback button bound to its token."""
    token = registry.register(
        handler,
        module_name=module_name,
        args=args,
        kwargs=kwargs,
        data=data,
        ttl=ttl,
        allow_user=allow_user,
        token=token,
    )

    if allow_user is not None and permissions is not None:
        if allow_user == "all":
            entry = registry.get(token)
            if entry is not None:
                entry["allow_all"] = True
        elif isinstance(allow_user, int):
            permissions.allow(allow_user, token, allow_ttl)
        elif isinstance(allow_user, (list, tuple, set)):
            for user_id in allow_user:
                permissions.allow(user_id, token, allow_ttl)

    if _return_token:
        return token

    if style is not None and style not in VALID_STYLES:
        style = None

    return _build_callback_button(text, token, style=style, icon=icon, **button_kwargs)


def _build_callback_button(text, token, *, style=None, icon=None, **extra):
    """Build ``Button.inline`` tolerating forks without ``style``/``icon``."""
    button_cls = _telethon_button()
    payload = token.encode() if isinstance(token, str) else token
    for attempt in (
        {"style": style, "icon": icon, **extra},
        {"icon": icon, **extra},
        {**extra},
    ):
        cleaned = {k: v for k, v in attempt.items() if v is not None}
        try:
            return button_cls.inline(text, payload, **cleaned)
        except TypeError:
            continue
    return button_cls.inline(text, payload)


# ---------------------------------------------------------------------------
# Markup normalisation: MCUB button objects/dicts -> Elys markup dicts
# ---------------------------------------------------------------------------


def _rows(buttons) -> list[list]:
    """Coerce any accepted markup shape into a list of rows.

    A flat ``[b1, b2, b3]`` is one row. Already-nested markup
    (``[[b1], [b2]]``) is left as vertical rows -- flattening those would
    smash a column keyboard into a single line.
    """
    if buttons is None:
        return []
    if isinstance(buttons, dict):
        return [[buttons]]
    if not isinstance(buttons, (list, tuple)):
        return [[buttons]]

    if any(isinstance(item, (list, tuple)) for item in buttons):
        return [
            list(item) if isinstance(item, (list, tuple)) else [item]
            for item in buttons
        ]
    return [list(buttons)]


def _style_of(button) -> str | None:
    style = getattr(button, "style", None)
    if isinstance(style, str) and style in VALID_STYLES:
        return style
    return None


def _icon_of(button) -> int | None:
    icon = getattr(button, "icon", None)
    if isinstance(icon, int):
        return icon
    document_id = getattr(icon, "document_id", None)
    return document_id if isinstance(document_id, int) else None


def _decorate(spec: dict, button) -> dict:
    style = _style_of(button)
    if style:
        spec["style"] = style
    icon = _icon_of(button)
    if icon:
        spec["emoji_id"] = icon
    return spec


def _from_dict(button: dict) -> dict | None:
    """Translate MCUB/Elys dict-shaped buttons into Elys markup."""
    spec: dict = {"text": str(button.get("text", ""))}
    for passthrough in ("style", "emoji_id", "always_allow", "force_me"):
        if button.get(passthrough) is not None:
            spec[passthrough] = button[passthrough]

    btn_type = button.get("type")
    callback = button.get("callback")

    if callable(callback):
        spec["callback"] = callback
        if button.get("args"):
            spec["args"] = tuple(button["args"])
        if button.get("kwargs"):
            spec["kwargs"] = dict(button["kwargs"])
        return spec

    if button.get("input") is not None and callable(button.get("handler")):
        spec["input"] = button["input"]
        spec["handler"] = button["handler"]
        if button.get("args"):
            spec["args"] = tuple(button["args"])
        if button.get("kwargs"):
            spec["kwargs"] = dict(button["kwargs"])
        return spec

    for key in ("url", "web_app", "copy", "action", "data"):
        if button.get(key) is not None:
            spec[key] = button[key]
            return spec

    if btn_type in {"callback", "callback_data"}:
        payload = button.get("data") or button.get("callback_data") or ""
        spec["data"] = payload.decode() if isinstance(payload, bytes) else str(payload)
        return spec

    for key in ("switch_inline_query_current_chat", "switch_inline_query"):
        if button.get(key) is not None:
            spec[key] = button[key]
            return spec

    if spec["text"]:
        # A label-only button; Elys needs an action, so make it inert.
        spec["action"] = "answer"
        spec["message"] = spec["text"]
        return spec

    return None


def _unwrap_tl(button):
    """Unwrap ``elystl``'s ``Button`` container around a raw TL button.

    Inline kinds (``Button.inline``, ``Button.url``, ``Button.switch_inline``)
    come back as bare TL objects, but reply-keyboard kinds like
    ``Button.request_phone`` are wrapped in a ``Button`` instance holding the
    real object on ``.button``. Reading ``.text`` off the wrapper silently
    returns ``Button.text``, the *static method*, so unwrap first.
    """
    inner = getattr(button, "button", None)
    if inner is not None and type(inner).__name__.startswith("KeyboardButton"):
        return inner
    return button


def _from_tl(button) -> dict | None:
    """Translate an ``elystl`` keyboard button object into Elys markup."""
    button = _unwrap_tl(button)
    name = type(button).__name__
    text = getattr(button, "text", "") or ""
    if not isinstance(text, str):
        text = ""
    spec: dict = {"text": str(text)}

    if name == "KeyboardButtonCallback":
        payload = getattr(button, "data", b"") or b""
        spec["data"] = payload.decode(errors="replace") if isinstance(payload, bytes) else str(payload)
    elif name in {"KeyboardButtonUrl", "KeyboardButtonUrlAuth"}:
        spec["url"] = getattr(button, "url", "")
    elif name in {"KeyboardButtonWebView", "KeyboardButtonSimpleWebView"}:
        spec["web_app"] = {"url": getattr(button, "url", "")}
    elif name == "KeyboardButtonSwitchInline":
        query = getattr(button, "query", "") or ""
        key = (
            "switch_inline_query_current_chat"
            if getattr(button, "same_peer", False)
            else "switch_inline_query"
        )
        spec[key] = query
    elif name == "KeyboardButtonCopy":
        spec["copy"] = getattr(button, "copy_text", None) or text
    else:
        # Reply-keyboard-only and unsupported kinds (request_phone, poll, game,
        # user profile...) have no inline equivalent. Keep the label visible
        # instead of dropping the row.
        logger.debug("MCUB button %s has no Elys inline equivalent", name)
        spec["action"] = "answer"
        spec["message"] = str(text) or "Unsupported button"

    return _decorate(spec, button)


def to_elys_markup(buttons) -> list[list[dict]]:
    """Normalise any MCUB markup into Elys's ``list[list[dict]]`` form."""
    result: list[list[dict]] = []

    for row in _rows(buttons):
        converted: list[dict] = []
        for button in row:
            if button is None:
                continue
            if isinstance(button, dict):
                spec = _from_dict(button)
            elif isinstance(button, str):
                spec = {"text": button, "action": "answer", "message": button}
            else:
                spec = _from_tl(button)
            if spec and spec.get("text") is not None:
                converted.append(spec)
        if converted:
            result.append(converted)

    return result


async def invoke_callback(entry: dict, call_event) -> typing.Any:
    """Call a registered handler with MCUB's argument convention."""
    handler = entry.get("handler")
    if handler is None:
        return None

    args = list(entry.get("args") or [])
    kwargs = dict(entry.get("kwargs") or {})
    if entry.get("data") is not None and "data" not in kwargs:
        kwargs["data"] = entry["data"]

    try:
        return await handler(call_event, *args, **kwargs)
    except TypeError as error:
        # Handlers that do not declare `data` are common; retry without it
        # rather than surfacing a signature error to the user.
        if "data" in kwargs and "data" in str(error):
            kwargs.pop("data")
            return await handler(call_event, *args, **kwargs)
        raise


async def invoke_by_signature(handler: typing.Callable, event, args: str, data) -> typing.Any:
    """MCUB inline_temp convention: ``(event)``, ``(event, args)`` or ``(..., data)``."""
    try:
        signature = inspect.signature(handler)
        count = len(
            [
                p
                for p in signature.parameters.values()
                if p.kind
                in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)
            ]
        )
        if any(
            p.kind is p.VAR_POSITIONAL for p in signature.parameters.values()
        ):
            count = 3
    except (TypeError, ValueError):
        count = 3

    if count >= 3:
        return await handler(event, args, data)
    if count == 2:
        return await handler(event, args)
    return await handler(event)
