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
    """Помощник для работы с форматированием сообщений (HTML, Markdown, Rich Messages, Raw, JSON)"""

    strings = {
        "name": "FormatHelper",
        "no_reply": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>Ответь на сообщение или укажи текст</b>",
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

    def _extract_source_text(
        self,
        message: Message,
        reply: Message | None,
    ) -> str | None:
        """Извлекает текст из аргументов команды или из реплая"""
        args = utils.get_args_raw(message)
        if args:
            return args

        if reply:
            return (
                getattr(reply, "raw_text", None)
                or getattr(reply, "message", None)
                or getattr(reply, "text", None)
            )

        return None

    # ==================== RICH MESSAGE ====================

    @loader.command(
        ru_doc="<html/текст> [reply] - Отправить или отредактировать сообщение как Rich Message",
        ua_doc="<html/текст> [reply] - Надіслати або відредагувати повідомлення як Rich Message",
        en_doc="<html/text> [reply] - Send or edit message as Rich Message",
    )
    async def rich(self, message: Message):
        """<html/text> [reply] - Send or edit message as Rich Message"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if not args and reply:
            args = (
                getattr(reply, "rich_message", None)
                or getattr(reply, "raw_text", None)
                or getattr(reply, "message", None)
                or getattr(reply, "text", "")
            )

        if not args:
            await utils.answer(message, self.strings["no_reply"])
            return

        await utils.answer(message, rich_message=args)

    @loader.command(
        ru_doc="[reply] - Получить Rich HTML код сообщения",
        ua_doc="[reply] - Отримати Rich HTML код повідомлення",
        en_doc="[reply] - Get Rich HTML code of message",
    )
    async def getrich(self, message: Message):
        """[reply] - Get Rich HTML code of message"""
        reply = await message.get_reply_message()
        target = reply or message
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
                    message.peer_id,
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

        if not rich_html:
            await utils.answer(message, self.strings["no_content"])
            return

        await self._send_or_code(message, rich_html, "rich_message.html", lang="html")

    # ==================== TELEGRAM HTML ====================

    @loader.command(
        ru_doc="<html/текст> [reply] - Отправить или отредактировать сообщение с парсингом Telegram HTML",
        ua_doc="<html/текст> [reply] - Надіслати або відредагувати повідомлення як Telegram HTML",
        en_doc="<html/text> [reply] - Send or edit message parsed as Telegram HTML",
    )
    async def html(self, message: Message):
        """<html/text> [reply] - Send or edit message parsed as Telegram HTML"""
        reply = await message.get_reply_message()
        text = self._extract_source_text(message, reply)

        if not text:
            await utils.answer(message, self.strings["no_reply"])
            return

        await utils.answer(message, text, parse_mode="html")

    @loader.command(
        ru_doc="[reply] - Получить Telegram HTML код сообщения",
        ua_doc="[reply] - Отримати Telegram HTML код повідомлення",
        en_doc="[reply] - Get Telegram HTML code of message",
    )
    async def gethtml(self, message: Message):
        """[reply] - Get Telegram HTML code of message"""
        reply = await message.get_reply_message()
        target = reply or message
        if not getattr(target, "message", None):
            await utils.answer(message, self.strings["no_content"])
            return

        try:
            rendered = html.unparse(target.message, target.entities or [])
        except Exception:
            rendered = getattr(target, "raw_text", None) or getattr(
                target, "message", ""
            )

        await self._send_or_code(message, rendered, "message.html", lang="html")

    # ==================== TELEGRAM MARKDOWN ====================

    @loader.command(
        ru_doc="<md/текст> [reply] - Отправить или отредактировать сообщение с парсингом Telegram Markdown",
        ua_doc="<md/текст> [reply] - Надіслати або відредагувати повідомлення як Telegram Markdown",
        en_doc="<md/text> [reply] - Send or edit message parsed as Telegram Markdown",
    )
    async def md(self, message: Message):
        """<md/text> [reply] - Send or edit message parsed as Telegram Markdown"""
        reply = await message.get_reply_message()
        text = self._extract_source_text(message, reply)

        if not text:
            await utils.answer(message, self.strings["no_reply"])
            return

        await utils.answer(message, text, parse_mode="md")

    @loader.command(
        ru_doc="[reply] - Получить Markdown код сообщения",
        ua_doc="[reply] - Отримати Markdown код повідомлення",
        en_doc="[reply] - Get Markdown code of message",
    )
    async def getmd(self, message: Message):
        """[reply] - Get Markdown code of message"""
        reply = await message.get_reply_message()
        target = reply or message
        if not getattr(target, "message", None):
            await utils.answer(message, self.strings["no_content"])
            return

        try:
            rendered = markdown.unparse(target.message, target.entities or [])
        except Exception:
            rendered = getattr(target, "raw_text", None) or getattr(
                target, "message", ""
            )

        await self._send_or_code(message, rendered, "message.md", lang="markdown")

    # ==================== RAW / ПЛАЙН ТЕКСТ ====================

    @loader.command(
        ru_doc="<текст> [reply] - Отправить или отредактировать сообщение как чистый текст (без форматирования)",
        ua_doc="<текст> [reply] - Надіслати або відредагувати повідомлення как чистий текст (без форматування)",
        en_doc="<text> [reply] - Send or edit message as raw text (without formatting)",
    )
    async def raw(self, message: Message):
        """<text> [reply] - Send or edit message as raw text (without formatting)"""
        reply = await message.get_reply_message()
        text = self._extract_source_text(message, reply)

        if not text:
            await utils.answer(message, self.strings["no_reply"])
            return

        await utils.answer(message, text, parse_mode=None)

    @loader.command(
        ru_doc="[reply] - Получить чистый сырой текст сообщения (без форматирования)",
        ua_doc="[reply] - Отримати чистий сирий текст повідомлення (без форматування)",
        en_doc="[reply] - Get raw text of message (without formatting)",
    )
    async def getraw(self, message: Message):
        """[reply] - Get raw text of message (without formatting)"""
        reply = await message.get_reply_message()
        target = reply or message
        text = (
            getattr(target, "raw_text", None)
            or getattr(target, "message", None)
            or getattr(target, "text", "")
        )

        if not text:
            await utils.answer(message, self.strings["no_content"])
            return

        await self._send_or_code(message, text, "message.txt")

    # ==================== JSON & ENTITIES ДАМП ====================

    @loader.command(
        ru_doc="[reply] - Получить JSON дамп структуры сообщения",
        ua_doc="[reply] - Отримати JSON дамп структури повідомлення",
        en_doc="[reply] - Get JSON dump of message structure",
    )
    async def msgjson(self, message: Message):
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
    async def entities(self, message: Message):
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
