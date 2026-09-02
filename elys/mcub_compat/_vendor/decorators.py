# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлькa | @hairpin01
#
# Vendored from MCUB core/lib/loader/decorators.py (branch: dev).
# These decorators only attach `_mcub_*` metadata to functions, so they are
# framework-agnostic and are kept byte-compatible with upstream on purpose.

from collections.abc import Callable
from typing import Any


def _validate_doc_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Allow only arbitrary ``doc_<locale>`` kwargs in command decorators."""
    invalid = [key for key in kwargs if not key.startswith("doc_")]
    if invalid:
        name = invalid[0]
        raise TypeError(f"unexpected keyword argument {name!r}")
    return kwargs


def command(
    pattern: str,
    *,
    alias: str | list[str] | None = None,
    doc: dict | None = None,
    doc_ru: str | None = None,
    doc_en: str | None = None,
    **doc_kwargs: Any,
) -> Callable:
    """Class-level decorator for registering commands in class-style modules."""

    extra_docs = _validate_doc_kwargs(doc_kwargs)
    command_meta = {"alias": alias, "doc": doc, "doc_ru": doc_ru, "doc_en": doc_en}
    command_meta.update(extra_docs)

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_commands"):
            func._mcub_commands = []
        func._mcub_commands.append((pattern, command_meta))
        return func

    return decorator


def inline(pattern: str) -> Callable:
    """Class-level decorator for registering inline handlers."""

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_inline"):
            func._mcub_inline = []
        func._mcub_inline.append(pattern)
        return func

    return decorator


def callback(func: Callable | None = None, *, ttl: int = 900) -> Callable:
    """Class-level decorator for callback handlers with auto-generated uuid."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_callbacks"):
            f._mcub_callbacks = []
        f._mcub_callbacks.append({"ttl": ttl})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def watcher(
    func: Callable | None = None, *, bot_client: bool = False, **tags: Any
) -> Callable:
    """Class-level decorator for registering message watchers.

    Available tags:
        out, incoming
        only_pm, no_pm
        only_groups, no_groups
        only_channels, no_channels
        only_media, no_media
        only_photos, no_photos
        only_videos, no_videos
        only_audios, no_audios
        only_docs, no_docs
        only_stickers, no_stickers
        only_forwards, no_forwards
        only_reply, no_reply
        regex="pattern"
        startswith="text", endswith="text", contains="text"
        from_id=<int>, chat_id=<int>
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_watchers"):
            f._mcub_watchers = []
        f._mcub_watchers.append({"bot_client": bot_client, "tags": tags})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def loop(
    interval: int = 60,
    autostart: bool = True,
    wait_before: bool = False,
) -> Callable:
    """Class-level decorator for registering background loops."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_loops"):
            f._mcub_loops = []
        f._mcub_loops.append(
            {
                "interval": interval,
                "autostart": autostart,
                "wait_before": wait_before,
            }
        )
        return f

    return decorator


def event(
    event_type: str, *args: Any, bot_client: bool = False, **kwargs: Any
) -> Callable:
    """Class-level decorator for registering custom event handlers.

    Available event types:
        newmessage, message, messageedited, edited, messagedeleted, deleted,
        messageread, read, userupdate, user, chataction, action,
        joinrequest, request, album, inlinequery, inline, callbackquery,
        callback, raw, custom
    """

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_events"):
            f._mcub_events = []
        f._mcub_events.append(
            {
                "event_type": event_type,
                "args": args,
                "bot_client": bot_client,
                "kwargs": kwargs,
            }
        )
        return f

    return decorator


def inline_temp(
    func: Callable | None = None,
    *,
    ttl: int = 300,
    allow_user: int | list[int] | str | None = None,
    allow_ttl: int = 100,
    article: Callable | None = None,
    data: Any | None = None,
) -> Callable:
    """Class-level decorator for registering temporary inline command handlers."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_inline_temp"):
            f._mcub_inline_temp = []
        f._mcub_inline_temp.append(
            {
                "ttl": ttl,
                "allow_user": allow_user,
                "allow_ttl": allow_ttl,
                "article": article,
                "data": data,
            }
        )
        return f

    if func is not None:
        return decorator(func)
    return decorator


def method(func: Callable | None = None) -> Callable:
    """Class-level decorator for registering generic setup methods."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_methods"):
            f._mcub_methods = []
        f._mcub_methods.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def on_install(func: Callable | None = None) -> Callable:
    """Class-level decorator for one-time install callback."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_on_install"):
            f._mcub_on_install = []
        f._mcub_on_install.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def on_uninstall(func: Callable | None = None) -> Callable:
    """Class-level decorator for uninstall callback."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_uninstall"):
            f._mcub_uninstall = []
        f._mcub_uninstall.append(True)
        return f

    if func is not None:
        return decorator(func)
    return decorator


def bot_command(
    pattern: str,
    *,
    alias: str | list[str] | None = None,
    doc: dict | None = None,
    doc_ru: str | None = None,
    doc_en: str | None = None,
    **doc_kwargs: Any,
) -> Callable:
    """Class-level decorator for registering bot commands."""

    extra_docs = _validate_doc_kwargs(doc_kwargs)
    command_meta = {"alias": alias, "doc": doc, "doc_ru": doc_ru, "doc_en": doc_en}
    command_meta.update(extra_docs)

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_mcub_bot_commands"):
            func._mcub_bot_commands = []
        func._mcub_bot_commands.append((pattern, command_meta))
        return func

    return decorator


def owner_only(func: Callable | None = None, *, only_admin: bool = False) -> Callable:
    """Class-level decorator to restrict command to owner/admins."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_owner"):
            f._mcub_owner = []
        f._mcub_owner.append({"only_admin": only_admin})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def permissions(
    func: Callable | None = None, *, log_level: str = "error", **perms: Any
) -> Callable:
    """Class-level decorator for setting command permissions."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_permissions"):
            f._mcub_permissions = []
        f._mcub_permissions.append({"log_level": log_level, **perms})
        return f

    if func is not None:
        return decorator(func)
    return decorator


def error_handler(
    func: Callable | None = None,
    *,
    log_level: str = "error",
    reraise: bool = False,
    message: str | None = None,
) -> Callable:
    """Class-level decorator for handling errors in command handlers."""

    def decorator(f: Callable) -> Callable:
        if not hasattr(f, "_mcub_error_handler"):
            f._mcub_error_handler = []
        f._mcub_error_handler.append(
            {"log_level": log_level, "reraise": reraise, "message": message}
        )
        return f

    if func is not None:
        return decorator(func)
    return decorator


# Aliases kept for parity with MCUB's public re-exports.
permission = permissions
owner = owner_only
uninstall = on_uninstall

__all__ = [
    "bot_command",
    "callback",
    "command",
    "error_handler",
    "event",
    "inline",
    "inline_temp",
    "loop",
    "method",
    "on_install",
    "on_uninstall",
    "owner",
    "owner_only",
    "permission",
    "permissions",
    "uninstall",
    "watcher",
]
