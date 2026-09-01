# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import io
import json
import logging

from elystl.extensions import html, markdown
from elystl.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class FormatHelperMod(loader.Module):
    """Помощник для работы с форматированием сообщений (Rich HTML, Telegram HTML, Markdown, Raw text, JSON)"""

    strings = {
        "name": "FormatHelper",
        "no_args_or_reply": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>Укажи текст для форматирования или ответь на сообщение</b>",
        "no_content": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>В сообщении нет текста</b>",
        "no_entities": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>В сообщении нет форматирования</b>",
    }

    async def _send_or_code(
        self,
        message: Message,
        content: str,
        filename: str,
        lang: str | None = None,
    ):
        """Отправляет результат моноширинным кодом или файлом, если он слишком большой"""
        if len(content) > 3000:
            file = io.BytesIO(content.encode("utf-8"))
            file.name = filename
            file.seek(0)
            await utils.answer(message, file=file)
            return

        escaped = utils.escape_html(content)
        if lang:
            result = f'<pre><code class="language-{lang}">{escaped}</code></pre>'
        else:
            result = f"<code>{escaped}</code>"

        await utils.answer(message, result)

    async def _extract_rich_html(self, target: Message) -> str | None:
        """Извлекает Rich HTML разметку из сообщения"""
        rich_html = None

        if getattr(target, "_elys_rich_message_native", None) is not None:
            try:
                from ..utils.rich import rich_message_to_html

                rich_html = rich_message_to_html(target._elys_rich_message_native)
            except Exception:
                pass

        if not rich_html and getattr(target, "rich_message", None):
            val = getattr(target, "rich_message", None)
            if isinstance(val, str):
                rich_html = val
            else:
                try:
                    from ..utils.rich import rich_message_to_html

                    rich_html = rich_message_to_html(val)
                except Exception:
                    pass

        if not rich_html:
            try:
                rich_html = await self._client.get_rich_message(
                    target.peer_id,
                    target.id,
                    raw=False,
                )
            except Exception:
                rich_html = None

        if not rich_html and getattr(target, "message", None):
            try:
                rich_html = html.unparse(target.message, target.entities or [])
            except Exception:
                rich_html = getattr(target, "raw_text", None) or getattr(
                    target, "message", ""
                )

        return rich_html or getattr(target, "raw_text", None) or getattr(target, "message", None)

    # ==================== FRICH ====================

    @loader.command(
        ru_doc="<html/текст> или [reply] - Отправить Rich HTML или получить Rich разметку ответа",
        ua_doc="<html/текст> або [reply] - Надіслати Rich HTML або отримати Rich розмітку відповіді",
        en_doc="<html/text> or [reply] - Send Rich HTML or get Rich markup of replied message",
    )
    async def frich(self, message: Message):
        """<html/text> or [reply] - Send Rich HTML or get Rich markup of replied message"""
        args = utils.get_args_raw(message)
        if args:
            # Текст передан напрямую — форматируем и отправляем в Rich
            await utils.answer(message, rich_message=args)
            return

        reply = await message.get_reply_message()
        if reply:
            # Текст не передан, но есть реплай — извлекаем Rich HTML исходник
            rich_html = await self._extract_rich_html(reply)
            if not rich_html:
                await utils.answer(message, self.strings["no_content"])
                return
            await self._send_or_code(message, rich_html, "rich_message.html", lang="html")
            return

        await utils.answer(message, self.strings["no_args_or_reply"])

    # ==================== FHTML ====================

    @loader.command(
        ru_doc="<html/текст> или [reply] - Отправить Telegram HTML или получить HTML код ответа",
        ua_doc="<html/текст> або [reply] - Надіслати Telegram HTML або отримати HTML код відповіді",
        en_doc="<html/text> or [reply] - Send Telegram HTML or get HTML code of replied message",
    )
    async def fhtml(self, message: Message):
        """<html/text> or [reply] - Send Telegram HTML or get HTML code of replied message"""
        args = utils.get_args_raw(message)
        if args:
            # Текст передан напрямую — отправляем с HTML форматированием
            await utils.answer(message, args, parse_mode="html")
            return

        reply = await message.get_reply_message()
        if reply:
            # Текст не передан, но есть реплай — извлекаем чистый HTML исходник
            if not getattr(reply, "message", None):
                await utils.answer(message, self.strings["no_content"])
                return

            try:
                rendered = html.unparse(reply.message, reply.entities or [])
            except Exception:
                rendered = getattr(reply, "raw_text", None) or getattr(reply, "message", "")

            await self._send_or_code(message, rendered, "message.html", lang="html")
            return

        await utils.answer(message, self.strings["no_args_or_reply"])

    # ==================== FMD ====================

    @loader.command(
        ru_doc="<md/текст> или [reply] - Отправить Telegram Markdown или получить Markdown код ответа",
        ua_doc="<md/текст> або [reply] - Надіслати Telegram Markdown або отримати Markdown код відповіді",
        en_doc="<md/text> or [reply] - Send Telegram Markdown or get Markdown code of replied message",
    )
    async def fmd(self, message: Message):
        """<md/text> or [reply] - Send Telegram Markdown or get Markdown code of replied message"""
        args = utils.get_args_raw(message)
        if args:
            # Текст передан напрямую — отправляем с Markdown форматированием
            await utils.answer(message, args, parse_mode="md")
            return

        reply = await message.get_reply_message()
        if reply:
            # Текст не передан, но есть реплай — извлекаем Markdown исходник
            if not getattr(reply, "message", None):
                await utils.answer(message, self.strings["no_content"])
                return

            try:
                rendered = markdown.unparse(reply.message, reply.entities or [])
            except Exception:
                rendered = getattr(reply, "raw_text", None) or getattr(reply, "message", "")

            await self._send_or_code(message, rendered, "message.md", lang="markdown")
            return

        await utils.answer(message, self.strings["no_args_or_reply"])

    # ==================== FTEXT ====================

    @loader.command(
        ru_doc="<текст> или [reply] - Отправить чистый текст или получить сырой текст ответа",
        ua_doc="<текст> або [reply] - Надіслати чистий текст або отримати сирий текст відповіді",
        en_doc="<text> or [reply] - Send raw text or get raw text of replied message",
    )
    async def ftext(self, message: Message):
        """<text> or [reply] - Send raw text or get raw text of replied message"""
        args = utils.get_args_raw(message)
        if args:
            # Текст передан напрямую — отправляем без форматирования
            await utils.answer(message, args, parse_mode=None)
            return

        reply = await message.get_reply_message()
        if reply:
            # Текст не передан, но есть реплай — извлекаем сырой текст
            text = (
                getattr(reply, "raw_text", None)
                or getattr(reply, "message", None)
                or getattr(reply, "text", "")
            )
            if not text:
                await utils.answer(message, self.strings["no_content"])
                return

            await self._send_or_code(message, text, "message.txt")
            return

        await utils.answer(message, self.strings["no_args_or_reply"])

    # ==================== FJSON & FENTITIES ====================

    @loader.command(
        ru_doc="[reply] - Получить JSON дамп структуры сообщения",
        ua_doc="[reply] - Отримати JSON дамп структури повідомлення",
        en_doc="[reply] - Get JSON dump of message structure",
    )
    async def fjson(self, message: Message):
        """[reply] - Get JSON dump of message structure"""
        reply = await message.get_reply_message()
        target = reply or message
        try:
            dump_data = target.to_dict()
            rendered = json.dumps(dump_data, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            rendered = f"Error dumping message: {e}"

        await self._send_or_code(message, rendered, "message.json", lang="json")

    @loader.command(
        ru_doc="[reply] - Получить список сущностей форматирования (entities) сообщения",
        ua_doc="[reply] - Отримати список сутностей форматування (entities) повідомлення",
        en_doc="[reply] - Get message formatting entities dump",
    )
    async def fentities(self, message: Message):
        """[reply] - Get message formatting entities dump"""
        reply = await message.get_reply_message()
        target = reply or message
        entities_list = getattr(target, "entities", None)

        if not entities_list:
            await utils.answer(message, self.strings["no_entities"])
            return

        try:
            entities_dump = [
                e.to_dict() if hasattr(e, "to_dict") else str(e) for e in entities_list
            ]
            rendered = json.dumps(
                entities_dump, indent=2, ensure_ascii=False, default=str
            )
        except Exception as e:
            rendered = f"Error dumping entities: {e}"

        await self._send_or_code(message, rendered, "entities.json", lang="json")
