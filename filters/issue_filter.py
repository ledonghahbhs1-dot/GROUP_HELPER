import re
from typing import Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# Comprehensive list of issue/not working/no effect keywords in English and Vietnamese
ISSUE_KEYWORDS_RAW = [
    # English Keywords (40+ phrases)
    "not work", "not working", "does not work", "doesnt work", "doesn't work",
    "dont work", "don't work", "wont work", "won't work", "isnt working", "isn't working",
    "stopped working", "not functioning", "no function", "no effect", "not effective",
    "not functional", "cannot work", "cant work", "can't work", "cant use", "can't use",
    "cannot use", "unable to use", "broken", "it broke", "it's broken", "tool broken",
    "script broken", "key not working", "key invalid", "key error", "failed to run",
    "fail to run", "nothing happens", "nothing happened", "not responding", "it crashes",
    "it crashed", "crashing", "keep crashing", "keeps crashing", "error running",
    "not working for me", "not doing anything", "does nothing", "doesn't do anything",
    "useless", "doesn't help", "won't open", "cant open", "can't open", "unable to open",
    
    # Vietnamese có dấu & không dấu (60+ phrases)
    "khong hoat dong", "không hoạt động", "ko hoat dong", "k hoat dong",
    "khong tac dung", "không tác dụng", "ko tac dung", "k tac dung",
    "khong co tac dung", "không có tác dụng", "ko co tac dung", "k co tac dung",
    "khong hieu qua", "không hiệu quả", "ko hieu qua", "k hieu qua",
    "chua co tac dung", "chưa có tác dụng", "chang co tac dung", "chẳng có tác dụng",
    "vo tac dung", "vô tác dụng", "khong an thua", "không ăn thua",
    "khong chay", "không chạy", "ko chay", "k chay",
    "khong chay duoc", "không chạy được", "ko chay dc", "k chay dc",
    "khong dung duoc", "không dùng được", "ko dung dc", "k dung dc",
    "khong xai duoc", "không xài được", "ko xai dc", "k xai dc",
    "khong mo duoc", "không mở được", "ko mo dc", "k mo dc",
    "bi loi", "bị lỗi", "loi roi", "lỗi rồi", "bi loi roi", "bị lỗi rồi",
    "hong roi", "hỏng rồi", "bi hong", "bị hỏng", "toang roi", "toang rồi",
    "khong an", "không ăn", "ko an", "k an",
    "khong nhan", "không nhận", "ko nhan", "k nhan",
    "khong duoc", "không được", "ko dc", "k dc",
    "khong dc roi", "không được rồi", "ko dc roi", "k dc roi",
    "tool khong chay", "tool không chạy", "tool bi loi", "tool bị lỗi",
    "tool loi", "tool lỗi", "script loi", "script lỗi", "script bi loi", "script bị lỗi",
    "key loi", "key lỗi", "key khong an", "key không ăn", "key ko nhan", "key không nhận",
    "hack khong chay", "hack không chạy", "mod bi loi", "mod bị lỗi"
]

class IssueDetector:
    def __init__(self):
        self.keywords: Set[str] = set()
        for kw in ISSUE_KEYWORDS_RAW:
            clean = normalize_text_for_filter(kw.strip().lower())
            if clean:
                self.keywords.add(clean)
            self.keywords.add(kw.strip().lower())

    def is_issue_query(self, text: str) -> Tuple[bool, str]:
        """
        Detects if the message is asking for help with a tool/script/feature that is not working,
        has no effect, is broken, or throws errors.
        Returns (is_issue: bool, matched_keyword: str)
        """
        if not text:
            return False, ""

        text_lower = text.lower().strip()
        normalized = normalize_text_for_filter(text_lower)

        for kw in self.keywords:
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True, kw

        return False, ""

issue_detector = IssueDetector()
