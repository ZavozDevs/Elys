# © ZavozDevs, 2026-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging
import re
import typing

logger = logging.getLogger(__name__)

# Registry: alias -> (emoji_id, fallback_unicode)
# Primary and alternative aliases map to the canonical custom emoji ID and unicode fallback.
EMOJI_REGISTRY: dict[str, tuple[str, str]] = {
    # System & Actions
    "stop": ("5210952531676504517", "🚫"),
    "ban": ("5210952531676504517", "🚫"),
    "error": ("5210952531676504517", "🚫"),
    "no": ("5210952531676504517", "🚫"),
    "cross": ("5287372146039861774", "❌"),
    "fail": ("5287372146039861774", "❌"),
    "wrong": ("5287372146039861774", "❌"),
    "check": ("5118861066981344121", "✅"),
    "ok": ("5118861066981344121", "✅"),
    "done": ("5118861066981344121", "✅"),
    "success": ("5118861066981344121", "✅"),
    "warn": ("5312383351217201533", "⚠️"),
    "warning": ("5312383351217201533", "⚠️"),
    "alert": ("5312383351217201533", "⚠️"),
    "exclamation": ("5775887550262546277", "❗"),
    "important": ("5775887550262546277", "❗"),
    "double_exclamation": ("5440660757194744323", "‼️"),
    "grey_exclamation": ("5355133243773435190", "❕"),
    "question": ("5382187118216879236", "❓"),
    "help": ("5382187118216879236", "❓"),
    "grey_question": ("6019130940012370273", "❔"),
    "info": ("5879813604068298387", "ℹ️"),
    "tip": ("5472146462362048818", "💡"),
    "bulb": ("5472146462362048818", "💡"),
    "idea": ("5472146462362048818", "💡"),
    "bullet": ("5253713110111365241", "▫️"),
    "small_square": ("5253713110111365241", "▫️"),
    "white_circle": ("5228879218363872764", "⚪"),
    "green_circle": ("5427009714745541184", "🟢"),
    "blue_circle": ("5784891605601225888", "🔵"),
    "gear": ("5341715473882955310", "⚙️"),
    "settings": ("5341715473882955310", "⚙️"),
    "sync": ("5774134533590880843", "🔄"),
    "reload": ("5774134533590880843", "🔄"),
    "refresh": ("5774134533590880843", "🔄"),
    "repeat": ("5253464392850221514", "🔁"),
    "wait": ("5451732530048802485", "⏳"),
    "hourglass": ("5451732530048802485", "⏳"),
    "clock": ("5345778951031658558", "🕖"),
    "search": ("5873225338984599714", "🔍"),
    "inspect": ("5337183664630709422", "🔎"),
    "zoom_in": ("5337183664630709422", "🔎"),
    "trash": ("5465665476971471368", "🗑️"),
    "delete": ("5465665476971471368", "🗑️"),
    "flash": ("5256099067523510898", "⚡"),
    "bolt": ("5256099067523510898", "⚡"),
    "lightning": ("5256099067523510898", "⚡"),
    "fire": ("5253877736207821121", "🔥"),
    "recycle": ("5318933532825888187", "♻️"),

    # Security & Access
    "lock": ("5870704313440932932", "🔒"),
    "locked": ("5870704313440932932", "🔒"),
    "unlock": ("5472308992514464048", "🔓"),
    "sec_rules": ("5472308992514464048", "🔐"),
    "keylock": ("5472308992514464048", "🔐"),
    "key": ("5472308992514464048", "🔑"),
    "shield": ("5253780051471642059", "🛡️"),
    "protect": ("5253780051471642059", "🛡️"),
    "perms": ("5870450390679425417", "🗒️"),
    "note": ("5870450390679425417", "🗒️"),
    "notepad": ("5870450390679425417", "🗒️"),

    # Users & Roles
    "owner": ("5386399931378440814", "😎"),
    "cool": ("5386399931378440814", "😎"),
    "user": ("5883964170268840032", "👤"),
    "users": ("5870772616305839506", "👥"),
    "group": ("5870772616305839506", "👥"),
    "bot": ("5372981976804366741", "🤖"),
    "robot": ("5372981976804366741", "🤖"),

    # Elys & Branding
    "star": ("5237836252400626980", "⭐"),
    "glowing_star": ("5134452506935427991", "🌟"),
    "sparkles": ("5249255582598210678", "✨"),
    "magic": ("5469791106591890404", "🪄"),
    "wand": ("5469791106591890404", "🪄"),
    "stealth": ("5870903672937911120", "🕶️"),
    "glasses": ("5870903672937911120", "🕶️"),
    "rocket": ("5431736674147114227", "🚀"),
    "party": ("5436040291507247633", "🎉"),
    "tada": ("5436040291507247633", "🎉"),
    "diamond": ("5471952986970267163", "💎"),
    "gem": ("5471952986970267163", "💎"),
    "money": ("5404553572727660202", "💰"),
    "heart": ("5238125033116705019", "❤️"),
    "heart_hands": ("5287454910059654880", "🫶"),

    # UI & Devices & Media
    "folder": ("5256113064821926998", "📁"),
    "folders": ("5431736674147114227", "🗂️"),
    "card_index": ("5431736674147114227", "🗂️"),
    "package": ("5431736674147114227", "📦"),
    "module": ("5431736674147114227", "📦"),
    "box": ("5431736674147114227", "📦"),
    "theme": ("5249090625789271993", "🖌️"),
    "brush": ("5249090625789271993", "🖌️"),
    "palette": ("5249090625789271993", "🎨"),
    "wrench": ("5249457712349097667", "🔧"),
    "globe": ("6037284117505116849", "🌐"),
    "lang": ("6037284117505116849", "🌐"),
    "web": ("6037284117505116849", "🌐"),
    "chat": ("6037254263187443802", "💬"),
    "speech": ("6037254263187443802", "💬"),
    "book": ("5208634061085492935", "📖"),
    "memo": ("5424772191403143504", "📝"),
    "pencil": ("5424772191403143504", "📝"),
    "newspaper": ("5434144690511290129", "📰"),
    "keyboard": ("5472111548572900003", "⌨️"),
    "laptop": ("5472146462362048818", "💻"),
    "computer": ("5472146462362048818", "💻"),
    "platform": ("5472146462362048818", "💻"),
    "device": ("5431736674147114227", "📱"),
    "phone": ("5431736674147114227", "📱"),
    "new": ("5361979468887893611", "🆕"),
    "new_badge": ("5361979468887893611", "🆕"),
    "watch": ("5424885441100782420", "👀"),
    "eyes": ("5424885441100782420", "👀"),
    "think": ("5346022209389372742", "🤔"),
    "thinking": ("5346022209389372742", "🤔"),
    "dizzy": ("5134202243486057363", "💫"),
    "spark": ("5134202243486057363", "💫"),
    "cold_face": ("5452023368054216810", "🥶"),
    "wave": ("5424885441100782420", "👋"),
    "hello": ("5424885441100782420", "👋"),
    "loudspeaker": ("6019094432790354513", "📢"),
    "silent": ("6010394680179562842", "😶"),
    "camera": ("5778335621491723621", "📷"),
    "chart": ("5931472654660800739", "📊"),
    "link": ("4916086774649848789", "🔗"),
    "roller_coaster": ("5440551785284510215", "🎢"),
    "statue": ("5454219968948229067", "🗽"),
    "melting_face": ("5325787248363314644", "🫠"),
    "tipping_hand": ("4940480187436369099", "💁‍♀️"),
    "dumpling": ("5382337996123020810", "🥟"),
    "pirate_flag": ("5386372293263892965", "🏴‍☠️"),

    # Numbers
    "num_1": ("5456197350416486261", "1️⃣"),
    "num_2": ("5456261689026581678", "2️⃣"),
    "num_3": ("5458366235886522404", "3️⃣"),
    "num_4": ("5456207331920483861", "4️⃣"),
    "num_5": ("5456185418997340146", "5️⃣"),

    # Gestures
    "thumbup": ("5197474765387864959", "👍"),
    "like": ("5197474765387864959", "👍"),
    "ok_hand": ("5458450833857322148", "👌"),
    "point_up": ("5355133243773435190", "☝️"),
    "hand_up": ("5469718869536940860", "👆"),
    "shrug": ("5427052514094619126", "🤷‍♀️"),

    # Flags
    "flag_gb": ("6323589145717376403", "🇬🇧"),
    "flag_uz": ("6323430017179059570", "🇺🇿"),
    "flag_ru": ("6323139226418284334", "🇷🇺"),
    "flag_ua": ("5276140694891666474", "🇺🇦"),
    "flag_it": ("6323471399188957082", "🇮🇹"),
    "flag_es": ("6323447995878606497", "🇪🇸"),
    "flag_fr": ("6323381024470337090", "🇫🇷"),
    "flag_de": ("6323412351710134444", "🇩🇪"),
    "flag_tr": ("6323362143785718617", "🇹🇷"),
    "flag_jp": ("6323362143785718617", "🇯🇵"),
    "flag_kz": ("6323267978775234907", "🇰🇿"),
    "flag_by": ("6323267978775234907", "🇧🇾"),
    "flag_pl": ("6323267978775234907", "🇵🇱"),
}

