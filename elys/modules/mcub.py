# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging

from elystl.tl.types import Message

from .. import loader, mcub_compat, utils

logger = logging.getLogger(__name__)


@loader.tds
class MCUBMod(loader.Module):
    """Диагностика слоя совместимости с модулями MCUB"""

    # Plain Unicode emoji only. Custom emoji need a verified document id that
    # the account can actually resolve; an unresolvable one makes Telegram
    # reject the whole edit with DocumentInvalidError ("The document file was
    # invalid and can't be used in inline mode"), which took this command down
    # entirely rather than just degrading the icon.
    strings = {
        "name": "MCUB",
        "header": (
            "🧩 <b>MCUB compatibility</b>\n\n"
            "<b>API level:</b> <code>{version}</code>\n"
            "<b>Upstream:</b> {upstream}\n"
            "<b>Virtual imports:</b> <code>{virtual}</code>\n"
            "<b>Callback tokens:</b> <code>{tokens}</code>\n"
            "<b>Inline prompts:</b> <code>{prompts}</code>"
        ),
        "no_modules": "\n\n💭 <b>No MCUB modules loaded</b>",
        "modules_header": "\n\n📦 <b>Loaded modules ({count}):</b>",
        "module_row": (
            "\n• <b>{name}</b> <code>{version}</code> — <i>{style}</i>\n"
            "  <code>{handlers}</code>"
        ),
        "contested": (
            "\n\n⚠️ <b>Import names owned by other packages:</b>"
            " <code>{names}</code>"
        ),
        "not_mcub": (
            "❌ <b>This is not an MCUB module</b> (detected:"
            " <code>{style}</code>)"
        ),
        "detected": (
            "🧩 <b>Detected style:</b> <code>{style}</code>\n"
            "<b>Name:</b> <code>{name}</code>\n"
            "<b>Author:</b> <code>{author}</code>\n"
            "<b>Version:</b> <code>{version}</code>\n"
            "<b>Requires:</b> <code>{requires}</code>"
        ),
        "no_file": "❌ <b>Reply to a module file to inspect it</b>",
    }

    strings_ru = {
        "no_modules": "\n\n💭 <b>Модули MCUB не загружены</b>",
        "modules_header": "\n\n📦 <b>Загруженные модули ({count}):</b>",
        "not_mcub": (
            "❌ <b>Это не модуль MCUB</b> (определено: <code>{style}</code>)"
        ),
        "no_file": "❌ <b>Ответь на файл модуля, чтобы его проверить</b>",
    }

    @loader.command(
        ru_doc="Показать состояние слоя совместимости MCUB",
        en_doc="Show the state of the MCUB compatibility layer",
    )
    async def mcubcheck(self, message: Message):
        info = mcub_compat.diagnostics()

        text = self.strings["header"].format(
            version=info["emulated_mcub_version"],
            upstream=info["upstream"],
            virtual=info["virtual_names"],
            tokens=info["callback_tokens"],
            prompts=len(info["inline_temp"]),
        )

        modules = info["modules"]
        if not modules:
            text += self.strings["no_modules"]
        else:
            text += self.strings["modules_header"].format(count=len(modules))
            for summary in modules.values():
                handlers = ", ".join(
                    f"{key}={value}"
                    for key, value in summary["handlers"].items()
                    if value
                )
                text += self.strings["module_row"].format(
                    name=utils.escape_html(summary["name"]),
                    version=utils.escape_html(str(summary["version"] or "?")),
                    style=utils.escape_html(summary["style"]),
                    handlers=utils.escape_html(handlers or "none"),
                )

        if info["contested_names"]:
            text += self.strings["contested"].format(
                names=utils.escape_html(", ".join(info["contested_names"]))
            )

        await utils.answer(message, text)

    @loader.command(
        ru_doc="Определить стиль модуля из файла в ответе",
        en_doc="Detect the module style of a replied-to file",
    )
    async def mcubdetect(self, message: Message):
        target = message if message.file else await message.get_reply_message()
        if target is None or not target.file:
            await utils.answer(message, self.strings["no_file"])
            return

        source = (await target.download_media(bytes)).decode("utf-8", errors="replace")
        style = mcub_compat.detect_style(source)

        if style not in mcub_compat.MCUB_STYLES:
            await utils.answer(message, self.strings["not_mcub"].format(style=style))
            return

        meta = mcub_compat.parse_header(source)
        await utils.answer(
            message,
            self.strings["detected"].format(
                style=style,
                name=utils.escape_html(meta.get("name") or "—"),
                author=utils.escape_html(meta.get("author") or "—"),
                version=utils.escape_html(meta.get("version") or "—"),
                requires=utils.escape_html(", ".join(meta["requires"]) or "—"),
            ),
        )
