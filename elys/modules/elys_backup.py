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
import datetime
import io
import logging
import os
import re
import time
import zipfile
import orjson

from pathlib import Path

from elystl.tl.types import Message

from .. import loader, utils
from ..inline.types import BotInlineCall

logger = logging.getLogger(__name__)


@loader.tds
class ElysBackupMod(loader.Module):
    """Handles database and modules backups"""

    strings = {"name": "ElysBackup"}

    async def client_ready(self):
        if not self.get("period"):
            await self.inline.bot.send_photo(
                self.tg_id,
                photo="https://raw.githubusercontent.com/ZavozDevs/assets/main/elys_userbot/unit_alpha.png",
                caption=self.strings["period"],
                reply_markup=self.inline.generate_markup(
                    utils.chunks(
                        [
                            {
                                "text": f"🕰 {i} h",
                                "callback": self._set_backup_period,
                                "args": (i,),
                            }
                            for i in [1, 2, 4, 6, 8, 12, 24, 48, 168]
                        ],
                        3,
                    )
                    + [
                        [
                            {
                                "text": "🚫 Never",
                                "callback": self._set_backup_period,
                                "args": (0,),
                            }
                        ]
                    ]
                ),
            )

        self._content_channel_id = await utils.wait_for_content_channel(self._db)

    async def _set_backup_period(self, call: BotInlineCall, value: int):
        if not value:
            self.set("period", "disabled")
            await self.inline.bot(
                call.answer(
                    self.strings["never_bot"].format(prefix=self.get_prefix()),
                    show_alert=True,
                )
            )
            await call.delete()
            return

        self.set("period", value * 60 * 60)
        self.set("last_backup", round(time.time()))

        await self.inline.bot(
            call.answer(
                self.strings["saved_bot"].format(prefix=self.get_prefix()),
                show_alert=True,
            )
        )
        await call.delete()

    @loader.command()
    async def set_backup_period(self, message: Message):
        """[time] | set your backup bd period"""
        if (
            not (args := utils.get_args_raw(message))
            or not args.isdigit()
            or int(args) not in range(200)
        ):
            await utils.answer(message, self.strings["invalid_args"])
            return

        if not int(args):
            self.set("period", "disabled")
            await utils.answer(
                message,
                f"<b>{self.strings['never'].format(prefix=self.get_prefix())}</b>",
            )
            return

        period = int(args) * 60 * 60
        self.set("period", period)
        self.set("last_backup", round(time.time()))
        await utils.answer(
            message, f"<b>{self.strings['saved'].format(prefix=self.get_prefix())}</b>"
        )

    async def _get_backup_topic_id(self) -> int | None:
        """Find the Backups forum topic in database cache or search on Telegram"""
        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await utils.get_topic_id(self._db, "Backups")
        if backup_topic_id:
            return backup_topic_id

        # Try to find existing topic on Telegram without creating a new one
        try:
            from elystl.tl.functions.channels import GetForumTopicsRequest

            entity = await self._client.get_entity(self._content_channel_id)
            result = await self._client(
                GetForumTopicsRequest(
                    peer=entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )
            for found_topic in result.topics:
                if getattr(found_topic, "title", None) == "Backups":
                    forums_cache = self._db.pointer("elys.forums", "forums_cache", {})
                    channel_title = getattr(entity, "title", "elys-userbot")
                    forums_cache.setdefault(channel_title, {})[
                        "Backups"
                    ] = found_topic.id
                    forums_cache.setdefault("elys-userbot", {})[
                        "Backups"
                    ] = found_topic.id
                    self._db.save()
                    return found_topic.id
        except Exception as e:
            logger.debug(f"Could not find Backups topic on Telegram: {e}")

        return None

    def _apply_restored_db(self, raw_db_str: str) -> None:
        """Applies restored database data with migration and runtime config preservation"""
        if re.search(r'"(?:heroku|hikka|legacy|ftg)\.', raw_db_str):
            raw_db_str = re.sub(
                r'"(?:heroku|hikka|legacy|ftg)\.(\S+":)', r'"elys.\1', raw_db_str
            )

        db_data = self._db.migrate_data(orjson.loads(raw_db_str))

        if not self._db.process_db_autofix(db_data):
            raise RuntimeError("Attempted to restore broken database")

        # Preserve current runtime essentials so restoring an external/old DB
        # doesn't destroy the current active Telegram forums/topics and bot token
        current_forums = self._db.get("elys.forums")
        current_bot_token = self._db.get("elys.inline", "bot_token", None)

        self._db.clear()
        self._db.update(**db_data)

        if current_forums and isinstance(current_forums, dict):
            restored_forums = self._db.get("elys.forums")
            if not isinstance(restored_forums, dict) or not self._db.get(
                "elys.forums", "channel_id", None
            ):
                self._db.set("elys.forums", current_forums)
            else:
                cached = self._db.get("elys.forums", "forums_cache", {})
                current_cached = current_forums.get("forums_cache", {})
                if isinstance(cached, dict) and isinstance(current_cached, dict):
                    for k, v in current_cached.items():
                        if isinstance(v, dict):
                            cached.setdefault(k, {}).update(v)
                    self._db.set("elys.forums", "forums_cache", cached)

                if current_forums.get("channel_id"):
                    self._db.set(
                        "elys.forums", "channel_id", current_forums["channel_id"]
                    )
                if current_forums.get("forum_id"):
                    self._db.set("elys.forums", "forum_id", current_forums["forum_id"])

        if current_bot_token:
            inline_cfg = self._db.get("elys.inline", {})
            if isinstance(inline_cfg, dict) and not inline_cfg.get("bot_token"):
                self._db.set("elys.inline", "bot_token", current_bot_token)

        self._db.save()

    @loader.loop(interval=1, autostart=True)
    async def handler(self):
        try:
            if self.get("period") == "disabled":
                raise loader.StopLoop

            if not self.get("period"):
                await asyncio.sleep(3)
                return

            if not self.get("last_backup"):
                self.set("last_backup", round(time.time()))
                await asyncio.sleep(self.get("period"))
                return

            await asyncio.sleep(
                self.get("last_backup") + self.get("period") - time.time()
            )

            db = io.BytesIO(
                orjson.dumps(
                    self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS
                )
            )
            db.name = "db.json"

            mods = io.BytesIO()
            with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                    for file in files:
                        if file.endswith(f"{self.tg_id}.py"):
                            with open(os.path.join(root, file), "rb") as f:
                                zipf.writestr(file, f.read())
                zipf.writestr(
                    "db_mods.json",
                    orjson.dumps(
                        self.lookup("LoaderMod").get("loaded_modules", {}),
                        option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
                    ),
                )

            mods.seek(0)
            mods.name = "mods.zip"

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("db.json", db.getvalue())
                z.writestr("mods.zip", mods.getvalue())

            archive.name = f"backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.backup"

            backup_topic_id = await self._get_backup_topic_id()
            if not backup_topic_id:
                logger.error("Backups topic not found in database")
                return

            await self.inline.bot.send_document(
                int(f"-100{self._content_channel_id}"),
                archive,
                reply_markup=self.inline.generate_markup(
                    [
                        [
                            {
                                "text": "↪️ Restore this",
                                "data": "elys/backupall/restore/confirm",
                            }
                        ]
                    ]
                ),
                message_thread_id=backup_topic_id,
            )

            self.set("last_backup", round(time.time()))
        except loader.StopLoop:
            raise
        except Exception:
            logger.exception("ElysBackup failed")
            await asyncio.sleep(60)

    @loader.callback_handler()
    async def restore(self, call: BotInlineCall):
        valid_prefixes = (
            "elys/backupall/restore",
            "heroku/backupall/restore",
            "hikka/backupall/restore",
        )
        if not any(call.data.startswith(pfx) for pfx in valid_prefixes):
            return

        if call.data.endswith("/confirm"):
            await utils.answer(
                call,
                "❓ <b>Are you sure?</b>",
                reply_markup={
                    "text": "✅ Yes",
                    "data": "elys/backupall/restore",
                },
            )
            return

        try:
            if not getattr(self, "_content_channel_id", None):
                self._content_channel_id = await utils.wait_for_content_channel(
                    self._db
                )

            # Try to get message from content channel or from caller chat
            msg = None
            if self._content_channel_id:
                try:
                    msgs = await self._client.get_messages(
                        self._content_channel_id, ids=[call.message.message_id]
                    )
                    if msgs and msgs[0] and msgs[0].media:
                        msg = msgs[0]
                except Exception:
                    pass

            if not msg:
                msgs = await self._client.get_messages(
                    call.message.chat.id, ids=[call.message.message_id]
                )
                if msgs and msgs[0] and msgs[0].media:
                    msg = msgs[0]

            if not msg or not msg.media:
                raise RuntimeError("Backup message or media not found")

            file = await msg.download_media(bytes)

            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    self._apply_restored_db(f.read().decode())

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        if "db_mods.json" in modzip.namelist():
                            with modzip.open("db_mods.json", "r") as modules:
                                db_mods = orjson.loads(modules.read().decode())
                                if isinstance(db_mods, dict):
                                    self.lookup("LoaderMod").set(
                                        "loaded_modules", db_mods
                                    )

                        for name in modzip.namelist():
                            if name == "db_mods.json" or not Path(name).name.endswith(
                                ".py"
                            ):
                                continue

                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())

            await self.inline.bot(
                call.answer(self.strings["all_restored_bot"], show_alert=True)
            )
            await self.invoke("restart", "-f", peer=call.message.chat.id)
        except Exception:
            logger.exception("Restore from backupall failed")
            await self.inline.bot(
                call.answer(self.strings["reply_to_file"], show_alert=True)
            )

    def _convert(self, backup):
        fixed = re.sub(r'"(?:heroku|hikka|legacy|ftg)\.(\S+":)', r'"elys.\1', backup)
        # Migrate system modules
        mod_renames = {
            "HerokuInfo": "ElysInfo",
            "HerokuConfig": "ElysConfig",
            "HerokuSecurity": "ElysSecurity",
            "HerokuSettings": "ElysSettings",
            "HerokuBackup": "ElysBackup",
            "HerokuAccounts": "ElysAccounts",
            "HerokuWeb": "ElysAccounts",
            "HikkaInfo": "ElysInfo",
            "HikkaConfig": "ElysConfig",
            "HikkaSecurity": "ElysSecurity",
            "HikkaSettings": "ElysSettings",
            "HikkaBackup": "ElysBackup",
        }
        for old, new in mod_renames.items():
            fixed = fixed.replace(f'"{old}"', f'"{new}"')
        txt = io.BytesIO(fixed.encode())
        txt.name = f"db-converted-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"
        return txt

    @staticmethod
    def _message_id(message) -> int:
        return getattr(message, "message_id", getattr(message, "id"))

    async def convert(self, call: BotInlineCall, ans, file):
        match ans:
            case "y":
                await utils.answer(call, self.strings["converting_db"])
                backup = self._convert(file)
                await utils.answer_file(
                    call,
                    backup,
                    caption=self.strings["backup_caption"].format(
                        prefix=utils.escape_html(self.get_prefix())
                    ),
                )
            case _:
                await utils.answer(
                    call,
                    self.strings["advice_converting"],
                    reply_markup=[[{"text": "🔻 Close", "action": "close"}]],
                )

    @loader.command()
    async def backupdb(self, message: Message):
        txt = io.BytesIO(
            orjson.dumps(self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
        )
        txt.name = f"db-backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"

        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await self._get_backup_topic_id()
        if not backup_topic_id:
            logger.error("Backups topic not found in database")
            await utils.answer(message, self.strings["backup_sent"])
            return

        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            txt,
            caption=self.strings["backup_caption"].format(
                prefix=utils.escape_html(self.get_prefix())
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backup_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoredb(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(
                message,
                self.strings["reply_to_file"],
            )
            return

        file = await reply.download_media(bytes)
        try:
            raw_content = file.decode()
        except UnicodeDecodeError:
            await utils.answer(
                message, self.strings["probably_zip"].format(self.get_prefix())
            )
            return

        try:
            self._apply_restored_db(raw_content)
        except Exception:
            logger.exception("Restore db failed")
            await utils.answer(message, self.strings["reply_to_file"])
            return

        await utils.answer(message, self.strings["db_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupmods(self, message: Message):
        mods_quantity = len(self.lookup("LoaderMod").get("loaded_modules", {}))

        result = io.BytesIO()
        result.name = "mods.zip"

        db_mods = orjson.dumps(
            self.lookup("LoaderMod").get("loaded_modules", {}),
            option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
        )

        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
                            mods_quantity += 1

            zipf.writestr("db_mods.json", db_mods)

        archive = io.BytesIO(result.getvalue())
        archive.name = f"mods-{datetime.datetime.now():%d-%m-%Y-%H-%M}.zip"

        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await self._get_backup_topic_id()
        if not backup_topic_id:
            logger.warning("Backups topic not found in database")
            await utils.answer_file(
                message,
                archive,
                caption=self.strings["modules_backup"].format(
                    mods_quantity,
                    utils.escape_html(self.get_prefix()),
                ),
            )
            return

        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            archive,
            caption=self.strings["modules_backup"].format(
                mods_quantity,
                utils.escape_html(self.get_prefix()),
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backup_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoremods(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings["reply_to_file"])
            return

        file = await reply.download_media(bytes)
        try:
            decoded_text = orjson.loads(file.decode())
        except Exception:
            try:
                file = io.BytesIO(file)
                file.name = "mods.zip"

                with zipfile.ZipFile(file) as zf:
                    if "db_mods.json" in zf.namelist():
                        with zf.open("db_mods.json", "r") as modules:
                            db_mods = orjson.loads(modules.read().decode())
                            if isinstance(db_mods, dict) and all(
                                (
                                    isinstance(key, str)
                                    and isinstance(value, str)
                                    and utils.check_url(value)
                                )
                                for key, value in db_mods.items()
                            ):
                                self.lookup("LoaderMod").set("loaded_modules", db_mods)

                    for name in zf.namelist():
                        if name == "db_mods.json" or not Path(name).name.endswith(
                            ".py"
                        ):
                            continue

                        path = loader.LOADED_MODULES_PATH / Path(name).name
                        with zf.open(name, "r") as module:
                            path.write_bytes(module.read())
            except Exception:
                logger.exception("Unable to restore modules")
                await utils.answer(message, self.strings["reply_to_file"])
                return
        else:
            if not isinstance(decoded_text, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in decoded_text.items()
            ):
                raise RuntimeError("Invalid backup")

            self.lookup("LoaderMod").set("loaded_modules", decoded_text)

        await utils.answer(message, self.strings["mods_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupall(self, message: Message):
        db = io.BytesIO(
            orjson.dumps(self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
        )
        db.name = "db.json"

        mods = io.BytesIO()
        with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
            zipf.writestr(
                "db_mods.json",
                orjson.dumps(
                    self.lookup("LoaderMod").get("loaded_modules", {}),
                    option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
                ),
            )

        mods.seek(0)
        mods.name = "mods.zip"

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("db.json", db.getvalue())
            z.writestr("mods.zip", mods.getvalue())

        archive.name = f"elys-{datetime.datetime.now():%d-%m-%Y-%H-%M}.backup"

        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await self._get_backup_topic_id()
        if not backup_topic_id:
            logger.error("Backups topic not found in database")
            await utils.answer(
                message,
                "<b>Backups topic not found in database. Please run quickstart to create it.</b>",
            )
            return

        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            archive,
            caption=self.strings["backupall_info"].format(
                prefix=utils.escape_html(self.get_prefix()),
            ),
            reply_markup=self.inline.generate_markup(
                [
                    [
                        {
                            "text": "↪️ Restore this",
                            "data": "elys/backupall/restore/confirm",
                        },
                    ],
                ],
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backupall_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoreall(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings["reply_to_file"])
            return

        status_message = await utils.answer(message, self.strings["restoring_backup"])
        file = await reply.download_media(bytes)
        try:
            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    self._apply_restored_db(f.read().decode())

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        if "db_mods.json" in modzip.namelist():
                            with modzip.open("db_mods.json", "r") as modules:
                                db_mods = orjson.loads(modules.read().decode())
                                if isinstance(db_mods, dict):
                                    self.lookup("LoaderMod").set(
                                        "loaded_modules", db_mods
                                    )

                        for name in modzip.namelist():
                            if name == "db_mods.json" or not Path(name).name.endswith(
                                ".py"
                            ):
                                continue

                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())
        except Exception:
            logger.exception("Restore all failed")
            await utils.answer(status_message, self.strings["reply_to_file"])
            return

        await utils.answer(status_message, self.strings["all_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)
