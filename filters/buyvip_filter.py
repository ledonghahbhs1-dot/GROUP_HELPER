import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter

# 100+ Multilingual Direct "I want to buy VIP" intent keywords across
# English, Vietnamese, Spanish, Portuguese, Russian, Indonesian, Turkish, French, German, Italian, etc.
BUYVIP_KEYWORDS_RAW = [
    # 1. English (25+ keywords)
    "buy vip", "buyvip", "buy vip key", "buy vip now", "purchase vip",
    "purchase vip key", "get vip", "get vip key", "i want to buy vip",
    "i want vip", "want to buy vip", "how to buy vip", "order vip",
    "order vip key", "pay for vip", "unlock vip", "upgrade to vip",
    "upgrade vip", "get vip access", "buy license", "buy vip license",
    "need vip", "need vip key", "i need vip", "how can i buy vip",
    "where to buy vip", "buy full vip", "subscribe vip",

    # 2. Vietnamese (Có dấu & Không dấu) (30+ keywords)
    "mua vip", "muavip", "mua vip key", "mua key vip", "mua vip di",
    "muon mua vip", "muốn mua vip", "toi muon mua vip", "tôi muốn mua vip",
    "cach mua vip", "cách mua vip", "dang ky vip", "đăng ký vip",
    "mua vip o dau", "mua vip ở đâu", "mua key o dau", "mua key ở đâu",
    "mua hack vip", "mua tool vip", "mua bản vip", "mua ban vip",
    "lam sao mua vip", "làm sao mua vip", "gia nhap vip", "gia nhập vip",
    "nang cap vip", "nâng cấp vip", "thanh toan mua vip", "thanh toán mua vip",
    "dat mua vip", "đặt mua vip", "lay vip", "lấy vip", "can mua vip", "cần mua vip",

    # 3. Spanish (12+ keywords)
    "comprar vip", "adquirir vip", "quiero comprar vip", "como comprar vip",
    "comprar clave vip", "comprar key vip", "comprar pase vip", "ordenar vip",
    "pagar vip", "obtener vip", "acceso vip comprar", "donde comprar vip",

    # 4. Portuguese (12+ keywords)
    "comprar vip", "adquirir vip", "quero comprar vip", "como comprar vip",
    "comprar chave vip", "comprar key vip", "pedir vip", "pagar vip",
    "obter vip", "assinar vip", "onde comprar vip", "quero o vip",

    # 5. Russian (12+ keywords)
    "купить вип", "купить vip", "как купить вип", "хочу вип", "хочу купить вип",
    "приобрести вип", "купить ключ вип", "заказать вип", "оплатить вип",
    "kupit vip", "hochu vip", "gde kupit vip",

    # 6. Indonesian & Malay (10+ keywords)
    "beli vip", "beli key vip", "mau beli vip", "cara beli vip", "pesan vip",
    "langganan vip", "bayar vip", "order vip", "dapatkan vip", "dimana beli vip",

    # 7. Turkish (6+ keywords)
    "vip satin al", "vip satın al", "nasil vip alinir", "nasıl vip alınır",
    "vip almak istiyorum", "vip satin alma",

    # 8. French (6+ keywords)
    "acheter vip", "comment acheter vip", "je veux acheter vip", "commander vip",
    "payer vip", "obtenir vip",

    # 9. German (6+ keywords)
    "vip kaufen", "wie kaufe ich vip", "ich moechte vip kaufen", "vip bestellen",
    "vip bezahlen", "vip erwerben",

    # 10. Italian (5+ keywords)
    "comprare vip", "acquistare vip", "voglio comprare vip", "come comprare vip",
    "ordinare vip",

    # 11. Tagalog / Filipino (4+ keywords)
    "bumili ng vip", "paano bumili ng vip", "gusto kong bumili ng vip", "bili ng vip",

    # 12. Arabic (4+ keywords)
    "شراء فيب", "كيفية شراء فيب", "اريد شراء فيب", "طلب فيب",

    # 13. Hindi (4+ keywords)
    "vip kharidna hai", "kaise vip kharide", "vip buy karna hai", "vip chahiye"
]

class BuyVipDetector:
    """Detects a direct intent to buy VIP across 100+ multilingual keywords."""
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in BUYVIP_KEYWORDS_RAW:
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

    def is_buyvip_query(self, text: str) -> Tuple[bool, str]:
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

buyvip_detector = BuyVipDetector()