# Alternate IDs mapping to aliases for backwards compatibility with heterogeneous packs
EXTRA_ID_MAP: dict[str, str] = {
    "5931415565955503486": "bot",
    "5819078828017849357": "bot",
    "5843799474362652262": "sync",
    "5879770735999717115": "user",
    "5341492148468465410": "package",
    "5931409969613116639": "shield",
    "5926783847453692661": "shield",
    "5325792861885570739": "clock",
    "5877458226823302157": "clock",
}

# Regex to find {e:name} and {emoji:name}
EMOJI_TOKEN_RE = re.compile(r"\{(?:e|emoji):([a-zA-Z0-9_]+)\}")

# Fallback reverse mapping: unicode symbol -> alias
SYMBOL_TO_ALIAS: dict[str, str] = {}
for _alias, (_eid, _fb) in EMOJI_REGISTRY.items():
    _clean = _fb.replace("\ufe0f", "")
    if _clean not in SYMBOL_TO_ALIAS:
        SYMBOL_TO_ALIAS[_clean] = _alias
        SYMBOL_TO_ALIAS[_fb] = _alias


def get_emoji(name: str, use_custom: bool = True) -> str:
    """
    Returns HTML custom emoji tag or fallback unicode character for a given alias name.
    Example: get_emoji('star') -> '<tg-emoji emoji-id=5237836252400626980>⭐</tg-emoji>'
    """
    data = EMOJI_REGISTRY.get(name)
    if not data:
        return f"{{e:{name}}}"
    eid, fb = data
    if use_custom and eid:
        return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
    return fb


