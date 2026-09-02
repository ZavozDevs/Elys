# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Virtual package tree that lets MCUB modules import their own namespaces.

MCUB modules import from ``core.lib.*``, ``core_inline.*``, ``utils.*`` and
``telethon``. None of those exist in Elys, and two of them (``core``, ``utils``)
are generic enough that a third-party distribution could legitimately own them.

The strategy, mirroring MCUB's own ``hikka_compat.fake_package`` in reverse:

1. Build the fake tree once as real :class:`types.ModuleType` objects, each
   given an importlib spec so ``importlib.util.find_spec()`` keeps working
   (Elys's ``# requires:`` handling calls it, and it raises ``ValueError`` on a
   module whose ``__spec__`` is ``None``).
2. Claim the names in ``sys.modules`` only when they are free. Names already
   owned by a real distribution are recorded as contested and never clobbered.
3. Execute MCUB module code with a scoped ``__import__`` in its ``__builtins__``.
   This is what makes the layer safe: because a function's ``import`` statement
   resolves ``__import__`` through its module globals at *call* time, the
   override also covers lazy imports inside command handlers, which MCUB
   modules use heavily.
4. ``telethon`` always goes through the scoped hook so that a real Telethon
   installed alongside ``elystl`` can never leak cross-fork TLObjects into a
   module that Elys will hand ``elystl`` objects to.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util
import logging
import sys
import threading
import types
import typing

logger = logging.getLogger(__name__)

#: Root package names the layer fabricates.
ALIAS_ROOTS = ("core", "core_inline", "utils")

#: MCUB targets Telethon; Elys ships the ``elystl`` fork with the same layout.
TELETHON_ROOT = "telethon"
ELYSTL_ROOT = "elystl"

_lock = threading.RLock()
_modules: dict[str, types.ModuleType] = {}
_claimed: set[str] = set()
_contested: set[str] = set()
_installed = False


def _new_module(name: str, *, package: bool) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name if package else name.rpartition(".")[0]
    if package:
        module.__path__ = []  # type: ignore[attr-defined]
    module.__spec__ = importlib.util.spec_from_loader(name, loader=None)
    if package and module.__spec__ is not None:
        module.__spec__.submodule_search_locations = []
    module.__mcub_virtual__ = True
    return module


def _register(name: str, *, package: bool = False) -> types.ModuleType:
    """Create (or fetch) a virtual module and link it onto its parent."""
    existing = _modules.get(name)
    if existing is not None:
        return existing

    module = _new_module(name, package=package)
    _modules[name] = module

    parent_name, _, leaf = name.rpartition(".")
    if parent_name:
        parent = _modules.get(parent_name) or _register(parent_name, package=True)
        setattr(parent, leaf, module)

    return module


def _populate(name: str, source: typing.Any, *, package: bool = False) -> None:
    """Copy the public surface of *source* onto virtual module *name*."""
    module = _register(name, package=package)
    exported = getattr(source, "__all__", None)
    names = exported or [n for n in dir(source) if not n.startswith("_")]
    for attr in names:
        try:
            setattr(module, attr, getattr(source, attr))
        except AttributeError:
            continue


def _build_tree() -> None:
    """Assemble the whole fake MCUB package tree."""
    from . import bridge_api

    for root in ALIAS_ROOTS:
        _register(root, package=True)
    for pkg in (
        "core.lib",
        "core.lib.loader",
        "core.lib.types",
        "core.lib.base",
        "core.lib.time",
        "core.lib.utils",
        "core.langpacks",
        "core_inline.api",
        "core_inline.lib",
    ):
        _register(pkg, package=True)

    for name, source in bridge_api.virtual_module_sources().items():
        _populate(name, source, package=name in {"utils", "core.langpacks"})


def _telethon_target(name: str) -> str:
    suffix = name[len(TELETHON_ROOT) :]
    return f"{ELYSTL_ROOT}{suffix}"


def _resolve_telethon(name: str) -> types.ModuleType | None:
    """Map ``telethon[.x.y]`` onto the equivalent ``elystl`` module."""
    if name != TELETHON_ROOT and not name.startswith(TELETHON_ROOT + "."):
        return None

    cached = _modules.get(name)
    if cached is not None:
        return cached

    try:
        resolved = importlib.import_module(_telethon_target(name))
    except ImportError:
        # Fork-only submodules (e.g. telethon.client.protection) legitimately
        # do not exist here; MCUB modules guard those imports themselves.
        return None

    _modules[name] = resolved
    return resolved


def _alias_for_import(name: str, fromlist) -> types.ModuleType | None:
    """Return the module ``__import__(name, fromlist=...)`` should yield."""
    target = _resolve_telethon(name) or _modules.get(name)
    if target is None:
        return None
    if fromlist:
        return target
    # `import a.b` binds the root package, matching CPython semantics.
    root = name.partition(".")[0]
    return _resolve_telethon(root) or _modules.get(root) or target


def install() -> None:
    """Build the tree and claim every free name in ``sys.modules``."""
    global _installed
    with _lock:
        if _installed:
            return

        _build_tree()

        for name, module in _modules.items():
            current = sys.modules.get(name)
            if current is None:
                sys.modules[name] = module
                _claimed.add(name)
            elif current is not module:
                _contested.add(name)

        if _contested:
            logger.debug(
                "MCUB virtual names already owned by real packages, scoped"
                " imports will shadow them for MCUB modules only: %s",
                ", ".join(sorted(_contested)),
            )

        _installed = True
        logger.debug("MCUB virtual package tree installed (%d names)", len(_modules))


def uninstall() -> None:
    """Release claimed names. Only safe once no MCUB module remains loaded."""
    global _installed
    with _lock:
        for name in sorted(_claimed, key=len, reverse=True):
            if sys.modules.get(name) is _modules.get(name):
                sys.modules.pop(name, None)
        _claimed.clear()
        _contested.clear()
        _modules.clear()
        _installed = False


def get_virtual_module(name: str) -> types.ModuleType | None:
    install()
    return _modules.get(name)


def make_import_hook() -> typing.Callable:
    """Build the ``__import__`` replacement injected into MCUB module globals."""
    install()
    original = builtins.__import__

    def _mcub_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name:
            root = name.partition(".")[0]
            # telethon is always redirected; the fake tree only takes over when
            # the name is contested or not yet resolvable normally.
            if root == TELETHON_ROOT or root in ALIAS_ROOTS:
                alias = _alias_for_import(name, fromlist)
                if alias is not None and (
                    root == TELETHON_ROOT
                    or name in _contested
                    or sys.modules.get(name) is _modules.get(name)
                ):
                    return alias

        try:
            return original(name, globals, locals, fromlist, level)
        except ImportError:
            if level == 0:
                alias = _alias_for_import(name, fromlist)
                if alias is not None:
                    return alias
            raise

    return _mcub_import


def build_module_namespace(module: types.ModuleType) -> dict:
    """Give *module* a ``__builtins__`` whose ``__import__`` is redirected."""
    namespace = module.__dict__
    namespace["__builtins__"] = {
        **builtins.__dict__,
        "__import__": make_import_hook(),
    }
    return namespace
