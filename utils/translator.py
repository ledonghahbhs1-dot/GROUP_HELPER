import asyncio
import html
import re
import urllib.parse
from typing import Optional, Tuple
import aiohttp
from cachetools import TTLCache
from utils.logger import logger

# In-memory translation cache (up to 2000 recent messages for 2 hours)
_translation_cache = TTLCache(maxsize=2000, ttl=7200)

LANG_MAP = {
    "vi": "Vietnamese",
    "es": "Spanish",
    "pt": "Portuguese",
    "ru": "Russian",
    "id": "Indonesian",
    "ms": "Malay",
    "tr": "Turkish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "tl": "Tagalog",
    "ar": "Arabic",
    "hi": "Hindi",
    "zh": "Chinese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "th": "Thai",
    "pl": "Polish",
    "uk": "Ukrainian",
    "nl": "Dutch",
    "ro": "Romanian",
}

def get_language_name(lang_code: str) -> str:
    """Returns human-readable language name from ISO code."""
    code = lang_code.lower().strip()
    return LANG_MAP.get(code, code.upper())

def is_translatable_text(text: str) -> bool:
    """
    Quick check to filter out text that definitely should not be auto-translated:
    - Pure URLs, bot commands, single letters, only digits/emojis.
    """
    if not text:
        return False

    cleaned = text.strip()
    if len(cleaned) < 3 or cleaned.startswith("/"):
        return False

    # Skip pure URLs
    if re.match(r"^https?://\S+$", cleaned, re.IGNORECASE) or re.match(r"^t\.me/\S+$", cleaned, re.IGNORECASE):
        return False

    # Skip if only numbers and symbols
    if re.match(r"^[\d\W_]+$", cleaned):
        return False

    return True

async def translate_to_english(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Translates non-English text to English.
    Returns:
        (detected_lang_code, detected_lang_name, translated_english_text)
        or None if text is already English, identical, or translation fails.
    """
    if not is_translatable_text(text):
        return None

    clean_text = text.strip()
    cache_key = clean_text.lower()

    if cache_key in _translation_cache:
        cached = _translation_cache[cache_key]
        return cached

    # Google Translate client endpoint
    url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=en&q={urllib.parse.quote(clean_text)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    if data and isinstance(data, list) and len(data) > 0 and len(data[0]) >= 2:
                        translated_text = str(data[0][0]).strip()
                        detected_lang = str(data[0][1]).lower().strip()

                        # If already English or undefined, no translation needed
                        if detected_lang in ("en", "und"):
                            _translation_cache[cache_key] = None
                            return None

                        # If translation is unchanged (e.g. usernames, untranslatable words)
                        if translated_text.lower() == clean_text.lower():
                            _translation_cache[cache_key] = None
                            return None

                        lang_name = get_language_name(detected_lang)
                        result = (detected_lang, lang_name, translated_text)
                        _translation_cache[cache_key] = result
                        return result
    except Exception as e:
        logger.warning("Translation request failed for text %r: %s", clean_text[:30], e)

    return None
