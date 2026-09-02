# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Event objects handed to MCUB module code.

Two shapes are needed:

``MCUBEvent``
    Wraps the ``elystl`` :class:`~elystl.tl.custom.Message` that Elys passes to
    command handlers, and presents it as a Telethon *event*. The critical
    difference is ``.message``: on a Telethon event that attribute is the
    Message object, but on a Message it is the **text string**. MCUB modules
    routinely write ``getattr(event.message, "reply_to", None)``, which would
    silently evaluate to ``None`` against a raw Elys Message and quietly break
    every topic-aware reply.

``MCUBCallbackEvent``
    Wraps Elys's :class:`~elys.inline.types.InlineCall` and presents MCUB's
    ``InlineMessage`` API: ``.data`` as **bytes** (Elys decodes to ``str``),
    ``edit(text, buttons=...)`` instead of ``reply_markup=``, ``answer(text,
    alert=...)``, and ``edit_rich(...)``.
"""

from __future__ import annotations

import logging
import typing

from .. import utils

logger = logging.getLogger(__name__)


def _as_bytes(value: typing.Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if value is None:
        return b""
    return str(value).encode("utf-8", errors="replace")


def _as_text(value: typing.Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return "" if value is None else str(value)


def to_html(text, parse_mode: str = "html") -> str:
    """Render *text* as HTML. Elys's form/edit path is HTML-only."""
    if text is None:
        return text
    mode = str(parse_mode or "html").lower()
    if mode in {"md", "markdown"}:
        try:
            from elystl.extensions import html as html_parser
            from elystl.extensions import markdown

            parsed, entities = markdown.parse(str(text))
            return html_parser.unparse(parsed, entities)
        except Exception:
            return str(text)
    return str(text)


def to_message_entities(text, parse_mode: str = "html"):
    """Return ``(message, entities)`` for a raw Telethon edit request."""
    if text is None:
        return None, None
    mode = str(parse_mode or "html").lower()
    try:
        if mode in {"md", "markdown"}:
            from elystl.extensions import markdown

            return markdown.parse(str(text))
        if mode == "html":
            from elystl.extensions import html as html_parser

            return html_parser.parse(str(text))
    except Exception:
        logger.debug("parse_mode=%s failed, sending raw text", parse_mode, exc_info=True)
    return str(text), None


