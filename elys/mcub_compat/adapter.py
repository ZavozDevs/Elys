# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""The Elys ``loader.Module`` that owns an MCUB module.

Composition, not inheritance. Making an MCUB ``ModuleBase`` also inherit Elys's
``Module`` would collide on three fronts: ``ModuleBase`` overrides
``__getattribute__``, declares ``strings``/``config`` as properties, and rebuilds
class registries in ``__init_subclass__`` -- while Elys assigns ``mod.strings``,
``mod.db``, ``mod.client`` and ``mod.inline`` directly during registration. In
particular ``Modules.send_config_one`` does ``mod.strings = Strings(...)``, which
would raise against a read-only property.

So the adapter is a plain Elys module holding a reference to the MCUB one. Elys
gets its own ``strings`` for help/docs; MCUB keeps its ``Strings`` object on its
own instance. Neither framework can clobber the other.

The bridge to Elys's *passive* discovery is :meth:`republish`, which stamps the
collected handlers onto the adapter under the names ``_get_members()`` looks
for (``*cmd``, ``is_watcher``, ``*_inline_handler``, ...).
"""

from __future__ import annotations

import asyncio
import logging
import types
import typing
import uuid

from .events import MCUBEvent
from .watchers import passes_filters

logger = logging.getLogger(__name__)

#: Elys reserves these; never stamp a command over them.
_RESERVED_COMMANDS = frozenset({"help", "dlmod", "loadmod", "unloadmod", "restart"})


def _inline_everyone() -> int:
    """``security.EVERYONE | security.OWNER``, imported lazily.

    ``elys.security`` sits inside Elys's ``security`` -> ``main`` -> ``loader``
    import cycle. Touching it at module import time would drag this package
    into that cycle and break any entry point that imports us first.
    """
    from .. import security

    return security.EVERYONE | security.OWNER


class MCUBAdapterMixin:
    """Everything the adapter adds on top of Elys's ``Module``.

    Kept separate from ``elys.types.Module`` because that module sits inside
    Elys's ``types`` -> ``utils`` -> ``tl_cache`` -> ``types`` import cycle;
    subclassing it at import time would make this package unimportable on its
    own. :func:`build_adapter_class` mixes the two together at load time,
    when Elys is fully initialised.
    """

    # Populated by `build_adapter_class`.
    mcub_name: str = "MCUB"
    mcub_style: str = "mcub_class"
    mcub_meta: dict = {}
    strings = {"name": "MCUB"}

    # Set by the loader before `complete_registration`.
    mcub_instance: typing.Any = None
    mcub_module: typing.Any = None
    registrations: typing.Any = None
    host: typing.Any = None
    kernel: typing.Any = None

    def __init__(self) -> None:
        # Elys instantiates adapters with no arguments, so all MCUB context
        # arrives on the synthesised class (see `build_adapter_class`).
        self._mcub_event_handlers: list[tuple] = []
        self._mcub_published: list[str] = []
        self._mcub_ready = False

        if self.host is not None:
            self.host.register_adapter(self.mcub_name, self)
        self.republish()

    # ------------------------------------------------------------------
    # publishing MCUB handlers into Elys's discovery model
    # ------------------------------------------------------------------

    def republish(self) -> None:
        """Stamp MCUB handlers onto self under Elys's discovery names."""
        for attr in self._mcub_published:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
        self._mcub_published = []

        registrations = self.registrations
        if registrations is None:
            return

        for name, meta in registrations.commands.items():
            if name in _RESERVED_COMMANDS:
                logger.warning(
                    "MCUB module %s tried to register reserved command %r; skipped",
                    self.mcub_name,
                    name,
                )
                continue
            self._publish(f"{name}cmd", self._make_command(name, meta))

        for index, watcher in enumerate(registrations.watchers):
            self._publish(
                f"mcub{index}{watcher['name']}watcher",
                self._make_watcher(watcher),
            )

        for pattern, handler in registrations.inline_handlers.items():
            self._publish(
                f"{pattern}_inline_handler", self._make_inline_handler(handler)
            )

        for key in registrations.inline_temp:
            self._publish(
                f"{key}_inline_handler", self._make_inline_temp_handler(key)
            )

        self._publish("mcub_callback_handler", self._make_callback_bridge())

        if registrations.bot_commands:
            self._publish("mcub_bot_updates", self._make_bot_command_bridge())

    def _publish(self, attr: str, func: typing.Callable) -> None:
        """Publish a handler as a *bound method* on this adapter.

        Elys identifies which module owns a handler with
        `cmd.__self__.__class__.__name__` (see `Modules.unregister_commands`,
        `unregister_watchers`, `unregister_raw_handlers`). Instance attributes
        skip descriptor binding, so assigning a plain function leaves no
        `__self__` and unloading raises AttributeError. Binding explicitly is
        what gives these handlers the same shape as a normal `async def` on an
        Elys module. Flags set on the function stay reachable, because method
        objects forward attribute lookups to `__func__`.
        """
        bound = func if hasattr(func, "__self__") else types.MethodType(func, self)
        object.__setattr__(self, attr, bound)
        self._mcub_published.append(attr)

    # -- handler factories ------------------------------------------------

    def _make_command(self, name: str, meta: dict) -> typing.Callable:
        handler = meta["handler"]
        docs = meta.get("docs") or {}

        # The leading parameter is supplied by `types.MethodType` in `_publish`;
        # `self` is already captured from the enclosing scope.
        async def command_handler(_adapter, message):
            event = MCUBEvent(message, self.mcub_name, self.kernel)
            return await handler(event)

        command_handler.is_command = True
        command_handler.__name__ = f"{name}cmd"
        command_handler.__doc__ = self._pick_doc(docs)
        if docs.get("ru"):
            command_handler.ru_doc = docs["ru"]
        if docs.get("en"):
            command_handler.en_doc = docs["en"]
        if meta.get("aliases"):
            command_handler.aliases = list(meta["aliases"])
        return command_handler

    def _make_watcher(self, watcher: dict) -> typing.Callable:
        handler = watcher["handler"]
        tags = watcher.get("tags") or {}
        name = watcher["name"]

        async def watcher_handler(_adapter, message):
            registrations = self.registrations
            if registrations and name in registrations.disabled_watchers:
                return None
            event = MCUBEvent(message, self.mcub_name, self.kernel)
            if tags and not passes_filters(event, tags):
                return None
            try:
                return await handler(event)
            except Exception:
                logger.exception(
                    "MCUB watcher %s.%s raised", self.mcub_name, name
                )
                return None

        watcher_handler.is_watcher = True
        watcher_handler.__name__ = f"mcub_{name}_watcher"
        # MCUB watchers see every message, including command invocations.
        watcher_handler.no_commands = False
        return watcher_handler

    def _make_inline_handler(self, handler: typing.Callable) -> typing.Callable:
        async def inline_handler(_adapter, query):
            from .events import MCUBInlineQuery

            return await handler(MCUBInlineQuery(query, kernel=self.kernel))

        inline_handler.is_inline_handler = True
        inline_handler.security = _inline_everyone()
        return inline_handler

    def _make_inline_temp_handler(self, key: str) -> typing.Callable:
        """Query-time article for an ``inline_temp`` id.

        The handler itself only fires once the user *sends* the result; that
        happens in ``Events._chosen_inline_handler`` via the compat hook.
        """

        async def inline_temp_handler(_adapter, query):
            entry = self.host.inline_temp_map.get(key)
            if entry is None:
                return None

            builder = entry.get("article")
            if callable(builder):
                try:
                    return builder(query)
                except Exception:
                    logger.exception("MCUB inline_temp article builder failed")

            return self.host.inline_temp_article(key)

        inline_temp_handler.is_inline_handler = True
        inline_temp_handler.security = _inline_everyone()
        return inline_temp_handler

    def _make_callback_bridge(self) -> typing.Callable:
        """Single global callback router.

        Every adapter publishes this under the same name, so Elys's
        ``callback_handlers.update({name: func})`` collapses them into one
        entry and the router runs exactly once per callback query.
        """
        host = self.host

        async def mcub_callback_handler(_adapter, call):
            try:
                await host.dispatch_callback(call)
            except Exception:
                logger.exception("MCUB callback dispatch failed")

        mcub_callback_handler.is_callback_handler = True
        # Elys gates callback handlers through inline security. MCUB does its
        # own default-deny check (CallbackPermissionManager + allow_user), so
        # let the call through here and enforce it there instead.
        mcub_callback_handler.security = _inline_everyone()
        return mcub_callback_handler

    def _make_bot_command_bridge(self) -> typing.Callable:
        """Route ``/command`` sent to the helper bot to MCUB handlers.

        Elys's ``bot_watcher`` convention only sees private messages and hard
        routes a bare ``/start`` to ``InlineStuff``, which would make
        ``@bot_command("start")`` unreachable. Registering a Bot-API update
        handler instead bypasses that restriction.
        """
        registrations = self.registrations

        async def mcub_bot_updates(_adapter, event):
            text = getattr(event, "raw_text", "") or getattr(event, "text", "") or ""
            if not text.startswith("/"):
                return None
            command = text[1:].split()[0].split("@")[0].lower()
            meta = registrations.bot_commands.get(command)
            if meta is None:
                return None
            try:
                return await meta["handler"](event)
            except Exception:
                logger.exception(
                    "MCUB bot command /%s from %s failed", command, self.mcub_name
                )
                return None

        mcub_bot_updates.is_bot_update_handler = True
        mcub_bot_updates.bot_update_types = ["message"]
        mcub_bot_updates.id = uuid.uuid4().hex
        return mcub_bot_updates

    def _pick_doc(self, docs: dict) -> str:
        if not docs:
            return ""
        language = getattr(self.host, "language", "en") if self.host else "en"
        for key in (language, "en", "ru"):
            if docs.get(key):
                return docs[key]
        return next(iter(docs.values()), "")

    # ------------------------------------------------------------------
    # Elys lifecycle
    # ------------------------------------------------------------------

    async def client_ready(self) -> None:
        if self._mcub_ready:
            return
        self._mcub_ready = True

        registrations = self.registrations
        instance = self.mcub_instance

        self._attach_events()

        if instance is not None:
            await self._safe(instance.on_load(), "on_load")
            if await self._first_install():
                await self._safe(instance.on_install(), "on_install")
            instance._loaded = True
        elif registrations is not None:
            if registrations.on_load is not None:
                await self._safe(
                    self._call_kernel_hook(registrations.on_load), "on_load"
                )
            if registrations.on_install is not None and await self._first_install():
                await self._safe(
                    self._call_kernel_hook(registrations.on_install), "on_install"
                )
            for func in registrations.methods:
                await self._safe(self._call_kernel_hook(func), "@method")

        self._start_loops()

    def _start_loops(self) -> None:
        registrations = self.registrations
        if registrations is None:
            return
        for loop in registrations.loops:
            loop._kernel = self.kernel
            if loop.autostart:
                try:
                    loop.start()
                except Exception:
                    logger.exception(
                        "Failed to autostart MCUB loop in %s", self.mcub_name
                    )

    def _attach_events(self) -> None:
        registrations = self.registrations
        if registrations is None or not registrations.events:
            return

        from elystl import events as tl_events

        from .kernel import EVENT_TYPE_ALIASES

        for spec in registrations.events:
            builder_name = EVENT_TYPE_ALIASES.get(spec["event_type"])
            builder_cls = getattr(tl_events, builder_name, None) if builder_name else None
            if builder_cls is None:
                logger.warning(
                    "MCUB event type %s is unavailable on Elys", spec["event_type"]
                )
                continue

            try:
                builder = builder_cls(*spec["args"], **spec["kwargs"])
            except Exception:
                logger.exception(
                    "Could not build %s event for MCUB module %s",
                    spec["event_type"],
                    self.mcub_name,
                )
                continue

            client = self._event_client(spec["bot_client"])
            if client is None:
                logger.warning(
                    "MCUB module %s wants a bot_client event but no bot is set up",
                    self.mcub_name,
                )
                continue

            handler = self._wrap_event_handler(spec["handler"])
            client.add_event_handler(handler, builder)
            self._mcub_event_handlers.append((client, handler, builder))

    def _event_client(self, bot_client: bool):
        if not bot_client:
            return self.host.client
        inline = self.host.inline_manager
        bot = getattr(inline, "_bot_client", None) if inline is not None else None
        return bot

    def _wrap_event_handler(self, handler: typing.Callable) -> typing.Callable:
        async def wrapper(event):
            try:
                return await handler(event)
            except Exception:
                logger.exception("MCUB event handler in %s failed", self.mcub_name)
                return None

        return wrapper

    async def _first_install(self) -> bool:
        """True once per module, mirroring MCUB's ``__installed__`` DB flag."""
        key = f"installed.{self.mcub_name}"
        database = self.host.database("__flags__")
        try:
            if await database.db_get("__flags__", _flag_key(key)):
                return False
            await database.db_set("__flags__", _flag_key(key), "1")
            return True
        except Exception:
            logger.debug("Could not evaluate MCUB install flag", exc_info=True)
            return False

    async def _call_kernel_hook(self, func: typing.Callable):
        result = func(self.kernel)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _safe(self, awaitable, label: str) -> None:
        try:
            if asyncio.iscoroutine(awaitable):
                await awaitable
        except Exception:
            logger.exception("MCUB %s failed in %s", label, self.mcub_name)

    async def on_unload(self) -> None:
        registrations = self.registrations

        if registrations is not None:
            for loop in registrations.loops:
                try:
                    loop.stop()
                except Exception:
                    logger.debug("Failed stopping MCUB loop", exc_info=True)

        for client, handler, builder in self._mcub_event_handlers:
            try:
                client.remove_event_handler(handler, builder)
            except Exception:
                logger.debug("Failed removing MCUB event handler", exc_info=True)
        self._mcub_event_handlers = []

        instance = self.mcub_instance
        if instance is not None:
            await self._safe(instance.on_unload(), "on_unload")
            try:
                instance._cleanup_callback_tokens()
            except Exception:
                logger.debug("Failed cleaning MCUB callback tokens", exc_info=True)
        elif registrations is not None and registrations.uninstall is not None:
            await self._safe(
                self._call_kernel_hook(registrations.uninstall), "uninstall"
            )

        if self.host is not None:
            self.host.unregister_adapter(self.mcub_name)

    # ------------------------------------------------------------------
    # introspection helpers used by `.mcubcheck` and tests
    # ------------------------------------------------------------------

    def mcub_summary(self) -> dict:
        registrations = self.registrations
        return {
            "name": self.mcub_name,
            "style": self.mcub_style,
            "version": self.mcub_meta.get("version"),
            "author": self.mcub_meta.get("author"),
            "handlers": registrations.summary() if registrations else {},
        }


def _flag_key(value: str) -> str:
    return "".join(c if c.isalnum() or c in "_.-" else "_" for c in value)[:64]


_adapter_base: type | None = None


def get_adapter_base() -> type:
    """Return (and cache) ``MCUBAdapterMixin`` + Elys's ``Module``."""
    global _adapter_base
    if _adapter_base is None:
        from ..types import Module

        _adapter_base = type("MCUBModuleAdapter", (MCUBAdapterMixin, Module), {})
    return _adapter_base


def build_adapter_class(
    *,
    name: str,
    style: str,
    meta: dict,
    description: str,
) -> type:
    """Synthesise the per-module adapter class Elys will instantiate.

    Elys finds a module by scanning ``vars(module)`` for a ``Module`` subclass
    and calling it with no arguments, so the MCUB context has to travel on the
    class rather than through ``__init__``.
    """
    class_name = f"MCUB_{_flag_key(name)}"
    namespace = {
        "mcub_name": name,
        "mcub_style": style,
        "mcub_meta": dict(meta),
        "strings": {"name": name},
        "__doc__": description or f"MCUB module {name}",
    }
    return type(class_name, (get_adapter_base(),), namespace)
