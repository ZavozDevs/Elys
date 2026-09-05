# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import atexit
import logging
import os
import random
import signal
import sys
from collections.abc import Callable


async def fw_protect():
    await asyncio.sleep(random.randint(1000, 2000) / 1000)


def get_startup_callback() -> Callable:
    return lambda *_: os.execl(
        sys.executable,
        sys.executable,
        "-m",
        os.path.relpath(os.path.abspath(os.path.dirname(os.path.abspath(__file__)))),
        *sys.argv[1:],
    )


def die():
    """Platform-dependent way to kill the current process group"""
    match True:
        case _ if "DOCKER" in os.environ:
            sys.exit(0)
        case _ if sys.platform == "win32":
            sys.exit(0)
        case _:
            os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)


def restart():
    if "--sandbox" in " ".join(sys.argv):
        exit(0)

    if "ELYS_DO_NOT_RESTART2" in os.environ:
        print(
            "ElysTL version 1.0.2 or higher is required, use `pip install heroku-tl-new -U` for update."
        )
        sys.exit(0)

    logging.getLogger().setLevel(logging.CRITICAL)

    print("🔄 Restarting...")

    if "ELYS_DO_NOT_RESTART" not in os.environ:
        os.environ["ELYS_DO_NOT_RESTART"] = "1"
    else:
        os.environ["ELYS_DO_NOT_RESTART2"] = "1"

    if "DOCKER" in os.environ or sys.platform == "win32":
        atexit.register(get_startup_callback())
    else:
        signal.signal(signal.SIGTERM, get_startup_callback())
    die()


def print_banner(banner: str):
    print("\033[2J\033[3;1f")
    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "assets",
                banner,
            )
        ),
    ) as f:
        print(f.read())
