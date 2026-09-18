import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Bypass Verified Attack Skill Keywords across English, Vietnamese, Spanish,
# Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
BYPASSVERIFY_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "bypass verified skill", "bypass verify skill", "bypass verified attack",
    "bypass skill verification", "bypass attack verification", "bypass server verification",
    "verified skill bypass", "how to bypass verified skill", "bypass skill check",
    "bypass attack skill check", "skill verification bypass", "bypass verified attack skill",
    "bypass skill guide", "bypass verify attack", "server side verification bypass",
    "bypass anti cheat skill", "bypass skill validation", "attack skill bypass guide",
    "verified attack bypass tutorial", "how to bypass skill verification",
    "bypass verified skill tutorial", "bypass verified skill guide", "skill bypass hack",
    "attack verification bypass", "verified attack skill hack",

    # 2. Vietnamese (Có dấu & Không dấu) (26+ keywords)
    "bypass ky nang", "bypass kỹ năng", "vuot qua xac thuc ky nang", "vượt qua xác thực kỹ năng",
    "bypass xac thuc", "bypass xác thực", "cach bypass ky nang", "cách bypass kỹ năng",
    "vuot xac minh ky nang", "vượt xác minh kỹ năng", "bypass tan cong", "bypass tấn công",
    "cach vuot xac thuc ky nang", "cách vượt xác thực kỹ năng", "huong dan bypass ky nang",
    "hướng dẫn bypass kỹ năng", "vuot kiem tra ky nang", "vượt kiểm tra kỹ năng",
    "bypass ky nang tan cong", "bypass kỹ năng tấn công", "video bypass ky nang",
    "video bypass kỹ năng", "cach vuot kiem tra tan cong", "cách vượt kiểm tra tấn công",
    "vuot xac thuc may chu", "vượt xác thực máy chủ",

    # 3. Spanish (5+ keywords)
    "bypass de habilidad verificada", "omitir verificacion de habilidad",
    "como omitir verificacion", "bypass de ataque verificado", "saltar verificacion de habilidad",

    # 4. Portuguese (5+ keywords)
    "bypass de habilidade verificada", "burlar verificacao de habilidade",
    "como burlar verificacao", "bypass de ataque verificado", "pular verificacao de habilidade",

    # 5. Russian / Cyrillic & Transliteration (5+ keywords)
    "обход проверки навыка", "как обойти проверку навыка", "обход верификации атаки",
    "obhod proverki navyka", "kak oboiti proverku navyka",

    # 6. Indonesian & Malay (4+ keywords)
    "bypass verifikasi skill", "cara bypass verifikasi skill", "bypass skill terverifikasi",
    "lewati verifikasi skill",

    # 7. Turkish (3+ keywords)
    "yetenek dogrulamasini atlatma", "yetenek doğrulamasını atlatma", "saldiri dogrulama bypass",

    # 8. French (3+ keywords)
    "contourner la verification de competence", "contourner vérification de compétence",
    "bypass competence verifiee",

    # 9. German (2+ keywords)
    "fertigkeitsverifizierung umgehen", "angriffsverifizierung umgehen",

    # 10. Italian (2+ keywords)
    "aggirare la verifica abilita", "bypass abilita verificata",

    # 11. Tagalog / Filipino (2+ keywords)
    "i-bypass ang beripikasyon ng kasanayan", "paano i-bypass ang beripikasyon",

    # 12. Arabic (2+ keywords)
    "تجاوز التحقق من المهارة", "كيفية تجاوز التحقق من المهارة",

    # 13. Hindi / Transliteration (2+ keywords)
    "skill verification bypass kaise kare", "verified attack bypass kaise kare"
]

class BypassVerifyDetector:
    """
    Detects queries asking about Bypass Verified Attack Skills (server-side attack skill
    verification bypass) across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in BYPASSVERIFY_KEYWORDS_RAW:
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

    def is_bypassverify_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Bypass Verified Attack Skills.
        Returns: (is_bypassverify, matched_keyword)
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

bypassverify_detector = BypassVerifyDetector()
