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

import asyncio
import contextlib
import copy
import logging
import re
import time

import bs4
from deep_translator import GoogleTranslator
from elystl.extensions import html
from elystl.tl import functions, types
from elystl.tl.custom import Message
import requests

from .. import loader, utils

logger = logging.getLogger(__name__)

LANG_CODE_RE = re.compile(r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,4})?$")


@loader.tds
class Translator(loader.Module):
    """Translates text"""

    strings = {
        "name": "Translator",
        "no_args": (
            "<tg-emoji emoji-id=5210952531676504517>❌</tg-emoji> <b>No"
            " arguments provided</b>"
        ),
        "error": (
            '<tg-emoji emoji-id="5210952531676504517">❌</tg-emoji> <b>Unable to'
            " translate text</b>"
        ),
        "language": "en",
        "translated_text": (
            '<blockquote><tg-emoji emoji-id="5424772191403143504">📝</tg-emoji>'
            " Translated text:</blockquote>\n\n{tr_text}"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "only_text",
                False,
                "only translated text in .tr",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "provider",
                "telegram",
                "Translation provider to use",
                validator=loader.validators.Choice(["telegram", "google"]),
            ),
        )

    @staticmethod
    def _mask_html(html_text: str):
        opaque_map = {}
        emoji_map = {}
        link_map = {}
        btn_map = {}
        date_map = {}

        def replace_opaque(match):
            full = match.group(0)
            idx = str(len(opaque_map))
            key = f"OPQ{idx}"
            opaque_map[key] = full
            return f"[[{key}]]"

        # 1. Mask opaque blocks: code blocks, math blocks, media markers, thinking blocks
        masked = re.sub(
            r"<pre(?:\s+[^>]*)?>.*?</pre>",
            replace_opaque,
            html_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        masked = re.sub(
            r"<tg-math-block(?:\s+[^>]*)?>.*?</tg-math-block>",
            replace_opaque,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )
        masked = re.sub(
            r"<tg-thinking(?:\s+[^>]*)?>.*?</tg-thinking>",
            replace_opaque,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )
        masked = re.sub(
            r"<i>\[(?:photo|video|audio|document|image|pageblock)[^\]]*\]</i>",
            replace_opaque,
            masked,
            flags=re.IGNORECASE,
        )

        # 2. Mask indexed tags
        def replace_btn(match):
            attrs = match.group(1).strip()
            content = match.group(2)
            idx = str(len(btn_map))
            btn_map[idx] = attrs
            return f"<btn{idx}>{content}</btn{idx}>"

        masked = re.sub(
            r"<tg-button\s+([^>]+)>(.*?)</tg-button>",
            replace_btn,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )

        def replace_emoji(match):
            attrs = match.group(1).strip()
            content = match.group(2)
            idx = str(len(emoji_map))
            emoji_map[idx] = attrs
            return f"<e{idx}>{content}</e{idx}>"

        masked = re.sub(
            r"<(?:tg-emoji|emoji)\s+([^>]+)>(.*?)</(?:tg-emoji|emoji)>",
            replace_emoji,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )

        def replace_shorthand_emoji(match):
            doc_id = match.group(2)
            content = match.group(3)
            idx = str(len(emoji_map))
            emoji_map[idx] = f'emoji-id="{doc_id}"'
            return f"<e{idx}>{content}</e{idx}>"

        masked = re.sub(
            r"<(e|emoji):(\d+)>(.*?)</\1:\2>",
            replace_shorthand_emoji,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )

        def replace_link(match):
            attrs = match.group(1).strip()
            content = match.group(2)
            idx = str(len(link_map))
            link_map[idx] = attrs
            return f"<a{idx}>{content}</a{idx}>"

        masked = re.sub(
            r"<a\s+([^>]+)>(.*?)</a>",
            replace_link,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )

        def replace_date(match):
            attrs = match.group(1).strip()
            content = match.group(2)
            idx = str(len(date_map))
            date_map[idx] = attrs
            return f"<d{idx}>{content}</d{idx}>"

        masked = re.sub(
            r"<date\s+([^>]+)>(.*?)</date>",
            replace_date,
            masked,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # 3. Shorthand tag normalization
        masked = re.sub(r"(?i)<blockquote\s+expandable\s*>", "<ebq>", masked)
        masked = re.sub(r"(?i)<expandable-blockquote\s*>", "<ebq>", masked)
        masked = re.sub(r"(?i)</expandable-blockquote>", "</ebq>", masked)
        masked = re.sub(r"(?i)<blockquote>", "<bq>", masked)
        masked = re.sub(r"(?i)</blockquote>", "</bq>", masked)
        masked = re.sub(r"(?i)<(?:tg-spoiler|spoiler)>", "<sp>", masked)
        masked = re.sub(r"(?i)</(?:tg-spoiler|spoiler)>", "</sp>", masked)
        masked = re.sub(r"(?i)<code>", "<c>", masked)
        masked = re.sub(r"(?i)</code>", "</c>", masked)

        return masked, opaque_map, emoji_map, link_map, btn_map, date_map

    @staticmethod
    def _unmask_html(
        translated_text: str,
        opaque_map: dict[str, str],
        emoji_map: dict[str, str],
        link_map: dict[str, str],
        btn_map: dict[str, str],
        date_map: dict[str, str],
    ) -> str:
        res = translated_text

        # 1. Unmask indexed tags with whitespace-tolerant and case-insensitive regexes
        for idx, attrs in emoji_map.items():
            tag_pattern = rf"(?i)<\s*e\s*{re.escape(idx)}\s*>(.*?)<\s*/\s*e\s*(?:{re.escape(idx)})?\s*>"
            doc_id_match = re.search(
                r'(?:emoji-id|id|document_id)\s*=\s*["\']?(\d+)["\']?', attrs
            )
            attrs_str = (
                f'emoji-id="{doc_id_match.group(1)}"'
                if doc_id_match
                else (
                    attrs
                    if (
                        attrs.startswith("emoji-id=")
                        or attrs.startswith("id=")
                        or attrs.startswith("document_id=")
                    )
                    else f'emoji-id="{attrs}"'
                )
            )
            res = re.sub(
                tag_pattern,
                rf"<tg-emoji {attrs_str}>\1</tg-emoji>",
                res,
                flags=re.DOTALL,
            )

        for idx, attrs in link_map.items():
            tag_pattern = rf"(?i)<\s*a\s*{re.escape(idx)}\s*>(.*?)<\s*/\s*a\s*(?:{re.escape(idx)})?\s*>"
            attrs_str = (
                attrs
                if (attrs.startswith("href=") or attrs.startswith("url="))
                else f"href={attrs}"
            )
            res = re.sub(
                tag_pattern,
                rf"<a {attrs_str}>\1</a>",
                res,
                flags=re.DOTALL,
            )

        for idx, attrs in btn_map.items():
            tag_pattern = rf"(?i)<\s*btn\s*{re.escape(idx)}\s*>(.*?)<\s*/\s*btn\s*(?:{re.escape(idx)})?\s*>"
            res = re.sub(
                tag_pattern,
                rf"<tg-button {attrs}>\1</tg-button>",
                res,
                flags=re.DOTALL,
            )

        for idx, attrs in date_map.items():
            tag_pattern = rf"(?i)<\s*d\s*{re.escape(idx)}\s*>(.*?)<\s*/\s*d\s*(?:{re.escape(idx)})?\s*>"
            res = re.sub(
                tag_pattern,
                rf"<date {attrs}>\1</date>",
                res,
                flags=re.DOTALL,
            )

        # 2. Restore shorthands
        res = re.sub(r"(?i)<\s*bq\s*>", "<blockquote>", res)
        res = re.sub(r"(?i)<\s*/\s*bq\s*>", "</blockquote>", res)
        res = re.sub(r"(?i)<\s*ebq\s*>", "<blockquote expandable>", res)
        res = re.sub(r"(?i)<\s*/\s*ebq\s*>", "</blockquote>", res)
        res = re.sub(r"(?i)<\s*sp\s*>", "<tg-spoiler>", res)
        res = re.sub(r"(?i)<\s*/\s*sp\s*>", "</tg-spoiler>", res)
        res = re.sub(r"(?i)<\s*c\s*>", "<code>", res)
        res = re.sub(r"(?i)<\s*/\s*c\s*>", "</code>", res)

        # 3. Restore opaque tokens
        for key, full in opaque_map.items():
            token_pattern = rf"(?i)\[\s*\[\s*{re.escape(key)}\s*\]\s*\]"
            res = re.sub(token_pattern, lambda _, repl=full: repl, res)

        return res

    @staticmethod
    def _split_masked_chunks(text: str, max_chunk_len: int = 1800) -> list[str]:
        if len(text) <= max_chunk_len:
            return [text]
        chunks = []
        current = []
        current_len = 0
        for line in text.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > max_chunk_len and current:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            chunks.append("\n".join(current))
        return chunks

    @staticmethod
    def _translate_google_chunk(
        chunk: str, target_lang: str, source_lang: str = "auto"
    ) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        for attempt in range(3):
            try:
                resp = requests.get(
                    "https://translate.google.com/m",
                    params={"tl": target_lang, "sl": source_lang, "q": chunk},
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 429:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                if resp.status_code != 200:
                    time.sleep(0.3 * (attempt + 1))
                    continue

                soup = bs4.BeautifulSoup(resp.text, "html.parser")
                element = soup.find("div", {"class": "result-container"}) or soup.find(
                    "div", {"class": "t0"}
                )
                if not element:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                result = element.get_text()
                if (
                    "Error 500 (Server Error)" in result
                    or "That’s all we know" in result
                ):
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return result
            except Exception:
                if attempt == 2:
                    break
                time.sleep(0.3 * (attempt + 1))

        # Fallback to deep_translator if direct fetch fails
        gt = GoogleTranslator(source=source_lang, target=target_lang)
        res = gt.translate(chunk)
        if not res or "Error 500 (Server Error)" in res or "That’s all we know" in res:
            raise ValueError(
                f"Google translate error response: {res[:100] if res else 'empty'}"
            )
        return res

    async def _translate_external(self, text: str, target_lang: str) -> str:
        provider = self.config["provider"]
        (
            masked_text,
            opaque_map,
            emoji_map,
            link_map,
            btn_map,
            date_map,
        ) = self._mask_html(text)

        def do_translate(content: str):
            if provider == "google":
                chunks = self._split_masked_chunks(content, max_chunk_len=1800)
                translated_chunks = []
                for chunk in chunks:
                    if not chunk.strip():
                        translated_chunks.append(chunk)
                        continue
                    res = self._translate_google_chunk(chunk, target_lang)
                    translated_chunks.append(res)
                return "\n".join(translated_chunks)

            return content

        loop = asyncio.get_event_loop()
        try:
            translated = await loop.run_in_executor(None, do_translate, masked_text)
            return self._unmask_html(
                translated,
                opaque_map,
                emoji_map,
                link_map,
                btn_map,
                date_map,
            )
        except Exception as e:
            logger.warning(
                "External translation with masked HTML failed: %s, falling back to plain text",
                e,
            )
            clean_text, _ = html.parse(text)
            return await loop.run_in_executor(None, do_translate, clean_text)

    @loader.command()
    async def tr(self, message: Message):
        """[lang] <text> - Translate text or reply to a message"""
        if not (args := utils.get_args_raw(message.raw_text)):
            text = None
            lang = self.strings["language"]
        else:
            parts = args.split(maxsplit=1)
            first_word = parts[0]
            if LANG_CODE_RE.match(first_word):
                lang = first_word
                text = parts[1] if len(parts) > 1 else None
            else:
                lang = self.strings["language"]
                text = args

        reply = None
        rich_message = None
        if not text:
            reply = await message.get_reply_message()
            if not reply:
                await utils.answer(message, self.strings["no_args"])
                return

            # Check if reply has a rich message
            rich_message = getattr(reply, "rich_message_entity", None)
            if rich_message is None:
                with contextlib.suppress(Exception):
                    rich_message = await self._client.get_rich_message(
                        message.peer_id,
                        reply.id,
                        raw=True,
                    )

            if rich_message is not None:
                rich_html = utils.rich_message_to_html(rich_message)
                if rich_html and rich_html.strip():
                    text, entities = html.parse(rich_html)
                else:
                    text = reply.raw_text or ""
                    entities = reply.entities or []
            else:
                text = reply.raw_text or ""
                entities = reply.entities or []
            target_msg = reply
        else:
            target_msg = message
            if message.entities and text:
                prefix_len = len(message.raw_text) - len(text)
                adjusted_entities = []
                for ent in message.entities:
                    if ent.offset >= prefix_len:
                        new_ent = copy.copy(ent)
                        new_ent.offset -= prefix_len
                        adjusted_entities.append(new_ent)
                    elif ent.offset + ent.length > prefix_len:
                        new_ent = copy.copy(ent)
                        new_ent.length = (ent.offset + ent.length) - prefix_len
                        new_ent.offset = 0
                        adjusted_entities.append(new_ent)
                entities = adjusted_entities
            else:
                entities = []

        if not text or not text.strip():
            await utils.answer(message, self.strings["no_args"])
            return

        provider = self.config["provider"]
        only_text = self.config["only_text"]
        logger.info(
            "Translator: input text=%r, entities=%s, lang=%s, only_text=%s, provider=%s, has_reply=%s, has_rich=%s",
            text,
            entities,
            lang,
            only_text,
            provider,
            reply is not None,
            rich_message is not None,
        )

        try:
            if provider == "telegram":
                if rich_message is not None:
                    try:
                        translated = await self._client.translate_rich_message(
                            lang,
                            entity=message.peer_id,
                            messages=[reply],
                            raw=True,
                        )
                        logger.info(
                            "Translator: translate_rich_message raw=%r",
                            translated,
                        )
                        if not translated:
                            raise ValueError(
                                "Telegram returned no translated Rich Message"
                            )
                        if only_text:
                            tr_text = utils.rich_message_to_html(translated[0])
                            logger.info(
                                "Translator: rich_message_to_html output=%r",
                                tr_text,
                            )
                        else:
                            await self._client.send_rich_message(
                                message.peer_id,
                                rich_message=translated[0],
                                reply_to=reply.id,
                                top_msg_id=utils.get_topic(reply),
                            )
                            if message.out:
                                await message.delete()
                            return
                    except Exception as e:
                        logger.warning(
                            "Translator: translate_rich_message failed: %s, falling back to TranslateTextRequest",
                            e,
                        )
                        rich_message = None

                if rich_message is None:
                    try:
                        logger.info(
                            "Translator: calling TranslateTextRequest text=%r, entities=%s",
                            text,
                            entities,
                        )
                        result = await self._client(
                            functions.messages.TranslateTextRequest(
                                to_lang=lang,
                                text=[
                                    types.TextWithEntities(
                                        text=text,
                                        entities=entities or [],
                                    )
                                ],
                            )
                        )
                        logger.info(
                            "Translator: TranslateTextRequest result=%r", result
                        )
                        if result and result.result:
                            tr_text = html.unparse(
                                result.result[0].text,
                                result.result[0].entities or [],
                            )
                            logger.info(
                                "Translator: TranslateTextRequest unparsed=%r (raw_entities=%s)",
                                tr_text,
                                result.result[0].entities,
                            )
                        else:
                            tr_text = text
                    except Exception as e:
                        logger.warning(
                            "Translator: TranslateTextRequest failed: %s, falling back",
                            e,
                        )
                        tr_text = await self._client.translate(
                            message.peer_id,
                            target_msg,
                            lang,
                            raw_text=text,
                            entities=entities,
                        )
                        logger.info("Translator: _client.translate result=%r", tr_text)
            else:
                if rich_message is not None:
                    html_input = utils.rich_message_to_html(rich_message)
                else:
                    html_input = html.unparse(text, entities) if entities else text

                tr_text = await self._translate_external(html_input, lang)
                logger.info("Translator: _translate_external result=%r", tr_text)

            if not tr_text or not tr_text.strip():
                raise ValueError("Translation returned empty result")

            if only_text:
                logger.info(
                    "Translator: answering only_text (rich=%s) tr_text=%r",
                    rich_message is not None,
                    tr_text,
                )
                if rich_message is not None:
                    await utils.answer(message, rich_message=tr_text)
                else:
                    await utils.answer(message, tr_text)
            else:
                formatted_response = self.strings["translated_text"].format(
                    tr_text=tr_text
                )
                logger.info(
                    "Translator: answering full (rich=%s) formatted_response=%r",
                    rich_message is not None,
                    formatted_response,
                )
                if rich_message is not None:
                    await utils.answer(message, rich_message=formatted_response)
                else:
                    await utils.answer(message, formatted_response)

        except Exception:
            logger.exception("Unable to translate text")
            await utils.answer(message, self.strings["error"])
