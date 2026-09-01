# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import contextlib
import inspect
import logging
import re
import typing

logger = logging.getLogger(__name__)

custom_placeholders = {}

LOADING_EMOJI_PREMIUM = "<tg-emoji emoji-id=5345778951031658558>😭</tg-emoji>"
LOADING_EMOJI_PLAIN = ">_<"


def get_loading_placeholder(client=None) -> str:
    """
    Returns custom loading emoji for Telegram Premium users, or plain text fallback.
    """
    try:
        if client:
            me = getattr(client, "elys_me", None)
            if me and getattr(me, "premium", False):
                return LOADING_EMOJI_PREMIUM
    except Exception:
        pass

    for ph_data in custom_placeholders.values():
        instance = ph_data.get("module_instance")
        if instance and hasattr(instance, "client") and instance.client:
            try:
                me = getattr(instance.client, "elys_me", None)
                if me and getattr(me, "premium", False):
                    return LOADING_EMOJI_PREMIUM
                break
            except Exception:
                pass

    return LOADING_EMOJI_PLAIN


def register_placeholder(
    placeholder: str,
    callback: typing.Callable,
    description: str | None = None,
):
    """
    Register placeholder
    """
    module_name = callback.__self__.__class__.__name__
    module_instance = callback.__self__
    custom_placeholders[placeholder] = {
        "module_name": module_name,
        "module_instance": module_instance,
        "callback": callback,
        "description": description,
        "placeholder_name": placeholder,
    }
    return True


async def get_placeholder(placeholder: str, data: dict | None = None) -> str:
    """
    Safely executes and returns placeholder data.
    """
    if placeholder not in custom_placeholders:
        return ""

    callback = custom_placeholders[placeholder]["callback"]
    try:
        if inspect.iscoroutinefunction(callback) or inspect.isawaitable(callback):
            try:
                callback_data = str(await callback(data))
            except TypeError:
                callback_data = str(await callback())
        else:
            try:
                callback_data = str(callback(data))
            except TypeError:
                callback_data = str(callback())
    except Exception as e:
        logger.debug("Failed to evaluate placeholder %s: %s", placeholder, e)
        callback_data = ""

    return callback_data


async def get_placeholders(
    data: dict,
    custom_message: str | None,
    client=None,
    message=None,
    on_ready_callback: typing.Callable | None = None,
    timeout: float = 0.08,
) -> dict:
    """
    Evaluates placeholders mentioned in custom_message. Fast placeholders are evaluated
    immediately. Slower placeholders receive a loading indicator ('😭' or '>_<') and
    are resolved asynchronously in the background.
    """
    if custom_message is None or not custom_placeholders:
        return data

    matched = [
        name
        for name in custom_placeholders
        if f"{{{name}}}" in custom_message
    ]

    if not matched:
        return data

    tasks = {
        name: asyncio.create_task(get_placeholder(name, data))
        for name in matched
    }

    done, pending = await asyncio.wait(tasks.values(), timeout=timeout)

    for name, task in tasks.items():
        if task in done:
            try:
                data[name] = task.result()
            except Exception:
                data[name] = ""
        else:
            data[name] = get_loading_placeholder(client)

    if pending:
        async def _background_resolver():
            try:
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                for name, res in zip(tasks.keys(), results):
                    if isinstance(res, Exception):
                        data[name] = ""
                    else:
                        data[name] = str(res)

                if on_ready_callback:
                    if inspect.iscoroutinefunction(on_ready_callback):
                        await on_ready_callback(data)
                    else:
                        on_ready_callback(data)
                elif message:
                    from . import other as utils_other

                    new_text = re.sub(
                        r"{(\w+)}",
                        lambda match: str(data.get(match.group(1), match.group(0))),
                        custom_message,
                    )
                    with contextlib.suppress(Exception):
                        await utils_other.answer(message, new_text)
            except Exception as e:
                logger.debug("Background placeholder resolver error: %s", e)

        asyncio.create_task(_background_resolver())

    return data


def unregister_placeholders(module_name: str) -> int:
    """
    Removes placeholders by module_name
    """
    placeholders_to_remove = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            placeholders_to_remove.append(placeholder_name)
    for placeholder_name in placeholders_to_remove:
        del custom_placeholders[placeholder_name]
    return True


def config_placeholders():
    """
    Return placeholders list for config
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        result.append(
            f"{{{placeholder_name}}} - {placeholder_data.get('description') if placeholder_data.get('description') is not None else 'No docs'}"
        )
    if result == []:
        return None
    else:
        return "\n".join(result)


def module_placeholders(module_name: str) -> list[str]:
    """
    Return placeholder names registered by module
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            result.append(placeholder_name)
    return result


def help_placeholders(module_name, self):
    """
    Return placeholders list for help
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            if placeholder_data.get("description") is not None:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - {placeholder_data.get('description')}"
                )
            else:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - No docs"
                )
    return result


def debug_placeholders():
    """
    Just for debug purposes
    """
    return custom_placeholders
