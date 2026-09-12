# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import contextlib
import getpass
import inspect
import logging
import os
import platform as lib_platform
import re
import sys
import time
import typing

import elystl
from elystl.errors import WebpageMediaEmptyError
from elystl.tl.types import Message
from elystl.types import InputMediaWebPage
from elystl.utils import get_display_name

from .. import loader, utils, version

logger = logging.getLogger(__name__)


@loader.tds
class ElysInfoMod(loader.Module):
    """Show userbot info"""

    strings = {"name": "ElysInfo"}  # noqa: RUF012

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
                True,
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
            logical = os.cpu_count() or 1
            physical = logical
            try:
                with open("/proc/cpuinfo") as f:
                    cores = set()
                    phys_id = 0
                    core_id = 0
                    for line in f:
                        if line.startswith("physical id"):
                            phys_id = int(line.split(":")[1])
                        elif line.startswith("core id"):
                            core_id = int(line.split(":")[1])
                            cores.add((phys_id, core_id))
                    if cores:
                        physical = len(cores)
            except Exception:
                pass
            return f"{physical} ({logical}) core(-s); {utils.get_cpu_usage()}% total"
        except PermissionError:
            return None
        except Exception:
            logger.exception("Unsupported placeholder")
            return None

    def _get_os_name(self):
        # 1. Standard Linux / Termux os-release
        paths = ["/etc/os-release"]
        if "PREFIX" in os.environ:
            paths.append(os.path.join(os.environ["PREFIX"], "etc", "os-release"))

        for path in paths:
            try:
                with open(path) as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME"):
                            return line.split("=")[1].strip().strip('"')
            except FileNotFoundError:
                pass

        # 2. Android / Termux version detection via getprop
        if sys.platform == "android" or "TERMUX_VERSION" in os.environ:
            try:
                import subprocess

                rel = subprocess.check_output(
                    ["getprop", "ro.build.version.release"], text=True, timeout=1
                ).strip()
                if rel:
                    return f"Android {rel}"
            except Exception:
                pass
            return "Android"

        # 3. macOS
        if sys.platform == "darwin":
            mac_ver = lib_platform.mac_ver()[0]
            return f"macOS {mac_ver}" if mac_ver else "macOS"

        # 4. Windows
        if sys.platform == "win32":
            return f"Windows {lib_platform.release()}"

        # 5. Generic fallback
        if lib_platform.system():
            return f"{lib_platform.system()} {lib_platform.release()}"

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
            except Exception:  # noqa: BLE001
                upd = ""

        me = (
            f'<b><a href="tg://user?id={self._client.elys_me.id}">{utils.escape_html(get_display_name(self._client.elys_me))}</a></b>'
            .replace("{", "")
            .replace("}", "")
        )
        build = utils.get_commit_url()
        _version = f'<i>{".".join(list(map(str, list(version.__version__))))}</i>'
        prefix = f"«<code>{utils.escape_html(self.get_prefix())}</code>»"

        platform = utils.get_named_platform()
        platform_emoji = utils.get_named_platform_emoji()

        for emoji, token in [
            ("🍊", "{e:orange_heart_info}"),
            ("🍇", "{e:purple_heart_info}"),
            ("😶🌫️", "{e:cloud_face_info}"),
            ("❓", "{e:phone_info}"),
            ("🍀", "{e:clover_info}"),
            ("🦾", "{e:arm_info}"),
            ("🚂", "{e:train_info}"),
            ("🐳", "{e:whale_info}"),
            ("🕶", "{e:phone_info}"),
            ("🐈⬛", "{e:cat_info}"),
            ("✌️", "{e:peace_info}"),
            ("💎", "{e:diamond}"),
            ("🛡", "{e:storm_info}"),
            ("🌼", "{e:heart_info}"),
            ("🎡", "{e:ferris_info}"),
            ("🐧", "{e:penguin_info}"),
            ("🧃", "{e:juice_info}"),
            ("🦅", "{e:eagle_info}"),
            ("💻", "{e:laptop_info}"),
            ("🍏", "{e:apple_info}"),
        ]:
            from .. import emojis

            platform_emoji = platform_emoji.replace(emoji, emojis.render_emojis(token))
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
                except Exception:  # noqa: BLE001
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
                except Exception as e:  # noqa: BLE001
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
