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

import ast
import asyncio
import contextlib
import difflib
import inspect
import logging
import re
import typing

import requests
from elystl.tl.types import Message
from elystl.types import InputMediaWebPage

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)


@loader.tds
class Help(loader.Module):
    """Shows help for modules and commands"""

    strings = {  # noqa: RUF012
        "name": "Help",
        "module_header": "<tg-emoji emoji-id=5134452506935427991>🌟</tg-emoji> <b>{}</b>:",
        "mod_doc": "\n<i><tg-emoji emoji-id=5879813604068298387>ℹ️</tg-emoji> {}\n</i>",
        "inline_cmd_li": "\n<tg-emoji emoji-id=5372981976804366741>🤖</tg-emoji> <code>{}</code> {}",
        "preview_downloading": "<i>Загрузка предпросмотра модуля...</i>",
        "preview_fetch_err": "<b>Не удалось скачать модуль по ссылке</b>",
        "preview_parse_err": "<b>Не удалось проанализировать модуль</b>",
        "preview_install_url": "\n\n<i>Это предпросмотр. Для установки:</i> {}",
        "preview_install_reply": "\n\n<i>Это предпросмотр. Для установки:</i> {} ответом на файл",
        "preview_install_btn": "📥 Установить",
        "preview_installing": "<i>Установка модуля...</i>",
        "btn_close": "Закрыть",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "core_emoji",
                "<tg-emoji emoji-id=5238035813761069618>◼️</tg-emoji>",
                lambda: "Core module bullet",
            ),
            loader.ConfigValue(
                "plain_emoji",
                "<tg-emoji emoji-id=5238160913273502720>⚫</tg-emoji>",
                lambda: "Plain module bullet",
            ),
            loader.ConfigValue(
                "empty_emoji",
                "<tg-emoji emoji-id=5238094680582823847>▪️</tg-emoji>",
                lambda: "Empty modules bullet",
            ),
            loader.ConfigValue(
                "desc_icon",
                "<tg-emoji emoji-id=5246701816518843050>⭐</tg-emoji>",
                lambda: "Desc emoji",
            ),
            loader.ConfigValue(
                "command_emoji",
                "<tg-emoji emoji-id=5197195523794157505>▫️</tg-emoji>",
                lambda: "Emoji for command",
            ),
            loader.ConfigValue(
                "banner_url",
                None,
                lambda: "Banner for .help",
                validator=loader.validators.RandomLink(),
            ),
            loader.ConfigValue(
                "media_quote",
                "False",
                lambda: "quote a banner in help",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "invert_media",
                "False",
                lambda: "invert banner",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_preview_in_help",
                True,
                lambda: self.strings["show_preview_in_help"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "rich_mode",
                False,
                lambda: self.strings["_cfg_rich_mode"],
                validator=loader.validators.Boolean(),
            ),
        )

    def _get_banner_url(
        self, doc: typing.Any = None, instance: typing.Any = None
    ) -> str | None:
        if instance is None and not isinstance(doc, (str, bytes)) and doc is not None:
            instance = doc
            doc = getattr(instance, "__source__", None) or getattr(instance, "__doc__", None)

        if instance is not None:
            banner = getattr(instance, "banner_url", None)
            if banner:
                return banner
            mcub_instance = getattr(instance, "mcub_instance", None)
            banner = getattr(mcub_instance, "banner_url", None)
            if banner:
                return banner

        if isinstance(doc, bytes):
            doc = doc.decode("utf-8", errors="ignore")

        if isinstance(doc, str):
            match = re.search(r"# ?(?:meta )?banner(?:_url)?: ?(.+)", doc)
            if match:
                return match.group(1).strip()

        return None

    @loader.command(
        ru_doc="[args] | Спрячет ваши модули",
        ua_doc="[args] | Сховає ваші модулі",
        de_doc="[args] | Versteckt Ihre Module",
    )
    async def helphide(self, message: Message):
        """[args] | hide your modules"""
        if not (modules := utils.get_args(message)):
            await utils.answer(message, self.strings["no_mod"])
            return

        currently_hidden = self.get("hide", [])
        hidden, shown = [], []
        for module in filter(lambda module: self.lookup(module), modules):
            module = self.lookup(module)
            module = module.__class__.__name__
            if module in currently_hidden:
                currently_hidden.remove(module)
                shown += [module]
            else:
                currently_hidden += [module]
                hidden += [module]

        self.set("hide", currently_hidden)

        await utils.answer(
            message,
            self.strings["hidden_shown"].format(
                len(hidden),
                len(shown),
                "\n".join([f"👁‍🗨 <i>{m}</i>" for m in hidden]),
                "\n".join([f"👁 <i>{m}</i>" for m in shown]),
            ),
        )

    def find_aliases(self, command: str) -> list:
        """Find aliases for command"""
        if command not in self.allmodules.commands:
            return []
        _command = self.allmodules.commands[command]
        aliases = getattr(_command, "aliases", None)
        if not aliases and getattr(_command, "alias", None):
            aliases = [_command.alias]

        return list(aliases) if aliases else []

    async def modhelp(self, message: Message, args: str):
        exact = True
        if not (module := self.lookup(args)):
            if method := self.allmodules.dispatch(
                args.lower().strip(self.get_prefix())
            )[1]:
                module = method.__self__
            else:
                module = self.lookup(
                    next(
                        (
                            sorted(
                                [
                                    module.strings["name"]
                                    for module in self.allmodules.modules
                                ],
                                key=lambda x: difflib.SequenceMatcher(
                                    None,
                                    args.lower(),
                                    x,
                                ).ratio(),
                                reverse=True,
                            )
                        ),
                        None,
                    )
                )

                exact = False

        try:
            name = module.strings("name")
        except (KeyError, AttributeError):
            name = getattr(module, "name", "ERROR")

        _name = (
            "{} (v{})".format(
                utils.escape_html(name), ".".join(map(str, module.__version__))
            )
            if hasattr(module, "__version__")
            else utils.escape_html(name)
        )

        reply = self.strings["module_header"].format(_name)
        inline_cmd = ""
        cmds = ""
        if module.__doc__:
            reply += self.strings["mod_doc"].format(
                utils.escape_html(inspect.getdoc(module))
            )

        if isinstance(self.lookup(args), loader.Library):
            return await utils.answer(message, self.strings["help_lib"].format(name))

        commands = {
            name: func
            for name, func in module.commands.items()
            if await self.allmodules.check_security(message, func)
        }

        if hasattr(module, "inline_handlers"):
            for name, fun in module.inline_handlers.items():
                inline_cmd += self.strings["inline_cmd_li"].format(
                    f"@{self.inline.bot_username} {name}",
                    (
                        utils.escape_html(inspect.getdoc(fun))
                        if fun.__doc__
                        else self.strings["undoc"]
                    ),
                )

        lines = []
        for name, fun in commands.items():
            lines.append(
                f'{self.config["command_emoji"]}'
                " <code>{}{}</code>{} {}".format(
                    utils.escape_html(self.get_prefix()),
                    name,
                    (
                        " ({})".format(
                            ", ".join(
                                f"<code>{utils.escape_html(self.get_prefix())}{alias}</code>"
                                for alias in self.find_aliases(name)
                            )
                        )
                        if self.find_aliases(name)
                        else ""
                    ),
                    (
                        utils.escape_html(inspect.getdoc(fun))
                        if fun.__doc__
                        else self.strings["undoc"]
                    ),
                )
            )
        cmds = "\n".join(lines)
        developer = re.search(
            r"# ?meta developer: ?(.+)", getattr(module, "__source__", None)
        )
        dev_text = developer.group(1) if developer else None
        placeholders = "\n".join(
            utils.help_placeholders(module.__class__.__name__, self)
        )

        banner_kwargs = {}
        banner_url = None
        if self.config["show_preview_in_help"]:
            with contextlib.suppress(Exception):
                banner_url = getattr(module, "banner_url", None) or getattr(
                    getattr(module, "mcub_instance", None), "banner_url", None
                )
                if not banner_url:
                    source = getattr(module, "__source__", None)
                    banner_url = self._get_banner_url(source, module)

                if banner_url:
                    banner_kwargs = {
                        "file": InputMediaWebPage(banner_url, optional=True),
                        "invert_media": True,
                    }

        if self.config["rich_mode"]:
            rich_reply = reply.replace("\r\n", "<br>").replace("\n", "<br>")
            rich_commands = "".join(f"<p>{line.strip()}</p>" for line in lines)
            rich_inline_commands = inline_cmd.replace("\r\n", "<br>").replace(
                "\n", "<br>"
            )
            base_rich_message = f"{rich_reply}<details><summary>{self.strings.get('rich_commands', 'Commands')}</summary>" f"{rich_commands}{rich_inline_commands}</details>" + (
                f"<details><summary>{self.strings.get('rich_placeholders', 'Placeholders')}</summary>"
                f"{placeholders}</details>"
                if placeholders
                else ""
            ) + (
                f"<p>{self.strings['developer'].format(dev_text)}</p>"
                if dev_text
                else ""
            ) + (
                f"<p>{self.strings['not_exact']}</p>" if not exact else ""
            ) + (
                f"<p>{self.strings['core_notice']}</p>"
                if module.__origin__.startswith("<core")
                else ""
            )
            if banner_url:
                rich_message = (
                    f'<figure><img src="{banner_url}"/></figure>' + base_rich_message
                )
                try:
                    await utils.answer(message, rich_message=rich_message)
                    return
                except Exception:  # noqa: BLE001
                    await utils.answer(message, rich_message=base_rich_message)
                    return

            await utils.answer(message, rich_message=base_rich_message)
            return

        plain_text = (
            f"{reply}<blockquote expandable>{cmds}{inline_cmd}</blockquote>"
            + (
                f"\n<blockquote expandable>{placeholders}</blockquote>"
                if placeholders
                else ""
            )
            + (f"\n\n{self.strings['developer']}".format(dev_text) if dev_text else "")
            + (f"\n\n{self.strings['not_exact']}" if not exact else "")
            + (
                f"\n{self.strings['core_notice']}"
                if module.__origin__.startswith("<core")
                else ""
            )
        )

        try:
            await utils.answer(
                message,
                plain_text,
                **banner_kwargs,
            )
        except Exception:  # noqa: BLE001
            await utils.answer(
                message,
                plain_text,
            )

    def _parse_module_preview(
        self, code: str, default_name: str = "Unknown"
    ) -> dict:
        meta = {
            "name": None,
            "version": None,
            "doc": None,
            "developer": None,
            "banner_url": None,
            "commands": [],
            "inline_commands": [],
            "requires": [],
        }

        # 1. Regex headers (# meta ... / # ...)
        m_name = re.search(
            r"^\s*#\s*(?:meta\s+)?name\s*:\s*(.+)$", code, re.M | re.I
        )
        if m_name:
            meta["name"] = m_name.group(1).strip()

        m_dev = re.search(
            r"^\s*#\s*(?:meta\s+developer|author)\s*:\s*(.+)$", code, re.M | re.I
        )
        if m_dev:
            meta["developer"] = m_dev.group(1).strip()

        m_banner = re.search(
            r"^\s*#\s*(?:meta\s+banner(?:_url)?|banner(?:_url)?)\s*:\s*(.+)$",
            code,
            re.M | re.I,
        )
        if m_banner:
            meta["banner_url"] = m_banner.group(1).strip()

        m_ver = re.search(
            r"^\s*#\s*(?:meta\s+)?version\s*:\s*(.+)$", code, re.M | re.I
        )
        if m_ver:
            meta["version"] = m_ver.group(1).strip()

        m_desc = re.search(
            r"^\s*#\s*(?:meta\s+)?description\s*:\s*(.+)$", code, re.M | re.I
        )
        if m_desc:
            meta["doc"] = m_desc.group(1).strip()

        # Requirements
        for req_m in re.finditer(
            r"^\s*#\s*(?:scope:\s*requires|requires)\s*:\s*(.+)$",
            code,
            re.M | re.I,
        ):
            for token in re.split(r"[,\s]+", req_m.group(1).strip()):
                token = token.strip().rstrip(",")
                if token and not token.startswith(("-", "_", ".")):
                    meta["requires"].append(token)

        match_dep = re.search(
            r"^\s*dependencies\s*=\s*[\[\(]([^\]\)]*)[\]\)]", code, re.M
        )
        if match_dep:
            for token in re.findall(r"""['"]([^'"]+)['"]""", match_dep.group(1)):
                token = token.strip().rstrip(",")
                if token and not token.startswith(("-", "_", ".")):
                    meta["requires"].append(token)

        tree = None
        with contextlib.suppress(Exception):
            tree = ast.parse(code)

        if tree:

            def is_module_class(node: ast.ClassDef) -> bool:
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id in (
                        "Module",
                        "ModuleBase",
                        "Library",
                    ):
                        return True
                    if isinstance(base, ast.Attribute) and base.attr in (
                        "Module",
                        "ModuleBase",
                        "Library",
                    ):
                        return True
                for dec in node.decorator_list:
                    dec_f = dec.func if isinstance(dec, ast.Call) else dec
                    if isinstance(dec_f, ast.Name) and dec_f.id in (
                        "tds",
                        "translatable_docstring",
                    ):
                        return True
                    if isinstance(dec_f, ast.Attribute) and dec_f.attr in (
                        "tds",
                        "translatable_docstring",
                    ):
                        return True
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "strings"
                            ):
                                return True
                    if isinstance(
                        item, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        if item.name.endswith("cmd") and not item.name.startswith(
                            "_"
                        ):
                            return True
                return False

            module_classes = [
                n
                for n in tree.body
                if isinstance(n, ast.ClassDef) and is_module_class(n)
            ]
            if not module_classes:
                all_classes = [
                    n for n in tree.body if isinstance(n, ast.ClassDef)
                ]
                if all_classes:
                    module_classes = [
                        max(
                            all_classes,
                            key=lambda c: len(
                                [
                                    x
                                    for x in c.body
                                    if isinstance(
                                        x,
                                        (
                                            ast.FunctionDef,
                                            ast.AsyncFunctionDef,
                                        ),
                                    )
                                ]
                            ),
                        )
                    ]

            for node in module_classes:
                class_doc = ast.get_docstring(node)
                if class_doc and not meta["doc"]:
                    meta["doc"] = class_doc.strip()

                cls_strings = {}
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                if target.id in (
                                    "strings",
                                    "strings_ru",
                                ) and isinstance(item.value, ast.Dict):
                                    for k, v in zip(
                                        item.value.keys, item.value.values
                                    ):
                                        if isinstance(
                                            k, ast.Constant
                                        ) and isinstance(v, ast.Constant):
                                            cls_strings[str(k.value)] = str(
                                                v.value
                                            )
                                            if (
                                                k.value == "name"
                                                and not meta["name"]
                                            ):
                                                meta["name"] = str(v.value)
                                elif (
                                    target.id in ("__version__", "version")
                                    and not meta["version"]
                                ):
                                    if isinstance(
                                        item.value, (ast.Tuple, ast.List)
                                    ):
                                        vals = [
                                            str(el.value)
                                            for el in item.value.elts
                                            if isinstance(el, ast.Constant)
                                        ]
                                        if vals:
                                            meta["version"] = ".".join(vals)
                                    elif isinstance(item.value, ast.Constant):
                                        meta["version"] = str(item.value.value)
                                elif (
                                    target.id == "developer"
                                    and isinstance(item.value, ast.Constant)
                                    and not meta["developer"]
                                ):
                                    meta["developer"] = str(item.value.value)
                                elif (
                                    target.id in ("banner_url", "banner")
                                    and isinstance(item.value, ast.Constant)
                                    and not meta["banner_url"]
                                ):
                                    meta["banner_url"] = str(item.value.value)

                if not meta["doc"] and "_cls_doc" in cls_strings:
                    meta["doc"] = cls_strings["_cls_doc"]

                for item in node.body:
                    if isinstance(
                        item, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        fn_name = item.name
                        fn_doc = ast.get_docstring(item) or ""

                        is_cmd = False
                        cmd_name = None
                        aliases = []
                        is_inline = False

                        for dec in item.decorator_list:
                            dec_call = (
                                dec if isinstance(dec, ast.Call) else None
                            )
                            dec_func = dec_call.func if dec_call else dec
                            dec_parts = []
                            curr = dec_func
                            while isinstance(curr, ast.Attribute):
                                dec_parts.append(curr.attr)
                                curr = curr.value
                            if isinstance(curr, ast.Name):
                                dec_parts.append(curr.id)
                            dec_id = ".".join(reversed(dec_parts))

                            if dec_id in ("loader.command", "command", "cmd"):
                                is_cmd = True
                                if dec_call:
                                    if dec_call.args and isinstance(
                                        dec_call.args[0], ast.Constant
                                    ):
                                        cmd_name = str(dec_call.args[0].value)
                                    for kw in dec_call.keywords:
                                        if kw.arg == "alias" and isinstance(
                                            kw.value, ast.Constant
                                        ):
                                            aliases.append(str(kw.value.value))
                                        elif kw.arg == "aliases" and isinstance(
                                            kw.value, (ast.List, ast.Tuple)
                                        ):
                                            aliases.extend(
                                                [
                                                    str(el.value)
                                                    for el in kw.value.elts
                                                    if isinstance(
                                                        el, ast.Constant
                                                    )
                                                ]
                                            )
                                        elif kw.arg in (
                                            "ru_doc",
                                            "doc",
                                            "ua_doc",
                                            "de_doc",
                                        ) and isinstance(kw.value, ast.Constant):
                                            if (
                                                not fn_doc
                                                or kw.arg == "ru_doc"
                                            ):
                                                fn_doc = str(kw.value.value)

                            elif dec_id in (
                                "loader.inline_handler",
                                "inline_handler",
                            ):
                                is_inline = True

                        if (
                            not is_cmd
                            and fn_name.endswith("cmd")
                            and not fn_name.startswith("_")
                        ):
                            is_cmd = True
                            cmd_name = fn_name[:-3]

                        final_cmd_name = cmd_name or fn_name
                        if is_cmd:
                            if (
                                not fn_doc
                                and f"_cmd_doc_{final_cmd_name}" in cls_strings
                            ):
                                fn_doc = cls_strings[
                                    f"_cmd_doc_{final_cmd_name}"
                                ]
                            meta["commands"].append(
                                {
                                    "name": final_cmd_name,
                                    "aliases": aliases,
                                    "doc": fn_doc.strip() if fn_doc else "",
                                }
                            )
                        elif (
                            is_inline
                            or fn_name.endswith("inline_handler")
                            or fn_name.startswith("inline_")
                        ):
                            if not fn_name.startswith("_inline__"):
                                clean_inline = fn_name
                                if clean_inline.endswith("inline_handler"):
                                    clean_inline = clean_inline[:-14]
                                elif clean_inline.startswith("inline_"):
                                    clean_inline = clean_inline[7:]
                                meta["inline_commands"].append(
                                    {
                                        "name": clean_inline or fn_name,
                                        "doc": (
                                            fn_doc.strip() if fn_doc else ""
                                        ),
                                    }
                                )

                if not meta["name"]:
                    meta["name"] = node.name

            # MCUB kernel-style register check
            for fn in tree.body:
                if (
                    isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name == "register"
                ):
                    for stmt in ast.walk(fn):
                        if isinstance(stmt, ast.Call):
                            for kw in stmt.keywords:
                                if kw.arg == "commands" and isinstance(
                                    kw.value, ast.Dict
                                ):
                                    for k, v in zip(
                                        kw.value.keys, kw.value.values
                                    ):
                                        if isinstance(k, ast.Constant):
                                            c_name = str(k.value)
                                            c_doc = ""
                                            if isinstance(v, ast.Name):
                                                target_fn = next(
                                                    (
                                                        f
                                                        for f in tree.body
                                                        if isinstance(
                                                            f,
                                                            (
                                                                ast.FunctionDef,
                                                                ast.AsyncFunctionDef,
                                                            ),
                                                        )
                                                        and f.name == v.id
                                                    ),
                                                    None,
                                                )
                                                if target_fn:
                                                    c_doc = (
                                                        ast.get_docstring(
                                                            target_fn
                                                        )
                                                        or ""
                                                    )
                                            meta["commands"].append(
                                                {
                                                    "name": c_name,
                                                    "aliases": [],
                                                    "doc": c_doc.strip(),
                                                }
                                            )
                                elif (
                                    kw.arg == "name"
                                    and isinstance(kw.value, ast.Constant)
                                    and not meta["name"]
                                ):
                                    meta["name"] = str(kw.value.value)
                                elif (
                                    kw.arg == "description"
                                    and isinstance(kw.value, ast.Constant)
                                    and not meta["doc"]
                                ):
                                    meta["doc"] = str(kw.value.value)

        # Fallback if no commands parsed via AST
        if not meta["commands"]:
            for m in re.finditer(r"async\s+def\s+([a-zA-Z0-9_]+)cmd\s*\(", code):
                meta["commands"].append(
                    {
                        "name": m.group(1),
                        "aliases": [],
                        "doc": "",
                    }
                )

        if not meta["name"]:
            clean_default = default_name.split("/")[-1].split("\\")[-1]
            if clean_default.endswith(".py"):
                clean_default = clean_default[:-3]
            meta["name"] = clean_default or "Unknown"

        meta["requires"] = list(dict.fromkeys(meta["requires"]))
        return meta

    async def _inline__install_preview(self, call: InlineCall, url: str):
        loader_mod = self.lookup("Loader")
        if not loader_mod:
            await call.answer("Loader module not found", show_alert=True)
            return

        await call.edit(self.strings["preview_installing"])
        await loader_mod.download_and_install(url, call)

    async def preview_module_url(self, message: Message, url: str):
        clean_url = url.strip("<>").strip()
        if re.match(
            r"^(https:\/\/github\.com\/.*?\/.*?\/blob\/.*\.py)|"
            r"(https:\/\/gitlab\.com\/.*?\/.*?\/-\/blob\/.*\.py)$",
            clean_url,
        ):
            clean_url = clean_url.replace("/blob/", "/raw/")

        loader_mod = self.lookup("Loader")
        auth = (
            loader_mod.config.get("basic_auth")
            if loader_mod and hasattr(loader_mod, "config")
            else None
        )

        msg = await utils.answer(message, self.strings["preview_downloading"])
        code = None
        try:
            if (
                loader_mod
                and hasattr(loader_mod, "_storage")
                and loader_mod._storage
                and hasattr(loader_mod._storage, "fetch")
            ):
                code = await loader_mod._storage.fetch(clean_url, auth=auth)
            else:
                res = await utils.run_sync(
                    requests.get,
                    clean_url,
                    auth=tuple(auth.split(":", 1)) if auth else None,
                    timeout=10,
                    headers={"User-Agent": "ElysUserbot/1.0"},
                )
                if not str(res.status_code).startswith("2"):
                    await utils.answer(msg, self.strings["preview_fetch_err"])
                    return
                code = res.text
        except Exception:
            logger.exception("Failed to download module from %s", clean_url)
            await utils.answer(msg, self.strings["preview_fetch_err"])
            return

        if not code:
            await utils.answer(msg, self.strings["preview_fetch_err"])
            return

        await self.preview_module(msg, code, origin=clean_url, url=clean_url)

    async def preview_module(
        self,
        message: Message,
        code: str,
        origin: str = "<string>",
        url: str | None = None,
    ):
        meta = self._parse_module_preview(code, default_name=origin)

        name = meta["name"]
        version = meta["version"]
        doc = meta["doc"]
        developer = meta["developer"]
        banner_url = meta["banner_url"] or self._get_banner_url(code)
        commands = meta["commands"]
        inline_commands = meta["inline_commands"]
        requires = meta["requires"]

        _name = (
            f"{utils.escape_html(name)} (v{version})"
            if version
            else utils.escape_html(name)
        )

        reply = self.strings["module_header"].format(_name)

        if doc:
            reply += self.strings["mod_doc"].format(utils.escape_html(doc))

        lines = []
        for cmd in commands:
            c_name = cmd["name"]
            aliases = cmd.get("aliases") or []
            c_doc = cmd.get("doc") or self.strings["undoc"]
            alias_str = (
                " ({})".format(
                    ", ".join(
                        f"<code>{utils.escape_html(self.get_prefix())}{alias}</code>"
                        for alias in aliases
                    )
                )
                if aliases
                else ""
            )
            lines.append(
                f'{self.config["command_emoji"]}'
                f" <code>{utils.escape_html(self.get_prefix())}{c_name}</code>{alias_str}"
                f" {utils.escape_html(c_doc)}"
            )

        inline_cmd = ""
        for icmd in inline_commands:
            i_name = icmd["name"]
            i_doc = icmd.get("doc") or self.strings["undoc"]
            bot_user = (
                self.inline.bot_username if self.inline.init_complete else "bot"
            )
            inline_cmd += self.strings["inline_cmd_li"].format(
                f"@{bot_user} {i_name}",
                utils.escape_html(i_doc),
            )

        cmds = "\n".join(lines)
        cmds_block = (
            f"<blockquote expandable>{cmds}{inline_cmd}</blockquote>"
            if (cmds or inline_cmd)
            else ""
        )

        dev_block = (
            f"\n\n{self.strings['developer'].format(utils.escape_html(developer))}"
            if developer
            else ""
        )

        if url:
            install_hint = self.strings["preview_install_url"].format(
                f"<code>{utils.escape_html(self.get_prefix())}lm {url}</code>"
            )
        else:
            install_hint = self.strings["preview_install_reply"].format(
                f"<code>{utils.escape_html(self.get_prefix())}lm</code>"
            )

        banner_kwargs = {}
        if self.config["show_preview_in_help"] and banner_url:
            banner_kwargs = {
                "file": InputMediaWebPage(banner_url, optional=True),
                "invert_media": True,
            }

        reply_markup = None
        if url and self.inline.init_complete:
            reply_markup = [
                [
                    {
                        "text": self.strings["preview_install_btn"],
                        "callback": self._inline__install_preview,
                        "args": (url,),
                    },
                    {"text": self.strings["btn_close"], "action": "close"},
                ]
            ]

        if self.config["rich_mode"]:
            rich_reply = reply.replace("\r\n", "<br>").replace("\n", "<br>")
            rich_commands = "".join(f"<p>{line.strip()}</p>" for line in lines)
            rich_inline = inline_cmd.replace("\r\n", "<br>").replace(
                "\n", "<br>"
            )
            base_rich_message = (
                f"{rich_reply}<details><summary>{self.strings.get('rich_commands', 'Commands')}</summary>{rich_commands}{rich_inline}</details>"
                + (
                    f"<p>{self.strings['developer'].format(utils.escape_html(developer))}</p>"
                    if developer
                    else ""
                )
                + f"<p>{install_hint.strip()}</p>"
            )
            if banner_url:
                rich_message = (
                    f'<figure><img src="{banner_url}"/></figure>'
                    + base_rich_message
                )
                try:
                    await utils.answer(
                        message,
                        rich_message=rich_message,
                        reply_markup=reply_markup,
                    )
                    return
                except Exception:  # noqa: BLE001
                    pass
            await utils.answer(
                message,
                rich_message=base_rich_message,
                reply_markup=reply_markup,
            )
            return

        plain_text = f"{reply}{cmds_block}{dev_block}{install_hint}"

        try:
            await utils.answer(
                message,
                plain_text,
                reply_markup=reply_markup,
                **banner_kwargs,
            )
        except Exception:  # noqa: BLE001
            await utils.answer(
                message,
                plain_text,
                reply_markup=reply_markup,
            )

    @loader.command(
        ru_doc="[args] | Помощь с вашими модулями или предпросмотр модуля!",
        ua_doc="[args] | допоможіть з вашими модулями або передперегляд модуля!",
        de_doc="[args] | Hilfe mit deinen Modulen oder Modulvorschau!",
    )
    async def help(self, message: Message):
        """[args] | help with your modules or preview module!"""

        args = utils.get_args_raw(message)

        # 1. Check reply to a file or message itself having a file/document
        target_file_msg = (
            message
            if getattr(message, "file", None)
            else (await message.get_reply_message())
        )
        if target_file_msg and (
            getattr(target_file_msg, "file", None)
            or getattr(target_file_msg, "document", None)
        ):
            file_name = (
                getattr(target_file_msg.file, "name", None)
                or getattr(
                    getattr(target_file_msg, "document", None), "name", None
                )
                or ""
            )
            mime = (
                getattr(target_file_msg.file, "mime_type", None)
                or getattr(
                    getattr(target_file_msg, "document", None), "mime_type", None
                )
                or ""
            )
            if (
                file_name.endswith((".py", ".txt"))
                or "text" in mime
                or "python" in mime
                or not file_name
            ):
                try:
                    doc = await target_file_msg.download_media(bytes)
                    if doc:
                        code = doc.decode("utf-8")
                        if any(
                            marker in code
                            for marker in (
                                "def ",
                                "class ",
                                "import ",
                                "#",
                                "Module",
                                "register",
                            )
                        ):
                            await self.preview_module(
                                message, code, origin=file_name or "module.py"
                            )
                            return
                except UnicodeDecodeError:
                    pass
                except Exception:
                    logger.exception("Failed to preview module from file")

        # 2. Check URL in args or in replied message
        url = None
        if args and re.search(r"https?://\S+", args):
            url = re.search(r"https?://\S+", args).group(0).strip()
        elif (
            not args
            and (reply := await message.get_reply_message())
            and reply.text
        ):
            reply_text = reply.raw_text or reply.text or ""
            match = re.search(r"https?://\S+", reply_text)
            if match and (
                match.group(0).endswith(".py")
                or "raw.githubusercontent" in match.group(0)
                or "/blob/" in match.group(0)
            ):
                url = match.group(0).strip()

        if url:
            await self.preview_module_url(message, url)
            return

        banner = str(self.config["banner_url"])

        if self.config["banner_url"] and self.config["media_quote"] is True:
            banner = InputMediaWebPage(str(self.config["banner_url"]))

        if (
            self.config["banner_url"] and self.client.elys_me.premium is False
        ):  # bcs non-premium users can add in caption only 1024 symbols
            banner = InputMediaWebPage(str(self.config["banner_url"]))

        if not self.config["banner_url"]:
            banner = None

        force = False
        if "-f" in args:
            args = args.replace(" -f", "").replace("-f", "")
            force = True

        only_core = False
        if "-c" in args:
            args = args.replace(" -c", "").replace("-c", "")
            only_core = True
            force = True

        only_loaded = False
        if "-l" in args:
            args = args.replace(" -l", "").replace("-l", "")
            only_loaded = True
            force = True

        if args:
            await self.modhelp(message, args)
            return

        hidden = self.get("hide", [])

        reply = self.strings["all_header"].format(
            len(self.allmodules.modules),
            (
                0
                if force
                else sum(
                    module.__class__.__name__ in hidden
                    for module in self.allmodules.modules
                )
            ),
        )
        shown_warn = False

        plain_ = []
        core_ = []
        no_commands_ = []

        for mod in self.allmodules.modules:
            if not hasattr(mod, "commands"):
                logger.debug("Module %s is not inited yet", mod.__class__.__name__)
                continue

            if mod.__class__.__name__ in self.get("hide", []) and not force:
                continue

            tmp = ""

            try:
                name = mod.strings["name"]
            except KeyError:
                name = getattr(mod, "name", "ERROR")

            placeholders = utils.module_placeholders(mod.__class__.__name__)

            if (
                not getattr(mod, "commands", None)
                and not getattr(mod, "inline_handlers", None)
                and not getattr(mod, "callback_handlers", None)
                and not placeholders
            ):
                no_commands_ += [
                    "\n{} <code>{}</code>".format(self.config["empty_emoji"], name)
                ]
                continue

            core = mod.__origin__.startswith("<core")

            tmp += "\n{} <code>{}</code>".format(
                self.config["core_emoji"] if core else self.config["plain_emoji"], name
            )
            first = True

            commands = [
                name
                for name, func in mod.commands.items()
                if await self.allmodules.check_security(message, func) or force
            ]

            for cmd in commands:
                if first:
                    tmp += f": ( {cmd}"
                    first = False
                else:
                    tmp += f" | {cmd}"

            icommands = []

            if force:
                icommands.extend([*mod.inline_handlers.keys()])
            else:
                results = await asyncio.gather(
                    *(
                        self.inline.check_inline_security(
                            func=func,
                            user=(
                                message.sender_id
                                if not message.out
                                else self._client.tg_id
                            ),
                        )
                        for func in mod.inline_handlers.values()
                    )
                )

                icommands = [
                    name
                    for name, passed in zip(mod.inline_handlers.keys(), results)
                    if passed is True
                ]

            for cmd in icommands:
                if first:
                    tmp += f": ( 🤖 {cmd}"
                    first = False
                else:
                    tmp += f" | 🤖 {cmd}"

            for placeholder in placeholders:
                if first:
                    tmp += f": ( {{{placeholder}}}"
                    first = False
                else:
                    tmp += f" | {{{placeholder}}}"

            if commands or icommands or placeholders:
                tmp += " )"
                if core:
                    core_ += [tmp]
                else:
                    plain_ += [tmp]
            elif not shown_warn and (mod.commands or mod.inline_handlers):
                reply = (
                    "<i>You have permissions to execute only these"
                    f" commands</i>\n{reply}"
                )
                shown_warn = True

        plain_.sort(key=str.lower)
        core_.sort(key=str.lower)
        no_commands_.sort(key=str.lower)

        if self.config["rich_mode"]:
            rich_message = (
                f"<figure><img src=\"{self.config['banner_url']}\"/></figure>"
                if self.config["banner_url"]
                else ""
            ) + f"{self.config['desc_icon']} {reply}"
            rich_core = "".join(f"<p>{item.strip()}</p>" for item in core_)
            rich_modules = "".join(
                f"<p>{item.strip()}</p>"
                for item in plain_ + (no_commands_ if force else [])
            )
            if only_core:
                sections = [(self.strings.get("rich_core", "Core"), rich_core)]
            elif only_loaded:
                sections = [(self.strings.get("rich_modules", "Modules"), rich_modules)]
            else:
                sections = [
                    (self.strings.get("rich_core", "Core"), rich_core),
                    (self.strings.get("rich_modules", "Modules"), rich_modules),
                ]
            rich_message += "".join(
                f"<details><summary>{title}</summary>{content}</details>"
                for title, content in sections
                if content
            )
            if not self.lookup("LoaderMod").fully_loaded:
                rich_message += f"<p>{self.strings['partial_load']}</p>"
            await utils.answer(message, rich_message=rich_message)
            return

        core_text = "".join(core_).strip()
        plain_text = "".join(plain_ + (no_commands_ if force else [])).strip()

        partial_notice = (
            ""
            if self.lookup("LoaderMod").fully_loaded
            else f"\n<blockquote expandable>{self.strings['partial_load']}</blockquote>"
        )

        match True:
            case _ if only_core:
                await utils.answer(
                    message,
                    (
                        self.config["desc_icon"]
                        + f" {reply}\n<blockquote expandable>{core_text}</blockquote>"
                        + partial_notice
                    ),
                    file=banner,
                    invert_media=self.config["invert_media"],
                )
            case _ if only_loaded:
                await utils.answer(
                    message,
                    (
                        self.config["desc_icon"]
                        + f" {reply}\n<blockquote expandable>{plain_text}</blockquote>"
                        + partial_notice
                    ),
                    file=banner,
                    invert_media=self.config["invert_media"],
                )
            case _:
                await utils.answer(
                    message,
                    (
                        self.config["desc_icon"]
                        + f" {reply}\n<blockquote expandable>{core_text}</blockquote>\n<blockquote expandable>{plain_text}</blockquote>"
                        + partial_notice
                    ),
                    file=banner,
                    invert_media=self.config["invert_media"],
                )

    @loader.command(
        ru_doc="| Ссылка на чат помощи",
        ua_doc="| посилання для чату служби підтримки",
        de_doc="| Link zum Support-Chat",
    )
    async def support(self, message):
        """| link for support chat"""

        await utils.answer(
            message,
            self.strings["offchats"],
        )
