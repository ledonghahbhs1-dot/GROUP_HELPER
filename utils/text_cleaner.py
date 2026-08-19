import re
import unicodedata

# Vietnamese accents map to unsigned
VN_ACCENTS_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
}

# Common leetspeak replacements
LEET_MAP = {
    '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's',
    '7': 't', '@': 'a', '!': 'i', '$': 's', '+': 't',
    '*': '', '_': '', '-': '', '.': '', ',': '', '|': 'i'
}

def remove_vietnamese_accents(text: str) -> str:
    """Converts accented Vietnamese text to plain ASCII-like lowercase"""
    text = text.lower()
    res = []
    for ch in text:
        res.append(VN_ACCENTS_MAP.get(ch, ch))
    return "".join(res)

def normalize_text_for_filter(text: str) -> str:
    """
    Deep normalization:
    - Lowercases
    - Strips Vietnamese accents
    - Replaces leetspeak
    - Collapses consecutive duplicate letters (e.g. dddmmmmm -> dm)
    - Strips spaces and special separators to detect hidden words (e.g. d_m, d.m, d m)
    """
    if not text:
        return ""
    
    text = text.lower()
    # Replace accents
    text = remove_vietnamese_accents(text)
    
    # Replace leet characters
    for k, v in LEET_MAP.items():
        text = text.replace(k, v)
        
    # Collapse repetitive chars (3 or more down to 1: e.g. cooooon -> con)
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    
    return text

def strip_all_delimiters(text: str) -> str:
    """Removes all non-alphanumeric characters for compact match"""
    return re.sub(r'[^a-zA-Z0-9]', '', normalize_text_for_filter(text))
