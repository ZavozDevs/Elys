# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""What each virtual MCUB module name resolves to.

:mod:`elys.mcub_compat.virtualpkg` builds the package tree; this module decides
what lands inside it. Names that map onto real implementations point at our own
modules or the vendored MIT ports; the rest are small shims defined here,
because they are only needed to satisfy an import in module code.
"""

import logging
import types
import typing
from urllib.parse import urlparse

from . import events as _events
from . import helpers as _helpers
from . import inline as _inline
from . import module_base as _module_base
from . import scop as _scop
from ._vendor import arg_parser as _arg_parser
from ._vendor import cache as _cache
from ._vendor import colors as _colors
from ._vendor import decorators as _decorators
from ._vendor import emoji_parser as _emoji_parser
from ._vendor import html_parser as _html_parser
from ._vendor import langpacks as _langpacks
from ._vendor import module_config as _module_config
from ._vendor import permissions as _permissions
from ._vendor import rich_buttons as _rich_buttons
from ._vendor import strings as _strings_mod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# exceptions (core.lib.utils.exceptions)
# ---------------------------------------------------------------------------


class CommandConflictError(Exception):
    """Raised when two modules claim the same command."""

    def __init__(self, message: str = "", conflict_type: str = "", command: str = ""):
        super().__init__(message)
        self.conflict_type = conflict_type
        self.command = command


class McubTelethonError(Exception):
    """MCUB-Telethon specific failure."""


class CallInsecure(Exception):
    """Raised by MCUB when a module touches a protected attribute.

    Elys's compatibility layer is deliberately not a sandbox, so nothing here
    raises this; it exists only so ``except CallInsecure`` keeps parsing.
    """


class ScamModuleDetected(Exception):
    """MCUB antiscam rejection."""


# ---------------------------------------------------------------------------
# core.lib.loader.repository
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_remote_url(url: str) -> tuple[bool, str]:
    """Mirror MCUB's remote-URL gate for ``import_lib`` and installers."""
    try:
        parsed = urlparse(str(url))
    except Exception:
        return False, "Malformed URL"
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, "Only http(s) URLs are allowed"
    if not parsed.netloc:
        return False, "URL has no host"
    return True, ""


# ---------------------------------------------------------------------------
# core.lib.utils.logger
# ---------------------------------------------------------------------------


class ErrorFormatter:
    """Minimal stand-in for MCUB's traceback formatter."""

    @staticmethod
    def format_exception(error: BaseException, *, limit: int | None = None) -> str:
        import traceback

        return "".join(
            traceback.format_exception(type(error), error, error.__traceback__, limit)
        )

    @staticmethod
    def short(error: BaseException) -> str:
        return f"{type(error).__name__}: {error}"


# ---------------------------------------------------------------------------
# core.lib.loader.security
# ---------------------------------------------------------------------------


class SecurityChats:
    """Placeholder for MCUB's per-chat security store.

    Elys enforces chat security in ``elys.security``/``elys.dispatcher`` before
    a module ever sees the message, so this only needs to answer permissively.
    """

    def can_process_event(self, *args, **kwargs) -> bool:
        return True

    def is_allowed(self, *args, **kwargs) -> bool:
        return True


# ---------------------------------------------------------------------------
# core.version
# ---------------------------------------------------------------------------


class VersionManager:
    """MCUB version helpers, answered from Elys's emulated API level."""

    @staticmethod
    def compare_versions(left: str, right: str) -> int:
        return _scop.compare_versions(left, right)

    @staticmethod
    async def get_latest_kernel_version() -> str:
        from ._vendor import MCUB_VERSION

        return MCUB_VERSION

    @staticmethod
    def detect_branch() -> str:
        from ..version import branch

        return str(branch)

    @staticmethod
    def get_commit_sha() -> str:
        from .. import utils

        return utils.get_git_hash() or ""

    @staticmethod
    def get_github_commit_url() -> str:
        from .. import utils

        return utils.get_commit_url() or ""


# ---------------------------------------------------------------------------
# core_inline.api.inline
# ---------------------------------------------------------------------------


