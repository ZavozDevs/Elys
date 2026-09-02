# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""
Vendored MCUB (Magic Core Userbot) components.

Every module in this package is a near-verbatim copy of MIT-licensed source
from the MCUB project, kept here so that MCUB modules loaded inside Elys see
byte-compatible behaviour instead of a hand-written approximation.

The leading underscore matters: the repository's ``.gitignore`` carries a
generic ``vendor/`` rule, so a directory literally named ``vendor`` would be
silently excluded from commits and the layer would break for anyone cloning.

    Upstream: https://github.com/hairpin01/MCUB-fork (branch ``dev``)
    License:  MIT
    Copyright (c) 2026 Шмэлькa | @hairpin01

Each file keeps its original SPDX identifier and copyright notice. Local
changes are limited to import rewiring (``core.*``/``utils.*`` -> relative,
``telethon`` -> ``elystl``, PyYAML -> ruamel.yaml) and are marked inline where
they are not purely mechanical.

Mapping to upstream paths:

    strings.py            <- utils/strings.py
    langpacks/__init__.py <- core/langpacks/__init__.py
    langpacks/*.yaml      <- core/langpacks/*.yaml (global groups only)
    langpacks/icons/      <- core/langpacks/icons/
    cache.py              <- core/lib/time/cache.py
    arg_parser.py         <- utils/arg_parser.py
    permissions.py        <- core/lib/base/permissions.py
    rich_buttons.py       <- core/lib/rich_buttons.py
    colors.py             <- core/lib/utils/colors.py
    emoji_parser.py       <- utils/emoji_parser.py
    html_parser.py        <- utils/html_parser.py
    module_config.py      <- core/lib/loader/module_config.py

Do not add Elys-specific logic here; put it in the parent package so that
re-syncing with upstream stays mechanical.
"""

MCUB_UPSTREAM = "https://github.com/hairpin01/MCUB-fork"
MCUB_BRANCH = "dev"
MCUB_VERSION = "1.4.6.1"

__all__ = ["MCUB_BRANCH", "MCUB_UPSTREAM", "MCUB_VERSION"]