class MCUBEvent:
    """Telethon-event facade over an Elys ``Message``."""

    __slots__ = (
        "_mcub_kernel",
        "_mcub_module",
        "_mcub_msg",
        "_mcub_pipe_output",
        "pipe_exit_code",
    )

    def __init__(self, message, module_name: str = "", kernel=None) -> None:
        object.__setattr__(self, "_mcub_msg", message)
        object.__setattr__(self, "_mcub_module", module_name)
        object.__setattr__(self, "_mcub_kernel", kernel)
        object.__setattr__(self, "_mcub_pipe_output", None)
        object.__setattr__(self, "pipe_exit_code", 0)

    # -- identity ---------------------------------------------------------

    @property
    def message(self):
        """The underlying Message.

        Telethon events expose the Message here; Elys hands us the Message
        itself, where ``.message`` is the text. Returning the object keeps
        ``event.message.reply_to`` working the way module authors expect.
        """
        return object.__getattribute__(self, "_mcub_msg")

    @property
    def raw_message(self):
        return object.__getattribute__(self, "_mcub_msg")

    @property
    def text(self) -> str:
        return getattr(self.raw_message, "text", "") or ""

    @property
    def raw_text(self) -> str:
        return getattr(self.raw_message, "raw_text", "") or ""

    @property
    def id(self) -> int:
        return getattr(self.raw_message, "id", 0)

    @property
    def message_id(self) -> int:
        return getattr(self.raw_message, "id", 0)

    @property
    def chat_id(self):
        message = self.raw_message
        try:
            return utils.get_chat_id(message)
        except Exception:
            return getattr(message, "chat_id", None)

    @property
    def sender_id(self):
        message = self.raw_message
        return getattr(message, "sender_id", None) or getattr(message, "from_id", None)

    @property
    def client(self):
        return getattr(self.raw_message, "client", None)

    @property
    def is_reply(self) -> bool:
        return bool(getattr(self.raw_message, "reply_to", None))

    @property
    def reply_to_msg_id(self):
        return getattr(self.raw_message, "reply_to_msg_id", None)

    # -- pipeline (MCUB-only; Elys has no pipeline, so this stays inert) ---

    @property
    def piped(self) -> bool:
        return False

    @property
    def pipe_input(self):
        return None

    @property
    def pipe_output(self):
        return object.__getattribute__(self, "_mcub_pipe_output")

    @pipe_output.setter
    def pipe_output(self, value) -> None:
        object.__setattr__(self, "_mcub_pipe_output", value)

    # -- helpers MCUB adds on top of Telethon -----------------------------

    def no_owner(self) -> bool:
        """True when the sender is not the account owner."""
        client = self.client
        owner_id = getattr(client, "tg_id", None)
        sender_id = self.sender_id
        if owner_id is None or sender_id is None:
            return False
        return int(sender_id) != int(owner_id)

    @property
    def is_admin(self) -> bool:
        return not self.no_owner()

    async def get_thread_id(self):
        message = self.raw_message
        reply_to = getattr(message, "reply_to", None)
        if reply_to is None:
            return None
        if getattr(reply_to, "forum_topic", False):
            return getattr(reply_to, "reply_to_top_id", None) or getattr(
                reply_to, "reply_to_msg_id", None
            )
        return None

    def format_with_html(self, text: str, *args, **kwargs) -> str:
        if args or kwargs:
            try:
                return text.format(*args, **kwargs)
            except (IndexError, KeyError, ValueError):
                return text
        return text

    # -- messaging --------------------------------------------------------

    @staticmethod
    def _normalize_send_kwargs(kwargs: dict) -> dict:
        reply_markup = kwargs.pop("reply_markup", None)
        if reply_markup is not None and "buttons" not in kwargs:
            kwargs["buttons"] = reply_markup
        if kwargs.pop("as_html", False):
            kwargs.setdefault("parse_mode", "html")
        kwargs.pop("kernel", None)
        return kwargs

    async def edit(self, text=None, *args, **kwargs):
        kwargs = self._normalize_send_kwargs(kwargs)
        return await utils.answer(self.raw_message, text, *args, **kwargs)

    async def reply(self, text=None, *args, **kwargs):
        kwargs = self._normalize_send_kwargs(kwargs)
        return await self.raw_message.reply(text, *args, **kwargs)

    async def respond(self, text=None, *args, **kwargs):
        kwargs = self._normalize_send_kwargs(kwargs)
        return await self.raw_message.respond(text, *args, **kwargs)

    async def answer(self, text=None, *args, **kwargs):
        """MCUB's ``answer`` is edit-or-reply, matching ``utils.answer``."""
        return await self.edit(text, *args, **kwargs)

    async def delete(self):
        return await self.raw_message.delete()

    async def get_reply_message(self):
        return await self.raw_message.get_reply_message()

    # -- passthrough ------------------------------------------------------

    def __getattr__(self, name: str):
        if name.startswith("_mcub_"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_mcub_msg"), name)

    def __setattr__(self, name: str, value) -> None:
        if name in MCUBEvent.__slots__ or name == "pipe_output":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_mcub_msg"), name, value)

    def __repr__(self) -> str:
        return f"<MCUBEvent {object.__getattribute__(self, '_mcub_msg')!r}>"


class MCUBCallbackEvent:
    """MCUB ``InlineMessage`` facade over an Elys ``InlineCall``."""

    def __init__(self, call, *, unit_id: str = "", kernel=None) -> None:
        self._call = call
        self._kernel = kernel
        self.unit_id = unit_id or getattr(call, "unit_id", "") or ""

    # -- identity ---------------------------------------------------------

    @property
    def data(self) -> bytes:
        """Raw callback payload. MCUB compares against ``bytes`` literals."""
        return _as_bytes(getattr(self._call, "data", b""))

    @property
    def data_str(self) -> str:
        return _as_text(getattr(self._call, "data", ""))

    @property
    def inline_message_id(self):
        return getattr(self._call, "inline_message_id", None)

    @property
    def chat_id(self):
        return getattr(self._call, "chat_id", None)

    @property
    def message_id(self):
        return getattr(self._call, "message_id", None)

    @property
    def sender_id(self):
        return getattr(self._call, "sender_id", None)

    @property
    def from_user(self):
        return getattr(self._call, "from_user", None)

    @property
    def text(self) -> str:
        message = getattr(self._call, "message", None)
        if message is not None:
            return getattr(message, "text", "") or getattr(message, "message", "") or ""
        return getattr(self._call, "text", "") or ""

    # -- actions ----------------------------------------------------------

    async def answer(self, text: str = "", alert: bool = False, **kwargs):
        """Toast or modal alert. Elys accepts ``alert=`` directly.

        Form handles returned by ``inline.form()`` have no callback query to
        answer, so this degrades to a no-op there rather than raising.
        """
        responder = getattr(self._call, "answer", None)
        if not callable(responder):
            logger.debug("answer() on a non-callback inline message ignored")
            return None
        try:
            return await responder(text, alert=alert, **kwargs)
        except TypeError:
            return await responder(text, show_alert=alert, **kwargs)

    async def edit(self, text=None, buttons=None, *, parse_mode="html", **kwargs):
        """MCUB names the markup ``buttons``; Elys names it ``reply_markup``.

        Elys's ``_edit_unit`` hardcodes HTML and rejects a ``parse_mode``
        kwarg, so markdown is converted here rather than forwarded.
        """
        from .buttons import to_elys_markup

        if buttons is not None:
            kwargs["reply_markup"] = to_elys_markup(buttons)
        kwargs.pop("parse_mode", None)
        if text is not None:
            kwargs["text"] = to_html(text, parse_mode)
        await self._call.edit(**kwargs)
        return self

    async def edit_rich(
        self,
        html: str | None = None,
        buttons=None,
        *,
        rich_buttons=None,
        rich_message=None,
        markdown: str | None = None,
        text: str = "",
        fallback: bool = False,
        fallback_text: str | None = None,
        **kwargs,
    ):
        """Rich-message edit.

        ``elystl`` supports ``rich_message`` on inline edits natively, so this
        forwards the payload rather than emulating it.
        """
        from .buttons import to_elys_markup

        if rich_buttons is not None:
            if not isinstance(html, str):
                raise TypeError("html must be a string when rich_buttons are used")
            if markdown is not None or rich_message is not None:
                raise ValueError(
                    "rich_buttons require HTML, not markdown or rich_message"
                )
            from ._vendor.rich_buttons import append_rich_buttons

            html = append_rich_buttons(html, rich_buttons)

        payload = rich_message if rich_message is not None else (html or markdown)
        if payload is None:
            raise ValueError("Either html, markdown or rich_message must be provided")

        if buttons is not None:
            kwargs["reply_markup"] = to_elys_markup(buttons)

        try:
            await self._call.edit(rich_message=payload, **kwargs)
            return self
        except Exception as error:
            if not fallback:
                raise
            logger.debug("Rich inline edit failed, falling back: %s", error)
            body = fallback_text if fallback_text is not None else (html or text or "")
            await self._call.edit(text=body, **kwargs)
            return self

    async def delete(self):
        return await self._call.delete()

    async def unload(self):
        unload = getattr(self._call, "unload", None)
        if callable(unload):
            return await unload()
        return None

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._call, name)

    def __repr__(self) -> str:
        return f"<MCUBCallbackEvent data={self.data_str!r}>"


class MCUBInlineQuery:
    """Facade over Elys's ``InlineQuery`` for ``@inline`` handlers."""

    def __init__(self, query, *, kernel=None) -> None:
        self._query = query
        self._kernel = kernel

    @property
    def builder(self):
        return getattr(self._query, "builder", None)

    @property
    def args(self) -> str:
        return getattr(self._query, "args", "") or ""

    @property
    def query(self):
        return self._query

    async def answer(self, results, *args, **kwargs):
        return await self._query.answer(results, *args, **kwargs)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._query, name)


def wrap_event(message, module_name: str = "", kernel=None):
    """Wrap an Elys Message for MCUB module consumption.

    Objects that already look like MCUB events (or are not messages at all,
    such as pipeline contexts in tests) pass through untouched.
    """
    if isinstance(message, (MCUBEvent, MCUBCallbackEvent, MCUBInlineQuery)):
        return message
    if message is None:
        return None
    if not hasattr(message, "client") and not hasattr(message, "_client"):
        return message
    return MCUBEvent(message, module_name, kernel)
