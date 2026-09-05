# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""``ModuleBase`` for class-style MCUB modules, backed by Elys.

Structure follows MCUB's ``core/lib/loader/base.py`` closely: the same twelve
``__init_subclass__`` registries, the same three-argument ``__init__(kernel,
client, register)`` (so modules overriding ``__init__`` and calling ``super()``
keep working), and the same ordering of registration side effects.

Registration is deliberately still performed *inside* ``__init__``, exactly as
upstream does, because ``@owner_only``/``@permissions``/``@error_handler``
wrapping happens there. The handlers land in a
:class:`~elys.mcub_compat.kernel.Registrations` sink that the adapter later
republishes to Elys.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import logging
import typing
from abc import ABC
from collections.abc import Callable, Mapping

from elystl.tl import types as tl_types
from .buttons import DEFAULT_TTL, make_callback_button, registry as callback_registry
from ._vendor.decorators import (  # noqa: F401  (re-exported for module authors)
    bot_command,
    callback,
    command,
    error_handler,
    event,
    inline,
    inline_temp,
    loop,
    method,
    on_install,
    on_uninstall,
    owner,
    owner_only,
    permission,
    permissions,
    uninstall,
    watcher,
)
from ._vendor.rich_buttons import (
    RichButtonRow,
    RichCallbackButton,
    RichPageButton,
    render_rich_button,
    render_rich_page_button,
    validate_rich_button,
    validate_rich_page_button,
)
from ._vendor.strings import Strings

logger = logging.getLogger(__name__)

_REGISTRY_NAMES = (
    "_cmd_registry",
    "_inline_registry",
    "_callback_registry",
    "_watcher_registry",
    "_loop_registry",
    "_event_registry",
    "_method_registry",
    "_on_install_registry",
    "_uninstall_registry",
    "_bot_cmd_registry",
    "_owner_registry",
    "_permission_registry",
    "_error_handler_registry",
    "_inline_temp_registry",
)

_FLAT_STRING_LOCALES = ("ru", "en", "uk", "de", "es", "fr", "it", "pt")


class _ModuleLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        module_name = self.extra.get("module_name", "Unnamed")
        return f"[{module_name}] {msg}", kwargs


