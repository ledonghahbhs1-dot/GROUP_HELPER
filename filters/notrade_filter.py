import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual No-Sample Trade (trade orbs without owning a sample) Keywords across
# English, Vietnamese, Spanish, Portuguese, Russian, Indonesian, Turkish, French, German,
# Italian, Tagalog, Arabic, Hindi
NOTRADE_KEYWORDS_RAW = [
    # 1. English (20+ keywords)
    "trade without sample", "trading without sample", "no sample trade",
    "trade orb without sample", "how to trade without sample", "no-sample trade guide",
    "trade without sample orb", "trade orbs no sample", "sample free trade",
    "trade without owning sample", "no sample orb trade", "trade guide no sample",
    "how to trade orb without sample", "trade orb no sample tutorial", "no sample needed trade",
    "trade orb no sample needed", "no sample trade tutorial", "no sample trade trick",
    "trade orbs without owning sample", "trade orb hack no sample",

    # 2. Vietnamese (Có dấu & Không dấu) (24+ keywords)
    "trade khong can mau", "trade không cần mẫu", "doi orb khong can mau", "đổi orb không cần mẫu",
    "trao doi khong can mau", "trao đổi không cần mẫu", "cach trade khong can mau",
    "cách trade không cần mẫu", "huong dan trade khong mau", "hướng dẫn trade không mẫu",
    "doi orb ma khong can mau goc", "đổi orb mà không cần mẫu gốc", "trade orb khong mau",
    "trade orb không mẫu", "video trade khong mau", "video trade không mẫu",
    "cach doi orb khong can mau", "cách đổi orb không cần mẫu", "trao doi orb khong mau",
    "trao đổi orb không mẫu", "cach trao doi khong can mau goc", "cách trao đổi không cần mẫu gốc",
    "doi orb khong so huu mau", "đổi orb không sở hữu mẫu",

    # 3. Spanish (5+ keywords)
    "comerciar sin muestra", "intercambiar sin muestra", "como comerciar sin muestra",
    "intercambio de orbes sin muestra", "cambiar orbes sin muestra",

    # 4. Portuguese (5+ keywords)
    "trocar sem amostra", "comercio sem amostra", "como trocar sem amostra",
    "troca de orbs sem amostra", "negociar sem amostra",

    # 5. Russian / Cyrillic & Transliteration (5+ keywords)
    "обмен без образца", "торговля без образца", "как обменять без образца",
    "obmen bez obraztsa", "kak obmenyat bez obraztsa",

    # 6. Indonesian & Malay (4+ keywords)
    "tukar tanpa sampel", "cara tukar tanpa sampel", "trading tanpa sampel", "tukar orb tanpa sampel",

    # 7. Turkish (3+ keywords)
    "ornek olmadan takas", "örnek olmadan takas", "nasil ornek olmadan takas yapilir",

    # 8. French (3+ keywords)
    "echanger sans echantillon", "échanger sans échantillon", "comment echanger sans echantillon",

    # 9. German (2+ keywords)
    "tauschen ohne muster", "wie tauscht man ohne muster",

    # 10. Italian (2+ keywords)
    "scambiare senza campione", "come scambiare senza campione",

    # 11. Tagalog / Filipino (2+ keywords)
    "pagpapalitan nang walang sample", "paano magpalit nang walang sample",

    # 12. Arabic (2+ keywords)
    "التداول بدون عينة", "كيفية التداول بدون عينة",

    # 13. Hindi / Transliteration (2+ keywords)
    "bina sample trade kaise kare", "sample ke bina trade guide"
]

class NoTradeDetector:
    """
    Detects queries asking about No-Sample Trade (trading Orbs without owning a sample
    Orb) across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in NOTRADE_KEYWORDS_RAW:
            raw = kw.strip().lower()
            clean = normalize_text_for_filter(raw)
            if " " in raw:
                self.compound_phrases.append(raw)
                if clean != raw:
                    self.compound_phrases.append(clean)
            else:
                self.exact_keywords.add(raw)
                if clean:
                    self.exact_keywords.add(clean)

        self.compound_phrases.sort(key=len, reverse=True)

    def is_notrade_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about No-Sample Trade.
        Returns: (is_notrade, matched_keyword)
        """
        if not text:
            return False, ""

        text_lower = text.strip().lower()

        if text_lower in self.exact_keywords:
            return True, text_lower

        normalized = normalize_text_for_filter(text_lower)
        for phrase in self.compound_phrases:
            pattern = r'(?:\b|\s|^)' + re.escape(phrase) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, phrase

        for kw in self.exact_keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, kw

        return False, ""

notrade_detector = NoTradeDetector()
