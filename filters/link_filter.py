import re
from typing import List, Optional, Tuple
from aiogram.types import Message
from database.db import db

# Regular expressions for URL and Telegram link patterns
URL_REGEX = re.compile(
    r'(?:https?://|www\.|ftp://)'
    r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?'
    r'(?:/[^\s]*)?',
    re.IGNORECASE
)

# Detect domains without http/www like example.com, bit.ly, t.me
DOMAIN_REGEX = re.compile(
    r'(?<!@)\b(?:[a-zA-Z0-9-]{2,}\.)+'
    r'(?:com|net|org|xyz|me|io|info|biz|cc|vip|top|ru|vn|site|online|app|dev|link|club|store|pro|tv|gg|co|to|live|click|shop|space|fun|tech)'
    r'(?:/[^\s]*)?\b',
    re.IGNORECASE
)

TELEGRAM_INVITE_REGEX = re.compile(
    r'(?:t\.me|telegram\.me|telegram\.dog)/(?:joinchat/|\+|[a-zA-Z0-9_]{5,})',
    re.IGNORECASE
)

class LinkFilter:
    async def check_links(self, message: Message, chat_id: int) -> Tuple[bool, str]:
        """
        Checks if the message contains unauthorized links.
        Returns (is_violation: bool, detected_link: str)
        """
        text_sources = []
        if message.text:
            text_sources.append(message.text)
        if message.caption:
            text_sources.append(message.caption)

        # Check entity URLs (hidden hyperlinks)
        entities = (message.entities or []) + (message.caption_entities or [])
        for ent in entities:
            if ent.type == "url":
                full_text = message.text or message.caption or ""
                ent_text = full_text[ent.offset : ent.offset + ent.length]
                text_sources.append(ent_text)
            elif ent.type == "text_link" and ent.url:
                text_sources.append(ent.url)

        full_content = " ".join(text_sources)
        if not full_content:
            return False, ""

        # Fetch whitelisted domains for this chat
        whitelist = await db.get_whitelist_links(chat_id)

        # Check Telegram Invites first
        tg_match = TELEGRAM_INVITE_REGEX.search(full_content)
        if tg_match:
            detected = tg_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                return True, f"Link Telegram ({detected})"

        # Check General URLs
        url_match = URL_REGEX.search(full_content)
        if url_match:
            detected = url_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                return True, f"Liên kết web ({detected})"

        # Check Domain patterns
        domain_match = DOMAIN_REGEX.search(full_content)
        if domain_match:
            detected = domain_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                return True, f"Tên miền liên kết ({detected})"

        return False, ""

    def _is_whitelisted(self, link: str, whitelist: List[str]) -> bool:
        link_lower = link.lower()
        for allowed in whitelist:
            if allowed.lower() in link_lower:
                return True
        return False

link_filter = LinkFilter()
