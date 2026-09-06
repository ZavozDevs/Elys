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
import tempfile
import time
import typing

import elystl
import psutil
import requests
from elystl.errors import WebpageMediaEmptyError
from elystl.tl.types import Message
from elystl.types import InputMediaWebPage
from elystl.utils import get_display_name
from PIL import Image, ImageDraw, ImageFont

from .. import loader, utils, version

logger = logging.getLogger(__name__)

_CUSTOM_BANNER_CACHE: dict[str, str] = {}


def generate_custom_banner(nickname: str, template: str = "classic") -> str | None:
    text = nickname.strip().upper()
    if not text:
        return None
    cache_key = f"{template}:{text}"
    if cache_key in _CUSTOM_BANNER_CACHE:
        return _CUSTOM_BANNER_CACHE[cache_key]

    assets_dir = None
    try:
        from .. import utils

        base = utils.get_base_dir()
        assets_dir = os.path.join(os.path.dirname(base), "assets")
    except Exception:
        pass

    ethno_path = os.path.join(assets_dir, "ethnocentric.ttf") if assets_dir else None
    if not (ethno_path and os.path.exists(ethno_path)):
        ethno_path = None

    font_candidates = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/OpenSans-Bold.ttf",
        "/usr/share/fonts/TTF/FiraSans-Bold.ttf",
    ]
    fallback_font = next((f for f in font_candidates if os.path.exists(f)), None)

    is_latin = all(ord(c) < 128 for c in text)
    font_path = ethno_path if (is_latin and ethno_path) else fallback_font

    if template == "anime":
        base_path = os.path.join(assets_dir, "banner_anime.png") if assets_dir else None
        if not (base_path and os.path.exists(base_path)):
            return None
        center_x = 1803
        center_y = 395
        fill = (255, 255, 255)
        max_w = 700
        target_height = 80
        letter_spacing = 8
    elif template == "anime_white":
        base_path = os.path.join(assets_dir, "banner_anime_white.png") if assets_dir else None
        if not (base_path and os.path.exists(base_path)):
            return None
        center_x = 484
        center_y = 388
        fill = (255, 255, 255)
        max_w = 700
        target_height = 80
        letter_spacing = 8
    else:
        base_path = os.path.join(tempfile.gettempdir(), "elys_banner_base.png")
        if not os.path.exists(base_path):
            try:
                r = requests.get(
                    "https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/elys_info.png",
                    timeout=15,
                )
                if r.status_code == 200:
                    with open(base_path, "wb") as f:
                        f.write(r.content)
            except Exception:  # noqa: BLE001
                return None
        if not os.path.exists(base_path):
            return None
        center_x = 1577
        center_y = 593
        fill = (152, 152, 152)
        max_w = 850
        target_height = 80
        letter_spacing = 8

    try:
        im = Image.open(base_path).convert("RGB")
        draw = ImageDraw.Draw(im)

        if template == "classic":
            # Erase INFO below the line
            draw.rectangle([1220, 544, 1930, 648], fill=(6, 6, 6))

        font = (
            ImageFont.truetype(font_path, target_height)
            if font_path
            else ImageFont.load_default()
        )

        def get_text_width(txt, fnt, sp):
            total_w = 0
            for char in txt:
                bbox = fnt.getbbox(char)
                total_w += (bbox[2] - bbox[0]) + sp
            return total_w - sp if txt else 0

        w = get_text_width(text, font, letter_spacing)
        if w > max_w:
            scale = max_w / w
            target_height = max(30, int(target_height * scale))
            letter_spacing = max(2, int(letter_spacing * scale))
            font = (
                ImageFont.truetype(font_path, target_height)
                if font_path
                else ImageFont.load_default()
            )
            w = get_text_width(text, font, letter_spacing)

        cur_x = center_x - w / 2
        for char in text:
            bbox = font.getbbox(char)
            char_w = bbox[2] - bbox[0]
            char_h = bbox[3] - bbox[1]
            char_y = center_y - char_h / 2 - bbox[1]
            draw.text((cur_x, char_y), char, fill=fill, font=font)
            cur_x += char_w + letter_spacing

        temp_path = os.path.join(
            tempfile.gettempdir(), f"elys_banner_{template}_{abs(hash(text))}.png"
        )
        im.save(temp_path, "PNG", optimize=True)

        for attempt in range(3):
            try:
                with open(temp_path, "rb") as f:
                    resp = requests.post(
                        "https://freeimage.host/api/1/upload",
                        data={
                            "key": "6d207e02198a847aa98d0a2a901485a5",
                            "action": "upload",
                            "format": "json",
                        },
                        files={"source": f},
                        timeout=45,
                    )
                    data = resp.json()
                    if data.get("status_code") == 200:
                        url = data["image"]["url"]
                        _CUSTOM_BANNER_CACHE[cache_key] = url
                        return url
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)
    except Exception:
        logger.exception("Failed to generate custom banner for %s (%s)", nickname, template)
    return None


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
                validator=loader.validators.Choice(
                    [
                        "https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/elys_info.png",
                    ],
                    allow_custom=True,
                ),
            ),
            loader.ConfigValue(
                "banner_text",
                "",
                "Custom nickname on banner (empty for username)",
                validator=loader.validators.String(),
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

    async def client_ready(self):
        try:
            nick = (
                self.config["banner_text"]
                or (
                    self._client.elys_me.username
                    and self._client.elys_me.username.replace("@", "")
                )
                or get_display_name(self._client.elys_me)
                or "ELYS"
            )
            display_name = get_display_name(self._client.elys_me) or nick

            validator = self.config._config["banner_url"].validator
            possible_values = validator.validate.keywords["possible_values"]
            possible_values.clear()
            possible_values.append("https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/elys_info.png")

            async def _resolve_banner(
                text: str, cache_prefix: str, template: str = "classic"
            ) -> str | None:
                cached_name = self._db.get(
                    self.strings["name"], f"custom_banner_{cache_prefix}_name", None
                )
                cached_url = self._db.get(
                    self.strings["name"], f"custom_banner_{cache_prefix}_url", None
                )
                if cached_name == text and cached_url:
                    return cached_url
                url = await asyncio.to_thread(generate_custom_banner, text, template)
                if url:
                    self._db.set(
                        self.strings["name"], f"custom_banner_{cache_prefix}_name", text
                    )
                    self._db.set(
                        self.strings["name"], f"custom_banner_{cache_prefix}_url", url
                    )
                return url

            has_different_name = display_name.strip().upper() != nick.strip().upper()

            # Classic template banners
            url_nick = await _resolve_banner(nick, "classic_nick_v2", "classic")
            if url_nick and url_nick not in possible_values:
                possible_values.append(url_nick)

            if has_different_name:
                url_name = await _resolve_banner(display_name, "classic_name_v2", "classic")
                if url_name and url_name not in possible_values:
                    possible_values.append(url_name)

            # Anime template 1 (dark-haired girl on left)
            url_anime_nick = await _resolve_banner(nick, "anime_nick_v4", "anime")
            if url_anime_nick and url_anime_nick not in possible_values:
                possible_values.append(url_anime_nick)

            if has_different_name:
                url_anime_name = await _resolve_banner(display_name, "anime_name_v4", "anime")
                if url_anime_name and url_anime_name not in possible_values:
                    possible_values.append(url_anime_name)

            # Anime template 2 (white-haired girl on right)
            url_anime_white_nick = await _resolve_banner(
                nick, "anime_white_nick_v1", "anime_white"
            )
            if url_anime_white_nick and url_anime_white_nick not in possible_values:
                possible_values.append(url_anime_white_nick)

            if has_different_name:
                url_anime_white_name = await _resolve_banner(
                    display_name, "anime_white_name_v1", "anime_white"
                )
                if url_anime_white_name and url_anime_white_name not in possible_values:
                    possible_values.append(url_anime_white_name)

            if (
                self.config["banner_url"] not in possible_values
                and self.config["banner_url"] != "custom"
                and not (
                    self.config["banner_url"]
                    and str(self.config["banner_url"]).startswith("http")
                )
            ):
                self.config["banner_url"] = (
                    possible_values[1] if len(possible_values) > 1 else possible_values[0]
                )
        except Exception:
            logger.exception("Error in client_ready for ElysInfo")

    @loader.command()
    async def infocmd(self, message: Message):
        start = time.perf_counter_ns()
        target_message = None

        raw_banner = str(self.config["banner_url"]) if self.config["banner_url"] else None
        media_url = raw_banner if raw_banner and raw_banner.startswith("http") else None

        media = media_url
        if media_url and self.config["quote_media"] is True:
            media = InputMediaWebPage(media_url, optional=True)

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
