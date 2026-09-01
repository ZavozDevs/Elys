# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import ast
import asyncio
import contextlib
import difflib
import functools
import typing
from math import ceil

import elystl.utils
from elystl import events
from elystl.extensions import html
from elystl.tl.types import Message

from .. import loader, translations, utils
from ..inline.types import InlineCall
from ..types import ElysReplyMarkup

# Everywhere in this module, we use the following naming convention:
# `obj_type` of non-core module = False
# `obj_type` of core module = True
# `obj_type` of library = "library"


ROW_SIZE = 3
NUM_ROWS = 5


class _InlineFormDraft:
    inline_message_id = None

    def __init__(self):
        self.text: str | None = None
        self.reply_markup: ElysReplyMarkup | None = None
        self.kwargs: dict[str, typing.Any] = {}

    async def edit(
        self,
        text: str | None = None,
        reply_markup: ElysReplyMarkup | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        if text is None:
            text = kwargs.pop("text", None)

        if reply_markup is None and args:
            reply_markup = args[0]

        self.text = text
        self.reply_markup = reply_markup
        self.kwargs = kwargs

    async def answer(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        pass


@loader.tds
class ElysConfigMod(loader.Module):
    """Interactive configurator for Elys Userbot"""

    strings = {
        "name": "ElysConfig",
        "_cfg_chat_input": (
            "Enter config values via regular chat message instead of inline"
            " query (experimental)"
        ),
        "_cfg_switch_layout": (
            "Automatically invert keyboard layout for commands (e.g. .рудз -> .help)"
        ),
        "chat_input_prompt_set": (
            "✍️ <b>Send new value for <code>{}</code> of module <code>{}</code>"
            " as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "chat_input_prompt_set_lib": (
            "✍️ <b>Send new value for <code>{}</code> of library <code>{}</code>"
            " as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "chat_input_prompt_add": (
            "➕ <b>Send element to add to <code>{}</code> of module"
            " <code>{}</code> as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "chat_input_prompt_add_lib": (
            "➕ <b>Send element to add to <code>{}</code> of library"
            " <code>{}</code> as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "chat_input_prompt_remove": (
            "➖ <b>Send element to remove from <code>{}</code> of module"
            " <code>{}</code> as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "chat_input_prompt_remove_lib": (
            "➖ <b>Send element to remove from <code>{}</code> of library"
            " <code>{}</code> as a message to this chat.</b>\n\n<b>Current: {}</b>\n\n"
            "<i>⏳ Waiting for message... (it will be deleted automatically)</i>"
        ),
        "cancel_btn": "🚫 Cancel",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "cfg_emoji",
                "🌟",
                "Change emoji when opening inline",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "chat_input",
                False,
                lambda: self.strings["_cfg_chat_input"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "async_placeholders",
                True,
                "Enable lazy placeholders evaluation (shows loading emoji while resolving)",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "switch_layout",
                True,
                lambda: self.strings["_cfg_switch_layout"],
                validator=loader.validators.Boolean(),
            ),
        )
        self._active_chat_inputs: dict[str, dict] = {}

    def on_unload(self):
        for session in list(self._active_chat_inputs.values()):
            if "future" in session and not session["future"].done():
                session["future"].cancel()
            if "handler" in session:
                with contextlib.suppress(Exception):
                    self._client.remove_event_handler(
                        session["handler"], events.NewMessage
                    )
        self._active_chat_inputs.clear()

    @staticmethod
    def _normalize_chat_id(chat: typing.Any) -> int | None:
        if chat is None:
            return None
        if isinstance(chat, int):
            try:
                return elystl.utils.resolve_id(chat)[0]
            except Exception:
                return chat
        if hasattr(chat, "chat_id") or hasattr(chat, "chat"):
            try:
                chat_id = getattr(chat, "chat_id", None) or getattr(
                    getattr(chat, "chat", None), "id", None
                )
                if chat_id is not None:
                    return elystl.utils.resolve_id(chat_id)[0]
            except Exception:
                pass
        try:
            peer_id = elystl.utils.get_peer_id(chat)
            return elystl.utils.resolve_id(peer_id)[0]
        except Exception:
            pass
        return None

    @staticmethod
    def _get_series_min_len(validator: typing.Any) -> int:
        if validator is None:
            return 0
        if isinstance(validator, loader.validators.Validator):
            keywords = (
                getattr(getattr(validator, "validate", None), "keywords", {}) or {}
            )
            if keywords.get("fixed_len") is not None:
                return keywords["fixed_len"]
            if keywords.get("min_len") is not None:
                return keywords["min_len"]
        cls_name = getattr(validator, "__class__", type(validator)).__name__
        if cls_name == "RandomLink":
            return 1
        return 0

    @staticmethod
    def _format_series_item_label(
        idx: int, item: typing.Any, is_hidden: bool = False, max_len: int = 28
    ) -> str:
        if is_hidden:
            return f"🗑 {idx}. **********"
        s = str(item).strip()
        if s.startswith(("http://", "https://")):
            path_part = s.split("?")[0].rstrip("/").split("/")[-1]
            if path_part and len(path_part) <= max_len:
                display = path_part
            else:
                display = s
        else:
            display = s
        if len(display) > max_len:
            display = display[: max_len - 3] + "..."
        return f"🗑 {idx}. {display}"

    @staticmethod
    def prep_value(value: typing.Any) -> typing.Any:
        if isinstance(value, str):
            return f"<b><code>{utils.escape_html(value.strip())}</code></b>"

        if isinstance(value, list) and value:
            return (
                "<b><code>[</code></b>\n    "
                + "\n    ".join(
                    [
                        f"<b><code>{utils.escape_html(str(item))}</code></b>"
                        for item in value
                    ]
                )
                + "\n<b><code>]</code></b>"
            )

        return f"<b><code>{utils.escape_html(value)}</code></b>"

    def hide_value(self, value: typing.Any) -> str:
        if isinstance(value, list) and value:
            return self.prep_value(["*" * len(str(i)) for i in value])

        return self.prep_value("*" * len(str(value)))

    def _get_value(self, mod: str, option: str) -> str:
        return (
            self.prep_value(self.lookup(mod).config[option])
            if (
                not self.lookup(mod).config._config[option].validator
                or self.lookup(mod).config._config[option].validator.internal_id
                != "Hidden"
            )
            else self.hide_value(self.lookup(mod).config[option])
        )

    def _get_inline_value(self, mod: str, option: str, limit: int = 2500) -> str:
        value = self._get_value(mod, option)
        if len(value) <= limit:
            return value

        plain = utils.remove_html(value)
        suffix = "\n... <i>значение обрезано для inline-сообщения</i>"
        plain_limit = max(0, limit - len(suffix) - len("<b><code></code></b>"))
        return f"<b><code>{utils.escape_html(plain[:plain_limit])}</code></b>{suffix}"

    def _is_hidden(self, mod: str, option: str) -> bool:
        try:
            validator = self.lookup(mod).config._config[option].validator
            return bool(
                validator and getattr(validator, "internal_id", None) == "Hidden"
            )
        except Exception:
            return False

    @staticmethod
    def _paginate_text_markup(
        text: str,
        page: int,
        callback: typing.Any,
    ) -> tuple[str, list[list[dict[str, typing.Any]]]]:
        parsed_text, parsed_entities = html.parse(text)
        pages = list(
            utils.smart_split(parsed_text, typing.cast(typing.Any, parsed_entities))
        )

        if len(pages) <= 1:
            return text, []

        page = min(max(page, 0), len(pages) - 1)

        row = []
        if page > 0:
            row.append({"text": "◀️", "callback": callback, "args": (page - 1,)})

        row.append(
            {"text": f"{page + 1}/{len(pages)}", "callback": callback, "args": (page,)}
        )

        if page < len(pages) - 1:
            row.append({"text": "▶️", "callback": callback, "args": (page + 1,)})

        return pages[page], [row]

    @staticmethod
    def _put_pagination_before_nav(
        reply_markup: list[list[dict[str, typing.Any]]],
        pagination: list[list[dict[str, typing.Any]]],
    ) -> list[list[dict[str, typing.Any]]]:
        if not pagination:
            return reply_markup

        return reply_markup[:-1] + pagination + reply_markup[-1:]

    def _guess_back_to_page(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> dict:
        kwargs = {"obj_type": obj_type}
        cat = self.lookup(mod).config.get_category(option)
        if cat is not None:
            kwargs["category"] = cat.name
        return kwargs

    @staticmethod
    def _config_categories(instance: typing.Any) -> dict[str, list[str]]:
        return {
            category: options
            for category, options in instance.config.grouped_options().items()
            if category is not None
        }

    @staticmethod
    def _get_category_doc(instance: typing.Any, category: str) -> str:
        cat_obj = getattr(instance.config, "_categories", {}).get(category)
        return cat_obj.getdoc() if cat_obj else ""

    async def inline__set_config(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__reset_default(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        mod_instance = self.lookup(mod)
        mod_instance.config[option] = mod_instance.config.getdef(option)

        await call.edit(
            self.strings[
                "option_reset" if isinstance(obj_type, bool) else "option_reset_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__set_bool(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        validator = self.lookup(mod).config._config[option].validator
        doc = utils.escape_html(
            next(
                (
                    validator.doc[lang]
                    for original_lang in self._db.get(
                        translations.__name__, "lang", "en"
                    ).split(" ")
                    for lang in translations.iter_language_codes(original_lang)
                    if lang in validator.doc
                ),
                validator.doc["en"],
            )
        )

        await call.edit(
            self.strings[
                (
                    "configuring_option"
                    if isinstance(obj_type, bool)
                    else "configuring_option_lib"
                )
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                utils.escape_html(self.lookup(mod).config.getdoc(option)),
                self.prep_value(self.lookup(mod).config.getdef(option)),
                (
                    self.prep_value(self.lookup(mod).config[option])
                    if not validator or validator.internal_id != "Hidden"
                    else self.hide_value(self.lookup(mod).config[option])
                ),
                (
                    self.strings["typehint"].format(
                        doc,
                        eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                    )
                    if doc
                    else ""
                ),
            ),
            reply_markup=self._generate_bool_markup(mod, option, obj_type),
        )

        await call.answer("✅")

    def _generate_bool_markup(
        self,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        return [
            [
                *(
                    [
                        {
                            "text": f"❌ {self.strings['set']} `False`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, False),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    else [
                        {
                            "text": f"✅ {self.strings['set']} `True`",
                            "callback": self.inline__set_bool,
                            "args": (mod, option, True),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__add_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            with contextlib.suppress(Exception):
                query = ast.literal_eval(query)

            if isinstance(query, (set, tuple)):
                query = list(query)

            if not isinstance(query, list):
                query = [query]

            mod_instance = self.lookup(mod)
            current_val = mod_instance.config[option]
            if current_val is None:
                current_list = []
            elif isinstance(current_val, (list, tuple, set)):
                current_list = list(current_val)
            else:
                current_list = [current_val]

            mod_instance.config[option] = current_list + query
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__remove_item(
        self,
        call: InlineCall,
        query: str,
        mod: str,
        option: str,
        inline_message_id: str | None = None,
        obj_type: bool | str = False,
    ):
        try:
            mod_instance = self.lookup(mod)
            current_val = mod_instance.config[option]
            if current_val is None:
                current_list = []
            elif isinstance(current_val, (list, tuple, set)):
                current_list = list(current_val)
            else:
                current_list = [current_val]

            if not current_list:
                raise loader.validators.ValidationError(
                    self.strings["series_empty_error"].format(utils.escape_html(option))
                )

            validator = mod_instance.config._config[option].validator
            min_len = self._get_series_min_len(validator)

            if len(current_list) <= min_len:
                raise loader.validators.ValidationError(
                    self.strings["series_min_len_error"].format(
                        utils.escape_html(option),
                        min_len,
                    )
                )

            new_list = None
            query_str = str(query).strip()

            # 1. Check if query is 1-based index (e.g. "1", "#1", "2", "1, 2", "#1, #2")
            tokens = [
                tok.strip().lstrip("#").strip()
                for tok in query_str.replace(",", " ").split()
                if tok.strip()
            ]
            if tokens and all(
                tok.isdigit() or (tok.startswith("-") and tok[1:].isdigit())
                for tok in tokens
            ):
                indices_to_remove = set()
                for tok in tokens:
                    val = int(tok)
                    if 1 <= val <= len(current_list):
                        indices_to_remove.add(val - 1)
                    elif -len(current_list) <= val < 0:
                        indices_to_remove.add(len(current_list) + val)
                if indices_to_remove:
                    new_list = [
                        item
                        for i, item in enumerate(current_list)
                        if i not in indices_to_remove
                    ]

            # 2. If index didn't match, try exact matching
            if new_list is None:
                eval_query = query_str
                with contextlib.suppress(Exception):
                    eval_query = ast.literal_eval(query_str)

                if isinstance(eval_query, (set, tuple)):
                    eval_query = list(eval_query)

                if isinstance(eval_query, list):
                    query_items = [str(x) for x in eval_query]
                else:
                    query_items = [str(eval_query), query_str]

                tentative_list = [
                    item
                    for item in current_list
                    if str(item) not in query_items and item not in query_items
                ]
                if len(tentative_list) < len(current_list):
                    new_list = tentative_list

            # 3. If exact match didn't remove anything, try case-insensitive substring match
            if new_list is None:
                q_lower = query_str.lower()
                tentative_list = [
                    item for item in current_list if q_lower not in str(item).lower()
                ]
                if len(tentative_list) < len(current_list):
                    new_list = tentative_list

            if new_list is None or len(new_list) == len(current_list):
                raise loader.validators.ValidationError(
                    self.strings["series_not_found_error"].format(
                        utils.escape_html(query_str),
                        utils.escape_html(option),
                    )
                )

            if len(new_list) < min_len:
                raise loader.validators.ValidationError(
                    self.strings["series_min_len_error"].format(
                        utils.escape_html(option),
                        min_len,
                    )
                )

            mod_instance.config[option] = new_list
        except loader.validators.ValidationError as e:
            err_msg = str(e.args[0])
            if not err_msg.startswith(("<tg-emoji", "🚫", "⚠️", "❌")):
                err_msg = self.strings["validation_error"].format(err_msg)
            await call.edit(
                err_msg,
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
            inline_message_id=inline_message_id or call.inline_message_id,
        )

    async def inline__remove_series_index(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        index: int,
        obj_type: bool | str = False,
        series_page: int = 0,
        force_hidden: bool = False,
    ):
        mod_instance = self.lookup(mod)
        raw_items = mod_instance.config[option]
        if raw_items is None:
            items = []
        elif isinstance(raw_items, (list, tuple, set)):
            items = list(raw_items)
        else:
            items = [raw_items]

        if not items:
            await call.edit(
                self.strings["series_empty_error"].format(utils.escape_html(option)),
                reply_markup=[
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "mod": mod,
                                "config_opt": option,
                                "obj_type": obj_type,
                                "series_page": series_page,
                                "force_hidden": force_hidden,
                            },
                        }
                    ]
                ],
            )
            return

        validator = mod_instance.config._config[option].validator
        min_len = self._get_series_min_len(validator)

        if len(items) <= min_len:
            await call.edit(
                self.strings["series_min_len_error"].format(
                    utils.escape_html(option),
                    min_len,
                ),
                reply_markup=[
                    [
                        {
                            "text": self.strings["enter_value_btn"],
                            "callback": self.inline__prompt_chat_input,
                            "args": ("set", mod, option),
                            "kwargs": {"obj_type": obj_type},
                        },
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        },
                    ],
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "mod": mod,
                                "config_opt": option,
                                "obj_type": obj_type,
                                "series_page": series_page,
                                "force_hidden": force_hidden,
                            },
                        }
                    ],
                ],
            )
            return

        if index < 0 or index >= len(items):
            await self.inline__configure_option(
                call,
                mod=mod,
                config_opt=option,
                force_hidden=force_hidden,
                obj_type=obj_type,
                series_page=series_page,
            )
            return

        new_items = [item for i, item in enumerate(items) if i != index]

        try:
            mod_instance.config[option] = new_items
        except loader.validators.ValidationError as e:
            err_msg = str(e.args[0])
            if not err_msg.startswith(("<tg-emoji", "🚫", "⚠️", "❌")):
                err_msg = self.strings["validation_error"].format(err_msg)
            await call.edit(
                err_msg,
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {
                        "obj_type": obj_type,
                        "mod": mod,
                        "config_opt": option,
                        "series_page": series_page,
                        "force_hidden": force_hidden,
                    },
                },
            )
            return

        items_per_page = 5
        total_pages = max(1, ceil(len(new_items) / items_per_page))
        new_series_page = min(series_page, total_pages - 1)

        await self.inline__configure_option(
            call,
            mod=mod,
            config_opt=option,
            force_hidden=force_hidden,
            obj_type=obj_type,
            series_page=new_series_page,
        )

    def _generate_series_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
        series_page: int = 0,
        force_hidden: bool = False,
    ) -> list:
        use_chat_input = self.config["chat_input"] and not self._is_hidden(mod, option)
        inline_msg_id = getattr(call, "inline_message_id", None)
        is_hidden = self._is_hidden(mod, option) and not force_hidden

        mod_instance = self.lookup(mod)
        raw_items = mod_instance.config[option]
        if raw_items is None:
            items = []
        elif isinstance(raw_items, (list, tuple, set)):
            items = list(raw_items)
        else:
            items = [raw_items]

        enter_btn = (
            {
                "text": self.strings["enter_value_btn"],
                "callback": self.inline__prompt_chat_input,
                "args": ("set", mod, option),
                "kwargs": {"obj_type": obj_type},
            }
            if use_chat_input
            else {
                "text": self.strings["enter_value_btn"],
                "input": self.strings["enter_value_desc"],
                "handler": self.inline__set_config,
                "args": (mod, option, inline_msg_id),
                "kwargs": {"obj_type": obj_type},
            }
        )

        add_btn = (
            {
                "text": self.strings["add_item_btn"],
                "callback": self.inline__prompt_chat_input,
                "args": ("add", mod, option),
                "kwargs": {"obj_type": obj_type},
            }
            if use_chat_input
            else {
                "text": self.strings["add_item_btn"],
                "input": self.strings["add_item_desc"],
                "handler": self.inline__add_item,
                "args": (mod, option, inline_msg_id),
                "kwargs": {"obj_type": obj_type},
            }
        )

        remove_btn = (
            {
                "text": self.strings["remove_item_btn"],
                "callback": self.inline__prompt_chat_input,
                "args": ("remove", mod, option),
                "kwargs": {"obj_type": obj_type},
            }
            if use_chat_input
            else {
                "text": self.strings["remove_item_btn"],
                "input": self.strings["remove_item_desc"],
                "handler": self.inline__remove_item,
                "args": (mod, option, inline_msg_id),
                "kwargs": {"obj_type": obj_type},
            }
        )

        kb = [[enter_btn, add_btn]]
        if items and use_chat_input:
            kb.append([remove_btn])

        items_per_page = 5
        total_pages = max(1, ceil(len(items) / items_per_page))
        series_page = min(max(0, series_page), total_pages - 1)

        page_items = items[
            series_page * items_per_page : (series_page + 1) * items_per_page
        ]
        for offset, item in enumerate(page_items):
            actual_idx = series_page * items_per_page + offset
            label = self._format_series_item_label(actual_idx + 1, item, is_hidden)
            kb.append(
                [
                    {
                        "text": label,
                        "callback": self.inline__remove_series_index,
                        "args": (mod, option, actual_idx),
                        "kwargs": {
                            "obj_type": obj_type,
                            "series_page": series_page,
                            "force_hidden": force_hidden,
                        },
                    }
                ]
            )

        if total_pages > 1:
            pagination_row = []
            if series_page > 0:
                pagination_row.append(
                    {
                        "text": "◀️",
                        "callback": self.inline__configure_option,
                        "kwargs": {
                            "mod": mod,
                            "config_opt": option,
                            "obj_type": obj_type,
                            "series_page": series_page - 1,
                            "force_hidden": force_hidden,
                        },
                    }
                )
            pagination_row.append(
                {
                    "text": f"{series_page + 1}/{total_pages}",
                    "callback": self.inline__configure_option,
                    "kwargs": {
                        "mod": mod,
                        "config_opt": option,
                        "obj_type": obj_type,
                        "series_page": series_page,
                        "force_hidden": force_hidden,
                    },
                }
            )
            if series_page < total_pages - 1:
                pagination_row.append(
                    {
                        "text": "▶️",
                        "callback": self.inline__configure_option,
                        "kwargs": {
                            "mod": mod,
                            "config_opt": option,
                            "obj_type": obj_type,
                            "series_page": series_page + 1,
                            "force_hidden": force_hidden,
                        },
                    }
                )
            kb.append(pagination_row)

        if mod_instance.config[option] != mod_instance.config.getdef(option):
            kb.append(
                [
                    {
                        "text": self.strings["set_default_btn"],
                        "callback": self.inline__reset_default,
                        "args": (mod, option),
                        "kwargs": {"obj_type": obj_type},
                    }
                ]
            )

        kb.append(
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ]
        )
        return kb

    async def _choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            self.lookup(mod).config[option] = value
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await call.edit(
            self.strings[
                "option_saved" if isinstance(obj_type, bool) else "option_saved_lib"
            ].format(
                utils.escape_html(option),
                utils.escape_html(mod),
                self._get_inline_value(mod, option),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, option, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

        await call.answer("✅")

    async def _multi_choice_set_value(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        value: bool,
        obj_type: bool | str = False,
    ):
        try:
            if value in self.lookup(mod).config._config[option].value:
                self.lookup(mod).config._config[option].value.remove(value)
            else:
                self.lookup(mod).config._config[option].value += [value]

            self.lookup(mod).config.reload()
        except loader.validators.ValidationError as e:
            await call.edit(
                self.strings["validation_error"].format(e.args[0]),
                reply_markup={
                    "text": self.strings["try_again"],
                    "callback": self.inline__configure_option,
                    "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": option},
                },
            )
            return

        await self.inline__configure_option(
            call, mod=mod, config_opt=option, force_hidden=False, obj_type=obj_type
        )
        await call.answer("✅")

    def _generate_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        use_chat_input = self.config["chat_input"] and not self._is_hidden(mod, option)
        inline_msg_id = getattr(call, "inline_message_id", None)
        return [
            [
                (
                    {
                        "text": self.strings["enter_value_btn"],
                        "callback": self.inline__prompt_chat_input,
                        "args": ("set", mod, option),
                        "kwargs": {"obj_type": obj_type},
                    }
                    if use_chat_input
                    else {
                        "text": self.strings["enter_value_btn"],
                        "input": self.strings["enter_value_desc"],
                        "handler": self.inline__set_config,
                        "args": (mod, option, inline_msg_id),
                        "kwargs": {"obj_type": obj_type},
                    }
                )
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if self.lookup(mod).config[option] == value else '🔘'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    def _generate_multi_choice_markup(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ) -> list:
        possible_values = list(
            self.lookup(mod)
            .config._config[option]
            .validator.validate.keywords["possible_values"]
        )
        use_chat_input = self.config["chat_input"] and not self._is_hidden(mod, option)
        inline_msg_id = getattr(call, "inline_message_id", None)
        return [
            [
                (
                    {
                        "text": self.strings["enter_value_btn"],
                        "callback": self.inline__prompt_chat_input,
                        "args": ("set", mod, option),
                        "kwargs": {"obj_type": obj_type},
                    }
                    if use_chat_input
                    else {
                        "text": self.strings["enter_value_btn"],
                        "input": self.strings["enter_value_desc"],
                        "handler": self.inline__set_config,
                        "args": (mod, option, inline_msg_id),
                        "kwargs": {"obj_type": obj_type},
                    }
                )
            ],
            *utils.chunks(
                [
                    {
                        "text": (
                            f"{'☑️' if value in self.lookup(mod).config[option] else '◻️'} "
                            f"{value if len(str(value)) < 20 else str(value)[:20]}"
                        ),
                        "callback": self._multi_choice_set_value,
                        "args": (mod, option, value, obj_type),
                    }
                    for value in possible_values
                ],
                2,
            )[
                : (
                    6
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else 7
                )
            ],
            [
                *(
                    [
                        {
                            "text": self.strings["set_default_btn"],
                            "callback": self.inline__reset_default,
                            "args": (mod, option),
                            "kwargs": {"obj_type": obj_type},
                        }
                    ]
                    if self.lookup(mod).config[option]
                    != self.lookup(mod).config.getdef(option)
                    else []
                )
            ],
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__configure,
                    "args": (mod,),
                    "style": "primary",
                    "kwargs": self._guess_back_to_page(mod, option, obj_type),
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ],
        ]

    async def inline__configure_option(
        self,
        call: InlineCall,
        page: int = 0,
        mod: str = "",
        config_opt: str = "",
        force_hidden: bool = False,
        obj_type: bool | str = False,
        series_page: int = 0,
    ):
        module = self.lookup(mod)
        args = [
            utils.escape_html(config_opt),
            utils.escape_html(mod),
            utils.escape_non_html(module.config.getdoc(config_opt)),
            self.prep_value(module.config.getdef(config_opt)),
            (
                self.prep_value(module.config[config_opt])
                if not module.config._config[config_opt].validator
                or module.config._config[config_opt].validator.internal_id != "Hidden"
                or force_hidden
                else self.hide_value(module.config[config_opt])
            ),
        ]

        if (
            module.config._config[config_opt].validator
            and module.config._config[config_opt].validator.internal_id == "Hidden"
        ):
            additonal_button_row = (
                [
                    [
                        {
                            "text": self.strings["hide_value"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": False,
                                "series_page": series_page,
                            },
                        }
                    ]
                ]
                if force_hidden
                else [
                    [
                        {
                            "text": self.strings["show_hidden"],
                            "callback": self.inline__configure_option,
                            "kwargs": {
                                "obj_type": obj_type,
                                "mod": mod,
                                "config_opt": config_opt,
                                "force_hidden": True,
                                "series_page": series_page,
                            },
                        }
                    ]
                ]
            )
        else:
            additonal_button_row = []

        try:
            validator = module.config._config[config_opt].validator
            doc = utils.escape_html(
                next(
                    (
                        validator.doc[lang]
                        for original_lang in self._db.get(
                            translations.__name__, "lang", "en"
                        ).split(" ")
                        for lang in translations.iter_language_codes(original_lang)
                        if lang in validator.doc
                    ),
                    validator.doc["en"],
                )
            )
        except Exception:
            doc = None
            validator = None
            args += [""]
        else:
            args += [
                self.strings["typehint"].format(
                    doc,
                    eng_art="n" if doc.lower().startswith(tuple("euioay")) else "",
                )
            ]
            text = self.strings[
                (
                    "configuring_option"
                    if isinstance(obj_type, bool)
                    else "configuring_option_lib"
                )
            ].format(*args)
            text, pagination = self._paginate_text_markup(
                text,
                page,
                functools.partial(
                    self.inline__configure_option,
                    mod=mod,
                    config_opt=config_opt,
                    force_hidden=force_hidden,
                    obj_type=obj_type,
                    series_page=series_page,
                ),
            )
            match validator.internal_id:
                case "Boolean":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_bool_markup(mod, config_opt, obj_type),
                            pagination,
                        ),
                    )
                    return
                case "Series":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_series_markup(
                                call,
                                mod,
                                config_opt,
                                obj_type,
                                series_page=series_page,
                                force_hidden=force_hidden,
                            ),
                            pagination,
                        ),
                    )
                    return
                case "Choice":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_choice_markup(
                                call, mod, config_opt, obj_type
                            ),
                            pagination,
                        ),
                    )
                    return
                case "MultiChoice":
                    await call.edit(
                        text,
                        reply_markup=additonal_button_row
                        + self._put_pagination_before_nav(
                            self._generate_multi_choice_markup(
                                call, mod, config_opt, obj_type
                            ),
                            pagination,
                        ),
                    )
                    return

        text = self.strings[
            (
                "configuring_option"
                if isinstance(obj_type, bool)
                else "configuring_option_lib"
            )
        ].format(*args)

        text, pagination = self._paginate_text_markup(
            text,
            page,
            functools.partial(
                self.inline__configure_option,
                mod=mod,
                config_opt=config_opt,
                force_hidden=force_hidden,
                obj_type=obj_type,
                series_page=series_page,
            ),
        )

        use_chat_input = self.config["chat_input"] and not self._is_hidden(
            mod, config_opt
        )
        inline_msg_id = getattr(call, "inline_message_id", None)
        enter_btn = (
            {
                "text": self.strings["enter_value_btn"],
                "callback": self.inline__prompt_chat_input,
                "args": ("set", mod, config_opt),
                "kwargs": {"obj_type": obj_type},
            }
            if use_chat_input
            else {
                "text": self.strings["enter_value_btn"],
                "input": self.strings["enter_value_desc"],
                "handler": self.inline__set_config,
                "args": (mod, config_opt, inline_msg_id),
                "kwargs": {"obj_type": obj_type},
            }
        )

        await call.edit(
            text,
            reply_markup=additonal_button_row
            + [
                [enter_btn],
                [
                    {
                        "text": self.strings["set_default_btn"],
                        "callback": self.inline__reset_default,
                        "args": (mod, config_opt),
                        "kwargs": {"obj_type": obj_type},
                    }
                ],
                *pagination,
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "style": "primary",
                        "kwargs": self._guess_back_to_page(mod, config_opt, obj_type),
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ],
            ],
        )

    async def inline__prompt_chat_input(
        self,
        call: InlineCall,
        action: str,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        unit_id = (
            getattr(call, "unit_id", None)
            or getattr(getattr(call, "form", {}), "get", lambda k: None)("id")
            or utils.rand(16)
        )
        if unit_id in self._active_chat_inputs:
            old_session = self._active_chat_inputs.pop(unit_id)
            if "future" in old_session and not old_session["future"].done():
                old_session["future"].cancel()
            if "handler" in old_session:
                with contextlib.suppress(Exception):
                    self._client.remove_event_handler(
                        old_session["handler"], events.NewMessage
                    )

        unit = (
            self.inline._units.get(unit_id)
            if hasattr(self, "inline") and hasattr(self.inline, "_units")
            else None
        )

        target_chat_id = None
        if unit and unit.get("chat") is not None:
            target_chat_id = self._normalize_chat_id(unit.get("chat"))
        if target_chat_id is None and unit and unit.get("caller") is not None:
            target_chat_id = self._normalize_chat_id(unit.get("caller"))
        if target_chat_id is None:
            call_chat = getattr(call, "chat_id", None) or getattr(
                getattr(call, "message", None), "chat_id", None
            )
            target_chat_id = self._normalize_chat_id(call_chat)

        top_msg_id = (
            (unit.get("top_msg_id") if unit else None)
            or (
                utils.get_topic(unit.get("caller"))
                if unit and unit.get("caller")
                else None
            )
            or (
                utils.get_topic(getattr(call, "message", None))
                if hasattr(call, "message")
                else None
            )
        )

        button_sender_id = getattr(call, "sender_id", None) or getattr(
            getattr(call, "from_user", None), "id", None
        )

        match action:
            case "add":
                prompt_key = (
                    "chat_input_prompt_add"
                    if isinstance(obj_type, bool)
                    else "chat_input_prompt_add_lib"
                )
            case "remove":
                prompt_key = (
                    "chat_input_prompt_remove"
                    if isinstance(obj_type, bool)
                    else "chat_input_prompt_remove_lib"
                )
            case _:
                prompt_key = (
                    "chat_input_prompt_set"
                    if isinstance(obj_type, bool)
                    else "chat_input_prompt_set_lib"
                )

        text = self.strings[prompt_key].format(
            utils.escape_html(option),
            utils.escape_html(mod),
            self._get_inline_value(mod, option),
        )

        reply_markup = [
            [
                {
                    "text": self.strings["cancel_btn"],
                    "callback": self.inline__cancel_chat_input,
                    "args": (mod, option),
                    "kwargs": {"obj_type": obj_type},
                    "style": "danger",
                }
            ]
        ]

        await call.edit(text, reply_markup=reply_markup)
        with contextlib.suppress(Exception):
            await call.answer()

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        async def _message_handler(event):
            if future.done():
                return

            if target_chat_id is not None:
                msg_chat_id = self._normalize_chat_id(event.message)
                if msg_chat_id != target_chat_id:
                    return

            if top_msg_id is not None and utils.get_topic(event.message) != top_msg_id:
                return

            msg_sender_id = event.sender_id or getattr(event.message, "sender_id", None)
            my_id = getattr(self._client, "tg_id", None)

            if button_sender_id is not None:
                if button_sender_id == my_id:
                    if not event.out and msg_sender_id != my_id:
                        return
                else:
                    if msg_sender_id != button_sender_id:
                        return
            else:
                allowed_senders = [my_id]
                if hasattr(self._client, "dispatcher") and hasattr(
                    self._client.dispatcher, "security"
                ):
                    allowed_senders += self._client.dispatcher.security._owner or []
                if hasattr(self, "inline") and hasattr(self.inline, "_me"):
                    allowed_senders.append(self.inline._me)
                if not event.out and msg_sender_id not in allowed_senders:
                    return

            raw_text = (
                event.message.raw_text or getattr(event.message, "message", "") or ""
            ).strip()
            if not raw_text:
                return

            prefixes = {".", "/"}
            try:
                if hasattr(self, "get_prefixes"):
                    prefixes.update(self.get_prefixes())
                elif hasattr(self._client, "loader"):
                    prefixes.update(self._client.loader.get_prefixes())
            except Exception:
                pass
            try:
                if hasattr(self, "get_prefix"):
                    prefixes.add(self.get_prefix())
            except Exception:
                pass

            cancel_cmds = {"/cancel", ".cancel"} | {f"{p}cancel" for p in prefixes if p}

            if raw_text.lower() in cancel_cmds:
                future.set_result(event.message)
                return

            is_other_cmd = False
            for p in prefixes:
                if p and raw_text.startswith(p):
                    cmd_body = raw_text[len(p) :].strip()
                    if (
                        cmd_body
                        and not cmd_body.startswith(" ")
                        and not cmd_body.startswith(p)
                    ):
                        is_other_cmd = True
                        break

            if is_other_cmd:
                return

            future.set_result(event.message)

        self._client.add_event_handler(_message_handler, events.NewMessage)
        self._active_chat_inputs[unit_id] = {
            "future": future,
            "handler": _message_handler,
            "call": call,
            "mod": mod,
            "option": option,
            "obj_type": obj_type,
        }

        asyncio.create_task(
            self._wait_chat_input(
                unit_id,
                future,
                _message_handler,
                call,
                action,
                mod,
                option,
                obj_type,
            )
        )

    async def _wait_chat_input(
        self,
        unit_id: str,
        future: asyncio.Future,
        handler: typing.Callable,
        call: InlineCall,
        action: str,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        try:
            msg = await asyncio.wait_for(future, timeout=120)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(Exception):
                await self.inline__configure_option(
                    call, mod=mod, config_opt=option, obj_type=obj_type
                )
            return
        finally:
            with contextlib.suppress(Exception):
                self._client.remove_event_handler(handler, events.NewMessage)
            self._active_chat_inputs.pop(unit_id, None)

        with contextlib.suppress(Exception):
            await msg.delete()

        raw_text = (msg.raw_text or getattr(msg, "message", "") or "").strip()

        prefixes = {".", "/"}
        try:
            if hasattr(self, "get_prefixes"):
                prefixes.update(self.get_prefixes())
            elif hasattr(self._client, "loader"):
                prefixes.update(self._client.loader.get_prefixes())
        except Exception:
            pass
        try:
            if hasattr(self, "get_prefix"):
                prefixes.add(self.get_prefix())
        except Exception:
            pass

        cancel_cmds = {"/cancel", ".cancel"} | {f"{p}cancel" for p in prefixes if p}

        if raw_text.lower() in cancel_cmds:
            await self.inline__configure_option(
                call, mod=mod, config_opt=option, obj_type=obj_type
            )
            return

        match action:
            case "add":
                await self.inline__add_item(
                    call, raw_text, mod, option, obj_type=obj_type
                )
            case "remove":
                await self.inline__remove_item(
                    call, raw_text, mod, option, obj_type=obj_type
                )
            case _:
                await self.inline__set_config(
                    call, raw_text, mod, option, obj_type=obj_type
                )

    async def inline__cancel_chat_input(
        self,
        call: InlineCall,
        mod: str,
        option: str,
        obj_type: bool | str = False,
    ):
        unit_id = getattr(call, "unit_id", None)
        if unit_id and unit_id in self._active_chat_inputs:
            session = self._active_chat_inputs.pop(unit_id)
            if "future" in session and not session["future"].done():
                session["future"].cancel()
            if "handler" in session:
                with contextlib.suppress(Exception):
                    self._client.remove_event_handler(
                        session["handler"], events.NewMessage
                    )

        await self.inline__configure_option(
            call, mod=mod, config_opt=option, obj_type=obj_type
        )

    async def inline__configure_page(
        self,
        call: InlineCall,
        page: int = 0,
        mod: str = "",
        obj_type: bool | str = False,
        folder: str | None = None,
        category: str | None = None,
    ):
        await self.inline__configure(
            call,
            mod,
            page=page,
            obj_type=obj_type,
            folder=folder,
            category=category,
        )

    async def inline__configure(
        self,
        call: InlineCall,
        mod: str,
        page: int = 0,
        obj_type: bool | str = False,
        folder: str | None = None,
        category: str | None = None,
    ):

        module = self.lookup(mod)
        grouped = module.config.grouped_options()

        def fmt_value(option: str) -> str:
            value = self._get_inline_value(mod, option)
            if len(value) >= 200:
                value = list(utils.smart_split(*html.parse(value), 200))[0] + "..."
            return value

        close_btn = {
            "text": self.strings["close_btn"],
            "action": "close",
            "style": "danger",
        }

        if category is not None:
            params = list(grouped.get(category, []))
            option_lines = [
                f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            options_text = "\n".join(option_lines) if option_lines else "No options"

            cat_doc = self._get_category_doc(module, category)

            cat_text = self.strings[
                (
                    "configuring_category"
                    if isinstance(obj_type, bool)
                    else "configuring_category_lib"
                )
            ].format(
                utils.escape_html(mod),
                utils.escape_html(category),
                utils.escape_html(cat_doc),
                options_text,
            )
            cat_text, pagination = self._paginate_text_markup(
                cat_text,
                page,
                functools.partial(
                    self.inline__configure_page,
                    mod=mod,
                    obj_type=obj_type,
                    category=category,
                ),
            )

            return await call.edit(
                cat_text,
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + pagination
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__configure,
                            "args": (mod,),
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        elif folder is not None:
            params = list(module.config)
            option_lines = [
                f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{utils.escape_html(p)}</code>: {fmt_value(p)}"
                for p in params
            ]
            text = "\n".join(option_lines) if option_lines else "No options"
            text = self.strings[
                ("configuring_mod" if isinstance(obj_type, bool) else "configuring_lib")
            ].format(utils.escape_html(mod), text)
            text, pagination = self._paginate_text_markup(
                text,
                page,
                functools.partial(
                    self.inline__configure_page,
                    mod=mod,
                    obj_type=obj_type,
                    folder=folder,
                ),
            )

            return await call.edit(
                text,
                reply_markup=list(
                    utils.chunks(
                        [
                            {
                                "text": opt,
                                "callback": self.inline__configure_option,
                                "kwargs": {
                                    "obj_type": obj_type,
                                    "mod": mod,
                                    "config_opt": opt,
                                },
                            }
                            for opt in params
                        ],
                        2,
                    )
                )
                + pagination
                + [
                    [
                        {
                            "text": self.strings["back_btn"],
                            "callback": self.inline__global_config,
                            "style": "primary",
                            "kwargs": {"obj_type": obj_type},
                        },
                        close_btn,
                    ]
                ],
            )

        sections = []
        btns = []
        for section_name, section_params in grouped.items():
            if section_name is None:
                visible = [
                    p
                    for p in section_params
                    if not getattr(module.config._config.get(p), "folder", None)
                ]
                if not visible:
                    continue
                sections.append(
                    "\n".join(
                        "<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{}</code>: {}".format(
                            utils.escape_html(p), fmt_value(p)
                        )
                        for p in visible
                    )
                )
                btns += [
                    {
                        "text": opt,
                        "callback": self.inline__configure_option,
                        "kwargs": {"obj_type": obj_type, "mod": mod, "config_opt": opt},
                    }
                    for opt in visible
                ]
            else:
                cat_lines = [
                    "∟ <tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <code>{}</code>: {}".format(
                        utils.escape_html(p), fmt_value(p)
                    )
                    for p in section_params
                ]
                cat_text = [
                    self.strings["category_header"].format(
                        utils.escape_html(section_name)
                    ),
                    "<blockquote expandable>" + "\n".join(cat_lines),
                    "</blockquote>",
                ]
                sections.append("\n".join(cat_text))
                btns.append(
                    {
                        "text": f"📂 {section_name}",
                        "callback": self.inline__configure,
                        "args": (mod,),
                        "kwargs": {"obj_type": obj_type, "category": section_name},
                    }
                )

        text = "\n".join(sections).lstrip("\n") if sections else "No options"
        text = self.strings[
            "configuring_mod" if isinstance(obj_type, bool) else "configuring_lib"
        ].format(utils.escape_html(mod), text)
        text, pagination = self._paginate_text_markup(
            text,
            page,
            functools.partial(self.inline__configure_page, mod=mod, obj_type=obj_type),
        )

        await call.edit(
            text,
            reply_markup=list(utils.chunks(btns, 2))
            + pagination
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__global_config,
                        "style": "primary",
                        "kwargs": {"obj_type": obj_type},
                    },
                    close_btn,
                ]
            ],
        )

    def _fuzzy_lookup_configurable(self, query: str) -> tuple[str | None, bool]:
        query_lower = query.lower()
        best_score = -1.0
        best_name: str | None = None

        for mod in self.allmodules.modules:
            if not hasattr(mod, "config") or not mod.config:
                continue
            try:
                mod_name = (
                    mod.strings("name")
                    if callable(mod.strings)
                    else mod.__class__.__name__
                )
            except Exception:
                mod_name = mod.__class__.__name__

            cls_name = mod.__class__.__name__
            names = {mod_name, cls_name}
            if cls_name.endswith("Mod"):
                names.add(cls_name[:-3])

            for name in names:
                if name.lower() == query_lower:
                    return mod_name, True
                score = difflib.SequenceMatcher(None, query_lower, name.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = mod_name

        for lib in self.allmodules.libraries:
            if not hasattr(lib, "config") or not lib.config:
                continue
            lib_name = getattr(lib, "name", lib.__class__.__name__)
            if lib_name.lower() == query_lower:
                return lib_name, True
            score = difflib.SequenceMatcher(None, query_lower, lib_name.lower()).ratio()
            if score > best_score:
                best_score = score
                best_name = lib_name

        return best_name, False

    def _get_all_folders(self) -> dict:
        folders = {}
        for mod in self.allmodules.modules:
            if not hasattr(mod, "config") or not mod.config:
                continue
            mod_name = (
                mod.strings("name") if callable(mod.strings) else mod.__class__.__name__
            )
            module_folders = set()
            for param in mod.config:
                config_value = mod.config._config.get(param)
                if (
                    config_value
                    and hasattr(config_value, "folder")
                    and config_value.folder
                ):
                    module_folders.add(config_value.folder)

            for folder_name in module_folders:
                if folder_name not in folders:
                    folders[folder_name] = {}
                folders[folder_name][mod_name] = [p for p in mod.config]
        try:
            preset_folders = self.db.get("presets", "folders")
        except Exception:
            preset_folders = {}

        if preset_folders:
            for folder_name, mod_list in preset_folders.items():
                if folder_name not in folders:
                    folders[folder_name] = {}
                for raw_mod in mod_list:
                    for mod in self.allmodules.modules:
                        try:
                            if mod.__class__.__name__.lower() == raw_mod.lower():
                                mod_name = (
                                    mod.strings("name")
                                    if callable(mod.strings)
                                    else mod.__class__.__name__
                                )
                                if mod_name not in folders[folder_name]:
                                    folders[folder_name][mod_name] = [
                                        p for p in mod.config
                                    ]
                                break
                        except Exception:
                            continue

        return folders

    async def inline__choose_category(self, call: Message | InlineCall):
        all_folders = self._get_all_folders()

        folder_btns = [
            {
                "text": f"📁 {folder_name}",
                "callback": self.inline__global_folder,
                "kwargs": {"folder": folder_name},
            }
            for folder_name in sorted(all_folders.keys())
        ]

        await utils.answer(
            call,
            self.strings["choose_core"],
            reply_markup=[
                [
                    {
                        "text": self.strings["builtin"],
                        "callback": self.inline__global_config,
                        "kwargs": {"obj_type": True},
                    },
                    {
                        "text": self.strings["external"],
                        "callback": self.inline__global_config,
                    },
                ],
                *(
                    [
                        [
                            {
                                "text": self.strings["libraries"],
                                "callback": self.inline__global_config,
                                "kwargs": {"obj_type": "library"},
                            }
                        ]
                    ]
                    if self.allmodules.libraries
                    and any(hasattr(lib, "config") for lib in self.allmodules.libraries)
                    else []
                ),
                *list(utils.chunks(folder_btns, 2)),
                [
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    }
                ],
            ],
        )

    async def _send_initial_config_form(
        self,
        message: Message,
        handler: typing.Callable[..., typing.Awaitable[typing.Any]],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        draft = _InlineFormDraft()
        await handler(draft, *args, **kwargs)

        if draft.text is None:
            return

        form_kwargs = dict(draft.kwargs)
        form_kwargs.pop("inline_message_id", None)

        await self.inline.form(
            draft.text,
            message=message,
            reply_markup=draft.reply_markup,
            silent=True,
            **form_kwargs,
        )

    async def inline__global_folder(
        self,
        call: InlineCall,
        folder: str,
    ):
        all_folders = self._get_all_folders()
        folder_options = all_folders.get(folder, {})

        btns = [
            {
                "text": f"{mod_name}",
                "callback": self.inline__configure,
                "kwargs": {"obj_type": False, "mod": mod_name, "folder": folder},
            }
            for mod_name in sorted(folder_options.keys())
        ]

        text_parts = []
        for mod_name, params in folder_options.items():
            try:
                raw_parts = []
                for param in params:
                    try:
                        raw_value = str(self.lookup(mod_name).config[param])
                        if len(raw_value) > 100:
                            raw_value = raw_value[:100] + "..."
                        raw_parts.append(
                            f"<code>{utils.escape_html(param)}</code>: <code>{utils.escape_html(raw_value)}</code>"
                        )
                    except Exception:
                        raw_parts.append(f"<code>{utils.escape_html(param)}</code>")
                text_parts.append(
                    f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <b>{utils.escape_html(mod_name)}</b>"
                )
            except Exception:
                text_parts.append(
                    f"<tg-emoji emoji-id=5253713110111365241>▫️</tg-emoji> <b>{utils.escape_html(mod_name)}</b>"
                )

        await call.edit(
            self.strings["configuring_folder"].format(
                utils.escape_html(folder),
                "\n".join(text_parts) if text_parts else "No options",
            ),
            reply_markup=list(utils.chunks(btns, 1))
            + [
                [
                    {
                        "text": self.strings["back_btn"],
                        "callback": self.inline__choose_category,
                        "style": "primary",
                    },
                    {
                        "text": self.strings["close_btn"],
                        "action": "close",
                        "style": "danger",
                    },
                ]
            ],
        )

    async def inline__global_config(
        self,
        call: InlineCall,
        page: int = 0,
        obj_type: bool | str = False,
    ):
        if isinstance(obj_type, bool):
            to_config = [
                mod.strings("name")
                for mod in self.allmodules.modules
                if hasattr(mod, "config")
                and callable(mod.strings)
                and (mod.__origin__.startswith("<core") or not obj_type)
                and (not mod.__origin__.startswith("<core") or obj_type)
            ]
        else:
            to_config = [
                lib.name for lib in self.allmodules.libraries if hasattr(lib, "config")
            ]

        to_config.sort()

        kb = []
        for mod_row in utils.chunks(
            to_config[page * NUM_ROWS * ROW_SIZE : (page + 1) * NUM_ROWS * ROW_SIZE],
            3,
        ):
            row = [
                {
                    "text": btn,
                    "callback": self.inline__configure,
                    "args": (btn,),
                    "kwargs": {"obj_type": obj_type},
                }
                for btn in mod_row
            ]
            kb += [row]

        if len(to_config) > NUM_ROWS * ROW_SIZE:
            kb += self.inline.build_pagination(
                callback=functools.partial(
                    self.inline__global_config, obj_type=obj_type
                ),
                total_pages=ceil(len(to_config) / (NUM_ROWS * ROW_SIZE)),
                current_page=page + 1,
            )

        kb += [
            [
                {
                    "text": self.strings["back_btn"],
                    "callback": self.inline__choose_category,
                    "style": "primary",
                },
                {
                    "text": self.strings["close_btn"],
                    "action": "close",
                    "style": "danger",
                },
            ]
        ]

        await call.edit(
            self.strings[
                "configure" if isinstance(obj_type, bool) else "configure_lib"
            ],
            reply_markup=kb,
        )

    @staticmethod
    def _get_config_obj_type(instance: typing.Any) -> bool | str:
        if isinstance(instance, loader.Library):
            return "library"

        return instance.__origin__.startswith("<core")

    def _resolve_configurable(
        self,
        query: str,
    ) -> tuple[str | None, typing.Any, bool | str | None]:
        if (instance := self.lookup(query)) and hasattr(instance, "config"):
            return query, instance, self._get_config_obj_type(instance)

        fuzzy_name, _ = self._fuzzy_lookup_configurable(query)
        if fuzzy_name and (instance := self.lookup(fuzzy_name)):
            if hasattr(instance, "config") and instance.config:
                return fuzzy_name, instance, self._get_config_obj_type(instance)

        return None, None, None

    @staticmethod
    def _category_option(
        instance: typing.Any,
        category: str,
        option: str,
    ) -> str | None:
        if option in ElysConfigMod._config_categories(instance).get(category, []):
            return option

        return None

    def _parse_config_update(
        self,
        instance: typing.Any,
        raw: str,
        reply_text: str | None = None,
        first_part: bool = False,
    ) -> tuple[str, str] | None:
        if first_part:
            split = raw.split(maxsplit=3)
            if len(split) >= 4:
                _, category, option, value = split
                if config_opt := self._category_option(instance, category, option):
                    return config_opt, value

            split = raw.split(maxsplit=2)
            if len(split) >= 3 and split[1] in instance.config:
                return split[1], split[2]

            if len(split) == 2 and reply_text and split[1] in instance.config:
                return split[1], reply_text

            return None

        split = raw.split(maxsplit=2)
        if len(split) >= 3:
            category, option, value = split
            if config_opt := self._category_option(instance, category, option):
                return config_opt, value

        split = raw.split(maxsplit=1)
        if len(split) >= 2:
            return split[0], split[1]

        return None

    async def _apply_config_updates(
        self,
        message: Message,
        mod: str,
        instance: typing.Any,
        first_update: tuple[str, str],
        parts: list[str],
    ) -> None:
        updates = []

        for option, value in [first_update]:
            if option not in instance.config:
                await utils.answer(message, self.strings["no_option"])
                return

            try:
                instance.config[option] = value
            except loader.validators.ValidationError as e:
                await utils.answer(
                    message, self.strings["validation_error"].format(e.args[0])
                )
                return

            updates.append((option, self._get_value(mod, option)))

        for part in parts:
            update = self._parse_config_update(instance, part)
            if update is None:
                await utils.answer(message, self.strings["args"])
                return

            option, value = update
            if option not in instance.config:
                await utils.answer(message, self.strings["no_option"])
                return

            try:
                instance.config[option] = value
            except loader.validators.ValidationError as e:
                await utils.answer(
                    message, self.strings["validation_error"].format(e.args[0])
                )
                return

            updates.append((option, self._get_value(mod, option)))

        lines = []
        for option, value in updates:
            lines.append(
                self.strings[
                    (
                        "option_saved"
                        if isinstance(instance, loader.Module)
                        else "option_saved_lib"
                    )
                ].format(utils.escape_html(option), utils.escape_html(mod), value)
            )

        await utils.answer(message, "\n".join(lines))

    async def _configcmd_impl(self, message: Message):
        raw = utils.get_args_raw(message).strip()
        args_s = raw.split()

        if not args_s:
            await self.inline__choose_category(message)
            return

        mod_name, instance, obj_type = self._resolve_configurable(args_s[0])
        if not mod_name or not instance or obj_type is None:
            await self.inline__choose_category(message)
            return

        parts = [part.strip() for part in raw.split("&&") if part.strip()]
        reply = await message.get_reply_message()
        reply_text = reply.raw_text if reply and reply.raw_text else None
        first_update = self._parse_config_update(
            instance,
            parts[0],
            reply_text=reply_text,
            first_part=True,
        )

        if first_update is not None:
            await self._apply_config_updates(
                message,
                mod_name,
                instance,
                first_update,
                parts[1:],
            )
            return

        if len(args_s) == 1:
            await self._send_initial_config_form(
                message,
                self.inline__configure,
                mod_name,
                obj_type=obj_type,
            )
            return

        if args_s[1] in instance.config.keys():
            await self._send_initial_config_form(
                message,
                self.inline__configure_option,
                mod=mod_name,
                config_opt=args_s[1],
                obj_type=obj_type,
            )
            return

        if args_s[1] in self._config_categories(instance):
            if len(args_s) >= 3 and (
                config_opt := self._category_option(instance, args_s[1], args_s[2])
            ):
                await self._send_initial_config_form(
                    message,
                    self.inline__configure_option,
                    mod=mod_name,
                    config_opt=config_opt,
                    obj_type=obj_type,
                )
                return

            await self._send_initial_config_form(
                message,
                self.inline__configure,
                mod_name,
                obj_type=obj_type,
                category=args_s[1],
            )
            return

        await self.inline__choose_category(message)

    async def configcmd(self, message: Message):
        await self._configcmd_impl(message)

    @loader.command(alias="fcfg")
    async def cfgcmd(self, message: Message):
        await self._configcmd_impl(message)
