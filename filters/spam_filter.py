import time
from collections import defaultdict
from typing import Dict, List, Tuple
import config

class SpamFilter:
    def __init__(self):
        # Maps (chat_id, user_id) -> list of timestamp floats
        self.message_history: Dict[Tuple[int, int], List[float]] = defaultdict(list)
        # Maps (chat_id, user_id) -> list of (text, timestamp)
        self.duplicate_history: Dict[Tuple[int, int], List[Tuple[str, float]]] = defaultdict(list)

    def check_spam(self, chat_id: int, user_id: int, text: str = "") -> Tuple[bool, str]:
        now = time.time()
        key = (chat_id, user_id)

        # 1. Message Frequency / Flood Check
        history = self.message_history[key]
        # Keep only timestamps within interval
        history = [t for t in history if now - t <= config.SPAM_INTERVAL_SEC]
        history.append(now)
        self.message_history[key] = history

        if len(history) > config.SPAM_MESSAGE_LIMIT:
            return True, f"Gửi quá {config.SPAM_MESSAGE_LIMIT} tin nhắn trong {config.SPAM_INTERVAL_SEC}s (Flood)"

        # 2. Duplicate Text Flood Check
        if text and len(text.strip()) > 3:
            clean_text = text.strip().lower()
            dup_hist = self.duplicate_history[key]
            # Keep only items within duplicate interval
            dup_hist = [(t_text, t_time) for (t_text, t_time) in dup_hist if now - t_time <= config.SPAM_DUPLICATE_INTERVAL]
            dup_hist.append((clean_text, now))
            self.duplicate_history[key] = dup_hist

            # Count duplicates of the same text
            same_text_count = sum(1 for (t_text, _) in dup_hist if t_text == clean_text)
            if same_text_count >= config.SPAM_DUPLICATE_LIMIT:
                return True, f"Spam tin nhắn trùng lặp {same_text_count} lần liên tiếp"

        # 3. Massive Character Spam (e.g. aaaaaaaaaaaaaaaaaaaaa)
        if text:
            import re
            match = re.search(r'(.)\1{25,}', text)
            if match:
                return True, "Spam ký tự kéo dài bất thường"

        # 4. Excessive CAPS spam (for messages >= 25 chars)
        if text and len(text) >= 25:
            alpha_chars = [c for c in text if c.isalpha()]
            if len(alpha_chars) >= 20:
                caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if caps_ratio >= 0.85:
                    return True, "Spam chữ viết hoa (CAPS LOCK)"

        return False, ""

    def cleanup_old_data(self):
        """Periodically cleans up memory for inactive users"""
        now = time.time()
        for key in list(self.message_history.keys()):
            self.message_history[key] = [t for t in self.message_history[key] if now - t <= 60]
            if not self.message_history[key]:
                del self.message_history[key]

        for key in list(self.duplicate_history.keys()):
            self.duplicate_history[key] = [(txt, t) for (txt, t) in self.duplicate_history[key] if now - t <= 120]
            if not self.duplicate_history[key]:
                del self.duplicate_history[key]

spam_filter = SpamFilter()
