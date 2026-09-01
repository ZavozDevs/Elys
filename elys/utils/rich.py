# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import base64
import html


def _escape(value) -> str:
    return html.escape(str(value), quote=False)


def _attribute(value) -> str:
    return html.escape(str(value), quote=True)


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _escape(value)

    name = type(value).__name__
    if name == "TextEmpty":
        return ""
    if name == "TextPlain":
        return _escape(getattr(value, "text", ""))
    if name == "TextConcat":
        return "".join(_text(item) for item in getattr(value, "texts", []))
    if name == "TextWithEntities":
        from elystl.extensions import html as html_parser

        return html_parser.unparse(
            getattr(value, "text", ""),
            getattr(value, "entities", None) or [],
        )

    tags = {
        "TextBold": ("<b>", "</b>"),
        "TextItalic": ("<i>", "</i>"),
        "TextUnderline": ("<u>", "</u>"),
        "TextStrike": ("<s>", "</s>"),
        "TextFixed": ("<code>", "</code>"),
        "TextSubscript": ("<sub>", "</sub>"),
        "TextSuperscript": ("<sup>", "</sup>"),
        "TextMarked": ("<mark>", "</mark>"),
        "TextSpoiler": ("<tg-spoiler>", "</tg-spoiler>"),
    }
    if name in tags:
        start, end = tags[name]
        return start + _text(getattr(value, "text", None)) + end

    if name in {"TextUrl", "TextAutoUrl"}:
        url = getattr(value, "url", None) or getattr(value, "text", "")
        return f'<a href="{_attribute(url)}">{_text(getattr(value, "text", None))}</a>'
    if name in {"TextEmail", "TextAutoEmail"}:
        email = getattr(value, "email", None) or getattr(value, "text", "")
        return f'<a href="mailto:{_attribute(email)}">{_text(getattr(value, "text", None))}</a>'
    if name in {"TextPhone", "TextAutoPhone"}:
        phone = getattr(value, "phone", None) or getattr(value, "text", "")
        return f'<a href="tel:{_attribute(phone)}">{_text(getattr(value, "text", None))}</a>'
    if name == "TextMentionName":
        return f'<a href="tg://user?id={_attribute(getattr(value, "user_id", ""))}">{_text(value.text)}</a>'
    if name == "TextMention":
        return _text(getattr(value, "text", None))
    if name in {"TextHashtag", "TextCashtag", "TextBotCommand", "TextBankCard"}:
        return _text(getattr(value, "text", None))
    if name == "TextCustomEmoji":
        doc_id = _attribute(getattr(value, "document_id", ""))
        alt = (
            getattr(value, "alt", None)
            or getattr(getattr(value, "text", None), "text", None)
            or getattr(value, "text", None)
            or "⭐️"
        )
        return f'<tg-emoji emoji-id="{doc_id}">{_escape(alt)}</tg-emoji>'
    if name == "TextImage":
        return f'<i>[image:{_attribute(getattr(value, "document_id", ""))}]</i>'
    if name == "TextMath":
        return f"<tg-math-block>{_escape(getattr(value, 'source', ''))}</tg-math-block>"
    if name == "TextDate":
        attributes = [f'date="{_attribute(getattr(value, "date", ""))}"']
        for field, tag in (
            ("relative", "relative"),
            ("short_time", "short-time"),
            ("long_time", "long-time"),
            ("short_date", "short-date"),
            ("long_date", "long-date"),
            ("day_of_week", "day-of-week"),
        ):
            if getattr(value, field, False):
                attributes.append(tag)
        return (
            f'<date {" ".join(attributes)}>{_text(getattr(value, "text", None))}</date>'
        )
    if name == "TextAnchor":
        return f'<a name="{_attribute(getattr(value, "name", ""))}">{_text(getattr(value, "text", None))}</a>'
    if name == "TextDiff":
        return _text(getattr(value, "text", None))
    if name == "TextButton":
        return _text(getattr(value, "text", None))

    nested = getattr(value, "text", None)
    if nested is not None:
        return _text(nested)
    return _escape(getattr(value, "source", ""))


def _caption(value) -> str:
    if value is None:
        return ""
    text = _text(getattr(value, "text", None))
    credit = _text(getattr(value, "credit", None))
    if credit:
        return f"{text}<cite>{credit}</cite>" if text else f"<cite>{credit}</cite>"
    return text


def _media(name: str, value) -> str:
    media_id = getattr(value, f"{name}_id", "")
    caption = _caption(getattr(value, "caption", None))
    marker = f"<i>[{name}:{_attribute(media_id)}]</i>"
    return marker + caption


