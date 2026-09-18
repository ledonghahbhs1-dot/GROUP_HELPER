import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Farm Orb / Quest / Rank Up Keywords across English, Vietnamese, Spanish,
# Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
ORBQUEST_KEYWORDS_RAW = [
    # 1. English (28+ keywords)
    "farm orb", "farm orbs", "orb farm", "orb farming", "quest farm", "farm quest",
    "quest farming", "orb quest", "orb quest farm", "farm orb quest", "how to farm orb",
    "how to farm orbs", "orb farming guide", "orb farming tutorial", "orb tutorial",
    "quest guide", "quest tutorial", "easy quest", "how to get orbs", "farm orb guide",
    "rank up", "rank up guide", "how to rank up", "level up", "level up guide",
    "how to level up", "max rank", "increase rank", "boost rank", "rank guide",
    "leveling guide", "rank up tutorial", "level up tutorial",

    # 2. Vietnamese (Có dấu & Không dấu) (40+ keywords)
    "farm orb", "cay orb", "cày orb", "cay quest", "cày quest", "farm quest",
    "cach farm orb", "cách farm orb", "cach cay orb", "cách cày orb",
    "huong dan farm orb", "hướng dẫn farm orb", "farm orb quest", "cay orb quest", "cày orb quest",
    "video farm orb", "video hướng dẫn farm orb", "cach farm quest", "cách farm quest",
    "nong rank", "nâng rank", "len rank", "lên rank", "tang rank", "tăng rank",
    "len level", "lên level", "tang level", "tăng level", "cach nang rank", "cách nâng rank",
    "cach len rank", "cách lên rank", "cach tang rank", "cách tăng rank",
    "huong dan nang rank", "hướng dẫn nâng rank", "video nâng rank", "video nang rank",
    "cach len level", "cách lên level", "nang cap rank", "nâng cấp rank",
    "nang hang", "nâng hạng", "len hang", "lên hạng", "cach nang hang", "cách nâng hạng",

    # 3. Spanish (10+ keywords)
    "granja de orbes", "farmear orbes", "subir de rango", "como subir de rango",
    "subir rango", "guia de rango", "farmear misiones", "subir nivel",
    "como subir nivel", "orbes de mision",

    # 4. Portuguese (10+ keywords)
    "farm de orbs", "farmar orbs", "subir de rank", "como subir de rank",
    "subir rank", "guia de rank", "farmar missao", "subir nivel",
    "como subir nivel", "orbs de missao",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "ферма орбов", "фарм орб", "повысить ранг", "как повысить ранг", "гайд по рангу",
    "фарм квестов", "повысить уровень", "farm orb", "kak povysit rang", "farm kvestov",

    # 6. Indonesian & Malay (8+ keywords)
    "farm orb", "cara farm orb", "naik rank", "cara naik rank", "naik level",
    "cara naik level", "farm quest", "panduan naik rank",

    # 7. Turkish (6+ keywords)
    "orb ciftligi", "orb çiftliği", "rank yukseltme", "rank yükseltme",
    "seviye atlama", "gorev ciftligi",

    # 8. French (6+ keywords)
    "farm orbe", "monter en rang", "comment monter en rang", "monter de niveau",
    "guide de rang", "farm quete",

    # 9. German (6+ keywords)
    "orb farmen", "rang erhohen", "rang erhöhen", "level aufsteigen",
    "rang anleitung", "quest farmen",

    # 10. Italian (4+ keywords)
    "farm orbe", "salire di rango", "come salire di rango", "salire di livello",

    # 11. Tagalog / Filipino (4+ keywords)
    "pag-farm ng orb", "pataas ng rank", "paano tumaas ang rank", "pag-level up",

    # 12. Arabic (4+ keywords)
    "زراعة الكرات", "رفع الرتبة", "كيفية رفع الرتبة", "رفع المستوى",

    # 13. Hindi / Transliteration (4+ keywords)
    "orb kaise farm karen", "rank kaise badhaye", "level up guide", "quest farming guide"
]

class OrbQuestDetector:
    """
    Detects queries asking about Farm Orb / Quest Farming / Rank Up (Level Up) across
    100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in ORBQUEST_KEYWORDS_RAW:
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

    def is_orbquest_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Farm Orb / Quest Farming / Rank Up.
        Returns: (is_orbquest, matched_keyword)
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

orbquest_detector = OrbQuestDetector()
