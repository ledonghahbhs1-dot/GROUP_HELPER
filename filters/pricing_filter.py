import html
import re
from typing import List, Set, Tuple
from utils.text_cleaner import normalize_text_for_filter, strip_all_delimiters

# 100+ Multilingual Pricing Keywords across English, Vietnamese, Spanish, Portuguese, Russian, Indonesian, Turkish, French, German, Italian, Tagalog, Arabic, Hindi
PRICING_KEYWORDS_RAW = [
    # 1. English (30+ keywords)
    "price", "prices", "pricing", "cost", "costs", "costing", "rate", "rates", "fee", "fees",
    "charge", "charges", "how much", "how much is it", "how much for vip", "how much is vip",
    "what is the price", "what is the cost", "subscription price", "vip price", "sub price",
    "plan price", "package price", "price list", "price of key", "key price", "vip cost",
    "how much does it cost", "price info", "price check", "check price", "vip rate", "monthly price",
    "daily price", "subscription cost", "vip plans", "pricing plan", "pricing plans",

    # 2. Vietnamese (Có dấu & Không dấu) (45+ keywords)
    "gia", "giá", "gia ca", "giá cả", "gia vip", "giá vip", "gia key", "giá key",
    "gia tien", "giá tiền", "bang gia", "bảng giá", "bao gia", "báo giá",
    "check gia", "check giá", "xin gia", "xin giá", "hoi gia", "hỏi giá",
    "gia bao nhieu", "giá bao nhiêu", "bao nhieu", "bao nhiêu", "bao nhieu tien", "bao nhiêu tiền",
    "bao nhieu 1 key", "bao nhiêu 1 key", "bao nhieu 1 thang", "bao nhiêu 1 tháng",
    "gia 1 thang", "giá 1 tháng", "gia 30 ngay", "giá 30 ngày", "gia 2 ngay", "giá 2 ngày",
    "het bao nhieu", "hết bao nhiêu", "ton bao nhieu", "tốn bao nhiêu", "gia sub", "giá sub",
    "gia the nao", "giá thế nào", "gia re", "giá rẻ", "mat bao nhieu", "mất bao nhiêu",
    "chi phi", "chi phí", "phi vip", "phí vip", "bang gia vip", "bảng giá vip",
    "don gia", "đơn giá", "gia ban", "giá bán", "gia mua", "giá mua",
    "mua key gia bao nhieu", "mua key giá bao nhiêu", "inbox gia", "inbox giá", "ib gia", "ib giá",

    # 3. Spanish (18+ keywords)
    "precio", "precios", "cuanto", "cuánto", "cuanto cuesta", "cuánto cuesta",
    "cuanto sale", "cuánto sale", "cual es el precio", "cuál es el precio",
    "costo", "costos", "coste", "costes", "valor", "tarifa", "tarifas",
    "cuanto vale", "cuánto vale", "que precio tiene", "qué precio tiene",
    "cuanto por el vip", "cuánto por el vip", "precio del vip", "precio vip", "costo vip",

    # 4. Portuguese (15+ keywords)
    "preco", "preço", "precos", "preços", "quanto", "quanto custa", "quanto e", "quanto é",
    "qual o valor", "qual o preco", "qual o preço", "custo", "custos",
    "valor do vip", "preco do vip", "preço do vip", "mensalidade", "tarifa",
    "valor da key", "preco da key", "preço da key",

    # 5. Russian / Cyrillic & Transliteration (16+ keywords)
    "цена", "цены", "сколько", "сколько стоит", "почем", "почём", "прайс",
    "стоимость", "тариф", "тарифы", "цена вип", "сколько за вип",
    "cena", "skolko", "skolko stoit", "stoimost", "prays", "tarify",

    # 6. Indonesian & Malay (12+ keywords)
    "harga", "harga vip", "berapa", "berapaan", "berapa harga", "berapa harganya",
    "tarif", "biaya", "ongkos", "harga key", "harga langganan", "berapa vip",

    # 7. Turkish (10+ keywords)
    "fiyat", "fiyati", "fiyatı", "ne kadar", "kacta", "kaç para",
    "ucret", "ücret", "maliyet", "vip fiyati", "key fiyati", "key fiyatı",

    # 8. French (10+ keywords)
    "prix", "cout", "coût", "couts", "coûts", "combien", "combien coute",
    "combien coûte", "tarif", "tarifs", "prix du vip", "prix de la clé",

    # 9. German (10+ keywords)
    "preis", "preise", "kosten", "wie viel", "wieviel", "wie viel kostet",
    "tarif", "tarife", "vip preis", "key preis",

    # 10. Italian (8+ keywords)
    "prezzo", "prezzi", "quanto costa", "costo", "costi", "tariffa", "tariffe", "costo del vip",

    # 11. Tagalog / Filipino (6+ keywords)
    "magkano", "presyo", "halaga", "bayad", "magkano vip", "magkano ang key",

    # 12. Arabic (6+ keywords)
    "سعر", "بكم", "كم السعر", "كم تكلفة", "الاسعار", "سعر المفتاح",

    # 13. Hindi / Transliteration (6+ keywords)
    "kitna", "kitne ka hai", "price kya hai", "daam", "keemat", "kitna lagega"
]

class PricingDetector:
    """
    Detects pricing / cost queries across 100+ multilingual keywords and phrases.
    """
    def __init__(self):
        self.exact_keywords: Set[str] = set()
        self.compound_phrases: List[str] = []

        for kw in PRICING_KEYWORDS_RAW:
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

    def is_pricing_query(self, text: str) -> Tuple[bool, str]:
        """
        Checks if text is asking for pricing / package costs.
        Returns: (is_pricing, matched_keyword)
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

pricing_detector = PricingDetector()
