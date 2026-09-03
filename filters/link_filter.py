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
    r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:joinchat/|\+|[a-zA-Z0-9_+/=-]+)',
    re.IGNORECASE
)

# Detect links to other Telegram bots (e.g. t.me/xxx_bot, t.me/xxxbot, t.me/app?startapp=..., tg://resolve?domain=xxx_bot)
TELEGRAM_BOT_REGEX = re.compile(
    r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:[a-zA-Z0-9_]*bot(?:\W|$)|[a-zA-Z0-9_]+/(?:app|start|bot)|[a-zA-Z0-9_]+\?(?:start|startapp)=)',
    re.IGNORECASE
)

# Detect bot mentions like @xxx_bot or @xxxbot
BOT_MENTION_REGEX = re.compile(
    r'(?<!\w)@([a-zA-Z0-9_]{3,32}bot)\b',
    re.IGNORECASE
)

# Detect tg:// deep links to bots
TG_RESOLVE_BOT_REGEX = re.compile(
    r'tg://resolve\?(?:[^\s]*&)?domain=([a-zA-Z0-9_]*bot)\b',
    re.IGNORECASE
)

def mask_link_preview(link: str, max_words: int = 4) -> str:
    """
    Truncates a link to show only the first 3-4 keywords/tokens, followed by '...'
    Ensures that the full URL or sensitive ref/payload is never exposed in the chat.
    Examples:
        'https://t.me/tapswap_bot?start=r_123456' -> 'https://t.me/tapswap_bot...'
        'https://t.me/hamster_kombat_bot/start?startapp=123' -> 'https://t.me/hamster_kombat...'
        '@dogshouse_bot' -> '@dogshouse_bot...'
        'https://subdomain.website.com/category/article' -> 'https://subdomain.website.com/category...'
    """
    if not link:
        return ""
    link = link.strip()
    clean_url = re.sub(r'[\?\#].*$', '', link)
    
    scheme_match = re.match(r'^(https?://)', clean_url, re.IGNORECASE)
    scheme = scheme_match.group(1) if scheme_match else ''
    body = clean_url[len(scheme):]
    
    matches = list(re.finditer(r'[a-zA-Z0-9]+', body))
    if not matches:
        return (clean_url[:20] + '...') if len(clean_url) > 20 else (clean_url + '...')
    
    if len(matches) > max_words:
        cut_pos = matches[max_words - 1].end()
        shortened = scheme + body[:cut_pos].rstrip('/_-.')
        return shortened + '...'
    else:
        shortened = scheme + body.rstrip('/_-.')
        if len(shortened) > 30:
            shortened = shortened[:30]
        return shortened + '...'

class LinkFilter:
    def mask_link_preview(self, link: str, max_words: int = 4) -> str:
        return mask_link_preview(link, max_words)

    def is_bot_link(self, link: str, own_bot_username: str = "") -> bool:
        """Check if the given link or mention points to a Telegram bot"""
        if not link:
            return False
        if own_bot_username:
            clean_own = own_bot_username.lower().lstrip('@')
            if clean_own and clean_own in link.lower():
                return False
        if TELEGRAM_BOT_REGEX.search(link):
            return True
        if BOT_MENTION_REGEX.search(link):
            return True
        if TG_RESOLVE_BOT_REGEX.search(link):
            return True
        return False

    async def check_links(self, message: Message, chat_id: int, own_bot_username: str = "") -> Tuple[bool, str, bool]:
        """
        Checks if the message contains unauthorized links or bot links.
        Returns: (is_violation: bool, masked_preview: str, is_bot_link: bool)
        """
        # Fetch whitelisted domains for this chat
        whitelist = await db.get_whitelist_links(chat_id)

        # 1. Direct Telegram Entity Check (URLs, Text Links, Mentions)
        entities = (message.entities or []) + (message.caption_entities or [])
        full_text = message.text or message.caption or ""
        for ent in entities:
            if ent.type == "url":
                ent_url = full_text[ent.offset : ent.offset + ent.length]
                if ent_url and not self._is_whitelisted(ent_url, whitelist):
                    is_bot = self.is_bot_link(ent_url, own_bot_username)
                    masked = mask_link_preview(ent_url)
                    return True, masked, is_bot
            elif ent.type == "text_link" and ent.url:
                if not self._is_whitelisted(ent.url, whitelist):
                    is_bot = self.is_bot_link(ent.url, own_bot_username)
                    masked = mask_link_preview(ent.url)
                    return True, masked, is_bot
            elif ent.type == "mention":
                ent_mention = full_text[ent.offset : ent.offset + ent.length]
                if ent_mention and self.is_bot_link(ent_mention, own_bot_username):
                    if not self._is_whitelisted(ent_mention, whitelist):
                        masked = mask_link_preview(ent_mention)
                        return True, masked, True

        # 2. Extract all text content
        text_sources = []
        if message.text:
            text_sources.append(message.text)
        if message.caption:
            text_sources.append(message.caption)

        full_content = " ".join(text_sources)
        if not full_content:
            return False, "", False

        # 3. Check Telegram Bot Links / Deep links
        bot_match = TELEGRAM_BOT_REGEX.search(full_content)
        if bot_match:
            detected = bot_match.group(0)
            if not self._is_whitelisted(detected, whitelist) and not (own_bot_username and own_bot_username.lower().lstrip('@') in detected.lower()):
                masked = mask_link_preview(detected)
                return True, masked, True

        # 4. Check Bot Mentions (@xxx_bot)
        mention_match = BOT_MENTION_REGEX.search(full_content)
        if mention_match:
            detected = mention_match.group(0)
            if not self._is_whitelisted(detected, whitelist) and not (own_bot_username and own_bot_username.lower().lstrip('@') in detected.lower()):
                masked = mask_link_preview(detected)
                return True, masked, True

        # 5. Check Telegram Resolve links
        tg_resolve_match = TG_RESOLVE_BOT_REGEX.search(full_content)
        if tg_resolve_match:
            detected = tg_resolve_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                masked = mask_link_preview(detected)
                return True, masked, True

        # 6. Check Telegram Group / Channel Invites
        tg_match = TELEGRAM_INVITE_REGEX.search(full_content)
        if tg_match:
            detected = tg_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                masked = mask_link_preview(detected)
                return True, masked, False

        # 7. Check General URLs
        url_match = URL_REGEX.search(full_content)
        if url_match:
            detected = url_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                is_bot = self.is_bot_link(detected, own_bot_username)
                masked = mask_link_preview(detected)
                return True, masked, is_bot

        # 8. Check Domain patterns
        domain_match = DOMAIN_REGEX.search(full_content)
        if domain_match:
            detected = domain_match.group(0)
            if not self._is_whitelisted(detected, whitelist):
                is_bot = self.is_bot_link(detected, own_bot_username)
                masked = mask_link_preview(detected)
                return True, masked, is_bot

        return False, "", False

    def _is_whitelisted(self, link: str, whitelist: List[str]) -> bool:
        link_lower = link.lower()
        for allowed in whitelist:
            if allowed.lower() in link_lower:
                return True
        return False

link_filter = LinkFilter()
