# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import contextlib
import getpass
import inspect
import logging
import platform as lib_platform
import re
import time
import typing

import elystl
import psutil
from elystl.errors import WebpageMediaEmptyError
from elystl.tl.types import Message
from elystl.types import InputMediaWebPage
from elystl.utils import get_display_name

from .. import loader, utils, version

logger = logging.getLogger(__name__)


@loader.tds
class ElysInfoMod(loader.Module):
    """Show userbot info"""

    strings = {"name": "ElysInfo"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "custom_message",
                doc=lambda: (
                    self.strings["_cfg_cst_msg"]
                    + "\n"
                    + (
                        "\n"
                        + self.strings["_cfg_cst_ph"].format(
                            "\n" + utils.config_placeholders()
                        )
                        if utils.config_placeholders()
                        else ""
                    )
                ),
            ),
            loader.ConfigValue(
                "banner_url",
                "https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/elys_info.png",
                lambda: self.strings["_cfg_banner"],
                validator=loader.validators.RandomLink(),
            ),
            loader.ConfigValue(
                "ping_emoji",
                "🌟",
                lambda: self.strings["ping_emoji"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "quote_media",
                False,
                "Switch preview media to quote",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "invert_media",
                False,
                "Switch preview invert media",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "rich_mode",
                False,
                lambda: self.strings["_cfg_rich_mode"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_elys",
                True,
                "Show platform custom emoji if user has Telegram Premium",
                validator=loader.validators.Boolean(),
            ),
        )

    def _get_cpu_info(self) -> str | None:
        try:
            return f"{psutil.cpu_count(logical=False)} ({psutil.cpu_count()}) core(-s); {psutil.cpu_percent()}% total"
        except PermissionError:
            return None
        except Exception:
            logger.exception("Unsupported placeholder")
            return None

    def _get_os_name(self):
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME"):
                        return line.split("=")[1].strip().strip('"')
        except FileNotFoundError:
            return self.strings["non_detectable"]

    async def _render_info(
        self,
        start: float,
        template_key: str = "info_message",
        on_ready_callback: typing.Callable | None = None,
    ) -> str:
        async_enabled = utils.is_async_enabled(self._client)
        loading_ph = utils.get_loading_placeholder(self._client)

        if async_enabled:
            upd = loading_ph
        else:
            try:
                is_avail = await self.lookup("Updater").check_for_updates()
                upd = (
                    self.strings["upd_avail"]
                    if is_avail
                    else self.strings["up_to_date"]
                )
            except Exception:
                upd = ""

        me = (
            '<b><a href="tg://user?id={}">{}</a></b>'.format(
                self._client.elys_me.id,
                utils.escape_html(get_display_name(self._client.elys_me)),
            )
            .replace("{", "")
            .replace("}", "")
        )
        build = utils.get_commit_url()
        _version = f'<i>{".".join(list(map(str, list(version.__version__))))}</i>'
        prefix = f"«<code>{utils.escape_html(self.get_prefix())}</code>»"

        platform = utils.get_named_platform()
        platform_emoji = utils.get_named_platform_emoji()

        for emoji, icon in [
            ("🍊", '<tg-emoji emoji-id="5449599833973203438">🧡</tg-emoji>'),
            ("🍇", '<tg-emoji emoji-id="5449468596952507859">💜</tg-emoji>'),
            ("😶‍🌫️", '<tg-emoji emoji-id="5370547013815376328">😶‍🌫️</tg-emoji>'),
            ("❓", '<tg-emoji emoji-id="5407025283456835913">📱</tg-emoji>'),
            ("🍀", '<tg-emoji emoji-id="5395325195542078574">🍀</tg-emoji>'),
            ("🦾", '<tg-emoji emoji-id="5386766919154016047">🦾</tg-emoji>'),
            ("🚂", '<tg-emoji emoji-id="5359595190807962128">🚂</tg-emoji>'),
            ("🐳", '<tg-emoji emoji-id="5431815452437257407">🐳</tg-emoji>'),
            ("🕶", '<tg-emoji emoji-id="5407025283456835913">📱</tg-emoji>'),
            ("🐈‍⬛", '<tg-emoji emoji-id="6334750507294262724">🐈‍⬛</tg-emoji>'),
            ("✌️", '<tg-emoji emoji-id="5469986291380657759">✌️</tg-emoji>'),
            ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>'),
            ("🛡", '<tg-emoji emoji-id="5282731554135615450">🌩</tg-emoji>'),
            ("🌼", '<tg-emoji emoji-id="5224219153077914783">❤️</tg-emoji>'),
            ("🎡", '<tg-emoji emoji-id="5226711870492126219">🎡</tg-emoji>'),
            ("🐧", '<tg-emoji emoji-id="5361541227604878624">🐧</tg-emoji>'),
            ("🧃", '<tg-emoji emoji-id="5422884965593397853">🧃</tg-emoji>'),
            ("🦅", '<tg-emoji emoji-id="5427286516797831670">🦅</tg-emoji>'),
            ("💻", '<tg-emoji emoji-id="5469825590884310445">💻</tg-emoji>'),
            ("🍏", '<tg-emoji emoji-id="5372908412604525258">🍏</tg-emoji>'),
        ]:
            platform_emoji = platform_emoji.replace(emoji, icon)
        data = {
            "banner_url": self.config["banner_url"],
            "me": me,
            "version": _version,
            "build": build,
            "prefix": prefix,
            "platform": platform,
            "platform_emoji": platform_emoji,
            "upd": upd,
            "python_ver": lib_platform.python_version(),
            "uptime": utils.formatted_uptime(),
            "cpu_usage": utils.get_cpu_usage(),
            "ram_usage": f"{utils.get_ram_usage()} MB",
            "branch": version.branch,
            "hostname": lib_platform.node(),
            "user": getpass.getuser(),
            "os": self._get_os_name() or self.strings["non_detectable"],
            "kernel": lib_platform.release(),
            "ping": round((time.perf_counter_ns() - start) / 10**6, 3),
            "htl_ver": elystl.__version__,
            "git_status": utils.get_git_status(),
        }

        cpu_info = self._get_cpu_info()
        if cpu_info:
            data["cpu"] = cpu_info

        template = self.config["custom_message"] or self.strings[template_key]

        data = await utils.get_placeholders(
            data,
            template,
            client=self._client,
            on_ready_callback=on_ready_callback,
            lazy=async_enabled,
        )

        if async_enabled and on_ready_callback and upd == loading_ph:

            async def _bg_resolve_upd():
                try:
                    is_avail = await self.lookup("Updater").check_for_updates()
                    data["upd"] = (
                        self.strings["upd_avail"]
                        if is_avail
                        else self.strings["up_to_date"]
                    )
                except Exception:
                    data["upd"] = ""
                if inspect.iscoroutinefunction(on_ready_callback):
                    await on_ready_callback(data)
                else:
                    on_ready_callback(data)

            asyncio.create_task(_bg_resolve_upd())

        if self.config["custom_message"]:
            try:
                placeholders_msg = re.sub(
                    r"{(\w+)}",
                    lambda match: str(data.get(match.group(1), match.group(0))),
                    self.config["custom_message"],
                )
            except KeyError:
                logger.exception("Missing placeholder in custom_message")
                placeholders_msg = self.config["custom_message"]
            return placeholders_msg

        return self.strings[template_key].format(
            (
                utils.get_platform_emoji()
                if self._client.elys_me.premium and self.config.get("show_elys", True)
                else ""
            ),
            **data,
        )

    @loader.command()
    async def infocmd(self, message: Message):
        start = time.perf_counter_ns()
        target_message = None
        media = str(self.config["banner_url"]) if self.config["banner_url"] else None

        if self.config["banner_url"] and self.config["quote_media"] is True:
            media = InputMediaWebPage(str(self.config["banner_url"]), optional=True)

        async def _on_placeholders_ready(updated_data):
            for _ in range(60):
                if target_message is not None:
                    break
                await asyncio.sleep(0.05)

            if target_message:
                try:
                    if self.config["custom_message"]:
                        updated_text = re.sub(
                            r"{(\w+)}",
                            lambda match: str(
                                updated_data.get(match.group(1), match.group(0))
                            ),
                            self.config["custom_message"],
                        )
                    else:
                        template_key = (
                            "rich_info_message"
                            if self.config["rich_mode"]
                            else "info_message"
                        )
                        updated_text = self.strings[template_key].format(
                            (
                                utils.get_platform_emoji()
                                if self._client.elys_me.premium
                                and self.config.get("show_elys", True)
                                else ""
                            ),
                            **updated_data,
                        )

                    with contextlib.suppress(Exception):
                        if self.config["rich_mode"]:
                            await utils.answer(
                                target_message, rich_message=updated_text
                            )
                        else:
                            await utils.answer(
                                target_message,
                                updated_text,
                                file=media,
                                invert_media=self.config["invert_media"],
                            )
                except Exception as e:
                    logger.debug("Failed to update placeholders: %s", e)

        if self.config["rich_mode"]:
            target_message = await utils.answer(
                message,
                rich_message=await self._render_info(
                    start,
                    template_key="rich_info_message",
                    on_ready_callback=_on_placeholders_ready,
                ),
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
            return

        try:
            match True:
                case _ if self.config["custom_message"] is None:
                    target_message = await utils.answer(
                        message,
                        await self._render_info(
                            start,
                            on_ready_callback=_on_placeholders_ready,
                        ),
                        file=media,
                        reply_to=getattr(message, "reply_to_msg_id", None),
                        invert_media=self.config["invert_media"],
                    )
                case _:
                    if "{ping}" in self.config["custom_message"]:
                        message = await utils.answer(message, self.config["ping_emoji"])
                    target_message = await utils.answer(
                        message,
                        await self._render_info(
                            start,
                            on_ready_callback=_on_placeholders_ready,
                        ),
                        file=media,
                        reply_to=getattr(message, "reply_to_msg_id", None),
                        invert_media=self.config["invert_media"],
                    )
        except WebpageMediaEmptyError:
            await utils.answer(
                message,
                self.strings["no_banner"].format(
                    link=self.config["banner_url"],
                ),
                reply_to=getattr(message, "reply_to_msg_id", None),
            )

    @loader.command()
    async def ubinfo(self, message: Message):
        await utils.answer(message, self.strings["desc"])
