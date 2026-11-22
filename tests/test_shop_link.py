"""Task 104: "Mua AI Products" URL button towards the TELE_SHOPS bot."""
import asyncio
import os
import unittest
from unittest.mock import patch

from handlers import member_handlers as mh
from utils import shop_link as sl


def env(value):
    return patch.dict(os.environ, {} if value is None else {"SHOP_BOT_USERNAME": value}, clear=False)


def clear():
    return patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "SHOP_BOT_USERNAME"}, clear=True)


def flat(markup):
    return [b for row in markup.inline_keyboard for b in row]


class ShopLinkTests(unittest.TestCase):
    def test_url_built_from_env_without_payload(self):
        with env("my_shop_bot"):
            self.assertEqual(sl.shop_bot_url(), "https://t.me/my_shop_bot")
        with env("  @My_Shop_Bot "):
            self.assertEqual(sl.shop_bot_url(), "https://t.me/My_Shop_Bot")  # '@' and spaces tolerated

    def test_payload_is_added_only_when_configured(self):
        with env("my_shop_bot"), patch.object(sl, "SHOP_START_PAYLOAD", "ai_products"):
            self.assertEqual(sl.shop_bot_url(), "https://t.me/my_shop_bot?start=ai_products")

    def test_missing_or_invalid_username_hides_the_button(self):
        with clear():
            self.assertIsNone(sl.shop_bot_url())
            self.assertIsNone(sl.ai_products_button())
        for bad in ("", "   ", "@", "abc", "1bot_name", "has space", "a/b/c_bot", "x" * 40, "https://t.me/x_bot", "bot?start=1"):
            with env(bad):
                self.assertIsNone(sl.ai_products_button(), bad)

    def test_button_is_a_url_button_not_callback(self):
        with env("my_shop_bot"):
            button = sl.ai_products_button()
        self.assertEqual(button.text, "Mua AI Products (Gemini/ChatGPT)")
        self.assertEqual(button.url, "https://t.me/my_shop_bot")
        self.assertIsNone(button.callback_data)

    def test_with_ai_products_button_adds_a_last_row_only_when_set(self):
        base = [[sl.InlineKeyboardButton(text="A", url="https://x.y/a")]]
        with env("my_shop_bot"):
            rows = sl.with_ai_products_button(base).inline_keyboard
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1][0].url, "https://t.me/my_shop_bot")
        self.assertEqual(len(base), 1)  # input not mutated
        with clear():
            self.assertEqual(len(sl.with_ai_products_button(base).inline_keyboard), 1)


class WelcomeKeyboardsTests(unittest.IsolatedAsyncioTestCase):
    BUILDERS = ("build_buyvip_keyboard", "build_vip_script_keyboard", "build_free_script_keyboard",
                "build_pc_tool_keyboard", "build_all_scripts_keyboard")

    async def test_every_buy_vip_keyboard_gets_the_button_next_to_buy_vip(self):
        with env("my_shop_bot"):
            for name in self.BUILDERS:
                buttons = flat(await getattr(mh, name)(None))
                self.assertIn("BUY VIP NOW", [b.text for b in buttons], name)
                self.assertEqual([b.url for b in buttons if b.text.startswith("Mua AI Products")],
                                 ["https://t.me/my_shop_bot"], name)
            welcome = flat(await mh.build_welcome_keyboard(None))
            self.assertEqual(sum(b.text.startswith("Mua AI Products") for b in welcome), 1)

    async def test_without_env_keyboards_are_unchanged(self):
        with clear():
            for name in self.BUILDERS:
                buttons = flat(await getattr(mh, name)(None))
                self.assertFalse([b for b in buttons if "AI Products" in b.text], name)
                self.assertTrue(all(b.url for b in buttons), name)  # no empty / fake URL
            self.assertFalse([b for b in flat(await mh.build_welcome_keyboard(None)) if "AI Products" in b.text])


if __name__ == "__main__":
    unittest.main()
