import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Move Habitat & Building Keywords across English, Vietnamese, Spanish,
# Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
HABITAT_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "move habitat", "move habitats", "move building", "move buildings",
    "move habitat and building", "relocate habitat", "relocate building",
    "how to move habitat", "how to move building", "move habitat guide",
    "move building guide", "move habitat freely", "rearrange habitat", "rearrange building",
    "move island layout", "reposition habitat", "reposition building", "free move habitat",
    "free move building", "move buildings anywhere", "move habitat anywhere",
    "move habitat tutorial", "move building tutorial", "layout habitat", "island layout guide",

    # 2. Vietnamese (Có dấu & Không dấu) (28+ keywords)
    "di chuyen nha o", "di chuyển nhà ở", "di chuyen chuong", "di chuyển chuồng",
    "di chuyen toa nha", "di chuyển tòa nhà", "di chuyen cong trinh", "di chuyển công trình",
    "cach di chuyen chuong", "cách di chuyển chuồng", "cach di chuyen nha", "cách di chuyển nhà",
    "huong dan di chuyen chuong", "hướng dẫn di chuyển chuồng", "di chuyen tu do", "di chuyển tự do",
    "sap xep lai dao", "sắp xếp lại đảo", "di chuyen cong trinh tu do", "di chuyển công trình tự do",
    "cach sap xep chuong", "cách sắp xếp chuồng", "video di chuyen chuong", "video di chuyển chuồng",
    "chuyen vi tri chuong", "chuyển vị trí chuồng", "chuyen vi tri toa nha", "chuyển vị trí tòa nhà",

    # 3. Spanish (10+ keywords)
    "mover habitat", "mover hábitat", "mover edificio", "como mover habitat",
    "como mover edificio", "reubicar habitat", "reubicar edificio",
    "mover edificios libremente", "guia para mover habitat", "mover habitat sin limites",

    # 4. Portuguese (10+ keywords)
    "mover habitat", "mover edificio", "como mover habitat", "como mover edificio",
    "realocar habitat", "realocar edificio", "mover edificios livremente",
    "guia para mover habitat", "mover predio", "mover predios",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "переместить дом", "переместить здание", "как переместить дом",
    "как переместить здание", "перемещение зданий", "peremestit zdanie",
    "peremestit dom", "kak peremestit zdanie", "svobodnoe peremeshchenie", "peremeshchenie zdaniy",

    # 6. Indonesian & Malay (7+ keywords)
    "pindah habitat", "pindah bangunan", "cara pindah habitat", "cara pindah bangunan",
    "pindahkan bangunan", "pindah rumah naga", "panduan pindah bangunan",

    # 7. Turkish (6+ keywords)
    "habitat tasima", "habitat taşıma", "bina tasima", "bina taşıma",
    "nasil bina tasinir", "habitat nasil tasinir",

    # 8. French (6+ keywords)
    "deplacer habitat", "déplacer habitat", "deplacer batiment", "déplacer bâtiment",
    "comment deplacer habitat", "deplacer batiments librement",

    # 9. German (5+ keywords)
    "habitat verschieben", "gebaude verschieben", "gebäude verschieben",
    "wie verschiebt man habitat", "gebaude frei verschieben",

    # 10. Italian (4+ keywords)
    "spostare habitat", "spostare edificio", "come spostare habitat", "spostare edifici liberamente",

    # 11. Tagalog / Filipino (4+ keywords)
    "ilipat ang tahanan", "ilipat ang gusali", "paano ilipat ang gusali", "libreng paglipat ng gusali",

    # 12. Arabic (4+ keywords)
    "نقل الموطن", "نقل المبنى", "كيفية نقل المبنى", "نقل المباني بحرية",

    # 13. Hindi / Transliteration (4+ keywords)
    "habitat kaise move kare", "building kaise move kare", "imarat sthanantaran", "habitat sthanantaran guide"
]

class HabitatDetector:
    """
    Detects queries asking about Move Habitat & Buildings across 100+ multilingual
    keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in HABITAT_KEYWORDS_RAW:
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

    def is_habitat_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Move Habitat & Buildings.
        Returns: (is_habitat, matched_keyword)
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

habitat_detector = HabitatDetector()
