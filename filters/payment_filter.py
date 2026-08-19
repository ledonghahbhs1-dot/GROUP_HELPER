import re
from typing import List
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# Danh sách hơn 100 từ khóa thanh toán tiếng Anh và tiếng Việt
PAYMENT_KEYWORDS_RAW = [
    # English Keywords (40+ keywords)
    "pay", "payment", "payments", "payme", "how to pay", "where to pay", "ways to pay",
    "payment method", "payment methods", "payment info", "payment details", "payment options",
    "buy", "how to buy", "purchase", "how to purchase", "order", "how to order",
    "price", "prices", "pricing", "cost", "how much", "how much is it", "fee", "fees",
    "bank", "banking", "bank account", "bank transfer", "wire transfer", "bank details",
    "paypal", "paypal me", "paypal info", "paypal account",
    "binance", "binance id", "usdt", "crypto", "bep20", "deposit", "deposit address",
    "sociabuzz", "sociabuzz tribe", "vcb", "vietcombank", "donate", "donation", "tip", "tipping",
    "checkout", "invoice", "bill", "billing", "subscription", "sub price", "renew",
    "vip price", "buy vip", "get vip", "upgrade vip", "vip cost", "premium price",
    "transfer money", "send money", "funds", "pay now", "how to send money",
    "rewarble", "rewarble.com", "redeem", "redeem code", "gift card", "gift code", "voucher",
    
    # Tiếng Việt có dấu & không dấu (60+ keywords)
    "thanh toan", "thanh toán", "phuong thuc thanh toan", "phương thức thanh toán",
    "cach thanh toan", "cách thanh toán", "huong dan thanh toan", "hướng dẫn thanh toán",
    "chuyen khoan", "chuyển khoản", "chuyen tien", "chuyển tiền", "ck", "banking",
    "so tai khoan", "số tài khoản", "stk", "so tk", "số tk", "tai khoan ngan hang", "tài khoản ngân hàng",
    "ngan hang", "ngân hàng", "nap tien", "nạp tiền", "gui tien", "gửi tiền",
    "mua", "mua ban", "mua bán", "cach mua", "cách mua", "huong dan mua", "hướng dẫn mua",
    "mua vip", "nap vip", "nạp vip", "gia vip", "giá vip", "gia", "giá",
    "bang gia", "bảng giá", "bao gia", "báo giá", "check gia", "check giá",
    "gia bao nhieu", "giá bao nhiêu", "bao nhieu", "bao nhiêu", "bao nhieu tien", "bao nhiêu tiền",
    "gia ca", "giá cả", "don gia", "đơn giá", "chi phi", "chi phí", "phi", "phí",
    "mua sub", "mua bot", "thue bot", "thuê bot", "thue", "thuê",
    "dong tien", "đóng tiền", "tra tien", "trả tiền", "tien nong", "tiền nong",
    "mua the nao", "mua thế nào", "tra qua dau", "trả qua đâu", "chuyen qua dau", "chuyển qua đâu",
    "tai khoan", "tài khoản", "inbox gia", "inbox giá", "ib gia", "ib giá",
    "donate", "ung ho", "ủng hộ", "nap", "nạp", "nap the", "nạp thẻ",
    "vietcombank", "vcb", "binance", "paypal", "vi usdt", "ví usdt", "dia chi vi", "địa chỉ ví",
    "thanh toan the nao", "thanh toán thế nào", "tt qua dau", "tt qua đâu", "stk vcb",
    "chuyen khoan vcb", "chuyển khoản vcb", "xin stk", "xin số tài khoản", "cho xin stk", "cho xin số tài khoản",
    "ma the", "mã thẻ", "nap the cao", "nạp thẻ cào", "ma code", "mã code", "nhap code", "nhập code"
]

class PaymentDetector:
    def __init__(self):
        # Normalize and pre-compile keyword search patterns
        self.keywords = set()
        for kw in PAYMENT_KEYWORDS_RAW:
            clean = normalize_text_for_filter(kw.strip().lower())
            if clean:
                self.keywords.add(clean)
            self.keywords.add(kw.strip().lower())

    def is_payment_query(self, text: str) -> bool:
        """
        Detects if the user text is asking for payment information.
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Check direct commands or exact words
        if text_lower in ["pay", "payment", "buy", "price", "bank", "stk", "paypal", "binance", "donate", "vcb"]:
            return True

        # Normalized string without accents and delimiters
        normalized = normalize_text_for_filter(text_lower)
        stripped = strip_all_delimiters(normalized)

        # 1. Direct substring matching in normalized text
        for kw in self.keywords:
            # Word boundary or standalone phrase match
            pattern = r'(?:\b|\s|^)' + re.escape(kw) + r'(?:\b|\s|$)'
            if re.search(pattern, text_lower) or re.search(pattern, normalized):
                return True

        # 2. Check compound phrases like "xin stk", "bao gia", "mua vip"
        special_triggers = [
            "paypal", "binance", "vietcombank", "sociabuzz", "vcb",
            "chuyen khoan", "chuyen tien", "so tai khoan", "stk",
            "thanh toan", "bang gia", "bao gia", "gia bao nhieu",
            "how to pay", "payment method", "how to buy", "buy vip"
        ]
        for trig in special_triggers:
            if trig in normalized or trig in text_lower:
                return True

        return False

payment_detector = PaymentDetector()