def _list_item(value) -> str:
    name = type(value).__name__
    if name in {"PageListItemBlocks", "PageListOrderedItemBlocks"}:
        text = "".join(_block(item) for item in getattr(value, "blocks", []))
    else:
        text = _text(getattr(value, "text", None))
    if getattr(value, "checkbox", False):
        text = ("[x] " if getattr(value, "checked", False) else "[ ] ") + text
    attributes = []
    if name == "PageListOrderedItemBlocks" or name == "PageListOrderedItemText":
        if getattr(value, "num", None) is not None:
            attributes.append(f' value="{_attribute(value.num)}"')
    return f"<li{''.join(attributes)}>{text}</li>"


def _table_cell(value) -> str:
    tag = "th" if getattr(value, "header", False) else "td"
    attributes = []
    for field, attribute in (("colspan", "colspan"), ("rowspan", "rowspan")):
        value_ = getattr(value, field, None)
        if value_:
            attributes.append(f' {attribute}="{_attribute(value_)}"')
    if getattr(value, "align_center", False):
        attributes.append(' align="center"')
    elif getattr(value, "align_right", False):
        attributes.append(' align="right"')
    return f"<{tag}{''.join(attributes)}>{_text(getattr(value, 'text', None))}</{tag}>"


def _button(value) -> str:
    text = _text(getattr(value, "text", None))
    button_type = getattr(value, "type", None)
    type_name = type(button_type).__name__
    attributes = []
    if type_name == "InlineButtonTypeUrl":
        attributes = [
            'type="url"',
            f"url=\"{_attribute(getattr(button_type, 'url', ''))}\"",
        ]
    elif type_name == "InlineButtonTypeCallback":
        data = getattr(button_type, "data", b"")
        if isinstance(data, (bytes, bytearray, memoryview)):
            data = base64.urlsafe_b64encode(bytes(data)).decode()
        attributes = ['type="callback_data"', f'data="{_attribute(data)}"']
    elif type_name == "InlineButtonTypeSwitchInline":
        query = _attribute(getattr(button_type, "query", ""))
        tag = (
            "switch_inline_query_current_chat"
            if getattr(button_type, "same_peer", False)
            else "switch_inline_query"
        )
        attributes = [f'type="{tag}"', f'query="{query}"']
    elif type_name == "InlineButtonTypeWebView":
        attributes = [
            'type="web_app"',
            f"url=\"{_attribute(getattr(button_type, 'url', ''))}\"",
        ]
    elif type_name == "InlineButtonTypeCopy":
        attributes = [
            'type="copy_text"',
            f"text=\"{_attribute(getattr(button_type, 'copy_text', ''))}\"",
        ]
    elif type_name == "InlineButtonTypeUrlAuth":
        attributes = [
            'type="login_url"',
            f"url=\"{_attribute(getattr(button_type, 'url', ''))}\"",
        ]
    elif type_name == "InlineButtonTypeUserProfile":
        attributes = [
            'type="url"',
            f"url=\"tg://user?id={_attribute(getattr(button_type, 'user_id', ''))}\"",
        ]
    else:
        attributes = ['type="disabled"']
    style = getattr(getattr(value, "style", None), "__dict__", {})
    for key in ("bg_primary", "bg_danger", "bg_success", "link"):
        if style.get(key):
            attributes.append(f"style=\"{key.removeprefix('bg_')}\"")
            break
    return f"<tg-button {' '.join(attributes)}>{text}</tg-button>"


