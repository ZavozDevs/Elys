# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Async, string-typed database facade over Elys's synchronous database.

MCUB's contract is narrow and must be preserved exactly: ``db_get`` returns
``str | None`` and ``db_set`` stores ``str(value)``. Real MCUB modules rely on
that -- they ``json.dumps`` on write and ``json.loads`` on read, so handing
back a live ``dict`` (which Elys's ``db.get`` would happily do) breaks them.

All keys live under a ``mcub.<namespace>`` owner so MCUB modules can never
collide with Elys's own database namespaces.
"""

import logging
import re

logger = logging.getLogger(__name__)

OWNER_PREFIX = "mcub"
_VALID = re.compile(r"^[a-zA-Z0-9_.\-:]{1,64}$")


def _owner(namespace: str) -> str:
    namespace = str(namespace or "unknown")
    if not _VALID.match(namespace):
        raise ValueError(f"invalid MCUB db namespace: {namespace!r}")
    return f"{OWNER_PREFIX}.{namespace}"


def _check_key(key: str) -> str:
    key = str(key)
    if not _VALID.match(key):
        raise ValueError(f"invalid MCUB db key: {key!r}")
    return key


class MCUBDatabase:
    """MCUB ``DatabaseManager`` + ``DatabaseProxy`` surface, Elys-backed."""

    def __init__(self, db, module_name: str = "unknown") -> None:
        self._db = db
        self._module_name = module_name

    # -- MCUB DatabaseManager API (explicit namespace) --------------------

    async def db_get(self, module: str, key: str):
        return self._db.get(_owner(module), _check_key(key), None)

    async def db_set(self, module: str, key: str, value) -> None:
        self._db.set(_owner(module), _check_key(key), None if value is None else str(value))

    async def db_delete(self, module: str, key: str) -> None:
        self._db.set(_owner(module), _check_key(key), None)

    async def db_get_module_keys(self, module: str) -> list[str]:
        bucket = self._db.get(_owner(module), "__keys__", None)
        if bucket:
            return list(bucket)
        raw = getattr(self._db, "_db", None) or {}
        return [k for k in (raw.get(_owner(module)) or {}) if not k.startswith("__")]

    async def db_get_config_modules(self) -> list[str]:
        raw = getattr(self._db, "_db", None) or {}
        prefix = f"{OWNER_PREFIX}."
        return [k[len(prefix) :] for k in raw if k.startswith(prefix)]

    async def db_query(self, query: str, parameters=()) -> list:
        # Elys's database is JSON/Redis-backed, so raw SQL has no meaning here.
        logger.warning(
            "MCUB module %s called db_query(); unsupported on Elys, returning []",
            self._module_name,
        )
        return []

    # -- MCUB DatabaseProxy API (implicit, module-scoped) ------------------

    async def get(self, key: str, default=None):
        value = self._db.get(_owner(self._module_name), _check_key(key), None)
        return default if value is None else value

    async def set(self, key: str, value) -> None:
        await self.db_set(self._module_name, key, value)

    async def delete(self, key: str) -> bool:
        await self.db_delete(self._module_name, key)
        return True

    async def contains(self, key: str) -> bool:
        return (
            self._db.get(_owner(self._module_name), _check_key(key), None) is not None
        )

    async def keys(self, pattern: str | None = None) -> list[str]:
        found = await self.db_get_module_keys(self._module_name)
        if not pattern or pattern == "*":
            return found
        needle = pattern.strip("*")
        return [k for k in found if needle in k]

    # -- escape hatch -----------------------------------------------------

    @property
    def elys_db(self):
        """The raw Elys database, for shim internals only."""
        return self._db

    def __repr__(self) -> str:
        return f"<MCUBDatabase module={self._module_name!r}>"
