# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Source-level classification of module flavour.

MCUB kernel-style modules declare ``def register(kernel)``, which collides with
Elys's legacy ``module.register(module_name)`` fallback in
:meth:`elys.loader.Modules.register_module`. If we let such a module execute
unclassified, Elys hands a ``str`` to code expecting a kernel and the failure
surfaces as a baffling ``AttributeError``. So classification happens on the
source text, before ``exec_module``.
"""

from __future__ import annotations

import ast
import logging
import re
import typing

logger = logging.getLogger(__name__)

MCUB_CLASS = "mcub_class"
MCUB_KERNEL = "mcub_kernel"
MCUB_LEGACY_CLIENT = "mcub_client"
ELYS = "elys"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"

MCUB_STYLES = frozenset({MCUB_CLASS, MCUB_KERNEL, MCUB_LEGACY_CLIENT})

# `# name:` must stay *bare* here. `# meta name:` / `# meta developer:` /
# `# meta banner:` are the Hikka/Friendly-Telegram convention that Elys
# inherits, and treating them as MCUB headers made every Hikka module score on
# both sides at once and get rejected as ambiguous.
_HEADER_PATTERNS = {
    "name": r"^\s*#\s*name\s*:\s*(.+)$",
    "author": r"^\s*#\s*author\s*:\s*(.+)$",
    "version": r"^\s*#\s*version\s*:\s*(.+)$",
    "description": r"^\s*#\s*description\s*:\s*(.+)$",
    "banner_url": r"^\s*#\s*banner_url\s*:\s*(.+)$",
}

# Upstream MCUB also accepts `# meta name:`, so it is still read for metadata
# once a module has been classified -- just never used as a detection signal.
_META_PATTERNS = {
    "meta_name": r"^\s*#\s*meta\s+name\s*:\s*(.+)$",
    "meta_author": r"^\s*#\s*meta\s+developer\s*:\s*(.+)$",
    "meta_banner": r"^\s*#\s*meta\s+banner\s*:\s*(.+)$",
}

#: Any `# meta <key>:` directive is Hikka/Elys lineage evidence.
_HIKKA_META_RE = re.compile(r"^\s*#\s*meta\s+[\w-]+\s*:", re.MULTILINE | re.IGNORECASE)

# MCUB module namespaces that only ever exist inside MCUB.
_MCUB_IMPORT_ROOTS = (
    "core.lib",
    "core.langpacks",
    "core.version",
    "core_inline",
)
_MCUB_UTIL_MODULES = frozenset(
    {
        "utils",
        "utils.strings",
        "utils.helpers",
        "utils.arg_parser",
        "utils.security",
        "utils.platform",
        "utils.emoji_parser",
        "utils.html_parser",
        "utils.message_helpers",
        "utils.custom_placeholders",
        "utils.restart",
    }
)

# Decorators that exist in MCUB's module_base but never in Elys's loader.
_MCUB_ONLY_DECORATORS = frozenset(
    {
        "bot_command",
        "callback",
        "inline_temp",
        "owner_only",
        "permissions",
        "permission",
        "error_handler",
        "on_install",
        "on_uninstall",
        "uninstall",
        "method",
    }
)

# Elys/Hikka lineage markers.
_ELYS_ONLY_DECORATORS = frozenset({"tds", "translatable_docstring", "ratelimit"})
_ELYS_BASES = frozenset({"Module", "Library"})


def parse_header(code: str) -> dict:
    """Extract MCUB header comment directives from module source.

    ``# meta ...`` variants land under separate ``meta_*`` keys so that they can
    be used for metadata after classification without ever influencing it.
    """
    meta: dict[str, typing.Any] = {}

    for patterns in (_HEADER_PATTERNS, _META_PATTERNS):
        for key, pattern in patterns.items():
            match = re.search(pattern, code, re.MULTILINE | re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:
                    meta[key] = value

    meta["requires"] = parse_requires(code)
    return meta


def has_hikka_meta(code: str) -> bool:
    """True when the source carries a Hikka-style ``# meta <key>:`` directive."""
    return bool(_HIKKA_META_RE.search(code))


def parse_requires(code: str) -> list[str]:
    """Parse ``# requires:`` pip declarations plus ``dependencies = [...]``."""
    if isinstance(code, bytes):
        code = code.decode("utf-8", errors="ignore")
    if not isinstance(code, str):
        return []

    found: list[str] = []

    for match in re.finditer(
        r"^\s*#\s*requires\s*:\s*(.*)$", code, re.MULTILINE | re.IGNORECASE
    ):
        for token in re.split(r"[,\s]+", match.group(1).strip()):
            token = token.strip().rstrip(",")
            if token and not token.startswith(("-", "_", ".")):
                found.append(token)

    match = re.search(
        r"^\s*dependencies\s*=\s*[\[\(]([^\]\)]*)[\]\)]", code, re.MULTILINE
    )
    if match:
        for token in re.findall(r"""['"]([^'"]+)['"]""", match.group(1)):
            token = token.strip().rstrip(",")
            if token and not token.startswith(("-", "_", ".")):
                found.append(token)

    return list(dict.fromkeys(found))


def parse_localized_description(raw: str) -> dict | str:
    """Parse ``en: ... / ru: ... / uk: ...`` description headers.

    MCUB writes multi-locale descriptions on one comment line separated by
    ``/``. Anything that does not match that shape is returned untouched.
    """
    if not isinstance(raw, str) or ":" not in raw:
        return raw

    parts = [chunk.strip() for chunk in raw.split("/")]
    result = {}
    for part in parts:
        match = re.match(r"^([a-z]{2})\s*:\s*(.+)$", part, re.IGNORECASE)
        if not match:
            return raw
        result[match.group(1).lower()] = match.group(2).strip()

    return result or raw


