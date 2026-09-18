import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Arena Battle Keywords across English, Vietnamese, Spanish, Portuguese,
# Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
ARENA_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "arena battle", "arena battles", "easy arena battle", "easy arena", "arena win",
    "auto arena", "arena auto win", "how to win arena", "arena guide", "arena tutorial",
    "arena hack", "arena mod", "win arena", "arena instructions", "arena help",
    "arena video", "how to use arena battle", "arena battle guide", "arena battle tutorial",
    "arena feature", "arena function", "battle arena", "arena hack guide",
    "how does arena battle work", "arena not working", "arena battle video",
    "arena battle instructions", "arena walkthrough",

    # 2. Vietnamese (Có dấu & Không dấu) (35+ keywords)
    "dau truong", "đấu trường", "danh dau truong", "đánh đấu trường", "arena battle",
    "huong dan arena", "hướng dẫn arena", "huong dan dau truong", "hướng dẫn đấu trường",
    "cach danh dau truong", "cách đánh đấu trường", "video dau truong", "video đấu trường",
    "dau truong de dang", "đấu trường dễ dàng", "thang dau truong", "thắng đấu trường",
    "auto dau truong", "auto đấu trường", "cach dung arena", "cách dùng arena",
    "cach su dung arena battle", "cách sử dụng arena battle", "arena battle la gi",
    "arena battle là gì", "chuc nang arena", "chức năng arena", "tinh nang arena",
    "tính năng arena", "video huong dan arena", "video hướng dẫn arena",
    "cach choi dau truong", "cách chơi đấu trường", "loi dau truong", "lỗi đấu trường",
    "sua loi arena", "sửa lỗi arena", "easy arena battle la gi", "easy arena battle là gì",
    "cach lam easy arena", "cách làm easy arena",

    # 3. Spanish (10+ keywords)
    "arena facil", "arena fácil", "batalla de arena", "como ganar en la arena",
    "cómo ganar en la arena", "tutorial de arena", "guia de arena", "guía de arena",
    "video de arena", "arena batalla facil",

    # 4. Portuguese (10+ keywords)
    "arena facil batalha", "batalha de arena", "como vencer a arena", "tutorial da arena",
    "guia da arena", "video da arena", "arena batalha", "como usar a arena",
    "video tutorial arena", "arena facil",

    # 5. Russian / Cyrillic & Transliteration (10+ keywords)
    "арена", "битва арены", "легкая арена", "как выиграть арену", "гайд по арене",
    "видео арена", "туториал арена", "как пройти арену", "arena bitva", "kak vyigrat arenu",

    # 6. Indonesian & Malay (8+ keywords)
    "arena mudah", "pertarungan arena", "cara menang arena", "panduan arena",
    "video arena", "tutorial arena", "cara main arena", "arena battle mudah",

    # 7. Turkish (6+ keywords)
    "kolay arena", "arena savasi", "arena savaşı", "arena nasil kazanilir",
    "arena rehberi", "arena videosu",

    # 8. French (6+ keywords)
    "arene facile", "arène facile", "bataille d'arene", "comment gagner l'arene",
    "tuto arene", "video arene",

    # 9. German (6+ keywords)
    "einfache arena", "arena kampf", "wie gewinnt man arena", "arena anleitung",
    "arena video tutorial", "arena tutorial",

    # 10. Italian (4+ keywords)
    "arena facile", "battaglia arena", "come vincere arena", "video arena tutorial",

    # 11. Tagalog / Filipino (4+ keywords)
    "madaling arena", "labanan sa arena", "paano manalo sa arena", "gabay sa arena",

    # 12. Arabic (4+ keywords)
    "ساحة القتال", "المعركة السهلة", "فيديو الساحة", "كيفية الفوز في الساحة",

    # 13. Hindi / Transliteration (4+ keywords)
    "arena kaise jeete", "arena video guide", "arena guide", "asaan arena"
]

class ArenaDetector:
    """
    Detects queries asking about Arena Battle / Easy Arena Battle feature across
    100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in ARENA_KEYWORDS_RAW:
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

    def is_arena_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Arena Battle / Easy Arena Battle.
        Returns: (is_arena, matched_keyword)
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

arena_detector = ArenaDetector()