def register_inline_callback(
    kernel,
    callback,
    *,
    args=None,
    kwargs=None,
    ttl: int = 900,
    token: str | None = None,
    data=None,
    allow_user=None,
) -> str:
    """Register a callback and return its token (MCUB's low-level helper)."""
    from .buttons import registry

    return registry.register(
        callback,
        module_name=getattr(kernel, "module_name", "unknown"),
        args=args or [],
        kwargs=kwargs or {},
        data=data,
        ttl=ttl,
        allow_user=allow_user,
        token=token,
    )


def make_cb_button(
    kernel,
    text: str,
    callback,
    *,
    args=None,
    kwargs=None,
    ttl: int = 900,
    token: str | None = None,
    icon: int | None = None,
    style: str | None = None,
    allow_user=None,
    allow_ttl: int = 100,
    data=None,
):
    """MCUB's standalone callback-button builder used by kernel-style modules."""
    from .buttons import make_callback_button

    return make_callback_button(
        text,
        callback,
        module_name=getattr(kernel, "module_name", "unknown"),
        args=args or (),
        kwargs=kwargs or {},
        data=data,
        ttl=ttl,
        allow_user=allow_user,
        allow_ttl=allow_ttl,
        permissions=getattr(kernel, "callback_permissions", None),
        style=style,
        icon=icon,
        token=token,
    )


class InlineButton:
    """Static button builders from MCUB's ``CodeInline`` facade."""

    @staticmethod
    def url_button(text: str, url: str):
        from elystl import Button

        return Button.url(text, url)

    @staticmethod
    def switch_button(text: str, query: str = "", same_peer: bool = True):
        from elystl import Button

        return Button.switch_inline(text, query=query, same_peer=same_peer)


class InlineKeyboard:
    """Row builder matching MCUB's ``InlineKeyboard().row(...).rows`` usage."""

    def __init__(self) -> None:
        self.rows: list[list] = []

    def row(self, *buttons):
        self.rows.append([b for b in buttons if b is not None])
        return self

    def add(self, *buttons):
        return self.row(*buttons)


class CodeInline:
    """Thin facade so ``ui.action(...)`` keeps working."""

    def __init__(self, kernel, ttl: int = 900) -> None:
        self._kernel = kernel
        self._ttl = ttl

    def action(self, text: str, callback, *, args=None, kwargs=None, **extra):
        return make_cb_button(
            self._kernel,
            text,
            callback,
            args=args,
            kwargs=kwargs,
            ttl=self._ttl,
            **extra,
        )


class InlineBot:
    """Placeholder for ``core_inline.bot.InlineBot``."""

    def __init__(self, kernel=None, *args, **kwargs) -> None:
        self.kernel = kernel


class InlineHandlers:
    """Placeholder for ``core_inline.handlers.InlineHandlers``.

    MCUB modules only reach for this to look up stored form records; Elys owns
    its own unit registry, so form lookups return ``None`` and callers fall
    back to their non-form path.
    """

    def __init__(self, kernel=None, bot_client=None) -> None:
        self.kernel = kernel
        self.bot_client = bot_client

    def get_inline_form(self, form_id):
        return None

    def create_inline_form(self, *args, **kwargs):
        raise NotImplementedError(
            "MCUB's raw inline form store is not available on Elys; use"
            " kernel.inline.form(...) instead"
        )


# ---------------------------------------------------------------------------
# core.lib.loader.hikka_compat  (MCUB's own Hikka bridge -- inert here)
# ---------------------------------------------------------------------------


def is_hikka_module(source_code: str) -> bool:
    """Elys runs Hikka-lineage modules natively, so nothing needs the bridge."""
    return False


async def load_hikka_module(*args, **kwargs):
    raise NotImplementedError(
        "Elys loads Hikka/Heroku modules natively; MCUB's hikka_compat bridge"
        " is not needed and not provided"
    )


async def unload_hikka_module(*args, **kwargs) -> bool:
    return False


# ---------------------------------------------------------------------------
# core.lib.loader.kernel_proxy
# ---------------------------------------------------------------------------


def wrap_event_for_module(event, module_name: str = "", kernel=None):
    return _events.wrap_event(event, module_name, kernel)


def get_module_kernel(kernel, module_name: str, is_system: bool = False):
    return kernel


def get_module_client(kernel, module_name: str, is_system: bool = False):
    return getattr(kernel, "client", None)


def get_module_register(kernel, module_name: str, is_system: bool = False):
    return getattr(kernel, "register", None)


