import re
from typing import List, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters
from database.db import db

import re
from typing import List, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters
from database.db import db

# Explicit accented profanity (checked against raw text with word boundaries)
# Excludes ambiguous words like 'đi' (to go), 'dù' (though), 'các' (plural), 'lon' (can), 'cụ' (elder)
ACCENTED_BAD_WORDS = [
    "đĩ", "con đĩ", "đồ đĩ", "làm đĩ", "đĩ thoã", "đĩ mẹ",
    "địt", "địt mẹ", "địt con mẹ", "địt cụ", "địtmẹ",
    "đụ", "đụ má", "đụ mẹ", "đụmẹ", "đụmá", "đụ bà",
    "lồn", "hãm lồn", "xạo lồn", "xàm lồn", "như lồn", "con lồn",
    "cặc", "như cặc", "con cặc", "buồi", "đầu buồi",
    "óc chó", "chó đẻ", "súc vật", "súc sinh",
    "thằng chó", "thằng điên", "con mẹ mày", "mả mày", "mả cha mày", "tổ sư", "bố mày",
    "cút đi", "cút mẹ", "đéo", "đéo cần",
    "mất dạy", "đồ khốn", "khốn nạn", "bú cu"
]

# Unaccented profanity (phrases & unmistakable unique slang only - never ambiguous 2-letter words like 'di', 'du', 'cu', 'lon', 'cac')
UNACCENTED_BAD_WORDS = [
    "dm", "dmm", "dkm", "dcm", "clm", "clmm", "vcl", "vkl",
    "dit me", "ditme", "dit con me", "dit cu",
    "du ma", "du me", "duma", "dume",
    "con di", "do di", "lam di", "di thoa",
    "oc cho", "cho de", "suc vat", "sucsinh",
    "thang cho", "thang dien", "con me may", "ma may", "ma cha may", "to su", "bo may",
    "cut me", "cut di", "deo can",
    "nhu cac", "con cac", "nhu lon", "con lon", "ham lon", "hamlon", "xao lon", "xaolon", "xam lon",
    "bu cu",
    "bitch", "fuck", "fucker", "fucking", "asshole", "motherfucker", "cunt", "whore", "nigger", "pussy", "dick"
]

class ProfanityFilter:
    async def check_profanity(self, text: str, chat_id: int) -> Tuple[bool, str]:
        """
        Detects vulgar, abusive or insulting language using precise word boundaries.
        Prevents false positives on normal words like 'đi' (to go), 'media', 'condition'.
        Returns (is_violated: bool, matched_word: str)
        """
        if not text:
            return False, ""

        raw_lower = text.lower()
        normalized = normalize_text_for_filter(text)
        stripped = strip_all_delimiters(text)

        # 1. Check accented profanity on raw text with boundary
        for bad in ACCENTED_BAD_WORDS:
            pattern = r'(?<!\w)' + re.escape(bad) + r'(?!\w)'
            if re.search(pattern, raw_lower, re.IGNORECASE):
                return True, bad

        # 2. Check unaccented profanity on normalized text with boundary
        for bad in UNACCENTED_BAD_WORDS:
            pattern = r'(?<!\w)' + re.escape(bad) + r'(?!\w)'
            if re.search(pattern, normalized, re.IGNORECASE):
                return True, bad

        # 3. Check custom banned words from DB for this chat
        custom_words = await db.get_banned_words(chat_id)
        for custom in custom_words:
            c_clean = custom.strip().lower()
            if not c_clean:
                continue
            # If custom word has accents, check raw text; otherwise check normalized
            if any(ord(char) > 127 for char in c_clean):
                pattern = r'(?<!\w)' + re.escape(c_clean) + r'(?!\w)'
                if re.search(pattern, raw_lower, re.IGNORECASE):
                    return True, custom
            else:
                pattern = r'(?<!\w)' + re.escape(c_clean) + r'(?!\w)'
                if re.search(pattern, normalized, re.IGNORECASE):
                    return True, custom

        # 4. Obfuscated check for strong slurs (e.g. d.u.m.a, f.u.c.k, d_m_m)
        strong_slurs = ["duma", "dume", "ditme", "fuck", "bitch", "cunt", "asshole", "clmm", "vcl"]
        for slur in strong_slurs:
            if slur in stripped:
                return True, slur

        return False, ""

profanity_filter = ProfanityFilter()
