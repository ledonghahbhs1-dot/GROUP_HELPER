import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 110+ Multilingual No-Sample Trade (trade orbs without owning a sample) Keywords across
# English, Vietnamese, Spanish, Portuguese, Russian, Indonesian, Turkish, French, German,
# Italian, Tagalog, Arabic, Hindi
NOTRADE_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "trade without sample", "trading without sample", "no sample trade",
    "trade orb without sample", "how to trade without sample", "no-sample trade guide",
    "trade without sample orb", "trade orbs no sample", "sample free trade",
    "trade without owning sample", "no sample orb trade", "trade guide no sample",
    "how to trade orb without sample", "trade orb no sample tutorial", "no sample needed trade",
    "trade orb no sample needed", "no sample trade tutorial", "no sample trade trick",
    "trade orbs without owning sample", "trade orb hack no sample", "trade without dragon",
    "trade orbs without dragon", "trade no sample", "no sample trading", "no sample trade hack",

    # 2. Vietnamese (Có dấu & Không dấu) (30+ keywords)
    "trade khong can mau", "trade không cần mẫu", "doi orb khong can mau", "đổi orb không cần mẫu",
    "trao doi khong can mau", "trao đổi không cần mẫu", "cach trade khong can mau",
    "cách trade không cần mẫu", "huong dan trade khong mau", "hướng dẫn trade không mẫu",
    "doi orb ma khong can mau goc", "đổi orb mà không cần mẫu gốc", "trade orb khong mau",
    "trade orb không mẫu", "video trade khong mau", "video trade không mẫu",
    "cach doi orb khong can mau", "cách đổi orb không cần mẫu", "trao doi orb khong mau",
    "trao đổi orb không mẫu", "cach trao doi khong can mau goc", "cách trao đổi không cần mẫu gốc",
    "doi orb khong so huu mau", "đổi orb không sở hữu mẫu", "trade khong co mau",
    "trade không có mẫu", "trade khong can so huu", "trade không cần sở hữu", "trade orb khong can mau",
    "trade orb không cần mẫu",

    # 3. Spanish (12+ keywords)
    "comerciar sin muestra", "intercambiar sin muestra", "como comerciar sin muestra",
    "intercambio de orbes sin muestra", "cambiar orbes sin muestra", "trade sin muestra",
    "intercambio sin muestra", "intercambiar sin tener dragon", "trade sin muestra de orbes",
    "guia trade sin muestra", "tutorial trade sin muestra",

    # 4. Portuguese (10+ keywords)
    "trocar sem amostra", "comercio sem amostra", "como trocar sem amostra",
    "troca de orbs sem amostra", "negociar sem amostra", "trade sem amostra",
    "trocar sem ter dragao", "guia trade sem amostra", "tutorial trade sem amostra",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "обмен без образца", "торговля без образца", "как обменять без образца",
    "трейд без образца", "обмен сфер без образца", "obmen bez obraztsa",
    "kak obmenyat bez obraztsa", "treid bez obraztsa", "obmen bez sfery",

    # 6. Indonesian & Malay (8+ keywords)
    "tukar tanpa sampel", "cara tukar tanpa sampel", "trading tanpa sampel",
    "tukar orb tanpa sampel", "trade tanpa sampel", "panduan tukar tanpa sampel",
    "trade tanpa contoh",

    # 7. Turkish (6+ keywords)
    "ornek olmadan takas", "örnek olmadan takas", "nasil ornek olmadan takas yapilir",
    "ornek numunesiz takas", "numunesiz takas",

    # 8. French (6+ keywords)
    "echanger sans echantillon", "échanger sans échantillon",
    "comment echanger sans echantillon", "echange dorbes sans echantillon",
    "echange sans echantillon",

    # 9. German (6+ keywords)
    "tauschen ohne muster", "wie tauscht man ohne muster", "orb tausch ohne muster",
    "handeln ohne muster",

    # 10. Italian (5+ keywords)
    "scambiare senza campione", "come scambiare senza campione", "scambio senza campione",
    "commerciare senza campione",

    # 11. Tagalog / Filipino (4+ keywords)
    "pagpapalitan nang walang sample", "paano magpalit nang walang sample",
    "trade nang walang sample",

    # 12. Arabic (4+ keywords)
    "التداول بدون عينة", "كيفية التداول بدون عينة", "تبادل بدون عينة",

    # 13. Hindi / Transliteration (4+ keywords)
    "bina sample ke trade kaise kare", "orb trade bina sample", "no sample trade guide"
]

class NoTradeDetector:
    """
    Detects queries specifically asking how to trade orbs without owning a sample
    across 110+ multilingual keywords and phrases.
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
        Checks if text is specifically asking about trading orbs without sample.
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
