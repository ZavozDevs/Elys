# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""``# scop:`` compatibility directives for MCUB modules.

Reimplements MCUB's ``ModuleCompatChecker`` against the Elys environment.
Kernel version comparisons are resolved against the MCUB API level Elys
emulates (``_vendor.MCUB_VERSION``) rather than Elys's own version, because a
module author writing ``# scop: kernel min v1.4.0`` is declaring a required
MCUB API level.
"""

from __future__ import annotations

import logging
import shutil

from ._vendor import MCUB_VERSION

logger = logging.getLogger(__name__)

KNOWN_SCOPES = frozenset({"kernel", "inline", "ffmpeg"})


def parse_scop_directives(code: str) -> list[tuple[str, str]]:
    """Return every ``# scop:`` directive as a ``(scope, params)`` pair.

    ``# scop: kernel min v1.0.2`` -> ``("kernel", "min v1.0.2")``
    ``# scop: inline``            -> ``("inline", "")``
    """
    directives: list[tuple[str, str]] = []

    for line in code.split("\n"):
        stripped = line.strip()
        # MCUB writes "# scop:", but "# scope:" appears in its own modules too.
        for marker in ("# scop:", "# scope:"):
            if stripped.startswith(marker):
                rest = stripped[len(marker) :].strip()
                scope, _, params = rest.partition(" ")
                directives.append((scope, params.strip()))
                break

    return directives


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for chunk in str(value).strip().lstrip("v").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def compare_versions(left: str, right: str) -> int:
    a, b = _version_tuple(left), _version_tuple(right)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return (a > b) - (a < b)


def _check_kernel_scope(params: str) -> tuple[bool, str]:
    parts = params.split()
    if not parts:
        return True, ""

    current = MCUB_VERSION

    if parts[0] == "min":
        if len(parts) >= 2 and parts[1].startswith("v"):
            required = parts[1][1:]
            if compare_versions(current, required) < 0:
                return False, (
                    f"Module requires MCUB kernel version >= {required}, "
                    f"Elys emulates {current}"
                )
    elif parts[0] == "max":
        if len(parts) >= 2 and parts[1].startswith("v"):
            required = parts[1][1:]
            if compare_versions(current, required) > 0:
                return False, (
                    f"Module requires MCUB kernel version <= {required}, "
                    f"Elys emulates {current}"
                )
    elif parts[0].startswith("v"):
        spec = parts[0][1:]
        # "[__lastest__]" (sic) means "whatever is newest upstream". Elys cannot
        # resolve that without hitting the network, so treat it as satisfied.
        if spec != "[__lastest__]" and compare_versions(current, spec) != 0:
            return False, (
                f"Module requires MCUB kernel version exactly {spec}, "
                f"Elys emulates {current}"
            )

    return True, ""


def _check_inline_scope(inline_manager) -> tuple[bool, str]:
    if inline_manager is None or not getattr(inline_manager, "init_complete", False):
        return False, "Module requires an inline bot, but Elys has none configured"
    return True, ""


def _check_ffmpeg_scope() -> tuple[bool, str]:
    if shutil.which("ffmpeg") is None:
        return False, "Module requires ffmpeg to be installed on the system"
    return True, ""


def check_compatibility(code: str, inline_manager=None) -> tuple[bool, str]:
    """Verify every ``# scop:`` directive, returning ``(ok, reason)``.

    Unknown scopes are ignored rather than rejected so that new MCUB directives
    do not hard-fail modules that would otherwise work.
    """
    for scope, params in parse_scop_directives(code):
        if scope == "kernel":
            ok, reason = _check_kernel_scope(params)
        elif scope == "inline":
            ok, reason = _check_inline_scope(inline_manager)
        elif scope == "ffmpeg":
            ok, reason = _check_ffmpeg_scope()
        else:
            logger.debug("Ignoring unknown MCUB scop directive: %s %s", scope, params)
            continue

        if not ok:
            return False, reason

    return True, ""
