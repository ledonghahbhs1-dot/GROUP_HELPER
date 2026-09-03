import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# Multilingual keywords asking about features / functions / script capabilities / tính năng / chức năng
FEATURE_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "feature", "features", "feature list", "features list", "all features", "vip features",
    "free features", "function", "functions", "functionality", "capabilities",
    "mod list", "mods list", "hack list", "hacks list", "mod menu", "hack menu",
    "what can it do", "what features", "what does it have", "what does it do",
    "script features", "tool features", "script menu", "what is included", "feature details",

    # 2. Vietnamese (Có dấu & Không dấu) (35+ keywords)
    "tinh nang", "tính năng", "chuc nang", "chức năng", "cac tinh nang", "các tính năng",
    "tinh nang vip", "tính năng vip", "tinh nang free", "tính năng free",
    "danh sach tinh nang", "danh sách tính năng", "xem tinh nang", "xem tính năng",
    "co tinh nang gi", "có tính năng gì", "co chuc nang gi", "có chức năng gì",
    "co nhung gi", "có những gì", "lam dc gi", "làm được gì", "lam duoc gi",
    "co tac dung gi", "có tác dụng gì", "menu hack", "menu mod", "tinh nang script", "tính năng script",
    "tinh nang tool", "tính năng tool", "hack co gi", "hack có gì", "tool co gi", "tool có gì",
    "script co gi", "script có gì", "review script", "script review",

    # 3. Spanish (12+ keywords)
    "funciones", "funcion", "función", "caracteristicas", "características",
    "que funciones tiene", "que tiene", "menu de mods", "lista de funciones",
    "que hace", "que hace el script", "caracteristicas vip",

    # 4. Portuguese (12+ keywords)
    "funcoes", "funções", "funcao", "função", "recursos", "o que faz",
    "menu de mods", "lista de funcoes", "lista de funções", "recursos vip",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "функции", "функция", "фичи", "возможности", "список функций",
    "что умеет", "мод меню", "funktsii", "fichi", "vozmozhnosti",

    # 6. Indonesian & Malay (8+ keywords)
    "fitur", "fitur vip", "fitur script", "menu fitur", "daftar fitur",
    "apa saja fiturnya", "apa fiturnya", "bisa apa saja",

    # 7. Turkish (6+ keywords)
    "ozellikler", "özellikler", "ozellik", "özellik", "neler var", "hille ozellikleri",

    # 8. French & German (8+ keywords)
    "fonctionnalites", "fonctionnalités", "fonctions", "caracteristiques",
    "funktionen", "eigenschaften", "was kann es", "features liste"
]

class FeatureDetector:
    """
    Detects queries asking for script features / VIP feature list / capabilities.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in FEATURE_KEYWORDS_RAW:
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

    def is_feature_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about script / VIP features.
        Returns: (is_feature, matched_keyword)
        """
        if not text:
            return False, ""

        text_lower = text.strip().lower()

        # 1. Exact match
        if text_lower in self.exact_keywords:
            return True, text_lower

        # 2. Check compound phrases
        normalized = normalize_text_for_filter(text_lower)
        for phrase in self.compound_phrases:
            pattern = r'(?:\b|\s|^)' + re.escape(phrase) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, phrase

        # 3. Check standalone keywords with word boundary
        for kw in self.exact_keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, kw

        return False, ""

feature_detector = FeatureDetector()
