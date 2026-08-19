import re
from typing import Set
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# Danh sách hơn 100 từ khóa tìm kiếm Script, Tool, Key, Free, VIP, Dragon City
SCRIPT_KEYWORDS_RAW = [
    # English Keywords (50+ keywords)
    "script", "scripts", "tool", "tools", "free", "vip", "key", "keys",
    "dragon city", "dragoncity", "dc", "dc script", "dc tool", "dc bot", "dc mod", "dc hack",
    "free key", "vip key", "get key", "key vip", "get script", "get tool",
    "download script", "download tool", "download", "mod", "hack", "cheat",
    "bot", "auto", "auto dragon city", "dragon city script", "dragon city tool",
    "dragon city bot", "dragon city hack", "dragon city mod", "dragon city cheat",
    "dragon city free", "dragon city vip", "free script", "free tool", "vip script",
    "vip tool", "how to get key", "where to get key", "how to get script",
    "how to use tool", "how to use script", "active key", "activate key",
    "link script", "link tool", "wolfmod", "wolfmod script", "wolfmod tool",
    "gems hack", "food hack", "gold hack", "heroic race", "race bot",
    "chest bot", "arena bot", "breed bot", "ap dragon city", "apk mod",
    
    # Tiếng Việt có dấu & không dấu (60+ keywords)
    "xin key", "lay key", "lấy key", "nhan key", "nhận key", "key hom nay", "key hôm nay",
    "key free", "key vip", "key dc", "key dragon city", "cach lay key", "cách lấy key",
    "huong dan lay key", "hướng dẫn lấy key", "link lay key", "link lấy key",
    "tool dc", "script dc", "tool dragon city", "script dragon city",
    "ban hack", "bản hack", "ban mod", "bản mod", "tai tool", "tải tool",
    "tai script", "tải script", "link tool", "link script", "link download",
    "lay key o dau", "lấy key ở đâu", "kiem key", "kiếm key", "tim key", "tìm key",
    "cach dung tool", "cách dùng tool", "cach dung script", "cách dùng script",
    "huong dan hack", "hướng dẫn hack", "hack dragon city", "mod dragon city",
    "mua key", "mua key vip", "gia key", "giá key", "kich hoat key", "kích hoạt key",
    "dua race", "đua race", "bot race", "chay race", "chạy race",
    "bot dc", "auto dc", "tool free", "script free", "tool mien phi", "tool miễn phí",
    "script mien phi", "script miễn phí", "cho xin tool", "cho xin script",
    "share tool", "share script", "web tool", "trang web tool", "web lay key", "web lấy key"
]

class ScriptDetector:
    def __init__(self):
        self.keywords: Set[str] = set()
        for kw in SCRIPT_KEYWORDS_RAW:
            clean = normalize_text_for_filter(kw.strip().lower())
            if clean:
                self.keywords.add(clean)
            self.keywords.add(kw.strip().lower())

    def is_script_query(self, text: str) -> bool:
        """
        Detects if the message is looking for Dragon City Scripts, Tools, Keys, or Free/VIP access.
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Direct short triggers
        if text_lower in ["script", "scripts", "tool", "tools", "key", "keys", "free", "dragon city", "dragoncity", "dc"]:
            return True

        normalized = normalize_text_for_filter(text_lower)

        # 1. Regex word boundary matching
        for kw in self.keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True

        # 2. Key phrases
        key_phrases = [
            "wolfmod", "dragon city", "dragoncity", "lay key", "lấy key", "xin key",
            "nhan key", "nhận key", "vip key", "free key", "get key", "tool dc",
            "script dc", "hack dc", "mod dc", "link tool", "link script", "tai tool", "tai script"
        ]
        for phrase in key_phrases:
            if phrase in normalized or phrase in text_lower:
                return True

        return False

script_detector = ScriptDetector()
