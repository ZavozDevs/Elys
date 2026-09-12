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

import contextlib
import logging
import os
import shutil
import sys
import time
from datetime import timedelta

import elystl

parser = elystl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)

IS_DOCKER = "DOCKER" in os.environ
IS_HIKKAHOST = "HIKKAHOST" in os.environ
IS_RNHOST = "RNHOST" in os.environ or "RN_HOST" in os.environ
IS_MACOS = "com.apple" in os.environ.get("PATH", "") or sys.platform == "darwin"
IS_USERLAND = "userland" in os.environ.get("USER", "")
IS_TERMUX = (
    "TERMUX_VERSION" in os.environ
    or "com.termux" in os.environ.get("PREFIX", "")
    or sys.platform == "android"
)
IS_WSL = False
IS_WINDOWS = False
with contextlib.suppress(Exception):
    from platform import uname

    if "microsoft-standard" in uname().release:
        IS_WSL = True
    elif uname().system == "Windows":
        IS_WINDOWS = True


def get_named_platform() -> str:
    """
    Returns formatted platform name
    :return: Platform name
    """

    with contextlib.suppress(Exception):
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model") as f:
                model = f.read().strip()
                if any(board in model for board in ("Orange", "Raspberry")):
                    return model

    match True:

        case _ if IS_WSL:
            return "WSL"

        case _ if IS_WINDOWS:
            return "Windows"

        case _ if IS_MACOS:
            return "MacOS"

        case _ if IS_USERLAND:
            return "UserLand"

        case _ if IS_TERMUX:
            return "Termux"

        case _ if IS_HIKKAHOST:
            return "HikkaHost"

        case _ if IS_RNHOST:
            return "RnHost"

        case _ if IS_DOCKER:
            return "Docker"

        case _:
            return "VDS"


def get_named_platform_emoji() -> str:
    """
    Returns emoji for current platform
    """

    with contextlib.suppress(Exception):
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model") as f:
                model = f.read()
                if "Orange" in model:
                    return "🍊 "

                if "Raspberry" in model:
                    return "🍇 "
                else:
                    return "?"

    match True:

        case _ if IS_WSL:
            return "🍀 "

        case _ if IS_WINDOWS:
            return "💻 "

        case _ if IS_MACOS:
            return "🍏 "

        case _ if IS_USERLAND:
            return "🐧 "

        case _ if IS_TERMUX:
            return "🪐 "

        case _ if IS_HIKKAHOST:
            return "🌼 "

        case _ if IS_RNHOST:
            return "❤️‍🔥 "

        case _ if IS_DOCKER:
            return "🐳 "

        case _:
            return "💎 "


def get_platform_emoji() -> str:
    """
    Returns custom emoji for current platform + Elys logo
    :return: Emoji entity in string
    """
    from .. import emojis

    ELYS_LOGO = emojis.render_emojis(
        "{e:logo_star_1}{e:logo_star_2}{e:logo_star_3}{e:logo_star_4}"
    )

    platform_prefix = ""
    match True:
        case _ if IS_HIKKAHOST:
            platform_prefix = emojis.render_emojis("{e:platform_termux}")
        case _ if IS_USERLAND:
            platform_prefix = emojis.render_emojis("{e:platform_linux}")
        case _ if IS_TERMUX:
            platform_prefix = emojis.render_emojis("{e:platform_wsl}")
        case _ if IS_RNHOST:
            platform_prefix = emojis.render_emojis("{e:platform_android}")
        case _ if IS_DOCKER:
            platform_prefix = emojis.render_emojis("{e:platform_docker}")

    return f"{platform_prefix}{ELYS_LOGO}"


def uptime() -> int:
    """
    Returns userbot uptime in seconds
    """
    current_uptime = round(time.perf_counter() - init_ts)
    return current_uptime


def formatted_uptime() -> str:
    """
    Returns formatted uptime including days if applicable.
    :return: Formatted uptime
    """
    total_seconds = uptime()
    days, remainder = divmod(total_seconds, 86400)
    time_formatted = str(timedelta(seconds=remainder))
    if days > 0:
        return f"{days} day(s), {time_formatted}"
    return time_formatted


def _read_meminfo() -> dict[str, int]:
    """Reads /proc/meminfo into a dictionary with integer values in kB."""
    info: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    info[parts[0].strip()] = int(parts[1].split()[0])
    except Exception:  # noqa: BLE001
        pass
    return info


def _get_windows_memory() -> dict[str, int]:
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return {
                "total_phys": stat.ullTotalPhys,
                "avail_phys": stat.ullAvailPhys,
                "total_page": stat.ullTotalPageFile,
                "avail_page": stat.ullAvailPageFile,
            }
    except Exception:  # noqa: BLE001
        pass
    return {}


def get_ram_usage() -> float:
    """Returns current process memory usage in MB"""
    # Linux / Android (Termux) / WSL: /proc/self/status VmRSS is fastest (<15 µs)
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:  # noqa: BLE001
        pass

    # POSIX fallback (macOS / BSD)
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        scale = 1024 * 1024 if sys.platform == "darwin" else 1024
        return round(rss / scale, 1)
    except Exception:  # noqa: BLE001
        pass

    # Fallback to psutil if available
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 1)
    except Exception:  # noqa: BLE001
        return 0.0


