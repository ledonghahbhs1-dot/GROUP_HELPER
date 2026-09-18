import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Skip Heroic Race Battle Time Keywords across English, Vietnamese, Spanish,
# Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
HEROICRACE_KEYWORDS_RAW = [
    # 1. English (30+ keywords)
    "skip battle time", "skip heroic race", "heroic race skip", "skip cooldown heroic race",
    "skip event battle time", "heroic race guide", "heroic race tutorial",
    "how to skip heroic race", "skip battle cooldown", "skip heroic race timer",
    "heroic race cooldown skip", "instant heroic race", "heroic race hack",
    "skip race cooldown", "heroic race trick", "event battle skip", "skip event timer",
    "heroic race skip guide", "skip battle timer heroic race", "how to skip battle time",
    "skip heroic race cooldown", "heroic race no wait", "bypass heroic race timer",
    "heroic race timer bypass", "skip race wait time", "race cooldown skip",
    "heroic race speed skip", "no wait heroic race", "heroic race no cooldown",
    "heroic race instant win time",

    # 2. Vietnamese (Có dấu & Không dấu) (32+ keywords)
    "bo qua thoi gian dua", "bỏ qua thời gian đua", "skip dua anh hung", "skip đua anh hùng",
    "bo qua cho dua", "bỏ qua chờ đua", "cach skip dua", "cách skip đua",
    "huong dan skip dua anh hung", "hướng dẫn skip đua anh hùng",
    "bo qua thoi gian cho tran dau", "bỏ qua thời gian chờ trận đấu",
    "bo qua cooldown dua", "bỏ qua cooldown đua", "cach bo qua thoi gian dua", "cách bỏ qua thời gian đua",
    "dua anh hung khong can cho", "đua anh hùng không cần chờ", "video skip dua anh hung",
    "video skip đua anh hùng", "bo qua thoi gian su kien", "bỏ qua thời gian sự kiện",
    "dua anh hung instant", "đua anh hùng instant", "bo qua thoi gian tran dua",
    "bỏ qua thời gian trận đua", "khong can cho dua anh hung", "không cần chờ đua anh hùng",
    "meo skip dua", "mẹo skip đua", "cach lam dua anh hung nhanh", "cách làm đua anh hùng nhanh",

    # 3. Spanish (6+ keywords)
    "saltar tiempo de carrera", "saltar carrera heroica", "como saltar carrera heroica",
    "saltar espera de carrera", "guia carrera heroica", "carrera heroica sin espera",

    # 4. Portuguese (6+ keywords)
    "pular tempo de corrida", "pular corrida heroica", "como pular corrida heroica",
    "pular espera da corrida", "guia corrida heroica", "corrida heroica sem espera",

    # 5. Russian / Cyrillic & Transliteration (6+ keywords)
    "пропустить время гонки", "пропустить героическую гонку", "как пропустить гонку",
    "гайд героическая гонка", "propustit geroicheskuyu gonku", "kak propustit gonku",

    # 6. Indonesian & Malay (5+ keywords)
    "lewati waktu balapan", "lewati heroic race", "cara lewati heroic race",
    "panduan heroic race", "heroic race tanpa menunggu",

    # 7. Turkish (5+ keywords)
    "yaris suresini atla", "yarış süresini atla", "heroic race atlama",
    "nasil heroic race atlanir", "yaris bekleme atlama",

    # 8. French (4+ keywords)
    "passer le temps de course", "passer la course heroique",
    "comment passer la course heroique", "course heroique sans attente",

    # 9. German (4+ keywords)
    "rennzeit ueberspringen", "heroic race ueberspringen",
    "wie ueberspringt man heroic race", "heroic race ohne wartezeit",

    # 10. Italian (3+ keywords)
    "saltare il tempo di gara", "saltare la corsa eroica", "come saltare la corsa eroica",

    # 11. Tagalog / Filipino (2+ keywords)
    "laktawan ang oras ng karera", "paano laktawan ang heroic race",

    # 12. Arabic (3+ keywords)
    "تخطي وقت السباق", "تخطي سباق الأبطال", "كيفية تخطي سباق الأبطال",

    # 13. Hindi / Transliteration (2+ keywords)
    "heroic race skip kaise kare", "race time skip kaise kare"
]

class HeroicRaceDetector:
    """
    Detects queries asking about Skip Event Battle Time / Heroic Race cooldown skip
    across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in HEROICRACE_KEYWORDS_RAW:
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

    def is_heroicrace_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking about Skip Heroic Race Battle Time.
        Returns: (is_heroicrace, matched_keyword)
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

heroicrace_detector = HeroicRaceDetector()
