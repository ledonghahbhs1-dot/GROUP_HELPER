import re
from typing import Set, Tuple
from utils.text_cleaner import normalize_text_for_filter

# 100+ Scam/Fraud Related Keywords (Multiple Languages: English, Vietnamese, Spanish, Portuguese, Chinese, Russian, French, etc.)
SCAM_KEYWORDS_RAW = [
    # ===== ENGLISH (30+ keywords) =====
    "scam", "scammer", "fraud", "fraudster", "con", "con artist", "phishing", "phish",
    "stealing", "steal", "money laundering", "ponzi", "pyramid scheme", "fake",
    "counterfeit", "bogus", "trick", "deceive", "deception", "misleading",
    "cheating", "cheat", "hustle", "ripoff", "rip off", "ripoff artist",
    "blackmail", "extortion", "embezzlement", "swindle", "scheme",

    # ===== VIETNAMESE (30+ keywords) =====
    "lừa", "lừa đảo", "lừa danh", "lừa tiền", "lừa dối", "scam", "scammer",
    "gian lận", "gian dối", "chiếm đoạt", "chiếm doat", "đánh cắp", "danh cap",
    "khống chế tài khoản", "hacker", "giả mạo", "gia mao", "mạo danh", "mao danh",
    "ăn cơm nhà không trả tiền", "khũ khu", "khư khư", "chơi xấu", "chơi khăm",
    "lũng đoạn", "lung doan", "độc quyền", "độc lập", "thao túng", "thao tung",
    "tham nhũng", "tham nhung", "rửa tiền", "rua tien", "bán thân", "ban than",
    "lạm dụng", "lam dung", "công cộng", "cong cong", "tội danh", "toi danh",

    # ===== SPANISH (15+ keywords) =====
    "estafa", "estafador", "fraude", "defraudador", "engaño", "engañar",
    "falsificación", "falso", "falsa", "ladrón", "hurto", "robo",
    "extorsión", "chantaje", "timador", "timar", "suplantación",

    # ===== PORTUGUESE (15+ keywords) =====
    "fraude", "fraudador", "estelionatário", "golpe", "golpista",
    "enganação", "enganar", "falsificação", "falsificado", "roubo",
    "furto", "extorsão", "chantagem", "saque", "duvidoso", "suspeito",

    # ===== CHINESE (15+ keywords) =====
    "诈骗", "欺诈", "骗子", "骗人", "假冒", "冒充", "盗用", "盗窃",
    "抢劫", "勒索", "敲诈", "洗钱", "虚假", "虚伪", "欺骗", "信息盗窃",

    # ===== RUSSIAN (10+ keywords) =====
    "мошенничество", "мошенник", "обман", "обманщик", "подделка",
    "фальшивый", "кража", "воровство", "шантаж", "вымогательство",

    # ===== FRENCH (10+ keywords) =====
    "arnaque", "arnaqueur", "fraude", "escroc", "escroquerie", "faux",
    "contrefait", "vol", "extorsion", "chantage", "usurpation",

    # ===== ITALIAN (8+ keywords) =====
    "truffa", "truffatore", "frode", "falsificazione", "falso", "furto", "estorsione", "ricatto",

    # ===== GERMAN (8+ keywords) =====
    "Betrug", "Betrüger", "Betrugsmasche", "Fälschung", "gefälscht", "Raub", "Erpressung", "Diebstahl",

    # ===== TURKISH (8+ keywords) =====
    "dolandırma", "dolandırıcı", "sahtekarlık", "sahte", "hırsızlık", "gasp", "şantaj", "iz kaybı",

    # ===== THAI (5+ keywords) =====
    "ฉ้อโกง", "โกง", "ลวงโลก", "ปลอม", "ปล้น", "อดฮัก",

    # ===== JAPANESE (5+ keywords) =====
    "詐欺", "詐欺師", "偽造", "偽物", "窃盗", "恐喝", "架空",

    # ===== INDONESIAN (5+ keywords) =====
    "penipuan", "penipu", "penyelundupan", "pemalsuan", "pencuri",

    # ===== MALAY (5+ keywords) =====
    "penipuan", "penipu", "pengganas", "pemalsuan", "pencuri",
]

class ScamDetector:
    def __init__(self):
        self.keywords: Set[str] = set()
        self.language_map = {}

        for kw in SCAM_KEYWORDS_RAW:
            clean = normalize_text_for_filter(kw.strip().lower())
            if clean:
                self.keywords.add(clean)
            self.keywords.add(kw.strip().lower())

    def is_scam_message(self, text: str) -> Tuple[bool, str]:
        """
        Detects if the message contains scam/fraud keywords.
        Returns: (is_scam, matched_keyword)
        """
        if not text:
            return False, ""

        text_lower = text.lower().strip()
        normalized = normalize_text_for_filter(text_lower)

        # Check keywords with word boundaries
        for kw in self.keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, kw

        return False, ""

scam_detector = ScamDetector()
