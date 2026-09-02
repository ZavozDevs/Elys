# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""MCUB's inline API on top of Elys's inline engine.

The underlying mechanism already matches: both frameworks send a form by having
the *userbot* fire an inline query at its own bot and click the first result,
then capture ``inline_message_id`` from ``UpdateBotInlineSend``. What differs is
the object model, so this module is mostly translation:

* MCUB returns ``(ok, InlineMessage)`` tuples; Elys returns ``InlineMessage``
  or ``False``.
* MCUB passes ``buttons=``; Elys wants dict-shaped ``reply_markup=``.
* MCUB's ``gallery``/``list``/``text`` are list-driven with ``[◀][🔄][▶]``
  navigation, while Elys's ``gallery`` is callback-driven. Rather than bend
  Elys's semantics, those three are implemented as paginated forms here, which
  reproduces MCUB's UX exactly.

Note that MCUB confusingly has *two* classes called ``InlineManager`` -- the
form engine (``core/lib/loader/inline.py``) and an inline-query ACL store
(``core_inline/lib/manager.py``). Both surfaces live here, kept apart.
"""

# Required, not cosmetic: this class exposes MCUB's `list()` and `text()` API
# names, which shadow the builtins inside the class body. Without deferred
# annotations, `-> list[list[dict]]` is evaluated eagerly against the class
# namespace on Python < 3.14 and raises TypeError at import time.
from __future__ import annotations

import html as html_lib
import logging
import typing
import uuid

from .events import MCUBCallbackEvent

logger = logging.getLogger(__name__)

DEFAULT_TTL = 200
MAX_GALLERY_ROWS = 10


def _stringify_fields(title: str, fields) -> str:
    """MCUB appends ``fields`` below the title as ``key: value`` lines."""
    if not fields:
        return title or ""

    lines = [title] if title else []
    if isinstance(fields, dict):
        lines.extend(f"<b>{html_lib.escape(str(k))}:</b> {v}" for k, v in fields.items())
    elif isinstance(fields, (list, tuple)):
        lines.extend(str(item) for item in fields)
    else:
        lines.append(str(fields))
    return "\n".join(lines)


def _media_kwargs(media, media_type: str) -> dict:
    if not media:
        return {}
    kind = (media_type or "photo").lower()
    if kind in {"photo", "image"}:
        return {"photo": media}
    if kind == "gif":
        return {"gif": media}
    if kind == "video":
        return {"video": media}
    if kind == "audio":
        return {"audio": media}
    return {"file": media, "mime_type": "application/pdf"}


class MCUBInlineManager:
    """Form/gallery/list/rich surface for MCUB modules."""

    def __init__(self, host) -> None:
        self._host = host
        self._sessions: dict[str, dict] = {}

    # -- plumbing ---------------------------------------------------------

    @property
    def _inline(self):
        return self._host.inline_manager

    @property
    def bot(self):
        inline = self._inline
        return getattr(inline, "bot", None) if inline is not None else None

    @property
    def bot_username(self):
        inline = self._inline
        return getattr(inline, "bot_username", None) if inline is not None else None

    def _require_inline(self) -> bool:
        inline = self._inline
        if inline is None or not getattr(inline, "init_complete", False):
            logger.warning("MCUB module requested an inline form but Elys has no bot")
            return False
        return True

    def _wrap(self, result, unit_id: str = ""):
        if not result:
            return False, None
        return True, MCUBCallbackEvent(result, unit_id=unit_id, kernel=self._host)

    # -- forms ------------------------------------------------------------

    async def inline_form(
        self,
        chat_id,
        title: str,
        fields=None,
        buttons=None,
        auto_send: bool = True,
        ttl: int = DEFAULT_TTL,
        media=None,
        media_type: str = "photo",
        reply_to: int | None = None,
        parse_mode: str = "html",
        rich_text: str | None = None,
        rich_parse_mode: str = "html",
        rich_message=None,
        rich_rtl: bool | None = None,
        rich_noautolink: bool | None = None,
        rich_files=None,
        silent: bool = False,
        **kwargs,
    ):
        from .buttons import to_elys_markup

        if not self._require_inline():
            return (False, None) if auto_send else None

        text = _stringify_fields(title, fields)
        markup = to_elys_markup(buttons) if buttons else None

        form_kwargs: dict[str, typing.Any] = {
            "ttl": ttl or DEFAULT_TTL,
            "silent": silent,
        }
        form_kwargs.update(_media_kwargs(media, media_type))

        payload = rich_message if rich_message is not None else rich_text
        if payload is not None:
            form_kwargs["rich_message"] = payload

        for passthrough in ("force_me", "always_allow", "disable_security", "on_unload"):
            if passthrough in kwargs:
                form_kwargs[passthrough] = kwargs.pop(passthrough)

        if reply_to is not None:
            # Elys derives reply_to from a Message object, not a bare chat id.
            logger.debug("MCUB reply_to=%s ignored: Elys forms reply via Message", reply_to)

        try:
            result = await self._inline.form(
                text=text or " ",
                message=chat_id,
                reply_markup=markup,
                **form_kwargs,
            )
        except Exception as error:
            logger.exception("MCUB inline form failed: %s", error)
            return (False, None) if auto_send else None

        if not auto_send:
            return getattr(result, "unit_id", None)

        return self._wrap(result, getattr(result, "unit_id", "") or "")

    async def form(self, chat_id, title, fields=None, buttons=None, **kwargs):
        return await self.inline_form(chat_id, title, fields, buttons, **kwargs)

    async def rich_form(
        self,
        chat_id,
        rich_text: str | None = None,
        *,
        buttons=None,
        rich_buttons=None,
        auto_send: bool = True,
        ttl: int = DEFAULT_TTL,
        reply_to: int | None = None,
        rich_parse_mode: str = "html",
        rich_message=None,
        text: str | None = None,
        parse_mode: str | None = None,
        rtl: bool | None = None,
        noautolink: bool | None = None,
        files=None,
        rich_media=None,
        **kwargs,
    ):
        """Send a Telegram rich-message form.

        ``elystl`` implements ``rich_message`` natively, so the payload is
        forwarded rather than emulated. ``rich_buttons`` are appended to the
        HTML as ``<tg-button>`` rows, which Telegram parses server-side.
        """
        if rich_text is None and rich_message is None:
            raise ValueError("Either rich_text or rich_message must be provided")

        mode = rich_parse_mode.lower() if isinstance(rich_parse_mode, str) else "html"

        if rich_buttons is not None:
            if rich_message is not None:
                raise ValueError("rich_buttons require HTML rich_text, not rich_message")
            if mode != "html":
                raise ValueError("rich_buttons require rich_parse_mode='html'")
            from ._vendor.rich_buttons import append_rich_buttons

            rich_text = append_rich_buttons(rich_text, rich_buttons)

        if rich_media or files:
            logger.warning(
                "MCUB rich_media/rich_files are not supported on Elys; sending"
                " rich text without attached rich files"
            )

        return await self.inline_form(
            chat_id,
            text if text is not None else "",
            buttons=buttons,
            auto_send=auto_send,
            ttl=ttl,
            reply_to=reply_to,
            rich_text=rich_text,
            rich_parse_mode=mode,
            rich_message=rich_message,
            **kwargs,
        )

    # -- paginated helpers -------------------------------------------------

    async def gallery(
        self,
        chat_id,
        title: str,
        rows: list,
        ttl: int = DEFAULT_TTL,
        escape_html: bool = False,
        **kwargs,
    ):
        if not rows:
            return False, None

        pages = list(rows)[:MAX_GALLERY_ROWS]

        def render(index: int) -> tuple[str, dict]:
            row = pages[index] or {}
            caption = row.get("text") or row.get("title") or title or ""
            if escape_html:
                caption = html_lib.escape(caption)
            media = row.get("photo") or row.get("gif") or row.get("video")
            media_type = (
                "gif" if row.get("gif") else "video" if row.get("video") else "photo"
            )
            return caption, _media_kwargs(media, media_type)

        return await self._paginate(
            chat_id, len(pages), render, ttl=ttl, title=title, **kwargs
        )

    async def list(
        self,
        chat_id,
        title: str,
        items: list,
        ttl: int = DEFAULT_TTL,
        escape_html: bool = False,
        per_page: int = 10,
        **kwargs,
    ):
        if not items:
            return False, None

        chunks = [items[i : i + per_page] for i in range(0, len(items), per_page)]

        def render(index: int) -> tuple[str, dict]:
            body = "\n".join(
                html_lib.escape(str(item)) if escape_html else str(item)
                for item in chunks[index]
            )
            head = f"{title}\n\n" if title else ""
            return f"{head}{body}", {}

        return await self._paginate(
            chat_id, len(chunks), render, ttl=ttl, title=title, **kwargs
        )

    async def text(
        self,
        chat_id,
        text: str,
        *,
        chars_per_page: int = 1000,
        ttl: int = DEFAULT_TTL,
        **kwargs,
    ):
        if not text:
            return False, None

        pages = [
            text[i : i + chars_per_page] for i in range(0, len(text), chars_per_page)
        ] or [text]

        def render(index: int) -> tuple[str, dict]:
            return pages[index], {}

        return await self._paginate(chat_id, len(pages), render, ttl=ttl, **kwargs)

    async def _paginate(
        self,
        chat_id,
        total: int,
        render: typing.Callable[[int], tuple[str, dict]],
        *,
        ttl: int,
        title: str = "",
        **kwargs,
    ):
        """Render page 0 with MCUB's ``[◀][🔄][▶]`` navigation row."""
        session_id = uuid.uuid4().hex[:8]
        self._sessions[session_id] = {"page": 0, "total": total}

        strings = self._host.global_strings()

        async def turn(call, page: int):
            page = page % total
            self._sessions[session_id]["page"] = page
            body, media = render(page)
            wrapped = MCUBCallbackEvent(call, kernel=self._host)
            try:
                await wrapped.edit(body, buttons=self._nav(session_id, page, total, turn, strings))
            except Exception as error:
                logger.debug("Pagination edit failed: %s", error)
                await wrapped.answer(str(error), alert=True)

        body, media = render(0)
        buttons = self._nav(session_id, 0, total, turn, strings) if total > 1 else None

        return await self.inline_form(
            chat_id,
            body,
            buttons=buttons,
            ttl=ttl,
            **{**kwargs, **{k: v for k, v in media.items()}},
        )

    @staticmethod
    def _nav(session_id, page, total, handler, strings) -> list[list[dict]]:
        if total <= 1:
            return []
        label = strings("buttons").get("page") or "Page: {}"
        try:
            indicator = label.format(f"{page + 1}/{total}")
        except (IndexError, KeyError):
            indicator = f"{page + 1}/{total}"
        return [
            [
                {"text": "◀", "callback": handler, "args": (page - 1,)},
                {"text": indicator, "callback": handler, "args": (page,)},
                {"text": "▶", "callback": handler, "args": (page + 1,)},
            ]
        ]

    # -- raw query --------------------------------------------------------

    async def inline_query_and_click(
        self,
        chat_id,
        query: str,
        bot_username: str | None = None,
        result_index: int = 0,
        buttons=None,
        silent: bool = False,
        reply_to: int | None = None,
        form_sms=None,
        **kwargs,
    ):
        if not self._require_inline():
            return False, None

        client = self._host.client
        target = bot_username or self.bot_username
        try:
            results = await client.inline_query(target, query)
            if not results:
                return False, None
            message = await results[result_index].click(chat_id, reply_to=reply_to)
        except Exception as error:
            logger.exception("MCUB inline query failed: %s", error)
            return False, None

        return self._wrap(message, query)

    async def query(self, chat_id, query, **kwargs):
        return await self.inline_query_and_click(chat_id, query, **kwargs)

    # -- handler registration --------------------------------------------

    def register_inline_handler(self, pattern: str, handler) -> None:
        self._host.register_inline_handler(pattern, handler)

    def register_callback_handler(self, pattern, handler) -> None:
        if isinstance(pattern, str):
            pattern = pattern.encode()
        self._host.register_callback_prefix("<inline>", pattern, handler)

    # -- ACL surface (MCUB's other InlineManager) -------------------------

    def is_admin(self, user_id) -> bool:
        return self._host.is_admin(user_id)

    async def is_allowed(self, user_id, command: str | None = None, context=None) -> bool:
        return await self._host.inline_acl_is_allowed(user_id, command)

    async def allow_user(self, user_id, command: str | None = None) -> bool:
        return await self._host.inline_acl_set(user_id, command, True)

    async def deny_user(self, user_id, command: str | None = None) -> bool:
        return await self._host.inline_acl_set(user_id, command, False)

    async def get_allowed_users(self, command: str | None = None) -> list:
        return await self._host.inline_acl_list()

    async def clear_all(self) -> bool:
        return await self._host.inline_acl_clear()

    def __repr__(self) -> str:
        return f"<MCUBInlineManager sessions={len(self._sessions)}>"