def _dotted(node: ast.AST) -> list[str]:
    """Flatten ``a.b.c`` attribute chains into ``["a", "b", "c"]``."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    elif isinstance(current, ast.Call):
        parts.extend(reversed(_dotted(current.func)))
    return list(reversed(parts))


def _decorator_names(node) -> list[list[str]]:
    chains = []
    for decorator in getattr(node, "decorator_list", []):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        chain = _dotted(target)
        if chain:
            chains.append(chain)
    return chains


class _Scorer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.mcub = 0
        self.elys = 0
        self.register_param: str | None = None
        # Strong, unambiguous markers. Only these decide a classification;
        # the numeric scores are tie-breakers for modules with no strong marker.
        self.has_module_base = False
        self.has_mcub_import = False
        self.has_kernel_api = False
        self.has_elys_base = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith(_MCUB_IMPORT_ROOTS):
                self.has_mcub_import = True
                self.mcub += 2
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        names = {alias.name for alias in node.names}

        if node.level > 0:
            # `from .. import loader` is the Hikka/Elys idiom.
            if "loader" in names or "utils" in names:
                self.has_elys_base = True
                self.elys += 2
        elif module.startswith(_MCUB_IMPORT_ROOTS):
            self.has_mcub_import = True
            self.mcub += 2
            if "ModuleBase" in names:
                self.has_module_base = True
                self.mcub += 2
        elif module in _MCUB_UTIL_MODULES:
            self.mcub += 1
        elif module in {"hikka", "heroku", "hikka.loader", "heroku.loader"}:
            self.has_elys_base = True
            self.elys += 2

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            chain = _dotted(base)
            if not chain:
                continue
            leaf = chain[-1]
            if leaf == "ModuleBase":
                self.has_module_base = True
                self.mcub += 3
            elif leaf in _ELYS_BASES and (len(chain) == 1 or chain[0] == "loader"):
                self.has_elys_base = True
                self.elys += 3

        for chain in _decorator_names(node):
            if chain[-1] in _ELYS_ONLY_DECORATORS:
                self.has_elys_base = True
                self.elys += 2

        self.generic_visit(node)

    def _visit_function(self, node) -> None:
        for chain in _decorator_names(node):
            leaf = chain[-1]
            if leaf in _MCUB_ONLY_DECORATORS:
                self.mcub += 1
            elif leaf in _ELYS_ONLY_DECORATORS:
                self.has_elys_base = True
                self.elys += 2
            elif chain[:2] == ["kernel", "register"]:
                self.has_kernel_api = True
                self.mcub += 3
            elif chain[:1] == ["loader"] and leaf in {
                "raw_handler",
                "need_update",
                "sudo",
                "unrestricted",
                "inline_everyone",
            }:
                self.has_elys_base = True
                self.elys += 2

        self.generic_visit(node)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Attribute(self, node: ast.Attribute) -> None:
        chain = _dotted(node)
        if chain[:2] == ["kernel", "register"]:
            self.has_kernel_api = True
            self.mcub += 2
        elif chain[:2] == ["self", "subinline"]:
            self.mcub += 2
        elif chain[:2] == ["loader", "ModuleConfig"]:
            self.has_elys_base = True
            self.elys += 2
        self.generic_visit(node)


def _top_level_register(tree: ast.Module) -> str | None:
    """Return the first parameter name of a module-level ``register`` def."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == "register"
        ):
            args = node.args.posonlyargs + node.args.args
            if args:
                return args[0].arg
            return ""
    return None


def detect_style(code: str) -> str:
    """Classify module source as MCUB, Elys, ambiguous or unknown."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return UNKNOWN

    scorer = _Scorer()
    scorer.visit(tree)

    register_param = _top_level_register(tree)
    header = parse_header(code)
    has_name_header = bool(header.get("name"))
    kernel_register = register_param in {"kernel", "k"}

    # Signals are tiered, because code outranks comments. A base class or an
    # import is a fact about the module; a header comment is a claim about it,
    # and the two ecosystems disagree about who owns `# name:`/`# meta name:`.
    #
    # Tier 1 - code-level markers. `def register(kernel)` counts here: MCUB
    # requires it for function-style modules and nothing in the Hikka lineage
    # produces it (Elys's legacy fallback is `register(module_name)`).
    code_mcub = (
        scorer.has_module_base
        or scorer.has_mcub_import
        or scorer.has_kernel_api
        or kernel_register
    )
    code_elys = scorer.has_elys_base

    if code_mcub and code_elys:
        logger.debug(
            "Ambiguous module flavour (mcub=%d elys=%d)", scorer.mcub, scorer.elys
        )
        return AMBIGUOUS

    # An Elys/Hikka module stays Elys even if it trips weak MCUB heuristics
    # such as `import utils` or a method named `callback`.
    if code_elys:
        return ELYS

    # Tier 2 - header comments, consulted only when the code says nothing.
    if not code_mcub:
        if has_hikka_meta(code):
            # `# meta name:` / `# meta developer:` / `# meta banner:` are Hikka
            # lineage, never MCUB.
            return ELYS
        return ELYS if scorer.elys else UNKNOWN

    if scorer.has_module_base:
        return MCUB_CLASS

    if kernel_register:
        return MCUB_KERNEL

    if register_param == "client":
        return MCUB_LEGACY_CLIENT

    if register_param is not None and has_name_header:
        # Unannotated first parameter but a `# name:` header present: MCUB
        # treats this as kernel-style, so we do too.
        return MCUB_KERNEL

    return MCUB_CLASS if scorer.mcub >= 2 else UNKNOWN


def is_mcub_module(code: str) -> bool:
    return detect_style(code) in MCUB_STYLES