def get_ram_usage_system() -> dict:
    """
    Get system-wide RAM usage information
    :return: Dictionary with used, total in MB and percent
    """
    mem = _read_meminfo()
    if mem and "MemTotal" in mem:
        total = mem["MemTotal"] // 1024
        available = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
        used = max(0, total - available)
        percent = round((used / total) * 100, 1) if total else 0.0
        return {
            "percent": percent,
            "used": used,
            "total": total,
        }

    if IS_WINDOWS:
        win_mem = _get_windows_memory()
        if win_mem:
            total = round(win_mem["total_phys"] / 1024 / 1024)
            avail = round(win_mem["avail_phys"] / 1024 / 1024)
            used = max(0, total - avail)
            percent = round((used / total) * 100, 1) if total else 0.0
            return {
                "percent": percent,
                "used": used,
                "total": total,
            }

    with contextlib.suppress(Exception):
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = (page_size * os.sysconf("SC_PHYS_PAGES")) // (1024 * 1024)
        avail = (page_size * os.sysconf("SC_AVPHYS_PAGES")) // (1024 * 1024)
        used = max(0, total - avail)
        percent = round((used / total) * 100, 1) if total else 0.0
        return {
            "percent": percent,
            "used": used,
            "total": total,
        }

    with contextlib.suppress(Exception):
        import psutil

        vm = psutil.virtual_memory()
        return {
            "percent": round(vm.percent, 1),
            "used": round(vm.used / 1024 / 1024),
            "total": round(vm.total / 1024 / 1024),
        }

    return {"error": "Failed to get RAM usage"}


def get_swap_usage() -> dict:
    """
    Get swap usage information
    :return: Dictionary with used, total in MB and percent, or error string
    """
    mem = _read_meminfo()
    if mem and "SwapTotal" in mem:
        total = mem["SwapTotal"] // 1024
        if total == 0:
            return {"error": "Swap is not configured on this system"}
        free = mem.get("SwapFree", 0) // 1024
        used = max(0, total - free)
        percent = round((used / total) * 100, 1) if total else 0.0
        return {
            "percent": percent,
            "used": used,
            "total": total,
        }

    with contextlib.suppress(Exception):
        import psutil

        swap = psutil.swap_memory()
        if swap.total == 0:
            return {"error": "Swap is not configured on this system"}
        return {
            "percent": round(swap.percent, 1),
            "used": round(swap.used / 1024 / 1024),
            "total": round(swap.total / 1024 / 1024),
        }

    return {"error": "Swap is not configured on this system"}


_prev_cpu_times: tuple[float, float] | None = None

with contextlib.suppress(Exception):
    with open("/proc/stat") as _f:
        _line = _f.readline()
        if _line.startswith("cpu "):
            _fields = [float(x) for x in _line.split()[1:]]
            _prev_cpu_times = (_fields[3] + (_fields[4] if len(_fields) > 4 else 0.0), sum(_fields))


def get_cpu_usage() -> str:
    """
    Get CPU usage percentage using system-wide metrics.
    Uses /proc/stat delta calculation without blocking sleep.
    """
    global _prev_cpu_times
    try:
        with open("/proc/stat") as f:
            first_line = f.readline()
        if first_line.startswith("cpu "):
            fields = [float(x) for x in first_line.split()[1:]]
            idle = fields[3] + (fields[4] if len(fields) > 4 else 0.0)
            total = sum(fields)

            if _prev_cpu_times is not None:
                last_idle, last_total = _prev_cpu_times
                delta_total = total - last_total
                delta_idle = idle - last_idle
                _prev_cpu_times = (idle, total)
                if delta_total > 0:
                    percent = max(0.0, min(100.0, (1.0 - (delta_idle / delta_total)) * 100))
                    return f"{percent:.2f}"
            else:
                _prev_cpu_times = (idle, total)
                return "0.00"
    except (PermissionError, FileNotFoundError, Exception):  # noqa: BLE001
        pass

    with contextlib.suppress(Exception):
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0)
        return f"{cpu_percent:.2f}"

    return "0.00"


init_ts = time.perf_counter()

get_platform_name = get_named_platform


def get_ip_address() -> str:
    """
    Get the public IP address
    :return: IP address string
    """
    try:
        import requests

        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        return response.json()["ip"]
    except Exception:  # noqa: BLE001
        return "Unknown"


def get_disk_usage() -> dict:
    """
    Get disk usage information
    :return: Dictionary with total, used, free in GB
    """
    try:
        path = "/"
        if not os.path.exists(path):
            path = os.path.expanduser("~")
        total, used, free = shutil.disk_usage(path)
        percent = round((used / total) * 100, 1) if total else 0.0
        return {
            "total": round(total / (1024**3), 2),
            "used": round(used / (1024**3), 2),
            "free": round(free / (1024**3), 2),
            "percent": percent,
        }
    except Exception:  # noqa: BLE001
        pass

    with contextlib.suppress(Exception):
        import psutil

        disk = psutil.disk_usage("/")
        return {
            "total": round(disk.total / (1024**3), 2),
            "used": round(disk.used / (1024**3), 2),
            "free": round(disk.free / (1024**3), 2),
            "percent": disk.percent,
        }

    return {"total": 0, "used": 0, "free": 0, "percent": 0}
