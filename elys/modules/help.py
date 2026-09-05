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
import difflib
import inspect
import logging
import re
import typing

from elystl.tl.types import Message
from elystl.types import InputMediaWebPage


from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class Help(loader.Module):
    """Shows help for modules and commands"""

    strings = {"name": "Help"}

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
                            reversed(
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
                                )
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

        reply = "{} <b>{}</b>:".format(
            "<tg-emoji emoji-id=5134452506935427991>🌟</tg-emoji>",
            _name,
        )
        inline_cmd = ""
        cmds = ""
        if module.__doc__:
            reply += (
                "\n<i><tg-emoji emoji-id=5879813604068298387>ℹ️</tg-emoji> "
                + utils.escape_html(inspect.getdoc(module))
                + "\n</i>"
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
                inline_cmd += (
                    "\n<tg-emoji emoji-id=5372981976804366741>🤖</tg-emoji>"
                    " <code>{}</code> {}".format(
                        f"@{self.inline.bot_username} {name}",
                        (
                            utils.escape_html(inspect.getdoc(fun))
                            if fun.__doc__
                            else self.strings["undoc"]
                        ),
                    )
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
                                "<code>{}{}</code>".format(
                                    utils.escape_html(self.get_prefix()),
                                    alias,
                                )
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
            try:
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
            except Exception:
                pass

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
                except Exception:
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
        except Exception:
            await utils.answer(
                message,
                plain_text,
            )

    @loader.command(
        ru_doc="[args] | Помощь с вашими модулями!",
        ua_doc="[args] | допоможіть з вашими модулями!",
        de_doc="[args] | Hilfe mit deinen Modulen!",
    )
    async def help(self, message: Message):
        """[args] | help with your modules!"""

        args = utils.get_args_raw(message)

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
