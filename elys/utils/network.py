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

import logging
import socket

logger = logging.getLogger(__name__)


def get_hostname() -> str:
    """
    Get the hostname of the machine
    :return: Hostname
    """
    try:
        return socket.gethostname()
    except Exception:  # noqa: BLE001
        return "Unknown"


def resolve_domain(domain: str) -> str:
    """
    Resolve domain to IP address
    :param domain: Domain name
    :return: IP address or error message
    """
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror:
        return "Unable to resolve"


def is_port_open(host: str, port: int) -> bool:
    """
    Check if a port is open on a host
    :param host: Hostname or IP
    :param port: Port number
    :return: True if open, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:  # noqa: BLE001
        return False


def get_network_interfaces() -> dict[str, str]:
    """
    Get network interfaces and their IP addresses
    :return: Dictionary of interface: IP
    """
    interfaces = {}
    try:
        import fcntl
        import struct

        names = [name for _, name in socket.if_nameindex()]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for ifname in names:
            try:
                addr = socket.inet_ntoa(
                    fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack("256s", ifname.encode("utf-8")[:15]),
                    )[20:24]
                )
                interfaces[ifname] = addr
            except Exception:  # noqa: BLE001
                pass
        s.close()
        if interfaces:
            return interfaces
    except Exception:  # noqa: BLE001
        pass

    try:
        import psutil

        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces[name] = addr.address
                    break
        if interfaces:
            return interfaces
    except Exception:  # noqa: BLE001
        pass

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            interfaces[hostname] = ip
    except Exception:  # noqa: BLE001
        pass

    return interfaces
