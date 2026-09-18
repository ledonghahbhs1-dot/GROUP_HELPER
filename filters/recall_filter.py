import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Force Recall / No-Duplicate Recall Keywords across English, Vietnamese,
# Spanish, Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
RECALL_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "recall", "recalls", "recall dragon", "recall dragons", "force recall", "no duplicate recall",
    "recall without duplicate", "recall no duplicate", "how to recall dragon",
    "recall guide", "recall tutorial", "recall dragon city", "recall for orbs",
    "duplicate recall", "recall trick", "force recall dragon", "recall hack",
    "how to force recall", "recall no dupe", "recall dupe", "recall without dupe",
    "recall feature", "recall function", "recall dragons guide", "recall dragons tutorial",
    "recall video", "how does recall work",

    # 2. Vietnamese (Có dấu & Không dấu) (36+ keywords)
    "hoi sinh rong", "hồi sinh rồng", "recall rong", "recall rồng",
    "thu hoi rong", "thu hồi rồng", "force recall", "recall khong trung", "recall không trùng",
    "recall khong bi trung", "recall không bị trùng", "cach recall rong", "cách recall rồng",
    "huong dan recall", "hướng dẫn recall", "recall lay orb", "recall lấy orb",
    "thu hoi rong lay orb", "thu hồi rồng lấy orb", "cach thu hoi rong", "cách thu hồi rồng",
    "cach hoi sinh rong", "cách hồi sinh rồng", "recall rong khong can ban goc",
    "recall rồng không cần bản gốc", "recall khong can trung ban", "recall không cần trùng bản",
    "video recall", "video hướng dẫn recall", "cach force recall", "cách force recall",
    "recall vo han", "recall vô hạn", "thu hoi rong vo han", "thu hồi rồng vô hạn",
    "recall de lay orb", "recall để lấy orb",

    # 3. Spanish (10+ keywords)
    "reclamar dragon", "reclamar dragones", "recall forzado", "como reclamar dragon",
    "guia de recall", "reclamar sin duplicado", "recall sin duplicado",
    "reclamar dragones tutorial", "recall dragon ciudad", "reclamar para orbes",

    # 4. Portuguese (10+ keywords)
    "recall de dragao", "recall de dragões", "recall forcado", "como fazer recall",
    "guia de recall", "recall sem duplicata", "recall dragon city", "recall para orbs",
    "recall tutorial", "recall dragao guia",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "отзыв дракона", "принудительный отзыв", "как отозвать дракона",
    "отзыв без дубликата", "гайд по отзыву", "otzyv drakona", "prinuditelnyi otzyv",
    "kak otozvat drakona", "otzyv bez dublikata", "gaid po otzyvu",

    # 6. Indonesian & Malay (8+ keywords)
    "recall naga", "cara recall naga", "recall paksa", "recall tanpa duplikat",
    "panduan recall", "recall untuk orb", "cara force recall", "recall naga tutorial",

    # 7. Turkish (6+ keywords)
    "ejderha geri cagirma", "ejderha geri çağırma", "zorla geri cagirma",
    "nasil recall yapilir", "recall rehberi", "kopya olmadan recall",

    # 8. French (6+ keywords)
    "rappel de dragon", "rappel force", "comment rappeler un dragon",
    "rappel sans doublon", "guide de rappel", "rappel pour orbes",

    # 9. German (6+ keywords)
    "drachen zuruckrufen", "drachen zurückrufen", "erzwungener rueckruf",
    "wie ruft man drachen zurueck", "rueckruf anleitung", "rueckruf ohne duplikat",

    # 10. Italian (4+ keywords)
    "richiamo drago", "richiamo forzato", "come richiamare drago", "richiamo senza duplicato",

    # 11. Tagalog / Filipino (4+ keywords)
    "pagbawi ng dragon", "paano mag recall ng dragon", "sapilitang recall", "recall walang duplicate",

    # 12. Arabic (4+ keywords)
    "استدعاء التنين", "الاستدعاء الإجباري", "كيفية استدعاء التنين", "استدعاء بدون تكرار",

    # 13. Hindi / Transliteration (4+ keywords)
    "dragon recall kaise kare", "force recall kaise kare", "recall bina duplicate", "recall guide hindi"
]

class RecallDetector:
    """
    Detects queries asking about Force Recall / No-Duplicate Recall (recall dragons without
    owning a duplicate copy) across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in RECALL_KEYWORDS_RAW:
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

        # Sort compound phrases by length descending to match longest phrases first
        self.compound_phrases.sort(key=len, reverse=True)

    def is_recall_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Force Recall / No-Duplicate Recall.
        Returns: (is_recall, matched_keyword)
        """
        if not text:
            return False, ""

        text_lower = text.strip().lower()

        # 1. Exact match for single token commands
        if text_lower in self.exact_keywords:
            return True, text_lower

        # 2. Check compound phrases first
        normalized = normalize_text_for_filter(text_lower)
        for phrase in self.compound_phrases:
            pattern = r'(?:\b|\s|^)' + re.escape(phrase) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, phrase

        # 3. Check standalone single keywords with word boundary
        for kw in self.exact_keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, kw

        return False, ""

recall_detector = RecallDetector()
