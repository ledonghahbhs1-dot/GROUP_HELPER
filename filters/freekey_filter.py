import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual "How to get a Free Key" Keywords across English, Vietnamese, Spanish,
# Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
# NOTE: scoped specifically to FREE key phrasing (not general "key"/"vip key" pricing queries,
# which are still handled by script_filter.py / pricing_filter.py)
FREEKEY_KEYWORDS_RAW = [
    # 1. English (20+ keywords)
    "free key", "get free key", "how to get free key", "free key guide",
    "daily free key", "claim free key", "redeem free key", "how to claim free key",
    "free vip key", "get key free", "free key tutorial", "how to redeem free key",
    "free key instructions", "daily key guide", "claim daily key", "how to get daily key",
    "free key method", "free key trick", "get free vip key", "how to earn free key",

    # 2. Vietnamese (Có dấu & Không dấu) (26+ keywords)
    "nhan key free", "nhận key free", "cach nhan key free", "cách nhận key free",
    "lay key free", "lấy key free", "cach lay key mien phi", "cách lấy key miễn phí",
    "nhan key mien phi", "nhận key miễn phí", "huong dan nhan key free", "hướng dẫn nhận key free",
    "cach nhan key hang ngay", "cách nhận key hàng ngày", "key free hang ngay", "key free hàng ngày",
    "video nhan key free", "video nhận key free", "cach kiem key free", "cách kiếm key free",
    "lam sao de nhan key free", "làm sao để nhận key free", "cach doi key free", "cách đổi key free",
    "nhan key vip free", "nhận key vip free",

    # 3. Spanish (5+ keywords)
    "obtener clave gratis", "como obtener clave gratis", "clave gratis diaria",
    "reclamar clave gratis", "obtener key gratis",

    # 4. Portuguese (5+ keywords)
    "obter chave gratis", "como obter chave gratis", "chave gratis diaria",
    "resgatar chave gratis", "obter key gratis",

    # 5. Russian / Cyrillic & Transliteration (4+ keywords)
    "получить бесплатный ключ", "как получить бесплатный ключ",
    "бесплатный ключ ежедневно", "poluchit besplatnyi klyuch",

    # 6. Indonesian & Malay (4+ keywords)
    "dapatkan key gratis", "cara dapat key gratis", "key gratis harian", "klaim key gratis",

    # 7. Turkish (4+ keywords)
    "ucretsiz anahtar al", "ücretsiz anahtar al", "nasil ucretsiz key alinir", "gunluk ucretsiz key",

    # 8. French (4+ keywords)
    "obtenir une cle gratuite", "obtenir une clé gratuite",
    "comment obtenir une cle gratuite", "cle gratuite quotidienne",

    # 9. German (4+ keywords)
    "kostenlosen schlussel erhalten", "kostenlosen schlüssel erhalten",
    "wie bekommt man einen kostenlosen key", "taeglicher kostenloser key",

    # 10. Italian (3+ keywords)
    "ottenere chiave gratuita", "come ottenere chiave gratuita", "chiave gratuita giornaliera",

    # 11. Tagalog / Filipino (3+ keywords)
    "kumuha ng libreng key", "paano kumuha ng libreng key", "araw-araw na libreng key",

    # 12. Arabic (3+ keywords)
    "الحصول على مفتاح مجاني", "كيفية الحصول على مفتاح مجاني", "مفتاح مجاني يومي",

    # 13. Hindi / Transliteration (3+ keywords)
    "free key kaise le", "free key kaise milega", "daily free key guide"
]

class FreeKeyDetector:
    """
    Detects queries specifically asking how to get a FREE key (not general VIP/paid key
    pricing queries) across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in FREEKEY_KEYWORDS_RAW:
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

    def is_freekey_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking how to get a free key.
        Returns: (is_freekey, matched_keyword)
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

freekey_detector = FreeKeyDetector()
