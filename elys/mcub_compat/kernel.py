# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""``kernel`` and ``kernel.register`` as MCUB modules expect to see them.

Both module styles funnel through :class:`RegisterProxy`, which accumulates
handlers into a :class:`Registrations` sink. The adapter then republishes that
sink as attributes Elys's own introspection can discover.

Per project decision this is a lean translator, not a sandbox: the real Elys
client, database and inline manager are handed through without artificial
permission gates. MCUB's own ``ModuleKernelProxy`` blocks ~25 registry names
and ~42 client methods; we deliberately do not, because Elys already trusts
module code the same way it trusts its own.

One deliberate divergence from upstream: MCUB's ``Register`` attributes each
registration to its caller via ``inspect.stack()[1]``. That is unreliable under
our exec wrapping, so the proxy is bound to its owning module at construction.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import typing
import uuid
from types import MappingProxyType

from .. import utils
from ._vendor.colors import Colors
from ._vendor.permissions import CallbackPermissionManager

logger = logging.getLogger(__name__)

EVENT_TYPE_ALIASES = {
    "newmessage": "NewMessage",
    "message": "NewMessage",
    "messageedited": "MessageEdited",
    "edited": "MessageEdited",
    "messagedeleted": "MessageDeleted",
    "deleted": "MessageDeleted",
    "messageread": "MessageRead",
    "read": "MessageRead",
    "userupdate": "UserUpdate",
    "user": "UserUpdate",
    "chataction": "ChatAction",
    "action": "ChatAction",
    "joinrequest": "JoinRequest",
    "request": "JoinRequest",
    "album": "Album",
    "inlinequery": "InlineQuery",
    "inline": "InlineQuery",
    "callbackquery": "CallbackQuery",
    "callback": "CallbackQuery",
    "raw": "Raw",
    "custom": "Raw",
}

BOT_ONLY_EVENTS = frozenset({"inlinequery", "inline", "callbackquery", "callback"})

IMPORT_TO_PIP = {
    "PIL": "Pillow",
    "Image": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "google.generativeai": "google-generativeai",
    "speech_recognition": "SpeechRecognition",
    "dateutil": "python-dateutil",
    "Crypto": "pycryptodome",
    "usb": "pyusb",
    "gi": "PyGObject",
    "wx": "wxPython",
    "pkg_resources": "setuptools",
    "elystl": "Heroku-TL-New",
    "markdown_it": "markdown-it-py",
}


class ModuleLoggerAdapter(logging.LoggerAdapter):
    """``[ModuleName] message`` prefixing, matching MCUB's log format."""

    def process(self, msg, kwargs):
        module_name = self.extra.get("module_name", "Unnamed")
        return f"[{module_name}] {msg}", kwargs


class InfiniteLoop:
    """MCUB's managed background loop.

    Elys has its own ``InfiniteLoop`` but calls the target as
    ``func(module_instance, *args)`` whereas MCUB calls ``func(kernel)``. Rather
    than reconcile the two calling conventions we keep MCUB's class and let the
    adapter own start/stop, so Elys's loop scanner never sees these objects.
    """

    def __init__(self, func, interval, autostart, wait_before) -> None:
        self.func = func
        self.interval = interval
        self.autostart = autostart
        self._wait_before = wait_before
        self._task: asyncio.Task | None = None
        self._kernel = None
        self.status: bool = False
        self.last_run: float | None = None
        self.last_error: Exception | None = None
        self.fail_count: int = 0

    @property
    def is_running(self) -> bool:
        return bool(self._task and not self._task.done() and self.status)

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.ensure_future(self._run())

    def restart(self) -> None:
        self.stop()
        self.start()

    def stop(self) -> None:
        self.status = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        self.status = True
        try:
            while self.status:
                if self._wait_before:
                    await asyncio.sleep(self.interval)
                if not self.status:
                    break
                try:
                    self.last_run = time.time()
                    await self.func(self._kernel)
                    self.last_error = None
                    self.fail_count = 0
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    self.last_error = exc
                    self.fail_count += 1
                    logger.error(
                        "MCUB loop %s failed: %s", getattr(self.func, "__name__", "?"), exc
                    )
                if not self._wait_before:
                    await asyncio.sleep(self.interval)
        finally:
            self.status = False

    def __repr__(self) -> str:
        return (
            f"<InfiniteLoop func={getattr(self.func, '__name__', '?')!r} "
            f"interval={self.interval} running={self.status}>"
        )


