# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""The single object that binds the MCUB layer to a running Elys instance.

Everything a :class:`~elys.mcub_compat.kernel.KernelProxy` needs comes from
here, so there is exactly one place that knows about Elys internals. It is a
lazily created singleton attached to the Elys ``Modules`` registry.

It also owns the two pieces of shared dispatch that cannot live on a single
module: the callback-token router and the ``inline_temp`` map.
"""

from __future__ import annotations

import logging
import os
import time
import typing

from .. import utils
from .buttons import entry_allows_user, invoke_by_signature, invoke_callback, registry
from .db import MCUBDatabase
from .inline import MCUBInlineManager
from ._vendor.cache import TTLCache
from ._vendor.permissions import CallbackPermissionManager
from ._vendor.strings import Strings

logger = logging.getLogger(__name__)

_host: "MCUBHost | None" = None


def get_host(modules=None) -> "MCUBHost":
    """Return the process-wide host, creating it on first use."""
    global _host
    if _host is None:
        if modules is None:
            raise RuntimeError("MCUB host requested before Elys modules were available")
        _host = MCUBHost(modules)
    elif modules is not None and _host.modules is not modules:
        # A fresh Elys `Modules` registry means a restart-in-place; rebind.
        _host.rebind(modules)
    return _host


def peek_host() -> "MCUBHost | None":
    return _host


class MCUBHost:
    """Elys-side services for MCUB modules."""

    def __init__(self, modules) -> None:
        self.modules = modules
        self.cache = TTLCache()
        self.permissions = CallbackPermissionManager()
        self.mcub_inline = MCUBInlineManager(self)
        self.live_configs: dict[str, typing.Any] = {}
        self.inline_temp_map: dict[str, dict] = {}
        self.callback_prefixes: list[tuple[str, bytes, typing.Callable]] = []
        self.start_time = time.time()
        self.adapters: dict[str, typing.Any] = {}
        self._kernel_config: dict[str, typing.Any] = {}

    def rebind(self, modules) -> None:
        self.modules = modules

    # -- core objects -----------------------------------------------------

    @property
    def client(self):
        return self.modules.client

    @property
    def db(self):
        return self.modules.db

    @property
    def inline_manager(self):
        return getattr(self.modules, "inline", None)

    @property
    def prefix(self) -> str:
        try:
            return self.modules.get_prefix()
        except Exception:
            return "."

    @property
    def language(self) -> str:
        from .. import translations

        raw = self.db.get(translations.__name__, "lang", False)
        if isinstance(raw, str) and raw.strip():
            return raw.split()[0]
        return "en"

    @property
    def kernel_config(self) -> dict:
        """MCUB's ``kernel.config``; the only key modules really read is ``language``."""
        self._kernel_config["language"] = self.language
        self._kernel_config.setdefault("piped", False)
        return self._kernel_config

    def database(self, module_name: str) -> MCUBDatabase:
        return MCUBDatabase(self.db, module_name)

    def global_strings(self) -> Strings:
        """Strings limited to MCUB's global groups (buttons/error/null/...)."""
        return Strings(self.language, {"name": "null"})

    # -- paths / metadata -------------------------------------------------

    @property
    def modules_dir(self) -> str:
        from .. import loader

        return str(getattr(loader, "MODULES_NAME", "modules"))

    @property
    def loaded_modules_dir(self) -> str:
        from .. import loader

        return str(getattr(loader, "LOADED_MODULES_DIR", "."))

    @property
    def assets_dir(self) -> str:
        return os.path.join(utils.get_base_dir(), "assets")

    @property
    def logs_dir(self) -> str:
        return utils.get_base_dir()

    @property
    def config_file(self) -> str:
        return os.path.join(utils.get_base_dir(), "config.json")

    @property
    def logs_chat_id(self):
        return None

    @property
    def version_manager(self):
        from . import scop

        return scop

    @property
    def scheduler(self):
        return None

    # -- identity ---------------------------------------------------------

    def is_admin(self, user_id) -> bool:
        if user_id is None:
            return False
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return False
        if user_id == getattr(self.client, "tg_id", None):
            return True
        try:
            return user_id in self.client.dispatcher.security._owner
        except Exception:
            return False

    def lookup_module(self, module_name: str):
        needle = str(module_name).lower()
        for name, adapter in self.adapters.items():
            instance = getattr(adapter, "mcub_instance", None)
            candidates = {
                name.lower(),
                str(getattr(instance, "name", "")).lower(),
                adapter.__class__.__name__.lower(),
            }
            if needle in candidates:
                return instance if instance is not None else adapter
        found = self.modules.lookup(module_name)
        return found or None

    def loaded_modules(self) -> dict:
        return {
            name: getattr(adapter, "mcub_module", adapter)
            for name, adapter in self.adapters.items()
        }

    def system_modules(self) -> dict:
        return {}

    # -- registration plumbing --------------------------------------------

    def register_adapter(self, name: str, adapter) -> None:
        self.adapters[name] = adapter

    def unregister_adapter(self, name: str) -> None:
        self.adapters.pop(name, None)
        registry.forget_module(name)
        self.callback_prefixes = [
            item for item in self.callback_prefixes if item[0] != name
        ]
        for key, entry in list(self.inline_temp_map.items()):
            if entry.get("module_name") == name:
                self.inline_temp_map.pop(key, None)

    def register_inline_handler(self, pattern: str, handler) -> None:
        for adapter in self.adapters.values():
            registrations = getattr(adapter, "registrations", None)
            if registrations is not None and handler in registrations.inline_handlers.values():
                break
        self.on_registration_change()

    def register_callback_prefix(self, module_name: str, prefix: bytes, handler) -> None:
        self.callback_prefixes.append((module_name, prefix, handler))

    def publish_inline_temp(self, key: str, entry: dict) -> None:
        self.inline_temp_map[key] = entry

    def revoke_inline_temp(self, key: str) -> None:
        self.inline_temp_map.pop(key, None)

    def on_registration_change(self) -> None:
        for adapter in list(self.adapters.values()):
            republish = getattr(adapter, "republish", None)
            if callable(republish):
                try:
                    republish()
                except Exception:
                    logger.exception("Failed to republish MCUB adapter handlers")
        try:
            self.modules._rebuild_handlers()
        except Exception:
            logger.exception("Failed to rebuild Elys handlers after MCUB change")

    # -- module config ----------------------------------------------------

    async def get_module_config(self, module_name: str, default=None):
        import json

        raw = self.database(module_name).elys_db.get(
            "mcub.__configs__", _config_key(module_name), None
        )
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default

    async def save_module_config(self, module_name: str, config_data) -> bool:
        import json

        try:
            payload = json.dumps(config_data, ensure_ascii=False)
        except (TypeError, ValueError) as error:
            logger.warning("Cannot serialise MCUB config for %s: %s", module_name, error)
            return False
        self.db.set("mcub.__configs__", _config_key(module_name), payload)
        return True

    # -- inline ACL -------------------------------------------------------

    def _acl(self) -> list:
        stored = self.db.get("mcub.__inline_acl__", "users", None)
        return list(stored) if isinstance(stored, list) else []

    async def inline_acl_is_allowed(self, user_id, command=None) -> bool:
        if self.is_admin(user_id):
            return True
        return int(user_id) in self._acl()

    async def inline_acl_set(self, user_id, command, allowed: bool) -> bool:
        users = self._acl()
        user_id = int(user_id)
        if allowed and user_id not in users:
            users.append(user_id)
        elif not allowed and user_id in users:
            users.remove(user_id)
        self.db.set("mcub.__inline_acl__", "users", users)
        return True

    async def inline_acl_list(self) -> list:
        return self._acl()

    async def inline_acl_clear(self) -> bool:
        self.db.set("mcub.__inline_acl__", "users", [])
        return True

    # -- actions ----------------------------------------------------------

    async def invoke_command(self, command, *, args=None, chat_id=None, reply_to=None, prefix=None):
        prefix = prefix or self.prefix
        text = f"{prefix}{command}"
        if args:
            text = f"{text} {args}"
        if chat_id is None:
            chat_id = getattr(self.client, "tg_id", "me")
        return await self.client.send_message(chat_id, text, reply_to=reply_to)

    async def process_command(self, event) -> bool:
        message = getattr(event, "raw_message", event)
        try:
            await self.modules.client.dispatcher.handle_command(message)
            return True
        except Exception:
            logger.exception("MCUB process_command failed")
            return False

    async def shutdown(self) -> None:
        raise SystemExit(0)

    async def restart(self) -> None:
        restart_mod = self.modules.lookup("updater")
        restarter = getattr(restart_mod, "restart_common", None)
        if callable(restarter):
            return await restarter(None)
        raise SystemExit(0)

    async def install_from_url(self, url, module_name=None):
        loader_mod = self.modules.lookup("LoaderMod")
        if loader_mod is None:
            return False, "Loader is unavailable"
        try:
            source = await utils.run_sync(utils.check_url, url)
            if not source:
                return False, "Invalid url"
        except Exception:
            pass
        return False, "install_from_url is not supported from MCUB modules on Elys"

    # -- shared dispatch --------------------------------------------------

    async def dispatch_callback(self, call) -> bool:
        """Route a callback query to an MCUB token or prefix handler.

        Returns ``True`` when the callback belonged to an MCUB module. Elys
        invokes every registered callback handler, so anything not ours must
        fall through silently.
        """
        from .events import MCUBCallbackEvent

        raw = getattr(call, "data", b"")
        token = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        payload = token.encode("utf-8", errors="replace")
        sender_id = getattr(call, "sender_id", None)

        entry = registry.get(token)
        if entry is not None:
            if not self._callback_allowed(entry, token, sender_id):
                await _deny(call, self.global_strings())
                return True

            wrapped = MCUBCallbackEvent(call, kernel=self)
            try:
                await invoke_callback(entry, wrapped)
            except Exception:
                logger.exception(
                    "MCUB callback handler from %s failed", entry.get("module_name")
                )
                try:
                    await call.answer(
                        "Error occurred while processing request. More info in logs",
                        alert=True,
                    )
                except Exception:
                    pass
            return True

        for module_name, prefix, handler in list(self.callback_prefixes):
            if not payload.startswith(prefix):
                continue
            if not self.is_admin(sender_id) and not self.permissions.is_allowed(
                sender_id, token
            ):
                await _deny(call, self.global_strings())
                return True
            try:
                await handler(MCUBCallbackEvent(call, kernel=self))
            except Exception:
                logger.exception(
                    "MCUB prefix callback handler from %s failed", module_name
                )
            return True

        return False

    def _callback_allowed(self, entry: dict, token: str, sender_id) -> bool:
        if self.is_admin(sender_id):
            return True
        if entry_allows_user(entry, sender_id):
            return True
        return self.permissions.is_allowed(sender_id, token)

    async def dispatch_chosen_inline(self, update, query: str) -> bool:
        """Deliver ``@bot <uuid> <args>`` results to MCUB ``inline_temp`` handlers."""
        if not query:
            return False

        key = query.split()[0]
        entry = self.inline_temp_map.get(key)
        if entry is None:
            return False

        expires_at = entry.get("expires_at")
        if expires_at and expires_at < time.time():
            self.inline_temp_map.pop(key, None)
            return False

        user_id = getattr(update, "user_id", None)
        allow_user = entry.get("allow_user")
        if allow_user not in (None, "all"):
            permitted = (
                user_id == allow_user
                if isinstance(allow_user, int)
                else user_id in (allow_user or [])
            )
            if not permitted and not self.is_admin(user_id):
                return True
        elif allow_user is None and not self.is_admin(user_id):
            return True

        args = query.split(maxsplit=1)[1] if len(query.split()) > 1 else ""

        try:
            await invoke_by_signature(
                entry["handler"],
                _ChosenInlineEvent(update, self),
                args,
                entry.get("data"),
            )
        except Exception:
            logger.exception("MCUB inline_temp handler failed for %s", key)
        return True

    def inline_temp_article(self, key: str) -> dict | None:
        """Article payload shown while the user types an ``inline_temp`` query."""
        entry = self.inline_temp_map.get(key)
        if entry is None:
            return None
        return {
            "title": "MCUB",
            "description": "Send to continue",
            "message": f"<code>{utils.escape_html(key)}</code>",
        }

    def __repr__(self) -> str:
        return f"<MCUBHost adapters={len(self.adapters)}>"


