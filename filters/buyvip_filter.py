import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter

# Direct "I want to buy VIP" intent - not general pricing/info queries
# (those stay handled by pricing_filter.py). Scoped to English + Vietnamese
# since that's this bot's actual audience.
BUYVIP_KEYWORDS_RAW = [
    "buy vip", "buyvip", "buy vip key", "buy vip now", "purchase vip",
    "purchase vip key", "get vip", "get vip key", "i want to buy vip",
    "i want vip", "want to buy vip", "how to buy vip",

    "mua vip", "muavip", "mua vip key", "mua key vip", "mua vip di",
    "muon mua vip", "muốn mua vip", "toi muon mua vip", "tôi muốn mua vip",
    "cach mua vip", "cách mua vip", "dang ky vip", "đăng ký vip",
    "mua vip o dau", "mua vip ở đâu", "mua key o dau", "mua key ở đâu",
]

class BuyVipDetector:
    """Detects a direct intent to buy VIP (English/Vietnamese)."""
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in BUYVIP_KEYWORDS_RAW:
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

    def is_buyvip_query(self, text: str) -> Tuple[bool, str]:
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

buyvip_detector = BuyVipDetector()