def _collect_docs(kwargs: dict) -> dict:
    """Gather ``doc={...}`` plus arbitrary ``doc_<locale>`` keyword docs."""
    docs: dict[str, str] = {}

    doc = kwargs.get("doc")
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(key, str) and isinstance(value, str) and value.strip():
                docs[key.strip().lower()] = value.strip()

    for key, value in kwargs.items():
        if not isinstance(key, str) or not key.startswith("doc_"):
            continue
        locale = key[4:].strip().lower()
        if locale and isinstance(value, str) and value.strip():
            docs[locale] = value.strip()

    return docs


class Registrations:
    """Everything a single MCUB module asked to register."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.commands: dict[str, dict] = {}
        self.bot_commands: dict[str, dict] = {}
        self.aliases: dict[str, str] = {}
        self.watchers: list[dict] = []
        self.events: list[dict] = []
        self.loops: list[InfiniteLoop] = []
        self.inline_handlers: dict[str, typing.Callable] = {}
        self.callback_prefixes: list[tuple[bytes, typing.Callable]] = []
        self.inline_temp: dict[str, dict] = {}
        self.methods: list[typing.Callable] = []
        self.on_load: typing.Callable | None = None
        self.on_install: typing.Callable | None = None
        self.uninstall: typing.Callable | None = None
        self.disabled_watchers: set[str] = set()

    def summary(self) -> dict:
        return {
            "commands": len(self.commands),
            "bot_commands": len(self.bot_commands),
            "watchers": len(self.watchers),
            "events": len(self.events),
            "loops": len(self.loops),
            "inline_handlers": len(self.inline_handlers),
            "inline_temp": len(self.inline_temp),
        }


class RegisterProxy:
    """``kernel.register`` for MCUB modules."""

    MAX_LOOPS_PER_MODULE = 5

    def __init__(self, kernel: "KernelProxy", registrations: Registrations) -> None:
        self.kernel = kernel
        self._reg = registrations

    # -- decorators -------------------------------------------------------

    def method(self, func=None):
        def decorator(f):
            self._reg.methods.append(f)
            return f

        return decorator if func is None else decorator(func)

    def command(self, pattern: str, **kwargs):
        def decorator(func):
            cmd = self._normalize_command(pattern)
            if not cmd:
                return func

            docs = _collect_docs(kwargs)
            if not docs:
                raw_doc = (getattr(func, "__doc__", None) or "").strip()
                if raw_doc:
                    first = raw_doc.splitlines()[0].strip()
                    if first:
                        docs = {"ru": first, "en": first}

            aliases = kwargs.get("alias") or []
            if isinstance(aliases, str):
                aliases = [aliases]

            self._reg.commands[cmd] = {
                "handler": func,
                "docs": docs,
                "aliases": list(aliases),
                "meta": kwargs.get("more"),
            }
            for alias in aliases:
                self._reg.aliases[str(alias)] = cmd
            return func

        return decorator

    def bot_command(self, pattern: str, **kwargs):
        def decorator(func):
            cmd = str(pattern).lstrip("/").split()[0] if pattern else ""
            if not cmd:
                return func
            self._reg.bot_commands[cmd] = {
                "handler": func,
                "docs": _collect_docs(kwargs),
                "pattern": pattern,
            }
            return func

        return decorator

    def watcher(self, func=None, bot_client: bool = False, module=None, **tags):
        def decorator(f):
            name = getattr(f, "__name__", f"watcher_{len(self._reg.watchers)}")
            self._reg.watchers.append(
                {
                    "handler": f,
                    "name": name,
                    "tags": dict(tags),
                    "bot_client": bot_client,
                }
            )
            return f

        return decorator if func is None or not callable(func) else decorator(func)

    def loop(
        self,
        interval: int = 60,
        autostart: bool = True,
        wait_before: bool = False,
        module=None,
    ):
        def decorator(f):
            bound_instance = getattr(f, "__bound_instance__", None)
            raw_func = getattr(f, "__original__", f)

            async def loop_caller(kernel):
                if bound_instance is not None:
                    return await raw_func(bound_instance)
                return await raw_func(kernel)

            loop_caller.__name__ = getattr(raw_func, "__name__", "loop")
            instance = InfiniteLoop(loop_caller, interval, autostart, wait_before)
            instance._kernel = self.kernel

            if len(self._reg.loops) >= self.MAX_LOOPS_PER_MODULE:
                logger.warning(
                    "MCUB module %s exceeded %d loops, skipping %s",
                    self._reg.module_name,
                    self.MAX_LOOPS_PER_MODULE,
                    loop_caller.__name__,
                )
                return instance

            self._reg.loops.append(instance)
            return instance

        return decorator

    def event(
        self, event_type: str, *args, bot_client: bool = False, module=None, **kwargs
    ):
        key = str(event_type).lower()
        if key not in EVENT_TYPE_ALIASES:
            raise ValueError(
                f"Unknown event type: '{event_type}'. "
                f"Valid: {', '.join(sorted(EVENT_TYPE_ALIASES))}"
            )
        if key in BOT_ONLY_EVENTS and not ("pattern" in kwargs or "data" in kwargs):
            raise ValueError(
                f"Refusing to register '{event_type}' without a pattern/data filter"
                " - it would fire on every incoming update."
            )

        def decorator(handler):
            self._reg.events.append(
                {
                    "handler": handler,
                    "event_type": key,
                    "args": args,
                    "kwargs": kwargs,
                    "bot_client": bot_client,
                }
            )
            return handler

        return decorator

    def on_load(self, func=None):
        def decorator(f):
            self._reg.on_load = f
            return f

        return decorator if func is None else decorator(func)

    def on_install(self, func=None):
        def decorator(f):
            self._reg.on_install = f
            return f

        return decorator if func is None else decorator(func)

    def uninstall(self, func=None):
        def decorator(f):
            self._reg.uninstall = f
            return f

        return decorator if func is None else decorator(func)

    def owner(self, func=None, only_admin: bool = False):
        """Restrict a handler to the account owner."""

        def decorator(f):
            async def wrapper(event):
                sender_id = getattr(event, "sender_id", None)
                if sender_id is None:
                    return None
                if not self.kernel.is_admin(sender_id):
                    return None
                if not only_admin:
                    no_owner = getattr(event, "no_owner", None)
                    if callable(no_owner) and no_owner():
                        return None
                return await f(event)

            wrapper.__name__ = f"owner:{getattr(f, '__name__', 'handler')}"
            wrapper.__original__ = f
            return wrapper

        return decorator if func is None or not callable(func) else decorator(func)

    # -- non-decorator API ------------------------------------------------

    def inline_temp(
        self,
        func,
        ttl: int = 300,
        article=None,
        data=None,
        allow_user=None,
        allow_ttl: int = 100,
    ) -> str:
        temp_uuid = uuid.uuid4().hex[:8]
        self._reg.inline_temp[temp_uuid] = {
            "handler": func,
            "article": article,
            "data": data,
            "expires_at": time.time() + ttl if ttl else None,
            "module_name": self._reg.module_name,
            "allow_user": allow_user,
            "allow_ttl": allow_ttl,
        }
        self.kernel._publish_inline_temp(temp_uuid, self._reg.inline_temp[temp_uuid])
        return temp_uuid

    def cleanup_inline_temp(self, force: bool = False) -> int:
        now = time.time()
        removed = 0
        for key, entry in list(self._reg.inline_temp.items()):
            expires = entry.get("expires_at")
            if force or (expires and expires < now):
                self._reg.inline_temp.pop(key, None)
                self.kernel._revoke_inline_temp(key)
                removed += 1
        return removed

    def get_registered_methods(self) -> dict:
        return {getattr(f, "__name__", str(i)): f for i, f in enumerate(self._reg.methods)}

    def get_commands(self) -> dict:
        return {name: meta["handler"] for name, meta in self._reg.commands.items()}

    def get_command(self, command: str) -> dict:
        meta = self._reg.commands.get(command) or {}
        return {
            "handler": meta.get("handler"),
            "owner": self._reg.module_name,
            "docs": meta.get("docs", {}),
        }

    def get_bot_commands(self) -> dict:
        return {
            name: (meta["pattern"], meta["handler"])
            for name, meta in self._reg.bot_commands.items()
        }

    def get_watchers(self) -> list[dict]:
        return [
            {
                "module": self._reg.module_name,
                "method": w["name"],
                "enabled": w["name"] not in self._reg.disabled_watchers,
                "tags": dict(w["tags"]),
                "bot_client": w["bot_client"],
                "wrapper": w["handler"],
            }
            for w in self._reg.watchers
        ]

    def get_events(self) -> list:
        return [(e["handler"], e["event_type"], e["kwargs"]) for e in self._reg.events]

    def get_loops(self) -> list[InfiniteLoop]:
        return list(self._reg.loops)

    def get_all_aliases(self) -> dict:
        return dict(self._reg.aliases)

    def get_command_alias(self, command: str) -> str | None:
        for alias, cmd in self._reg.aliases.items():
            if cmd == command:
                return alias
        return None

    def get_use_bot(self) -> dict:
        inline = self.kernel._inline_manager
        available = inline is not None and getattr(inline, "init_complete", False)
        return {
            "available": available,
            "connected": available,
            "username": getattr(inline, "bot_username", None) if available else None,
        }

    def unregister_command(self, cmd: str) -> bool:
        if cmd in self._reg.commands:
            del self._reg.commands[cmd]
            for alias, target in list(self._reg.aliases.items()):
                if target == cmd:
                    del self._reg.aliases[alias]
            self.kernel._on_registration_change()
            return True
        return False

    def unregister_bot_command(self, cmd: str) -> bool:
        if cmd in self._reg.bot_commands:
            del self._reg.bot_commands[cmd]
            return True
        return False

    def disable_watcher(self, module_name: str, watcher_name: str) -> bool:
        for watcher in self._reg.watchers:
            if watcher["name"] == watcher_name:
                self._reg.disabled_watchers.add(watcher_name)
                return True
        return False

    def enable_watcher(self, module_name: str, watcher_name: str) -> bool:
        self._reg.disabled_watchers.discard(watcher_name)
        return True

    async def invoke(
        self,
        command: str,
        args: str | None = None,
        chat_id: int | None = None,
        reply_to: int | None = None,
        *,
        prefix: str | None = None,
        original_event=None,
    ):
        return await self.kernel._invoke_command(
            command, args=args, chat_id=chat_id, reply_to=reply_to, prefix=prefix
        )

    def message_proxy(self, msg, original_event=None):
        from .events import MCUBEvent

        return MCUBEvent(msg, self._reg.module_name, self.kernel)

    # -- helpers ----------------------------------------------------------

    def _normalize_command(self, pattern: str) -> str:
        prefix = re.escape(self.kernel.custom_prefix)
        cmd = re.sub(rf"^(\^|\\)?{prefix}", "", str(pattern))
        if cmd.endswith("$"):
            cmd = cmd[:-1]
        return cmd.strip().lower()

    def __repr__(self) -> str:
        return f"<RegisterProxy module={self._reg.module_name!r}>"


class KernelProxy:
    """``kernel`` for MCUB modules, backed by Elys primitives."""

    def __init__(self, module_name: str, registrations: Registrations, host) -> None:
        self.module_name = module_name
        self._reg = registrations
        self._host = host
        self.logger = ModuleLoggerAdapter(
            logging.getLogger(f"mcub.{module_name}"), {"module_name": module_name}
        )
        self.register = RegisterProxy(self, registrations)
        self.callback_permissions = host.permissions
        self.cache = host.cache
        self.Colors = Colors
        self.current_loading_module = module_name
        self.current_loading_module_type = "mcub"

    # -- clients / core objects -------------------------------------------

    @property
    def client(self):
        return self._host.client

    @property
    def bot_client(self):
        """The bot's Telethon client.

        MCUB modules call ``kernel.bot_client.on(...)`` and
        ``.add_event_handler(...)``, which Elys's ``TelethonBot`` wrapper
        (``inline.bot``) does not provide -- it is a thin Bot-API-shaped
        facade. The underlying client lives on ``inline._bot_client``.
        """
        inline = self._inline_manager
        if inline is None:
            return None
        return getattr(inline, "_bot_client", None) or getattr(inline, "bot", None)

    @property
    def inline_bot(self):
        return self.bot_client

    @property
    def _inline_manager(self):
        return self._host.inline_manager

    @property
    def inline(self):
        return BoundInline(self._host.mcub_inline, self)

    @property
    def inline_manager(self):
        return self.inline

    @property
    def subinline(self):
        return self.inline

    @property
    def db_manager(self):
        return self._host.database(self.module_name)

    @property
    def db(self):
        return self.db_manager

    @property
    def strings(self):
        return getattr(self._host, "strings", self._host.global_strings())

    @property
    def langpack(self):
        return getattr(self._host, "langpack", self._host.language)

    @property
    def security(self):
        sec = getattr(self._host, "security", None)
        if sec is not None:
            return sec
        modules = getattr(self._host, "modules", None)
        dispatcher = getattr(modules, "dispatcher", None)
        return getattr(dispatcher, "security", None)

    @property
    def security_chats(self):
        return self.security

    @property
    def chat_security(self):
        return self.security

    @property
    def loader(self):
        return self._host.modules

    async def send_message(self, entity, *args, **kwargs):
        return await self.client.send_message(entity, *args, **kwargs)

    async def edit_message(self, entity, message, *args, **kwargs):
        return await self.client.edit_message(entity, message, *args, **kwargs)

    @property
    def config(self):
        return self._host.kernel_config

    @property
    def scheduler(self):
        return self._host.scheduler

    @property
    def version_manager(self):
        return self._host.version_manager

    def resolve_pip_name(self, import_name: str) -> str:
        """Resolve an import name to its corresponding PyPI package name."""
        if not import_name:
            return import_name
        if import_name in IMPORT_TO_PIP:
            return IMPORT_TO_PIP[import_name]
        for k, v in IMPORT_TO_PIP.items():
            if k.lower() == import_name.lower():
                return v
        return import_name

    # -- identity ---------------------------------------------------------

    @property
    def VERSION(self) -> str:
        from ._vendor import MCUB_VERSION

        return MCUB_VERSION

    @property
    def CORE_NAME(self) -> str:
        return "Elys"

    @property
    def start_time(self):
        return self._host.start_time

    @property
    def ADMIN_ID(self):
        return getattr(self._host.client, "tg_id", None)

    @property
    def custom_prefix(self) -> str:
        return self._host.prefix

    @property
    def owner_prefixes(self) -> dict:
        return {}

    @property
    def MODULES_DIR(self) -> str:
        return self._host.modules_dir

    @property
    def MODULES_LOADED_DIR(self) -> str:
        return self._host.loaded_modules_dir

    @property
    def IMG_DIR(self) -> str:
        return self._host.assets_dir

    @property
    def LOGS_DIR(self) -> str:
        return self._host.logs_dir

    @property
    def CONFIG_FILE(self) -> str:
        return self._host.config_file

    @property
    def log_chat_id(self):
        return self._host.logs_chat_id

    @property
    def shutdown_flag(self) -> bool:
        return False

    @property
    def power_save_mode(self) -> bool:
        return False

    # -- registries (read-only views over what this module registered) ----

    @property
    def command_handlers(self) -> dict:
        return self.register.get_commands()

    @property
    def command_owners(self) -> dict:
        return dict.fromkeys(self._reg.commands, self.module_name)

    @property
    def command_docs(self) -> dict:
        return {name: meta.get("docs", {}) for name, meta in self._reg.commands.items()}

    @property
    def bot_command_handlers(self) -> dict:
        return self.register.get_bot_commands()

    @property
    def bot_command_owners(self) -> dict:
        return dict.fromkeys(self._reg.bot_commands, self.module_name)

    @property
    def bot_command_docs(self) -> dict:
        return {
            name: meta.get("docs", {}) for name, meta in self._reg.bot_commands.items()
        }

    @property
    def aliases(self) -> dict:
        return dict(self._reg.aliases)

    @property
    def inline_handlers(self) -> dict:
        return dict(self._reg.inline_handlers)

    @property
    def inline_handlers_owners(self) -> dict:
        return dict.fromkeys(self._reg.inline_handlers, self.module_name)

    @property
    def loaded_modules(self) -> dict:
        return self._host.loaded_modules()

    @property
    def system_modules(self) -> dict:
        return self._host.system_modules()

    @property
    def loaded_module_names(self) -> tuple:
        return tuple(self._host.loaded_modules())

    def iter_loaded_module_names(self) -> tuple:
        return self.loaded_module_names

    @property
    def _live_module_configs(self) -> dict:
        return self._host.live_configs

    @property
    def _inline_temp_map(self) -> dict:
        return self._host.inline_temp_map

    @property
    def inline_callback_map(self) -> dict:
        from .buttons import registry

        return registry._entries

    @property
    def error_load_modules(self) -> int:
        return 0

    # -- database ---------------------------------------------------------

    async def db_get(self, module: str, key: str):
        return await self.db_manager.db_get(module, key)

    async def db_set(self, module: str, key: str, value) -> None:
        await self.db_manager.db_set(module, key, value)

    async def db_delete(self, module: str, key: str) -> None:
        await self.db_manager.db_delete(module, key)

    async def get_module_config(self, module_name: str, default=None):
        return await self._host.get_module_config(module_name, default)

    async def save_module_config(self, module_name: str, config_data) -> bool:
        return await self._host.save_module_config(module_name, config_data)

    async def delete_module_config(self, module_name: str) -> bool:
        self._host.live_configs.pop(module_name, None)
        return await self._host.save_module_config(module_name, {})

    async def get_module_config_key(self, module_name: str, key: str, default=None):
        stored = await self.get_module_config(module_name) or {}
        return stored.get(key, default) if isinstance(stored, dict) else default

    async def set_module_config_key(self, module_name: str, key: str, value) -> bool:
        stored = await self.get_module_config(module_name) or {}
        if not isinstance(stored, dict):
            stored = {}
        stored[key] = value
        return await self.save_module_config(module_name, stored)

    async def delete_module_config_key(self, module_name: str, key: str) -> bool:
        stored = await self.get_module_config(module_name) or {}
        if isinstance(stored, dict):
            stored.pop(key, None)
        return await self.save_module_config(module_name, stored)

    def store_module_config_schema(self, module_name: str, config) -> None:
        """Register a live ``ModuleConfig`` so UIs can render it.

        Upstream stores it in ``_live_module_configs`` and nothing more, so this
        is the same operation as :meth:`set_live_module_config`. Real MCUB
        modules call it straight from ``on_load``, so a missing method aborts
        loading -- it is not optional in practice.
        """
        self._host.live_configs[module_name] = config

    def set_live_module_config(self, module_name: str, config) -> None:
        self._host.live_configs[module_name] = config

    def get_live_module_config(self, module_name: str, default=None):
        return self._host.live_configs.get(module_name, default)

    def save_config(self) -> bool:
        """Persist kernel config.

        Elys derives ``kernel.config`` from its own database rather than a
        config.json, and module-scoped writes already live in the override dict,
        so there is nothing to flush.
        """
        self.logger.debug("kernel.save_config() is a no-op on Elys")
        return True

    # -- inline helpers ---------------------------------------------------

    async def inline_form(self, chat_id, title, **kwargs):
        return await self._host.mcub_inline.inline_form(chat_id, title, **kwargs)

    async def rich_form(self, chat_id, rich_text=None, **kwargs):
        return await self._host.mcub_inline.rich_form(chat_id, rich_text, **kwargs)

    async def inline_query_and_click(self, chat_id, query, **kwargs):
        return await self._host.mcub_inline.inline_query_and_click(
            chat_id, query, **kwargs
        )

    def register_inline_handler(self, pattern: str, handler) -> None:
        self._reg.inline_handlers[str(pattern).lower()] = handler
        self._on_registration_change()

    def register_callback_handler(self, pattern, handler) -> None:
        if isinstance(pattern, str):
            pattern = pattern.encode()
        self._reg.callback_prefixes.append((pattern, handler))
        self._host.register_callback_prefix(self.module_name, pattern, handler)

    def unregister_module_inline_handlers(self, module_name: str) -> None:
        self._reg.inline_handlers.clear()
        self._on_registration_change()

    def get_module_inline_commands(self, module_name: str) -> list:
        return [(name, "") for name in self._reg.inline_handlers]

    def store_inline_callback(self, token: str, data: dict) -> None:
        from .buttons import registry

        entry = dict(data) if isinstance(data, dict) else {"handler": data}
        entry.setdefault("module_name", self.module_name)
        registry.put(token, entry, module_name=self.module_name)

    def remove_inline_callback_tokens(self, tokens) -> None:
        from .buttons import registry

        for token in tokens:
            registry.pop(token)

    def allow_inline_callback_user(self, user_id: int, token: str, allow_ttl: int) -> None:
        self.callback_permissions.allow(user_id, token, allow_ttl)

    def is_bot_available(self) -> bool:
        inline = self._inline_manager
        return inline is not None and bool(getattr(inline, "init_complete", False))

    # -- misc helpers -----------------------------------------------------

    def is_admin(self, user_id) -> bool:
        return self._host.is_admin(user_id)

    def get_prefix_for_sender(self, sender_id) -> str:
        return self._host.prefix

    def lookup_module(self, module_name: str, *, all_loaded: bool = False):
        return self._host.lookup_module(module_name)

    def get_loaded_module(self, module_name: str, *, all_loaded: bool = False):
        return self._host.lookup_module(module_name)

    def raw_text(self, source) -> str:
        return getattr(source, "raw_text", None) or getattr(source, "text", "") or ""

    def format_with_html(self, text: str, entities=None) -> str:
        if not entities:
            return text
        try:
            from elystl.extensions import html as html_parser

            return html_parser.unparse(text, entities)
        except Exception:
            return text

    async def get_thread_id(self, event):
        getter = getattr(event, "get_thread_id", None)
        if callable(getter):
            return await getter()
        return None

    def get_user_info(self, user_id):
        return {"id": user_id}

    def should_deliver_module_event(self, event, *, module=None, action="event") -> bool:
        return True

    def should_process_command_event(self, event) -> bool:
        return True

    def cprint(self, text: str, color: str = "") -> None:
        print(f"{color}{text}{Colors.RESET if color else ''}")

    async def handle_error(self, error, message: str | None = None, event=None, **kwargs):
        self.logger.error("%s: %s", message or "Operation failed", error)
        target = event or kwargs.get("cb_event")
        if target is None:
            return
        try:
            text = f"<b>{utils.escape_html(message or 'Error')}</b>\n<code>{utils.escape_html(str(error))}</code>"
            answer = getattr(target, "edit", None) or getattr(target, "answer", None)
            if callable(answer):
                await answer(text)
        except Exception:
            self.logger.debug("Failed to surface error to user", exc_info=True)

    async def log_module(self, message: str) -> None:
        self.logger.info(message)

    def log_error(self, message, *args, **kwargs) -> None:
        self.logger.error(str(message), *args)

    async def send_log_message(self, message: str, **kwargs) -> None:
        self.logger.info(str(message))

    def get_module_metadata(self, module_name: str) -> dict:
        """Header metadata (`# name:`, `# version:`, ...) for a loaded module."""
        adapter = self._host.adapters.get(module_name)
        if adapter is None:
            needle = str(module_name).lower()
            adapter = next(
                (
                    item
                    for name, item in self._host.adapters.items()
                    if name.lower() == needle
                ),
                None,
            )
        return dict(getattr(adapter, "mcub_meta", {}) or {})

    async def unregister_module_commands(self, module_name: str) -> bool:
        """Drop a module's commands, mirroring MCUB's loader teardown."""
        adapter = self._host.adapters.get(module_name)
        registrations = getattr(adapter, "registrations", None)
        if registrations is None:
            return False
        registrations.commands.clear()
        registrations.bot_commands.clear()
        registrations.aliases.clear()
        self._on_registration_change()
        return True

    @property
    def _inline(self):
        """Upstream's private handle for the form engine."""
        return self._host.mcub_inline

    @property
    def _log(self):
        return self.logger

    # MCUB's module catalogue lives in its own loader and repository engine.
    # Elys has `.dlmod`/`.loadmod` instead, so those APIs are genuinely absent
    # rather than stubbed -- a fake `download_module_from_repo` that silently
    # did nothing would be worse than a clear failure. Modules that probe with
    # `getattr(kernel, name, None)` still degrade cleanly, because this raises
    # AttributeError like any missing attribute.
    _UNSUPPORTED = MappingProxyType(
        {
            "_loader": "MCUB's module loader",
            "_module_sources": "MCUB's module source registry",
            "save_module_sources": "MCUB's module source registry",
            "load_module_from_file": "MCUB's module loader",
            "load_kernel": "MCUB's kernel switcher",
            "repositories": "MCUB's repository manager",
            "default_repo": "MCUB's repository manager",
            "add_repository": "MCUB's repository manager",
            "remove_repository": "MCUB's repository manager",
            "get_repo_name": "MCUB's repository manager",
            "get_repo_modules_list": "MCUB's repository manager",
            "download_module_from_repo": "MCUB's repository manager",
            "ensure_core_message_handlers": "MCUB's dispatcher internals",
            "ensure_registered_module_handlers": "MCUB's dispatcher internals",
            "dedupe_event_builders": "MCUB's dispatcher internals",
            "_debug_event_builders_snapshot": "MCUB's dispatcher internals",
        }
    )

    def __getattr__(self, name: str):
        """Explain missing kernel APIs instead of failing bare.

        Only reached when normal lookup fails, so it costs nothing on the happy
        path. The message names the attribute and the module asking for it,
        which is what turns "AttributeError: 'KernelProxy' object has no
        attribute 'x'" into something actionable.
        """
        if name.startswith("__"):
            raise AttributeError(name)

        owner = KernelProxy._UNSUPPORTED.get(name)
        if owner:
            raise AttributeError(
                f"kernel.{name} is part of {owner}, which the Elys MCUB"
                f" compatibility layer does not provide (requested by module"
                f" '{object.__getattribute__(self, 'module_name')}')"
            )
        raise AttributeError(
            f"kernel.{name} is not implemented by the Elys MCUB compatibility"
            f" layer (requested by module"
            f" '{object.__getattribute__(self, 'module_name')}')"
        )

    async def process_command(self, event, depth: int = 0) -> bool:
        return await self._host.process_command(event)

    async def send_to_topic(self, entity, topic: int, message: str = "", **kwargs):
        return await self.client.send_message(
            entity, message, reply_to=topic, **kwargs
        )

    async def send_file_to_topic(self, entity, topic: int, file, **kwargs):
        return await self.client.send_file(entity, file, reply_to=topic, **kwargs)

    async def send_with_emoji(self, chat_id, text: str, **kwargs):
        kwargs.setdefault("parse_mode", "html")
        return await self.client.send_message(chat_id, text, **kwargs)

    async def shutdown(self) -> None:
        await self._host.shutdown()

    async def restart(self, chat_id=None, message_id=None) -> None:
        await self._host.restart()

    async def install_from_url(self, url, module_name=None, auto_dependencies=True):
        return await self._host.install_from_url(url, module_name)

    def pipe_interpolate(self, text: str, pipe_input: str = "") -> str:
        return text

    async def async_pipe_interpolate(self, text: str, pipe_input: str = "", **kwargs) -> str:
        return text

    # -- internal bridges -------------------------------------------------

    def _publish_inline_temp(self, key: str, entry: dict) -> None:
        self._host.publish_inline_temp(key, entry)

    def _revoke_inline_temp(self, key: str) -> None:
        self._host.revoke_inline_temp(key)

    def _on_registration_change(self) -> None:
        self._host.on_registration_change()

    async def _invoke_command(self, command, *, args=None, chat_id=None, reply_to=None, prefix=None):
        return await self._host.invoke_command(
            command, args=args, chat_id=chat_id, reply_to=reply_to, prefix=prefix
        )

    def __repr__(self) -> str:
        return f"<KernelProxy module={self.module_name!r}>"


def make_permissions() -> CallbackPermissionManager:
    return CallbackPermissionManager()


class BoundInline:
    """Per-module view of the shared form engine.

    ``kernel.inline.form`` / ``gallery`` / ``list`` delegate to
    :class:`MCUBInlineManager`. Registration methods must land on *this*
    kernel's :class:`Registrations`, otherwise ``kernel.inline.register_*``
    is a silent no-op.
    """

    __slots__ = ("_kernel", "_manager")

    def __init__(self, manager, kernel: KernelProxy) -> None:
        object.__setattr__(self, "_manager", manager)
        object.__setattr__(self, "_kernel", kernel)

    def register_inline_handler(self, pattern: str, handler) -> None:
        self._kernel.register_inline_handler(pattern, handler)

    def register_callback_handler(self, pattern, handler) -> None:
        self._kernel.register_callback_handler(pattern, handler)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_manager"), name)


#: MCUB exposes the registration class as ``core.lib.loader.register.Register``.
Register = RegisterProxy
