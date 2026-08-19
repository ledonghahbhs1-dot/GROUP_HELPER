import re
from typing import List, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters
from database.db import db

# Comprehensive default Vietnamese & international bad words / toxicity dictionary
DEFAULT_BAD_WORDS = [
    # Vietnamese Slurs & Swears
    "dm", "dmm", "đm", "đmm", "dkm", "đkm", "dcm", "đcm", "clm", "clmm", "vcl", "vkl",
    "dit", "địt", "dit me", "địt mẹ", "ditme", "địtmẹ", "du", "đụ", "du ma", "đụ má", "duma", "đụmá",
    "du me", "đụ mẹ", "dume", "đụmẹ", "lon", "lồn", "cac", "cặc", "buoi", "buồi", "chim", "cu",
    "oc cho", "óc chó", "cho de", "chó đẻ", "suc vat", "súc vật", "sucsinh", "súc sinh",
    "di", "đĩ", "con di", "con đĩ", "cave", "phay", "di thoa", "đĩ thoã", "lam di", "làm đĩ",
    "thang cho", "thằng chó", "thang dien", "thằng điên", "con me may", "con mẹ mày",
    "ma may", "mả mày", "ma cha may", "mả cha mày", "to su", "tổ sư", "bo may", "bố mày",
    "cut", "cút", "cut di", "cút đi", "cut me", "cút mẹ", "deo", "đéo", "deo can", "đéo cần",
    "nhu cac", "như cặc", "nhu lon", "như lồn", "mat day", "mất dạy", "do khon", "đồ khốn",
    "khon nan", "khốn nạn", "hamlon", "hãm lồn", "xao lon", "xạo lồn", "xaolon", "xàm lồn",
    "bitch", "fuck", "fucker", "asshole", "motherfucker", "cunt", "whore", "nigger", "pussy", "dick"
]

class ProfanityFilter:
    async def check_profanity(self, text: str, chat_id: int) -> Tuple[bool, str]:
        """
        Detects vulgar, abusive or insulting language.
        Returns (is_violated: bool, matched_word: str)
        """
        if not text:
            return False, ""

        # 1. Normalize text
        normalized = normalize_text_for_filter(text)
        stripped = strip_all_delimiters(text)

        # 2. Get dynamic custom banned words from DB for this chat
        custom_words = await db.get_banned_words(chat_id)
        all_bad_words = set(DEFAULT_BAD_WORDS + [w.lower().strip() for w in custom_words])

        # 3. Check exact word tokens & regex patterns
        words_in_text = set(re.findall(r'\b\w+\b', normalized))

        for bad in all_bad_words:
            bad_norm = normalize_text_for_filter(bad)
            bad_stripped = strip_all_delimiters(bad)

            # Single word token check
            if " " not in bad_norm:
                if bad_norm in words_in_text:
                    return True, bad
            
            # Phrase check in normalized sentence
            if bad_norm in normalized:
                return True, bad

            # Obfuscated check (e.g. d.u.m.a -> duma)
            if len(bad_stripped) >= 3 and bad_stripped in stripped:
                return True, bad

        return False, ""

profanity_filter = ProfanityFilter()
