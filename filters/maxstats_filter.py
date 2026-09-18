import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Max Health / Max Damage / Max Star / Max Level (Hack Max Stats) Keywords
# across English, Vietnamese, Spanish, Portuguese, Russian, Indonesian, Turkish, French,
# German, Italian, Tagalog, Arabic, Hindi
MAXSTATS_KEYWORDS_RAW = [
    # 1. English (28+ keywords)
    "max health", "max hp", "god mode", "max damage", "one hit kill", "one-hit kill",
    "max star", "max stars", "max level", "max lvl", "hack max stats", "max stats",
    "unlimited health", "unlimited damage", "how to max health", "how to max damage",
    "how to max star", "how to max level", "max health guide", "max damage guide",
    "max star guide", "max level guide", "max hp hack", "damage hack", "health hack",
    "level hack", "star hack", "max stats guide", "max stats tutorial",

    # 2. Vietnamese (Có dấu & Không dấu) (42+ keywords)
    "max health", "max hp", "god mode", "max damage", "mau full", "máu full",
    "full mau", "full máu", "sat thuong max", "sát thương max", "max sat thuong",
    "max sát thương", "max sao", "max star", "max cap do", "max cấp độ",
    "max level", "max lv", "len max level", "lên max level", "cach max hp", "cách max hp",
    "cach max mau", "cách max máu", "cach max sat thuong", "cách max sát thương",
    "cach max sao", "cách max sao", "cach max level", "cách max level",
    "hack mau", "hack máu", "hack sat thuong", "hack sát thương", "hack level", "hack sao",
    "huong dan max stats", "hướng dẫn max stats", "video max stats", "cach hack max",
    "cách hack max", "one hit kill", "mot cham chet", "một chạm chết",

    # 3. Spanish (10+ keywords)
    "salud maxima", "salud máxima", "daño maximo", "daño máximo", "nivel maximo",
    "nivel máximo", "estrellas maximas", "estrellas máximas", "modo dios", "un golpe mata",

    # 4. Portuguese (10+ keywords)
    "vida maxima", "vida máxima", "dano maximo", "dano máximo", "nivel maximo",
    "nivel máximo", "estrelas maximas", "estrelas máximas", "modo deus", "um golpe mata",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "максимальное здоровье", "максимальный урон", "максимальный уровень",
    "максимальные звезды", "режим бога", "убийство с одного удара",
    "maksimalnoe zdorovie", "maksimalnyi uron", "maksimalnyi uroven", "rezhim boga",

    # 6. Indonesian & Malay (8+ keywords)
    "hp maksimal", "darah maksimal", "damage maksimal", "level maksimal",
    "bintang maksimal", "mode dewa", "cara max hp", "cara max damage",

    # 7. Turkish (6+ keywords)
    "max can", "maksimum can", "max hasar", "maksimum hasar", "max seviye", "tanri modu",

    # 8. French (6+ keywords)
    "sante maximale", "santé maximale", "degats maximum", "dégâts maximum",
    "niveau maximum", "mode dieu",

    # 9. German (6+ keywords)
    "max leben", "maximales leben", "max schaden", "maximaler schaden",
    "max level guide de", "gottmodus",

    # 10. Italian (4+ keywords)
    "salute massima", "danno massimo", "livello massimo", "modalita dio",

    # 11. Tagalog / Filipino (4+ keywords)
    "paano mag max hp", "max damage paano", "max level paano", "max star paano",

    # 12. Arabic (4+ keywords)
    "الصحة القصوى", "الضرر الأقصى", "المستوى الأقصى", "وضع الإله",

    # 13. Hindi / Transliteration (4+ keywords)
    "max health kaise kare", "max damage kaise kare", "max level kaise kare", "god mode kaise kare"
]

class MaxStatsDetector:
    """
    Detects queries asking about Hack Max Stats (Max Health, Max Damage, Max Star, Max Level)
    across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in MAXSTATS_KEYWORDS_RAW:
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

    def is_maxstats_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Max Health / Max Damage / Max Star / Max Level.
        Returns: (is_maxstats, matched_keyword)
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

maxstats_detector = MaxStatsDetector()