class _ChosenInlineEvent:
    """Minimal event for ``inline_temp`` handlers, mirroring MCUB's shape."""

    def __init__(self, update, host: MCUBHost) -> None:
        self._update = update
        self._host = host
        self.id = getattr(update, "id", None)
        self.user_id = getattr(update, "user_id", None)
        self.sender_id = self.user_id
        self.query = update
        self.data = b""
        self.chat_id = None
        self.message_id = None
        self.inline_message_id = getattr(update, "msg_id", None)

    @property
    def client(self):
        return self._host.client

    async def answer(self, *args, **kwargs):
        return None

    async def edit(self, text=None, buttons=None, **kwargs):
        from .buttons import to_elys_markup
        from elystl.tl.functions.messages import EditInlineBotMessageRequest

        if self.inline_message_id is None:
            return None

        request_kwargs: dict = {"id": self.inline_message_id}
        if text is not None:
            request_kwargs["message"] = text
        if buttons is not None:
            markup = self._host.inline_manager.generate_markup(to_elys_markup(buttons))
            request_kwargs["reply_markup"] = markup
        return await self._host.client(EditInlineBotMessageRequest(**request_kwargs))

    async def delete(self):
        return None

    def __repr__(self) -> str:
        return f"<MCUBChosenInline user={self.user_id}>"


async def _deny(call, strings: Strings) -> None:
    try:
        message = strings("error").get("permission_denied") or "Permission denied"
    except Exception:
        message = "Permission denied"
    try:
        await call.answer(str(message), alert=True)
    except Exception:
        logger.debug("Failed to answer denied MCUB callback", exc_info=True)


def _config_key(module_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "_.-" else "_" for c in str(module_name))
    return safe[:64] or "unknown"