class ModuleBase(ABC):
    """Base class for class-style MCUB modules."""

    name: str = "Unnamed"
    version: str = "1.0.0"
    author: str = "unknown"
    description: dict | str = {}
    dependencies: list = []
    banner_url: str | None = None

    strings: dict = {}
    config: typing.Any = None

    # Declared explicitly rather than generated through `vars()` in the class
    # body: mutating the class namespace that way is a CPython implementation
    # detail, and these are only defaults anyway -- `__init_subclass__` rebuilds
    # all of them for every concrete module.
    _cmd_registry: list = []
    _inline_registry: list = []
    _callback_registry: list = []
    _watcher_registry: list = []
    _loop_registry: list = []
    _event_registry: list = []
    _method_registry: list = []
    _on_install_registry: list = []
    _uninstall_registry: list = []
    _bot_cmd_registry: list = []
    _owner_registry: list = []
    _permission_registry: list = []
    _error_handler_registry: list = []
    _inline_temp_registry: list = []

    def __getattribute__(self, name: str):
        # `strings`/`config` start life as plain class dicts; route reads through
        # the accessors so module code always sees the wrapped objects.
        if name in ("config", "strings"):
            try:
                return object.__getattribute__(self, f"_get_{name}")()
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        for registry in _REGISTRY_NAMES:
            setattr(cls, registry, [])

        for _, attr in cls.__dict__.items():
            if not callable(attr):
                continue
            for pattern, meta in getattr(attr, "_mcub_commands", []):
                cls._cmd_registry.append((pattern, attr, meta))
            for item in getattr(attr, "_mcub_inline", []):
                pattern = item[0] if isinstance(item, tuple) and len(item) == 2 else item
                cls._inline_registry.append((pattern, attr))
            for info in getattr(attr, "_mcub_callbacks", []):
                cls._callback_registry.append((attr, info["ttl"]))
            for info in getattr(attr, "_mcub_watchers", []):
                cls._watcher_registry.append(
                    (attr, info["bot_client"], info["tags"])
                )
            for info in getattr(attr, "_mcub_loops", []):
                cls._loop_registry.append(
                    (
                        attr,
                        info["interval"],
                        info["autostart"],
                        info["wait_before"],
                    )
                )
            for info in getattr(attr, "_mcub_events", []):
                cls._event_registry.append(
                    (
                        attr,
                        info["event_type"],
                        info["args"],
                        info["bot_client"],
                        info["kwargs"],
                    )
                )
            if getattr(attr, "_mcub_methods", None):
                cls._method_registry.append(attr)
            for info in getattr(attr, "_mcub_inline_temp", []):
                cls._inline_temp_registry.append(
                    (
                        attr,
                        info["ttl"],
                        info.get("allow_user"),
                        info.get("allow_ttl"),
                        info["article"],
                        info["data"],
                    )
                )
            if getattr(attr, "_mcub_on_install", None):
                cls._on_install_registry.append(attr)
            if getattr(attr, "_mcub_uninstall", None):
                cls._uninstall_registry.append(attr)
            for info in getattr(attr, "_mcub_bot_commands", []):
                cls._bot_cmd_registry.append((attr, info))
            for info in getattr(attr, "_mcub_owner", []):
                cls._owner_registry.append((attr, info))
            for info in getattr(attr, "_mcub_permissions", []):
                cls._permission_registry.append((attr, info))
            for info in getattr(attr, "_mcub_error_handler", []):
                cls._error_handler_registry.append((attr, info))

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    def __init__(self, kernel, client, register) -> None:
        self.kernel = kernel
        self.client = client
        self._register = register
        self.subinline = kernel.inline

        self._loaded = False
        self._loops: list = []
        self._watchers: list = []
        self._uninstall_funcs: list = []
        self._on_install_funcs: list = []
        self._method_funcs: list = []
        self._callback_tokens: list[str] = []

        self.name = type(self).name
        self.log = _ModuleLoggerAdapter(
            logging.getLogger(f"mcub.{self.name}"), {"module_name": self.name}
        )
        self.db = kernel.db_manager
        self.cache = kernel.cache

        self._config = self._discover_config()
        self._strings = self._discover_strings()

        self._register_everything()

    def _discover_config(self):
        for klass in type(self).__mro__:
            if "config" in klass.__dict__:
                value = klass.__dict__["config"]
                if isinstance(value, property):
                    continue
                bind_owner = getattr(value, "bind_owner", None)
                if callable(bind_owner):
                    bind_owner(self)
                return value
        return None

    def _discover_strings(self):
        strings_dict = None
        for klass in type(self).__mro__:
            if "strings" in klass.__dict__:
                value = klass.__dict__["strings"]
                if not isinstance(value, property):
                    strings_dict = value
                    break

        if not strings_dict:
            return None

        try:
            payload = copy.deepcopy(dict(strings_dict))
            # If flat dictionary (contains string values instead of locale dicts), expand across all locales first
            is_flat = any(isinstance(v, str) for v in payload.values()) and "name" not in payload
            if is_flat:
                payload = {locale: dict(payload) for locale in _FLAT_STRING_LOCALES}
            elif "name" not in payload and all(
                isinstance(v, dict) for v in payload.values()
            ):
                for problem in Strings.validate(payload):
                    self.log.warning("strings validation: %s", problem)
            return Strings(self.kernel, payload)
        except Exception as error:
            self.log.error("Failed to initialise strings: %s", error)
            return None

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------

    def _register_everything(self) -> None:
        cls = type(self)

        owner_map = {f.__name__: info for f, info in cls._owner_registry}
        permission_map: dict[str, dict] = {}
        for func, info in cls._permission_registry:
            permission_map.setdefault(func.__name__, {}).update(info)
        error_map = {f.__name__: info for f, info in cls._error_handler_registry}

        for pattern, func, cmd_kwargs in cls._cmd_registry:
            handler = self._build_command_handler(
                func,
                permission_map.get(func.__name__),
                error_map.get(func.__name__),
                owner_map.get(func.__name__),
            )
            self._register.command(pattern, **cmd_kwargs)(handler)

        for func, cmd_info in cls._bot_cmd_registry:
            if isinstance(cmd_info, tuple) and len(cmd_info) == 2:
                pattern, meta = cmd_info
            elif isinstance(cmd_info, dict):
                pattern, meta = cmd_info.get("pattern"), cmd_info
            else:
                continue
            if not pattern:
                continue
            cmd_kwargs = {
                key: value
                for key, value in meta.items()
                if value is not None and (key in {"alias", "doc"} or key.startswith("doc_"))
            }
            handler = self._build_command_handler(
                func, permission_map.get(func.__name__), error_map.get(func.__name__), None
            )
            self._register.bot_command(pattern, **cmd_kwargs)(handler)

        for pattern, func in cls._inline_registry:
            inline_meta = {}
            for entry in getattr(func, "_mcub_inline", []):
                if isinstance(entry, tuple) and len(entry) == 2 and entry[0] == pattern:
                    inline_meta = entry[1]
                    break

            @functools.wraps(func)
            async def inline_handler(query, _func=func):
                return await _func(self, query)

            inline_handler.__original__ = func
            doc_str = (
                getattr(func, "__doc__", None)
                or inline_meta.get("doc_ru")
                or inline_meta.get("doc_en")
                or (
                    inline_meta.get("doc", {}).get("ru")
                    if isinstance(inline_meta.get("doc"), dict)
                    else None
                )
                or (
                    inline_meta.get("doc", {}).get("en")
                    if isinstance(inline_meta.get("doc"), dict)
                    else None
                )
            )
            if doc_str:
                inline_handler.__doc__ = doc_str
            if inline_meta.get("doc_ru"):
                inline_handler.ru_doc = inline_meta["doc_ru"]
            if inline_meta.get("doc_en"):
                inline_handler.en_doc = inline_meta["doc_en"]
            if inline_meta.get("doc") and isinstance(inline_meta["doc"], dict):
                inline_handler.doc = inline_meta["doc"]

            self.kernel.register_inline_handler(pattern, inline_handler)

        for func, ttl in cls._callback_registry:
            self._register_callback(func, ttl)

        for func, interval, autostart, wait_before in cls._loop_registry:
            self._register_loop(func, interval, autostart, wait_before)

        for func, bot_client, tags in cls._watcher_registry:
            self._register_watcher(
                func,
                bot_client=bot_client,
                permission_tags=permission_map.get(func.__name__),
                **tags,
            )

        for func, event_type, args, bot_client, kwargs in cls._event_registry:
            self._register_event(
                func,
                event_type,
                *args,
                bot_client=bot_client,
                permission_tags=permission_map.get(func.__name__),
                **kwargs,
            )

        self._method_funcs.extend(cls._method_registry)
        self._on_install_funcs.extend(cls._on_install_registry)
        self._uninstall_funcs.extend(cls._uninstall_registry)

        self._inline_temp_ids: dict[str, str] = {}
        for func, ttl, allow_user, allow_ttl, article, data in cls._inline_temp_registry:
            form_id = self._register_inline_temp(
                func, ttl, allow_user, allow_ttl, article, data
            )
            self._inline_temp_ids[f"{self.name}:{func.__name__}"] = form_id

    def _build_command_handler(self, func, permission_tags, error_config, owner_info):
        async def handler(event):
            if permission_tags and not self._passes_permission_tags(
                event, permission_tags
            ):
                return None
            if owner_info is not None and not self._passes_owner(event, owner_info):
                return None
            if error_config:
                return await self._run_with_error_handler(
                    func, self, event, error_config
                )
            return await func(self, event)

        handler.__name__ = getattr(func, "__name__", "handler")
        handler.__original__ = func
        handler.__bound_instance__ = self
        return handler

    def _passes_owner(self, event, owner_info: dict) -> bool:
        sender_id = getattr(event, "sender_id", None)
        if sender_id is None:
            return False
        if not self.kernel.is_admin(sender_id):
            return False
        if not owner_info.get("only_admin", False):
            no_owner = getattr(event, "no_owner", None)
            if callable(no_owner) and no_owner():
                return False
        return True

    def _passes_permission_tags(self, event, tags: dict) -> bool:
        from .watchers import passes_filters

        try:
            return passes_filters(event, tags)
        except Exception as error:
            self.log.warning("permission filter failed for %s: %s", tags, error)
            return False

    async def _run_with_error_handler(self, func, instance, event, config: dict):
        try:
            return await func(instance, event)
        except Exception as error:
            template = config.get("message")
            text = (
                template.format(
                    exc=str(error), func=func.__name__, module=self.name
                )
                if template
                else f"Error in {func.__name__}: {error}"
            )
            log_func = getattr(self.log, config.get("log_level", "error"), self.log.error)
            log_func(text)
            if config.get("reraise", False):
                raise
            return None

    def _register_watcher(self, func, bot_client=False, permission_tags=None, **tags):
        async def wrapper(event):
            if permission_tags and not self._passes_permission_tags(
                event, permission_tags
            ):
                return None
            return await func(self, event)

        wrapper.__name__ = getattr(func, "__name__", "watcher")
        wrapper.__original__ = func
        wrapper.__bound_instance__ = self
        self._watchers.append(wrapper)
        self._register.watcher(wrapper, bot_client=bot_client, **tags)

    def _register_event(
        self, func, event_type, *args, bot_client=False, permission_tags=None, **kwargs
    ):
        async def wrapper(event):
            if permission_tags and not self._passes_permission_tags(
                event, permission_tags
            ):
                return None
            return await func(self, event)

        wrapper.__name__ = getattr(func, "__name__", "event")
        wrapper.__original__ = func
        wrapper.__bound_instance__ = self
        self._register.event(event_type, *args, bot_client=bot_client, **kwargs)(wrapper)

    def _register_loop(self, func, interval, autostart, wait_before):
        async def wrapper():
            return await func(self)

        wrapper.__name__ = getattr(func, "__name__", "loop")
        wrapper.__original__ = func
        wrapper.__bound_instance__ = self

        instance = self._register.loop(interval, autostart, wait_before)(wrapper)
        self._loops.append(instance)
        # MCUB exposes the loop under its own method name so modules can call
        # `self.checker.start()`.
        object.__setattr__(self, func.__name__, instance)
        return instance

    def _register_inline_temp(self, func, ttl, allow_user, allow_ttl, article, data):
        async def wrapper(event, args="", cb_data=None):
            return await func(self, event, args, cb_data)

        wrapper.__original__ = func
        wrapper.__bound_instance__ = self
        return self.kernel.register.inline_temp(
            wrapper,
            ttl=ttl,
            article=article,
            data=data,
            allow_user=allow_user,
            allow_ttl=allow_ttl or 100,
        )

    def _make_class_callback_wrapper(self, func, ttl):
        raw_func = getattr(func, "__original__", func)
        instance = self

        async def wrapper(event, *args, **kwargs):
            if getattr(raw_func, "__self__", None) is not None:
                return await raw_func(event, *args, **kwargs)
            return await raw_func(instance, event, *args, **kwargs)

        wrapper.__original__ = func
        wrapper._ttl = ttl
        wrapper._is_class_callback = True
        wrapper._bound_instance = self
        return wrapper

    def _register_callback(self, func, ttl: int) -> None:
        token = callback_registry.register(
            self._make_class_callback_wrapper(func, ttl),
            module_name=self.name,
            ttl=ttl,
        )
        self._callback_tokens.append(token)

    def _cleanup_callback_tokens(self) -> None:
        callback_registry.forget_module(self.name)
        self._callback_tokens = []

    # ------------------------------------------------------------------
    # module-facing helpers
    # ------------------------------------------------------------------

    def get_prefix(self) -> str:
        return getattr(self.kernel, "custom_prefix", ".")

    def get_lang(self) -> str:
        config = getattr(self.kernel, "config", {})
        getter = getattr(config, "get", None)
        if callable(getter):
            return getter("language", "ru") or "ru"
        return "ru"

    def get_description(self) -> str:
        raw = type(self).description
        if isinstance(raw, str):
            return raw
        if isinstance(raw, Mapping):
            lang = self.get_lang()
            for key in (lang, "en", "ru"):
                value = raw.get(key)
                if value:
                    return str(value)
            for value in raw.values():
                if value:
                    return str(value)
        return ""

    def args(self, event):
        from ._vendor.arg_parser import parse_arguments

        text = getattr(event, "raw_text", "") or ""
        return parse_arguments(text, prefix=self.get_prefix())

    def args_raw(self, event) -> str:
        from .helpers import get_args_raw

        return get_args_raw(event)

    def args_html(self, event) -> str:
        from .helpers import get_args_html

        return get_args_html(event)

    async def answer(self, event, text, **kwargs):
        from .helpers import answer

        return await answer(event, text, **kwargs)

    async def edit(self, event, text, **kwargs):
        reply_markup = kwargs.pop("reply_markup", None)
        as_html = kwargs.pop("as_html", False)
        if reply_markup is not None:
            kwargs["buttons"] = reply_markup
        if as_html:
            kwargs.setdefault("parse_mode", "html")
        editor = getattr(event, "edit", None)
        if callable(editor):
            return await editor(text, **kwargs)
        return await self.answer(event, text, **kwargs)

    async def reply(self, event, text, **kwargs):
        reply_markup = kwargs.pop("reply_markup", None)
        as_html = kwargs.pop("as_html", False)
        if reply_markup is not None:
            kwargs["buttons"] = reply_markup
        if as_html:
            kwargs.setdefault("parse_mode", "html")
        replier = getattr(event, "reply", None)
        if callable(replier):
            return await replier(text, **kwargs)
        return await self.answer(event, text, **kwargs)

    async def invoke(self, command, args=None, chat_id=None, reply_to=None):
        return await self._register.invoke(
            command, args=args, chat_id=chat_id, reply_to=reply_to
        )

    async def inline(self, chat_id, title, fields=None, buttons=None, **kwargs):
        return await self.subinline.inline_form(
            chat_id, title, fields=fields, buttons=buttons, **kwargs
        )

    def inline_temp(
        self, func, ttl=300, allow_user=None, allow_ttl=100, article=None, data=None
    ) -> str:
        async def wrapper(event, *args, **kwargs):
            return await func(self, event, *args, **kwargs)

        wrapper.__original__ = func
        wrapper.__bound_instance__ = self
        return self.kernel.register.inline_temp(
            wrapper,
            ttl=ttl,
            article=article,
            data=data,
            allow_user=allow_user,
            allow_ttl=allow_ttl,
        )

    def get_inline_temp_id(self, method_name: str, module_name: str | None = None):
        key = f"{module_name or self.name}:{method_name}"
        return getattr(self, "_inline_temp_ids", {}).get(key)

    def lookup_module(self, module_name: str, *, all_loaded: bool = False):
        return self.kernel.lookup_module(module_name, all_loaded=all_loaded)

    def require_module(self, module_name: str, *, all_loaded: bool = False):
        module = self.lookup_module(module_name, all_loaded=all_loaded)
        if module is None:
            raise LookupError(f"Required module '{module_name}' is not loaded")
        return module

    async def import_lib(self, url: str, *, name: str | None = None):
        """MCUB's ``import_lib`` execs remote code into a bare module."""
        import sys
        import types
        import urllib.request

        if name is None:
            name = url.split("/")[-1]
            if name.endswith(".py"):
                name = name[:-3]
            if not name:
                return None

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Refusing to import library from non-HTTP url: {url}")

        try:
            with urllib.request.urlopen(url) as response:  # noqa: S310
                code = response.read().decode("utf-8")

            module = types.ModuleType(name)
            sys.modules[name] = module
            exec(code, module.__dict__)  # noqa: S102
            self.log.info("Imported library: %s from %s", name, url)
            return module
        except Exception as error:
            self.log.error("Failed to import lib %s: %s", name, error)
            raise

    async def save_config(self) -> None:
        if self._config is None:
            return
        try:
            await self.kernel.save_module_config(self.name, self._config.to_dict())
            self.kernel.set_live_module_config(self.name, self._config)
        except Exception as error:
            self.log.warning("Failed to save config for %s: %s", self.name, error)

    def _make_callback_button(self, text, callback_func, **kwargs):
        kwargs.setdefault("ttl", DEFAULT_TTL)
        return make_callback_button(
            text,
            self._make_class_callback_wrapper(callback_func, kwargs["ttl"]),
            module_name=self.name,
            permissions=self.kernel.callback_permissions,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # buttons
    # ------------------------------------------------------------------

    @property
    def Button(self) -> "ModuleBase.ButtonFactory":
        if not hasattr(self, "_button_factory"):
            factory_cls = getattr(type(self), "ButtonFactory", None)
            if isinstance(factory_cls, type) and issubclass(
                factory_cls, ModuleBase.ButtonFactory
            ):
                object.__setattr__(self, "_button_factory", factory_cls(self))
            else:
                object.__setattr__(
                    self, "_button_factory", ModuleBase.ButtonFactory(self)
                )
        return self._button_factory

    class ButtonFactory:
        """Mirror of MCUB's button factory, producing ``elystl`` buttons."""

        def __init__(self, outer) -> None:
            self._outer = outer
            from elystl import Button as _Button

            self._telethon_button = _Button
            self._strings_base = Strings(outer.kernel, {"name": "null"})

        @property
        def rich(self) -> "ModuleBase.RichButtonFactory":
            if not hasattr(self, "_rich_button_factory"):
                self._rich_button_factory = ModuleBase.RichButtonFactory(self._outer)
            return self._rich_button_factory

        def _call(self, name: str, *args, **kwargs):
            """Call a Button factory, dropping kwargs the fork rejects."""
            factory = getattr(self._telethon_button, name, None)
            if factory is None:
                raise NotImplementedError(
                    f"elystl.Button has no {name!r}; this MCUB button kind is"
                    " unsupported on Elys"
                )
            attempts = [kwargs]
            if "style" in kwargs:
                attempts.append({k: v for k, v in kwargs.items() if k != "style"})
            if "icon" in kwargs:
                attempts.append(
                    {k: v for k, v in kwargs.items() if k not in {"icon", "style"}}
                )
            last_error = None
            for attempt in attempts:
                cleaned = {k: v for k, v in attempt.items() if v is not None}
                try:
                    return factory(*args, **cleaned)
                except TypeError as error:
                    last_error = error
            raise last_error or TypeError(name)

        def inline(
            self,
            text: str,
            callback_func: Callable,
            *,
            ttl: int = DEFAULT_TTL,
            allow_user=None,
            allow_ttl: int = 100,
            args: tuple = (),
            kwargs: dict | None = None,
            data=None,
            pass_event: bool = True,
            auto_answer: bool | None = None,
            icon: int | None = None,
            style=None,
            **btn_kwargs,
        ):
            return self._outer._make_callback_button(
                text,
                callback_func,
                ttl=ttl,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
                args=args,
                kwargs=kwargs,
                data=data,
                style=style,
                icon=icon,
                **btn_kwargs,
            )

        def url(self, text, url, *, icon=None, style=None):
            return self._call("url", text, url, style=style, icon=icon)

        def text(self, text, *, resize=True, selective=False, icon=None, style=None):
            return self._call(
                "text", text, resize=resize, selective=selective, style=style, icon=icon
            )

        def switch(self, text, query="", *, same_peer=True, icon=None, style=None):
            return self._call(
                "switch_inline",
                text,
                query=query,
                same_peer=same_peer,
                style=style,
                icon=icon,
            )

        def switch_inline(self, text, query="", *, same_peer=True, icon=None, style=None):
            return self.switch(text, query=query, same_peer=same_peer, icon=icon, style=style)

        def web_app(self, text, url, *, icon=None, style=None):
            factory = getattr(self._telethon_button, "web_app", None)
            if factory is not None:
                return self._call("web_app", text, url, style=style, icon=icon)
            return tl_types.KeyboardButtonSimpleWebView(text=text, url=url)

        def auth(self, text, url, *, icon=None, style=None, **kwargs):
            return self._call("auth", text, url, style=style, icon=icon, **kwargs)

        def buy(self, text, *, icon=None, style=None):
            return self._call("buy", text, style=style, icon=icon)

        def input(
            self,
            text,
            handler,
            *,
            placeholder: str = "",
            ttl: int = DEFAULT_TTL,
            allow_user=None,
            allow_ttl: int = 100,
            article=None,
            data=None,
            icon=None,
            style=None,
        ):
            """Prompt button: opens inline mode, delivers typed text to *handler*."""

            async def wrapper(event, args="", cb_data=None):
                return await handler(event, args, cb_data)

            wrapper.__original__ = handler
            wrapper.__bound_instance__ = self._outer

            temp_uuid = self._outer.kernel.register.inline_temp(
                wrapper,
                ttl=ttl,
                article=article,
                data=data,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
            )
            query = f"{temp_uuid} {placeholder}" if placeholder else f"{temp_uuid} "
            return self._call(
                "switch_inline", text, query=query, same_peer=True, style=style, icon=icon
            )

        def close(
            self,
            event,
            text=None,
            handler=None,
            *,
            icon=None,
            style=None,
            allow_user=None,
            allow_ttl: int = 100,
        ):
            label = text or self._strings_base("buttons").get("close") or "Close"

            async def on_close(call):
                try:
                    delete = getattr(call, "delete", None)
                    if callable(delete):
                        await delete()
                finally:
                    answer = getattr(call, "answer", None)
                    if callable(answer):
                        await answer()

            return self.inline(
                label,
                handler or on_close,
                icon=icon,
                style=style,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
            )

        def copy(self, text="Copy", copy_text=None, *, icon=None, style=None):
            factory = getattr(self._telethon_button, "copy", None)
            if factory is not None:
                return self._call(
                    "copy", text, copy_text=copy_text, style=style, icon=icon
                )
            return tl_types.KeyboardButtonCopy(
                text=text,
                copy_text=copy_text if copy_text is not None else text,
                style=self._telethon_button._get_style(style, icon),
            )

        def request_phone(self, text="Share Phone", *, request_title=None, icon=None, style=None):
            return self._call(
                "request_phone", text, request_title=request_title, style=style, icon=icon
            )

        def request_location(
            self, text="Share Location", *, request_title=None, live_period=None, icon=None, style=None
        ):
            return self._call(
                "request_location",
                text,
                request_title=request_title,
                live_period=live_period,
                style=style,
                icon=icon,
            )

        def request_poll(self, text="Create Poll", *, request_title=None, quiz=False, icon=None, style=None):
            return self._call(
                "request_poll", text, request_title=request_title, quiz=quiz, style=style, icon=icon
            )

        def game(self, text, *, game=None, icon=None, style=None):
            if game:
                return self._call("game", text, game=game, style=style, icon=icon)
            return self._call("game", text, style=style, icon=icon)

        def mention(self, text, user=None, *, icon=None):
            return self._call("mention", text, user, icon=icon)

        def unknown(self, data, text="Button", *, icon=None, style=None):
            return self._call("unknown", text, data, style=style, icon=icon)

        def with_icon(self, btn, icon):
            return btn

        def style(self, btn, style):
            return btn

        def __getattr__(self, name: str):
            if hasattr(self._telethon_button, name):
                return lambda *args, **kwargs: self._call(name, *args, **kwargs)
            raise AttributeError(f"'ButtonFactory' object has no attribute '{name}'")

    class RichButtonFactory:
        """Callback buttons embedded in Telegram rich pages (MCUB ``dev``).

        These render as ``<tg-button>`` markup inside rich HTML, which Telegram
        parses server-side, so no client support is required beyond sending
        rich messages -- which ``elystl`` already does.
        """

        _ALIGNMENTS = frozenset({"left", "center", "right"})

        def __init__(self, outer) -> None:
            self._outer = outer

        def inline(
            self,
            text: str,
            handler: Callable,
            *,
            args: tuple | list = (),
            kwargs: Mapping | None = None,
            ttl: int = DEFAULT_TTL,
            allow_user=None,
            allow_ttl: int = 100,
            data=None,
            pass_event: bool = True,
            auto_answer: bool | None = None,
            icon: int | None = None,
            style: str | None = None,
            html_tag: bool = False,
            **button_kwargs,
        ):
            if not isinstance(text, str) or not text:
                raise ValueError("rich button text must be a non-empty string")
            if not callable(handler):
                raise TypeError("handler must be callable")
            if not isinstance(args, (tuple, list)):
                raise TypeError("args must be a tuple or list")
            if kwargs is not None and not isinstance(kwargs, Mapping):
                raise TypeError("kwargs must be a mapping or None")
            if not isinstance(html_tag, bool):
                raise TypeError("html_tag must be a bool")
            validate_rich_button(text, "x", style)
            if icon is not None:
                raise ValueError("rich page buttons do not support icon")

            token = self._outer._make_callback_button(
                text,
                handler,
                ttl=ttl,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
                args=args,
                kwargs=dict(kwargs) if kwargs is not None else None,
                data=data,
                style=style,
                _return_token=True,
                **button_kwargs,
            )
            validate_rich_button(text, token, style)
            spec = RichCallbackButton(text=text, token=token, style=style)
            return render_rich_button(spec) if html_tag else spec

        def row(self, *buttons, align: str = "center") -> RichButtonRow:
            if align not in self._ALIGNMENTS:
                raise ValueError("rich button row align must be left, center or right")
            if not buttons:
                raise ValueError("rich button row cannot be empty")
            if len(buttons) > 8:
                raise ValueError("rich button rows support at most 8 buttons")
            if not all(
                isinstance(b, (RichCallbackButton, RichPageButton)) for b in buttons
            ):
                raise TypeError("rich button rows accept only Button.rich specs")
            return RichButtonRow(tuple(buttons), align=align)

        @staticmethod
        def _page(text, type_, attrs=None, style=None, html_tag=False):
            if not isinstance(html_tag, bool):
                raise TypeError("html_tag must be a bool")
            button = RichPageButton(text, type_, attrs, style)
            validate_rich_page_button(button)
            return render_rich_page_button(button) if html_tag else button

        def url(self, text, url, *, style=None, html_tag=False):
            return self._page(text, "url", {"url": url}, style, html_tag)

        def text(self, text, *, resize=True, selective=False, style=None, html_tag=False):
            if resize is not True or selective is not False:
                raise ValueError(
                    "rich text buttons are display-only; use normal buttons= for"
                    " resize/selective"
                )
            return self._page(text, "disabled", None, style, html_tag)

        def switch(self, text, query="", *, same_peer=True, style=None, html_tag=False):
            type_ = (
                "switch_inline_query_current_chat"
                if same_peer
                else "switch_inline_query"
            )
            return self._page(text, type_, {"query": str(query)}, style, html_tag)

        def copy(self, text="Copy", copy_text=None, *, style=None, html_tag=False):
            return self._page(
                text,
                "copy_text",
                {"text": text if copy_text is None else str(copy_text)},
                style,
                html_tag,
            )

        def game(self, text="Play Game", *, style=None, html_tag=False):
            return self._page(text, "game", None, style, html_tag)

        def unknown(self, text="Unsupported", *, style=None, html_tag=False):
            return self._page(text, "disabled", None, style, html_tag)

        def input(
            self,
            text,
            handler,
            *,
            placeholder="",
            ttl=DEFAULT_TTL,
            allow_user=None,
            allow_ttl=100,
            article=None,
            data=None,
            style=None,
            html_tag=False,
        ):
            button = ModuleBase.ButtonFactory(self._outer).input(
                text,
                handler,
                placeholder=placeholder,
                ttl=ttl,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
                article=article,
                data=data,
                style=style,
            )
            payload = button.type if hasattr(button, "type") else button
            return self.switch(
                text,
                getattr(payload, "query", ""),
                same_peer=getattr(payload, "same_peer", True),
                style=style,
                html_tag=html_tag,
            )

        def close(
            self,
            event,
            text=None,
            handler=None,
            *,
            style=None,
            allow_user=None,
            allow_ttl=100,
            html_tag=False,
        ):
            async def default(call):
                delete = getattr(call, "delete", None)
                if callable(delete):
                    return await delete()
                return None

            return self.inline(
                text or "Close",
                handler or default,
                style=style,
                allow_user=allow_user,
                allow_ttl=allow_ttl,
                html_tag=html_tag,
            )

        def request_phone(self, *args, **kwargs):
            raise NotImplementedError(
                "Rich page buttons cannot request phone; use buttons=[self.Button"
                ".request_phone(...)]"
            )

        def request_location(self, *args, **kwargs):
            raise NotImplementedError(
                "Rich page buttons cannot request location; use buttons=[self.Button"
                ".request_location(...)]"
            )

        def request_poll(self, *args, **kwargs):
            raise NotImplementedError(
                "Rich page buttons cannot request polls; use buttons=[self.Button"
                ".request_poll(...)]"
            )

        def with_icon(self, *args, **kwargs):
            raise NotImplementedError("Rich page buttons do not support icons")

        def style(self, button, style):
            if isinstance(button, RichCallbackButton):
                result = RichCallbackButton(button.text, button.token, style)
                validate_rich_button(result.text, result.token, result.style)
                return result
            if isinstance(button, RichPageButton):
                result = RichPageButton(button.text, button.type, button.attrs, style)
                validate_rich_page_button(result)
                return result
            raise TypeError("style accepts a rich button spec, not HTML")

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def on_load(self) -> None:
        """Called after the module is fully loaded."""
        if self._config is not None:
            try:
                saved = await self.kernel.get_module_config(self.name)
                if saved:
                    self._config.from_dict(saved)
                self.kernel.set_live_module_config(self.name, self._config)
            except Exception as error:
                self.log.warning("Failed to load config for %s: %s", self.name, error)

        for func in self._method_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as error:
                self.log.error(
                    "@method error in %s.%s: %s",
                    type(self).__name__,
                    func.__name__,
                    error,
                )

    async def on_install(self) -> None:
        for func in self._on_install_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as error:
                self.log.error(
                    "@on_install error in %s.%s: %s",
                    type(self).__name__,
                    func.__name__,
                    error,
                )

    async def on_reload(self) -> None:
        """Called after the module is reloaded."""

    async def on_config_update(self, key, old_value, new_value) -> None:
        """Called when kernel config is updated."""

    async def on_language_change(self, new_lang: str) -> None:
        """Called when the userbot language changes."""

    async def on_unload(self) -> None:
        for func in self._uninstall_funcs:
            try:
                result = func(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as error:
                self.log.error(
                    "@uninstall error in %s.%s: %s",
                    type(self).__name__,
                    func.__name__,
                    error,
                )

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------

    # Upstream declares `strings`/`config` as class dicts *and* as properties;
    # `__getattribute__` above routes reads to the accessors. Kept identical to
    # MCUB so module code behaves the same way.
    @property
    def config(self):  # noqa: F811
        return self._get_config()

    def _get_config(self):
        return self._config

    @property
    def strings(self) -> Strings:  # noqa: F811
        return self._get_strings()

    def _get_strings(self):
        if isinstance(self._strings, dict):
            self._strings = self._wrap_flat_strings(self._strings)
        if self._strings is None:
            raise AttributeError(
                f"strings is not initialized for {self.name}. Make sure the module"
                " defines 'strings' as a class dict attribute."
            )
        return self._strings

    def _wrap_flat_strings(self, payload: dict):
        data = copy.deepcopy(payload)
        if any(isinstance(v, str) for v in data.values()):
            data = {locale: dict(data) for locale in _FLAT_STRING_LOCALES}
        return Strings(self.kernel, data)


__all__ = [
    "ModuleBase",
    "_ModuleLoggerAdapter",
    "bot_command",
    "callback",
    "command",
    "error_handler",
    "event",
    "inline",
    "inline_temp",
    "loop",
    "method",
    "on_install",
    "on_uninstall",
    "owner",
    "owner_only",
    "permission",
    "permissions",
    "uninstall",
    "watcher",
]
