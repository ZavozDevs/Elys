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
    """Helper module for Rich Messages and message formatting"""

    strings = {
        "name": "FormatHelper",
        "no_reply": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>Ответь на сообщение или укажи текст</b>",
        "no_content": "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>В сообщении нет текста или форматирования</b>",
        "rich_header": "<b>Rich Message HTML:</b>",
        "html_header": "<b>Telegram HTML:</b>",
        "md_header": "<b>Markdown:</b>",
        "json_header": "<b>Message JSON:</b>",
    }

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
                or getattr(reply, "text", None)
                or getattr(reply, "message", "")
            )

        if not args:
            await utils.answer(message, self.strings["no_reply"])
            return

        await utils.answer(message, rich_message=args)

    @loader.command(
        ru_doc="[reply] - Получить Rich HTML код сообщения для копирования и вставки",
        ua_doc="[reply] - Отримати Rich HTML код повідомлення для копіювання",
        en_doc="[reply] - Get Rich HTML code of message to copy and paste",
    )
    async def getrich(self, message: Message):
        """[reply] - Get Rich HTML code of message to copy and paste"""
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
                rich_html = getattr(target, "text", None) or getattr(
                    target, "message", ""
                )

        if not rich_html:
            await utils.answer(message, self.strings["no_content"])
            return

        if len(rich_html) > 3000:
            file = io.BytesIO(rich_html.encode("utf-8"))
            file.name = "rich_message.html"
            file.seek(0)
            await utils.answer(message, self.strings["rich_header"], file=file)
        else:
            await utils.answer(
                message,
                self.strings["rich_header"]
                + "\n\n<code>"
                + utils.escape_html(rich_html)
                + "</code>",
            )

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
            rendered = getattr(target, "text", None) or getattr(target, "message", "")

        if len(rendered) > 3000:
            file = io.BytesIO(rendered.encode("utf-8"))
            file.name = "message.html"
            file.seek(0)
            await utils.answer(message, self.strings["html_header"], file=file)
        else:
            await utils.answer(
                message,
                self.strings["html_header"]
                + "\n\n<code>"
                + utils.escape_html(rendered)
                + "</code>",
            )

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

        if len(rendered) > 3000:
            file = io.BytesIO(rendered.encode("utf-8"))
            file.name = "message.md"
            file.seek(0)
            await utils.answer(message, self.strings["md_header"], file=file)
        else:
            await utils.answer(
                message,
                self.strings["md_header"]
                + "\n\n<code>"
                + utils.escape_html(rendered)
                + "</code>",
            )

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

        if len(rendered) > 3000:
            file = io.BytesIO(rendered.encode("utf-8"))
            file.name = "message.json"
            file.seek(0)
            await utils.answer(message, self.strings["json_header"], file=file)
        else:
            await utils.answer(
                message,
                self.strings["json_header"]
                + '\n\n<pre><code class="language-json">'
                + utils.escape_html(rendered)
                + "</code></pre>",
            )