def get_module_db(kernel, module_name: str, is_system: bool = False):
    return getattr(kernel, "db_manager", None)


def get_module_config(kernel, module_name: str, is_system: bool = False):
    return getattr(kernel, "config", None)


# ---------------------------------------------------------------------------
# core.lib.time.scheduler
# ---------------------------------------------------------------------------


class Scheduler:
    """Degraded scheduler.

    MCUB's scheduler is only used by a handful of modules and always has an
    ``@loop`` alternative, so rather than duplicate a task engine we log and
    no-op. Callers get a falsy task id and can fall back.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._warned = False

    def _warn(self, method: str) -> None:
        if not self._warned:
            logger.warning(
                "MCUB scheduler.%s is unsupported on Elys; use @loop instead",
                method,
            )
            self._warned = True

    def add_interval_task(self, *args, **kwargs):
        self._warn("add_interval_task")
        return None

    def add_daily_task(self, *args, **kwargs):
        self._warn("add_daily_task")
        return None

    def add_task(self, *args, **kwargs):
        self._warn("add_task")
        return None

    def cancel_task(self, *args, **kwargs) -> bool:
        return False


# ---------------------------------------------------------------------------
# core.lib.loader.register  (only the pieces modules import directly)
# ---------------------------------------------------------------------------


def _register_module_source() -> types.SimpleNamespace:
    from .kernel import EVENT_TYPE_ALIASES, InfiniteLoop, Register  # noqa: F401
    from .watchers import passes_filters

    return types.SimpleNamespace(
        InfiniteLoop=InfiniteLoop,
        Register=Register,
        EVENT_TYPE_ALIASES=EVENT_TYPE_ALIASES,
        _watcher_passes_filters=passes_filters,
    )


# ---------------------------------------------------------------------------
# core.lib.types
# ---------------------------------------------------------------------------


def _types_source() -> types.SimpleNamespace:
    from .kernel import KernelProxy, RegisterProxy

    return types.SimpleNamespace(
        Event=_events.MCUBEvent,
        Message=_events.MCUBEvent,
        InlineMessage=_events.MCUBCallbackEvent,
        InlineQuery=_events.MCUBInlineQuery,
        Kernel=KernelProxy,
        Register=RegisterProxy,
        Client=object,
    )


def _security_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(SecurityChats=SecurityChats)


def _base_database_source() -> types.SimpleNamespace:
    from .db import MCUBDatabase

    return types.SimpleNamespace(DatabaseManager=MCUBDatabase)


def _base_client_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(Client=object)


def _base_config_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(Config=dict)


def _inline_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        InlineManager=_inline.MCUBInlineManager,
        InlineMessage=_events.MCUBCallbackEvent,
    )


def _security_utils_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        safe_extract_zip=_helpers.safe_extract_zip,
        safe_extract_archive=_helpers.safe_extract_archive,
        get_db_path=_helpers.get_db_path,
    )


def _platform_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        get_platform=_helpers.get_platform,
        is_termux=_helpers.is_termux,
        is_wsl=_helpers.is_wsl,
    )


def _restart_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(restart_kernel=_helpers.restart_kernel)


def _placeholders_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        resolve_placeholders=_helpers.resolve_placeholders,
        register_decorated_placeholders=_helpers.register_decorated_placeholders,
        unregister_scope=_helpers.unregister_scope,
        config_placeholders=_helpers.config_placeholders,
    )


def _message_helpers_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        answer=_helpers.answer,
        answer_file=_helpers.answer_file,
        edit_with_html=_helpers.edit_with_html,
        reply_with_html=_helpers.reply_with_html,
        send_with_html=_helpers.send_with_html,
        send_file_with_html=_helpers.send_file_with_html,
        clean_html_fallback=_helpers.clean_html_fallback,
    )


def _exceptions_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        CommandConflictError=CommandConflictError,
        McubTelethonError=McubTelethonError,
        CallInsecure=CallInsecure,
        ScamModuleDetected=ScamModuleDetected,
    )


def _repository_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(validate_remote_url=validate_remote_url)


def _logger_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(ErrorFormatter=ErrorFormatter)


def _kernel_proxy_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        wrap_event_for_module=wrap_event_for_module,
        get_module_kernel=get_module_kernel,
        get_module_client=get_module_client,
        get_module_register=get_module_register,
        get_module_db=get_module_db,
        get_module_config=get_module_config,
        CallInsecure=CallInsecure,
    )


def _hikka_compat_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        is_hikka_module=is_hikka_module,
        load_hikka_module=load_hikka_module,
        unload_hikka_module=unload_hikka_module,
    )


def _version_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(VersionManager=VersionManager)


def _scheduler_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(Scheduler=Scheduler, TaskScheduler=Scheduler)


def _api_inline_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        make_cb_button=make_cb_button,
        register_inline_callback=register_inline_callback,
        InlineButton=InlineButton,
        InlineKeyboard=InlineKeyboard,
        CodeInline=CodeInline,
    )


def _event_helpers_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        wrap_event_for_module=wrap_event_for_module,
        get_chat_id=_helpers.get_chat_id,
        get_thread_id=_helpers.get_thread_id,
    )


def _compat_source() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        ModuleCompatChecker=_ScopChecker,
        check_compatibility=_scop.check_compatibility,
        parse_scop_directives=_scop.parse_scop_directives,
    )


class _ScopChecker:
    """``ModuleCompatChecker``-shaped wrapper over :mod:`.scop`."""

    def __init__(self, kernel=None) -> None:
        self.kernel = kernel

    async def check_module_compatibility(self, code: str) -> tuple[bool, str]:
        inline = getattr(self.kernel, "_inline_manager", None)
        return _scop.check_compatibility(code, inline)


# ---------------------------------------------------------------------------
# the map
# ---------------------------------------------------------------------------


def virtual_module_sources() -> dict[str, typing.Any]:
    """Return ``{virtual module name: object whose attributes to expose}``."""
    return {
        # core.lib.loader
        "core.lib.loader.module_base": _module_base,
        "core.lib.loader.base": _module_base,
        "core.lib.loader.decorators": _decorators,
        "core.lib.loader.module_config": _module_config,
        "core.lib.loader.register": _register_module_source(),
        "core.lib.loader.inline": _inline_source(),
        "core.lib.loader.repository": _repository_source(),
        "core.lib.loader.security": _security_source(),
        "core.lib.loader.kernel_proxy": _kernel_proxy_source(),
        "core.lib.loader.hikka_compat": _hikka_compat_source(),
        "core.lib.loader.compat": _compat_source(),
        "core.lib.loader.protection": types.SimpleNamespace(),
        # core.lib
        "core.lib.rich_buttons": _rich_buttons,
        "core.lib.types": _types_source(),
        "core.lib.types.event": _types_source(),
        "core.lib.types.message": _types_source(),
        "core.lib.types.client": _base_client_source(),
        "core.lib.types.kernel": _types_source(),
        "core.lib.types.register": _types_source(),
        "core.lib.types.inline_message": _types_source(),
        "core.lib.base.permissions": _permissions,
        "core.lib.base.database": _base_database_source(),
        "core.lib.base.client": _base_client_source(),
        "core.lib.base.config": _base_config_source(),
        "core.lib.time.cache": _cache,
        "core.lib.time.scheduler": _scheduler_source(),
        "core.lib.utils.exceptions": _exceptions_source(),
        "core.lib.utils.logger": _logger_source(),
        "core.lib.utils.colors": _colors,
        "core.lib.utils.event_helpers": _event_helpers_source(),
        "core.lib.utils.profiler": types.SimpleNamespace(),
        # core
        "core.langpacks": _langpacks,
        "core.version": _version_source(),
        # core_inline
        "core_inline.api.inline": _api_inline_source(),
        "core_inline.bot": types.SimpleNamespace(InlineBot=InlineBot),
        "core_inline.lib.manager": _inline_source(),
        "core_inline.handlers": types.SimpleNamespace(InlineHandlers=InlineHandlers),
        # utils
        "utils": _helpers,
        "utils.strings": _strings_mod,
        "utils.helpers": _helpers,
        "utils.arg_parser": _arg_parser,
        "utils.security": _security_utils_source(),
        "utils.platform": _platform_source(),
        "utils.emoji_parser": _emoji_parser,
        "utils.html_parser": _html_parser,
        "utils.message_helpers": _message_helpers_source(),
        "utils.custom_placeholders": _placeholders_source(),
        "utils.restart": _restart_source(),
    }