def render_emojis(text: typing.Any, use_custom: bool = True) -> typing.Any:
    """
    Renders all {e:name} and {emoji:name} tokens in the given text into Telegram custom emoji tags.
    Fast path: returns original object immediately if text has no tokens.
    """
    if not isinstance(text, str):
        return text

    if "{e:" not in text and "{emoji:" not in text:
        return text

    def _replace(match: re.Match) -> str:
        token = match.group(1).lower()
        if token in EMOJI_REGISTRY:
            eid, fb = EMOJI_REGISTRY[token]
            if use_custom and eid:
                return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
            return fb
        return match.group(0)

    return EMOJI_TOKEN_RE.sub(_replace, text)


def clean_emojis(text: str) -> str:
    """
    Strips both {e:name} tokens and <tg-emoji> tags to plain unicode emojis.
    """
    if not isinstance(text, str):
        return text

    text = render_emojis(text, use_custom=False)
    return re.sub(r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", r"\1", text)


class _EmojiAccessor:
    """
    Convenient attribute-based access to emoji tags in Python code:
    e.g. E.star, E.stop, E.check, E.warn
    """
    def __getattr__(self, name: str) -> str:
        name_clean = name.lower()
        if name_clean in EMOJI_REGISTRY:
            return get_emoji(name_clean)
        raise AttributeError(f"No emoji alias registered with name '{name}'")

    def __getitem__(self, name: str) -> str:
        return self.__getattr__(name)


E = _EmojiAccessor()