def _block(value) -> str:
    if value is None:
        return ""

    name = type(value).__name__
    text = _text(getattr(value, "text", None))
    simple = {
        "PageBlockTitle": "h1",
        "PageBlockSubtitle": "h2",
        "PageBlockHeading1": "h1",
        "PageBlockHeading2": "h2",
        "PageBlockHeading3": "h3",
        "PageBlockHeading4": "h4",
        "PageBlockHeading5": "h5",
        "PageBlockHeading6": "h6",
        "PageBlockHeader": "h3",
        "PageBlockSubheader": "h4",
        "PageBlockKicker": None,
        "PageBlockParagraph": None,
        "PageBlockFooter": "footer",
    }
    if name in simple:
        tag = simple[name]
        return text if tag is None else f"<{tag}>{text}</{tag}>"
    if name == "PageBlockPreformatted":
        language = getattr(value, "language", "")
        if language:
            return f'<pre><code class="language-{_attribute(language)}">{text}</code></pre>'
        return f"<pre>{text}</pre>"
    if name == "PageBlockDivider":
        return "<hr>"
    if name == "PageBlockAnchor":
        return f'<a name="{_attribute(getattr(value, "name", ""))}"></a>'
    if name in {"PageBlockBlockquote", "PageBlockPullquote"}:
        caption = _caption(getattr(value, "caption", None))
        return f"<blockquote>{text}{f'<cite>{caption}</cite>' if caption else ''}</blockquote>"
    if name == "PageBlockBlockquoteBlocks":
        blocks = "".join(_block(item) for item in getattr(value, "blocks", []))
        return f"<blockquote>{blocks}{_caption(getattr(value, 'caption', None))}</blockquote>"
    if name in {
        "PageBlockPhoto",
        "PageBlockVideo",
        "PageBlockAudio",
        "PageBlockDocument",
    }:
        return _media(name.removeprefix("PageBlock").lower(), value)
    if name == "PageBlockMap":
        return _caption(getattr(value, "caption", None))
    if name == "PageBlockButtonRow":
        buttons = "".join(_button(item) for item in getattr(value, "buttons", []))
        return f"<tg-button-row>{buttons}</tg-button-row>"
    if name in {"PageBlockCollage", "PageBlockSlideshow"}:
        return "".join(_block(item) for item in getattr(value, "items", [])) + _caption(
            getattr(value, "caption", None)
        )
    if name == "PageBlockTable":
        title = (
            _text(getattr(value, "title", None))
            if getattr(value, "title", None)
            else ""
        )
        rows = "".join(
            "<tr>"
            + "".join(_table_cell(cell) for cell in getattr(row, "cells", []))
            + "</tr>"
            for row in getattr(value, "rows", [])
        )
        return title + ("\n" if title else "") + f"<table>{rows}</table>"
    if name in {"PageBlockList", "PageBlockOrderedList"}:
        tag = "ol" if name.endswith("OrderedList") else "ul"
        attributes = ""
        if tag == "ol":
            if getattr(value, "reversed", False):
                attributes += " reversed"
            if getattr(value, "start", None) is not None:
                attributes += f' start="{_attribute(value.start)}"'
            if getattr(value, "type", None):
                attributes += f' type="{_attribute(value.type)}"'
        items = "".join(_list_item(item) for item in getattr(value, "items", []))
        return f"<{tag}{attributes}>{items}</{tag}>"
    if name == "PageBlockDetails":
        title = _text(getattr(value, "title", None))
        summary_html = f"<summary>{title}</summary>" if title else ""
        blocks = "".join(_block(item) for item in getattr(value, "blocks", []))
        return f"<details>{summary_html}{blocks}</details>"
    if name == "PageBlockMath":
        return f"<tg-math-block>{_escape(getattr(value, 'source', ''))}</tg-math-block>"
    if name == "PageBlockThinking":
        return f"<tg-thinking>{text}</tg-thinking>"
    if name == "PageBlockEmbed":
        url = getattr(value, "url", None)
        return (
            f'<a href="{_attribute(url)}">{_escape(getattr(value, "html", "") or url or "[embed]")}</a>'
            if url
            else _escape(getattr(value, "html", "[embed]"))
        )
    if name == "PageBlockEmbedPost":
        return "".join(
            _block(item) for item in getattr(value, "blocks", [])
        ) + _caption(getattr(value, "caption", None))
    if name == "PageBlockRelatedArticles":
        return _text(getattr(value, "title", None))
    if name == "PageBlockAuthorDate":
        return _text(getattr(value, "author", None))
    if name in {"PageBlockChannel", "PageBlockCover", "PageBlockUnsupported"}:
        return f"<i>[{_escape(name)}]</i>"
    nested = getattr(value, "blocks", None)
    if nested is not None:
        return "".join(_block(item) for item in nested)
    return text if text else f"<i>[{_escape(name)}]</i>"


def rich_message_to_html(rich_message) -> str:
    if rich_message is None:
        return ""
    if isinstance(rich_message, str):
        return rich_message
    if isinstance(rich_message, (list, tuple)):
        return "\n".join(
            rendered
            for rendered in (rich_message_to_html(item) for item in rich_message)
            if rendered
        )
    name = type(rich_message).__name__
    if name.startswith("Text"):
        return _text(rich_message)
    if name.startswith("PageBlock"):
        return _block(rich_message)
    if hasattr(rich_message, "blocks"):
        blocks = getattr(rich_message, "blocks", None)
        if isinstance(blocks, (list, tuple)):
            return "\n".join(
                rendered for rendered in (_block(item) for item in blocks) if rendered
            )
    rendered = _block(rich_message)
    if rendered:
        return rendered
    return _text(rich_message)


def install_rich_message_support():
    try:
        from elystl.tl.custom.message import Message
    except ImportError:
        try:
            from herokutl.tl.custom.message import Message
        except ImportError:
            from telethon.tl.custom.message import Message

    if getattr(Message, "_elys_rich_message_support", False):
        return

    def get_rich_message(self):
        native = getattr(self, "_elys_rich_message_native", None) or getattr(
            self, "rich_message_raw", None
        )
        if native is not None:
            return rich_message_to_html(native)
        return None

    def set_rich_message(self, value):
        self._elys_rich_message_native = value

    def get_rich_message_entity(self):
        return getattr(self, "_elys_rich_message_native", None) or getattr(
            self, "rich_message_raw", None
        )

    Message.rich_message = property(get_rich_message, set_rich_message)
    Message.rich_message_entity = property(get_rich_message_entity)
    Message._elys_rich_message_support = True


install_rich_message_support()
