# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Native support for MCUB (Magic Core Userbot) modules inside Elys.

Both MCUB module styles are supported:

* **Class style** -- ``class MyMod(ModuleBase)`` with ``@command``, ``@loop``,
  ``@watcher``, ``@callback``, ``@bot_command`` and lifecycle hooks.
* **Kernel style** -- a ``# name:`` header plus ``def register(kernel)`` using
  ``kernel.register.*``.

Integration is two calls from :meth:`elys.loader.Modules.register_module`:
:func:`prepare` before the module body executes (so imports resolve and the
kernel exists) and :func:`finalize` after (to instantiate/register and publish
an Elys-visible adapter). A third entry point, :func:`handle_chosen_inline`,
is called from :mod:`elys.inline.events` to deliver ``inline_temp`` results.

Nothing here runs unless a module is actually detected as MCUB, so the layer
is inert for ordinary Elys modules.
"""

from __future__ import annotations

import inspect
import logging

from . import detect, virtualpkg
from .adapter import MCUBAdapterMixin, build_adapter_class, get_adapter_base
from .detect import (
    AMBIGUOUS,
    ELYS,
    MCUB_CLASS,
    MCUB_KERNEL,
    MCUB_LEGACY_CLIENT,
    MCUB_STYLES,
    UNKNOWN,
    detect_style,
    is_mcub_module,
    parse_header,
)
from .host import get_host, peek_host
from .kernel import KernelProxy, Registrations
from .module_base import ModuleBase
from ._vendor import MCUB_BRANCH, MCUB_UPSTREAM, MCUB_VERSION

logger = logging.getLogger(__name__)

__all__ = [
    "AMBIGUOUS",
    "ELYS",
    "MCUB_BRANCH",
    "MCUB_CLASS",
    "MCUB_KERNEL",
    "MCUB_LEGACY_CLIENT",
    "MCUB_STYLES",
    "MCUB_UPSTREAM",
    "MCUB_VERSION",
    "MCUBAdapterMixin",
    "MCUBContext",
    "ModuleBase",
    "UNKNOWN",
    "build_adapter_class",
    "detect_style",
    "diagnostics",
    "finalize",
    "get_adapter_base",
    "get_host",
    "handle_chosen_inline",
    "is_mcub_module",
    "parse_header",
    "peek_host",
    "prepare",
]


class MCUBContext:
    """State carried between :func:`prepare` and :func:`finalize`."""

    __slots__ = ("host", "kernel", "meta", "module_name", "name", "registrations", "style")

    def __init__(self, *, style, meta, name, module_name, host, kernel, registrations):
        self.style = style
        self.meta = meta
        self.name = name
        self.module_name = module_name
        self.host = host
        self.kernel = kernel
        self.registrations = registrations

    def __repr__(self) -> str:
        return f"<MCUBContext {self.name!r} style={self.style!r}>"


def _fallback_name(module_name: str) -> str:
    return str(module_name).rsplit(".", maxsplit=1)[-1] or "MCUB"


def prepare(module, source: str | None, modules) -> MCUBContext | None:
    """Detect and set up an MCUB module, or return ``None`` if it is not one.

    Must run **before** the module body executes. Kernel-style MCUB modules
    define ``def register(kernel)``, which collides with Elys's legacy
    ``module.register(module_name)`` fallback -- if we let such a module run
    unclassified, Elys passes a ``str`` where a kernel is expected and the real
    error is lost behind an ``AttributeError``.
    """
    if not source:
        return None

    style = detect_style(source)
    if style == AMBIGUOUS:
        from ..types import LoadError

        raise LoadError(
            "Module mixes Elys and MCUB APIs; refusing to guess which loader to"
            " use. Split it into one framework's style."
        )

    if style not in MCUB_STYLES:
        return None

    meta = parse_header(source)
    host = get_host(modules)

    ok, reason = _check_scop(source, host)
    if not ok:
        from ..types import LoadError

        raise LoadError(f"MCUB compatibility check failed: {reason}")

    # Upstream MCUB also honours `# meta name:`; safe to read here because the
    # module is already classified as MCUB.
    name = (
        meta.get("name")
        or meta.get("meta_name")
        or _fallback_name(getattr(module, "__name__", "mcub"))
    )
    registrations = Registrations(name)
    kernel = KernelProxy(name, registrations, host)

    # MCUB's own loader preloads these onto the module namespace, and modules
    # rely on the bare `kernel` / `client` globals.
    module.kernel = kernel
    module.client = kernel.client
    module.custom_prefix = host.prefix

    virtualpkg.build_module_namespace(module)

    logger.debug("Prepared MCUB module %s (style=%s)", name, style)
    return MCUBContext(
        style=style,
        meta=meta,
        name=name,
        module_name=getattr(module, "__name__", name),
        host=host,
        kernel=kernel,
        registrations=registrations,
    )


def _check_scop(source: str, host) -> tuple[bool, str]:
    from . import scop

    return scop.check_compatibility(source, host.inline_manager)


async def finalize(context: MCUBContext, module) -> type:
    """Instantiate/register the MCUB module and publish an Elys adapter.

    Returns the adapter class, which is also injected into the module namespace
    so Elys's own ``vars(module)`` scan picks it up unchanged.
    """
    instance = None

    if context.style == MCUB_CLASS:
        instance = _instantiate_class_module(context, module)
    else:
        await _run_register(context, module)

    name = context.name
    if instance is not None:
        declared = getattr(type(instance), "name", None)
        if declared and declared != "Unnamed":
            name = declared
        context.registrations.module_name = name
        context.kernel.module_name = name
        context.kernel.current_loading_module = name
        context.name = name

    description = _describe(context, instance)

    adapter_cls = build_adapter_class(
        name=name,
        style=context.style,
        meta=context.meta,
        description=description,
    )
    adapter_cls.mcub_instance = instance
    adapter_cls.mcub_module = module
    adapter_cls.registrations = context.registrations
    adapter_cls.host = context.host
    adapter_cls.kernel = context.kernel

    module.__dict__[adapter_cls.__name__] = adapter_cls
    module.__mcub_adapter__ = adapter_cls
    module.__mcub_context__ = context

    logger.info(
        "Loaded MCUB module %s (%s): %s",
        name,
        context.style,
        context.registrations.summary(),
    )
    return adapter_cls


def _instantiate_class_module(context: MCUBContext, module):
    cls = _find_module_base(module)
    if cls is None:
        from ..types import LoadError

        raise LoadError("MCUB class-style module defines no ModuleBase subclass")

    kernel = context.kernel
    return cls(kernel, kernel.client, kernel.register)


def _find_module_base(module) -> type | None:
    for value in vars(module).values():
        if (
            inspect.isclass(value)
            and issubclass(value, ModuleBase)
            and value is not ModuleBase
        ):
            return value
    return None


async def _run_register(context: MCUBContext, module) -> None:
    register = getattr(module, "register", None)
    if not callable(register):
        from ..types import LoadError

        raise LoadError("MCUB kernel-style module has no callable register()")

    argument = (
        context.kernel.client
        if context.style == MCUB_LEGACY_CLIENT
        else context.kernel
    )

    if inspect.iscoroutinefunction(register):
        await register(argument)
    else:
        result = register(argument)
        if inspect.isawaitable(result):
            await result


def _describe(context: MCUBContext, instance) -> str:
    if instance is not None:
        try:
            described = instance.get_description()
            if described:
                return described
        except Exception:
            logger.debug("MCUB description lookup failed", exc_info=True)

    raw = context.meta.get("description")
    if not raw:
        return ""

    parsed = detect.parse_localized_description(raw)
    if isinstance(parsed, str):
        return parsed

    language = getattr(context.host, "language", "en")
    for key in (language, "en", "ru"):
        if parsed.get(key):
            return parsed[key]
    return next(iter(parsed.values()), "")


async def handle_chosen_inline(inline_manager, update, query: str) -> bool:
    """Deliver a sent inline result to an MCUB ``inline_temp`` handler.

    Called from :meth:`elys.inline.events.Events._chosen_inline_handler`.
    Returns ``True`` when the result belonged to MCUB so Elys stops there.
    """
    host = peek_host()
    if host is None or not host.inline_temp_map:
        return False
    try:
        return await host.dispatch_chosen_inline(update, query)
    except Exception:
        logger.exception("MCUB chosen-inline dispatch failed")
        return False


def diagnostics() -> dict:
    """Snapshot for the ``.mcubcheck`` command and tests."""
    from .buttons import registry

    host = peek_host()
    return {
        "emulated_mcub_version": MCUB_VERSION,
        "upstream": f"{MCUB_UPSTREAM} ({MCUB_BRANCH})",
        "virtual_names": len(virtualpkg._modules),
        "contested_names": sorted(virtualpkg._contested),
        "modules": (
            {name: adapter.mcub_summary() for name, adapter in host.adapters.items()}
            if host
            else {}
        ),
        "callback_tokens": len(registry),
        "inline_temp": list(host.inline_temp_map) if host else [],
    }
