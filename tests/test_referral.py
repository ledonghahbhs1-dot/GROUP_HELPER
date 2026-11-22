"""Task 102: referral links + manual group events. No real Telegram, SQLite in a temp dir."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramAPIError

import handlers.referral_handlers as rh
from database.referral import ReferralStore

BOT_ID = 4242
ADMIN = 900001
CHAT = -100123
REFERRER = 11
GUEST = 22
GUEST2 = 33


class Clock:
    def __init__(self, start=1_700_000_000):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, minutes):
        self.t += int(minutes * 60)


def api_error(text="boom"):
    return TelegramAPIError(method=MagicMock(), message=text)


def make_bot(**overrides):
    bot = SimpleNamespace(
        id=BOT_ID,
        create_chat_invite_link=AsyncMock(return_value=SimpleNamespace(invite_link="https://t.me/+abcDEF123")),
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        pin_chat_message=AsyncMock(),
        unpin_chat_message=AsyncMock(),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
    for key, value in overrides.items():
        setattr(bot, key, value)
    return bot


def link(name, creator_id=BOT_ID):
    return SimpleNamespace(name=name, creator=SimpleNamespace(id=creator_id), invite_link="https://t.me/+x")


def join_event(member_id=GUEST, invite_link=None, is_bot=False, chat_type="supergroup"):
    return SimpleNamespace(chat=SimpleNamespace(id=CHAT, type=chat_type, title="G"), invite_link=invite_link,
                           new_chat_member=SimpleNamespace(user=SimpleNamespace(id=member_id, is_bot=is_bot)))


def gone_event(member_id=GUEST):
    return SimpleNamespace(chat=SimpleNamespace(id=CHAT, type="supergroup"),
                           new_chat_member=SimpleNamespace(user=SimpleNamespace(id=member_id)))


def message(user_id, chat_type="supergroup", sender_chat=None):
    return SimpleNamespace(
        chat=SimpleNamespace(id=CHAT, type=chat_type), from_user=SimpleNamespace(id=user_id, is_bot=False),
        sender_chat=sender_chat, reply=AsyncMock())


class StoreCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.clock = Clock()
        self.store = ReferralStore(database=SimpleNamespace(db_path=str(Path(self.dir.name) / "t.db")), clock=self.clock)
        await self.store.ensure_schema()
        for target in (patch.object(rh, "referral_store", self.store),
                       patch.object(rh, "_display_name", AsyncMock(return_value="Nguyen")),
                       patch.object(rh.config, "REFERRAL_CONFIRM_MINUTES", 10),
                       patch.object(rh.config, "REFERRAL_MILESTONES", [2, 3]),
                       patch.object(rh.config, "REFERRAL_ADMIN_IDS", [ADMIN])):
            target.start()
            self.addCleanup(target.stop)

    async def join(self, bot, member_id=GUEST, referrer=REFERRER):
        return await rh.on_member_joined(bot, join_event(member_id, link(f"ref:{referrer}")), self.store)


class PureHelperTests(unittest.TestCase):
    def test_referrer_from_invite_link_requires_our_name_and_creator(self):
        self.assertEqual(rh.referrer_from_invite_link(link("ref:123"), BOT_ID), 123)
        self.assertIsNone(rh.referrer_from_invite_link(link("ref:123", creator_id=1), BOT_ID))  # admin-made look-alike
        for bad in ("ref:abc", "ref:", "REF:1", "xref:1", "ref:0", "ref:1234567890123456", "", None):
            self.assertIsNone(rh.referrer_from_invite_link(link(bad), BOT_ID), bad)
        self.assertIsNone(rh.referrer_from_invite_link(None, BOT_ID))
        self.assertIsNone(rh.referrer_from_invite_link(SimpleNamespace(name="ref:1", creator=None), BOT_ID))

    def test_parse_event_args(self):
        self.assertEqual(rh.parse_event_args("2h Giảm giá VIP"), (7200, True, "Giảm giá VIP"))
        self.assertEqual(rh.parse_event_args("nopin 30m x"), (1800, False, "x"))
        self.assertEqual(rh.parse_event_args("1d nopin hi"), (86400, False, "hi"))
        self.assertEqual(rh.parse_event_args("không thời gian 2h"), (None, True, "không thời gian 2h"))
        self.assertEqual(rh.parse_event_args("2h dòng 1\ndòng 2"), (7200, True, "dòng 1\ndòng 2"))
        for bad in ("", "   ", "2h", "nopin", "99999d x", "0m x", "x" * (rh.MAX_EVENT_TEXT + 1)):
            with self.assertRaises(ValueError, msg=bad[:20]):
                rh.parse_event_args(bad)


class ReferralLinkTests(StoreCase):
    async def test_creates_link_named_ref_userid_and_stores_it(self):
        bot = make_bot()
        url = await rh.get_or_create_link(bot, CHAT, REFERRER, self.store)
        self.assertEqual(url, "https://t.me/+abcDEF123")
        bot.create_chat_invite_link.assert_awaited_once_with(chat_id=CHAT, name=f"ref:{REFERRER}")
        saved = await self.store.get_link(CHAT, REFERRER)
        self.assertEqual((saved["invite_link"], saved["name"]), (url, f"ref:{REFERRER}"))

    async def test_same_user_reuses_the_link(self):
        bot = make_bot()
        first = await rh.get_or_create_link(bot, CHAT, REFERRER, self.store)
        second = await rh.get_or_create_link(bot, CHAT, REFERRER, self.store)
        self.assertEqual(first, second)
        self.assertEqual(bot.create_chat_invite_link.await_count, 1)

    async def test_telegram_refusal_returns_none(self):
        bot = make_bot(create_chat_invite_link=AsyncMock(side_effect=api_error("not enough rights")))
        self.assertIsNone(await rh.get_or_create_link(bot, CHAT, REFERRER, self.store))
        self.assertIsNone(await self.store.get_link(CHAT, REFERRER))

    async def test_invite_command_replies_with_link_in_group_and_refuses_private(self):
        bot = make_bot()
        msg = message(REFERRER)
        await rh.cmd_invite(msg, bot)
        self.assertIn("https://t.me/+abcDEF123", msg.reply.await_args.args[0])
        private = message(REFERRER, chat_type="private")
        await rh.cmd_invite(private, bot)
        self.assertIn("trong nhóm", private.reply.await_args.args[0])
        self.assertEqual(bot.create_chat_invite_link.await_count, 1)

    async def test_invite_command_refuses_anonymous_admin_and_reports_missing_right(self):
        bot = make_bot()
        anonymous = message(rh.ANONYMOUS_ADMIN_BOT_ID)
        await rh.cmd_invite(anonymous, bot)
        bot.create_chat_invite_link.assert_not_awaited()
        denied = make_bot(create_chat_invite_link=AsyncMock(side_effect=api_error()))
        msg = message(REFERRER)
        await rh.cmd_invite(msg, denied)
        self.assertIn("quyền", msg.reply.await_args.args[0])


class ReferralCountTests(StoreCase):
    async def test_join_via_our_link_is_pending_not_counted_yet(self):
        bot = make_bot()
        self.assertTrue(await self.join(bot))
        self.assertEqual(await self.store.get_counts(CHAT, REFERRER), {"confirmed": 0, "pending": 1})
        self.clock.advance(5)
        self.assertEqual(await rh.process_due_referrals(bot, self.store), {"confirmed": 0, "revoked": 0, "retry": 0})
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 0)

    async def test_member_who_stays_is_counted_once_after_the_window(self):
        bot = make_bot()
        await self.join(bot)
        self.clock.advance(11)
        self.assertEqual((await rh.process_due_referrals(bot, self.store))["confirmed"], 1)
        self.assertEqual(await self.store.get_counts(CHAT, REFERRER), {"confirmed": 1, "pending": 0})
        self.assertEqual((await rh.process_due_referrals(bot, self.store))["confirmed"], 0)  # not counted twice
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 1)

    async def test_confirm_join_cannot_double_count(self):
        await self.join(make_bot())
        self.assertEqual(await self.store.confirm_join(CHAT, GUEST), 1)
        self.assertIsNone(await self.store.confirm_join(CHAT, GUEST))
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 1)

    async def test_leaving_before_the_window_never_counts(self):
        bot = make_bot()
        await self.join(bot)
        self.clock.advance(3)
        self.assertEqual(await rh.handle_member_gone(bot, gone_event(), self.store), "revoked")
        self.clock.advance(30)
        await rh.process_due_referrals(bot, self.store)
        self.assertEqual(await self.store.get_counts(CHAT, REFERRER), {"confirmed": 0, "pending": 0})
        self.assertEqual((await self.store.get_join(CHAT, GUEST))["status"], "revoked")

    async def test_kicked_member_found_missing_at_check_time_is_revoked(self):
        bot = make_bot(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="kicked")))
        await self.join(bot)
        self.clock.advance(11)
        self.assertEqual((await rh.process_due_referrals(bot, self.store))["revoked"], 1)
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 0)

    async def test_leaving_after_the_window_keeps_the_point(self):
        bot = make_bot()
        await self.join(bot)
        self.clock.advance(15)
        self.assertEqual(await rh.handle_member_gone(bot, gone_event(), self.store), "confirmed")
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 1)
        self.assertEqual(await rh.handle_member_gone(bot, gone_event(), self.store), "ignored")

    async def test_revoking_a_confirmed_join_takes_the_point_back_but_never_below_zero(self):
        await self.join(make_bot())
        await self.store.confirm_join(CHAT, GUEST)
        self.assertTrue(await self.store.revoke_join(CHAT, GUEST))
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 0)
        self.assertFalse(await self.store.revoke_join(CHAT, GUEST))
        self.assertEqual((await self.store.get_counts(CHAT, REFERRER))["confirmed"], 0)

    async def test_fraud_cases_are_not_recorded(self):
        bot = make_bot()
        self.assertFalse(await rh.on_member_joined(bot, join_event(GUEST, link("ref:11", creator_id=1)), self.store))  # forged name
        self.assertFalse(await rh.on_member_joined(bot, join_event(GUEST, link("hello")), self.store))
        self.assertFalse(await rh.on_member_joined(bot, join_event(GUEST, None), self.store))
        self.assertFalse(await rh.on_member_joined(bot, join_event(REFERRER, link(f"ref:{REFERRER}")), self.store))  # self-invite
        self.assertFalse(await rh.on_member_joined(bot, join_event(GUEST, link("ref:11"), is_bot=True), self.store))
        self.assertFalse(await rh.on_member_joined(bot, join_event(GUEST, link("ref:11"), chat_type="private"), self.store))
        self.assertTrue(await self.join(bot))
        self.assertFalse(await self.join(bot, referrer=44))  # same member again (even via someone else) is not credited twice
        self.assertEqual((await self.store.get_join(CHAT, GUEST))["referrer_id"], REFERRER)

    async def test_stale_unresolvable_pending_is_dropped(self):
        bot = make_bot(get_chat_member=AsyncMock(side_effect=api_error()))
        await self.join(bot)
        self.clock.advance(11)
        self.assertEqual((await rh.process_due_referrals(bot, self.store))["retry"], 1)
        self.clock.advance(25 * 60)
        self.assertEqual((await rh.process_due_referrals(bot, self.store))["revoked"], 1)

    async def test_my_referrals_command_shows_count_and_remaining(self):
        bot = make_bot()
        await self.join(bot)
        await self.store.confirm_join(CHAT, GUEST)
        await self.join(bot, GUEST2)
        msg = message(REFERRER)
        await rh.cmd_my_referrals(msg, bot)
        text = msg.reply.await_args.args[0]
        self.assertIn("1 thành công", text)
        self.assertIn("còn thiếu 1", text)  # next milestone is 2
        self.assertIn("Đang chờ xác nhận: 1", text)


class MilestoneTests(StoreCase):
    async def confirm(self, bot, member_id):
        await self.join(bot, member_id)
        return await rh.confirm_and_announce(bot, CHAT, member_id, self.store)

    async def test_milestone_announced_once_to_group_and_admin_only(self):
        bot = make_bot()
        await self.confirm(bot, 101)
        bot.send_message.assert_not_awaited()  # 1 < first milestone (2)
        await self.confirm(bot, 102)  # reaches 2
        targets = [call.args[0] for call in bot.send_message.await_args_list]
        self.assertEqual(sorted(targets), sorted([CHAT, ADMIN]))
        group_text = next(c.args[1] for c in bot.send_message.await_args_list if c.args[0] == CHAT)
        self.assertIn(f"tg://user?id={REFERRER}", group_text)
        self.assertIn("<b>2</b>", group_text)
        admin_text = next(c.args[1] for c in bot.send_message.await_args_list if c.args[0] == ADMIN)
        self.assertIn("KHÔNG tự cấp", admin_text)
        sent_after_two = bot.send_message.await_count
        # the same member again, and a re-run, must not announce 2 again
        self.assertIsNone(await rh.confirm_and_announce(bot, CHAT, 102, self.store))
        self.assertEqual(bot.send_message.await_count, sent_after_two)
        await self.confirm(bot, 103)  # milestone 3 is a new one -> announced once more
        self.assertEqual(bot.send_message.await_count, sent_after_two + 2)
        await self.confirm(bot, 104)  # 4: nothing new
        self.assertEqual(bot.send_message.await_count, sent_after_two + 2)

    async def test_claim_milestone_is_true_exactly_once(self):
        self.assertTrue(await self.store.claim_milestone(CHAT, REFERRER, 5))
        self.assertFalse(await self.store.claim_milestone(CHAT, REFERRER, 5))
        self.assertTrue(await self.store.claim_milestone(CHAT, REFERRER, 10))
        self.assertTrue(await self.store.claim_milestone(CHAT, 99, 5))

    async def test_failed_send_does_not_break_or_repeat(self):
        bot = make_bot(send_message=AsyncMock(side_effect=api_error()))
        await self.confirm(bot, 101)
        await self.confirm(bot, 102)  # must not raise
        calls = bot.send_message.await_count
        await self.confirm(bot, 103)
        self.assertEqual(bot.send_message.await_count, calls + 2)  # only milestone 3's two sends


class EventTests(StoreCase):
    async def test_non_admin_cannot_post_or_cancel_events(self):
        bot = make_bot()
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=False)):
            msg = message(REFERRER)
            await rh.cmd_event(msg, SimpleNamespace(args="2h Sale lớn"), bot)
            self.assertIn("Chỉ admin", msg.reply.await_args.args[0])
            bot.send_message.assert_not_awaited()
            bot.pin_chat_message.assert_not_awaited()
            cancel = message(REFERRER)
            await rh.cmd_cancel_event(cancel, SimpleNamespace(args="1"), bot)
            self.assertIn("Chỉ admin", cancel.reply.await_args.args[0])
        self.assertEqual(await self.store.active_events(CHAT), [])

    async def test_admin_posts_pins_and_stores_event(self):
        bot = make_bot()
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            msg = message(ADMIN)
            await rh.cmd_event(msg, SimpleNamespace(args="2h Sale <b>lớn</b>"), bot)
        sent_text = bot.send_message.await_args.args[1]
        self.assertIn("SỰ KIỆN", sent_text)
        self.assertIn("&lt;b&gt;lớn&lt;/b&gt;", sent_text)  # admin text is escaped, no HTML injection
        self.assertIn("Kết thúc", sent_text)
        bot.pin_chat_message.assert_awaited_once_with(CHAT, 777, disable_notification=False)
        events = await self.store.active_events(CHAT)
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["pinned"], events[0]["message_id"], events[0]["created_by"]), (1, 777, ADMIN))
        self.assertEqual(events[0]["ends_at"], self.clock() + 7200)

    async def test_nopin_and_pin_failure_are_handled(self):
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            bot = make_bot()
            await rh.cmd_event(message(ADMIN), SimpleNamespace(args="nopin Thông báo"), bot)
            bot.pin_chat_message.assert_not_awaited()
            failing = make_bot(pin_chat_message=AsyncMock(side_effect=api_error()))
            msg = message(ADMIN)
            await rh.cmd_event(msg, SimpleNamespace(args="Thông báo 2"), failing)
            self.assertIn("ghim", msg.reply.await_args.args[0])
        self.assertEqual([e["pinned"] for e in await self.store.active_events(CHAT)], [0, 0])

    async def test_bad_arguments_post_nothing(self):
        bot = make_bot()
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            msg = message(ADMIN)
            await rh.cmd_event(msg, SimpleNamespace(args=""), bot)
            self.assertIn("Cú pháp", msg.reply.await_args.args[0])
            private = message(ADMIN, chat_type="private")
            await rh.cmd_event(private, SimpleNamespace(args="hi"), bot)
        bot.send_message.assert_not_awaited()

    async def test_list_shows_active_events_to_anyone(self):
        await self.store.add_event(CHAT, "Sale A", ADMIN, 1, True, None)
        await self.store.add_event(-999, "Other chat", ADMIN, 2, False, None)
        msg = message(REFERRER)
        await rh.cmd_event_list(msg)
        text = msg.reply.await_args.args[0]
        self.assertIn("Sale A", text)
        self.assertNotIn("Other chat", text)
        empty_store = ReferralStore(database=SimpleNamespace(db_path=str(Path(self.dir.name) / "e.db")))
        await empty_store.ensure_schema()
        empty = message(REFERRER)
        with patch.object(rh, "referral_store", empty_store):
            await rh.cmd_event_list(empty)
        self.assertIn("không có sự kiện", empty.reply.await_args.args[0])

    async def test_admin_cancels_and_unpins(self):
        bot = make_bot()
        event_id = await self.store.add_event(CHAT, "Sale", ADMIN, 55, True, None)
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            msg = message(ADMIN)
            await rh.cmd_cancel_event(msg, SimpleNamespace(args=str(event_id)), bot)
            again = message(ADMIN)
            await rh.cmd_cancel_event(again, SimpleNamespace(args=str(event_id)), bot)
        bot.unpin_chat_message.assert_awaited_once_with(CHAT, 55)
        self.assertEqual(await self.store.active_events(CHAT), [])
        self.assertIn("Đã hủy", msg.reply.await_args.args[0])
        self.assertIn("Không tìm thấy", again.reply.await_args.args[0])

    async def test_cancel_without_id_needs_exactly_one_active_event(self):
        bot = make_bot()
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            msg = message(ADMIN)
            await rh.cmd_cancel_event(msg, SimpleNamespace(args=""), bot)
            self.assertIn("nhiều sự kiện", msg.reply.await_args.args[0])  # none or several -> ask for a number
            await self.store.add_event(CHAT, "A", ADMIN, 1, False, None)
            only = message(ADMIN)
            await rh.cmd_cancel_event(only, SimpleNamespace(args=""), bot)
            self.assertIn("Đã hủy", only.reply.await_args.args[0])
            bad = message(ADMIN)
            await rh.cmd_cancel_event(bad, SimpleNamespace(args="abc"), bot)
            self.assertIn("Cú pháp", bad.reply.await_args.args[0])

    async def test_cannot_cancel_an_event_of_another_chat(self):
        other = await self.store.add_event(-999, "Other", ADMIN, 1, False, None)
        with patch.object(rh, "is_admin_or_owner", AsyncMock(return_value=True)):
            msg = message(ADMIN)
            await rh.cmd_cancel_event(msg, SimpleNamespace(args=str(other)), make_bot())
        self.assertIn("Không tìm thấy", msg.reply.await_args.args[0])
        self.assertEqual(len(await self.store.active_events(-999)), 1)

    async def test_timed_event_ends_unpins_and_announces_once(self):
        bot = make_bot()
        await self.store.add_event(CHAT, "Sale", ADMIN, 66, True, self.clock() + 600)
        self.assertEqual(await rh.expire_events(bot, self.store), 0)
        self.clock.advance(11)
        self.assertEqual(await rh.expire_events(bot, self.store), 1)
        self.assertEqual(await rh.expire_events(bot, self.store), 0)
        bot.unpin_chat_message.assert_awaited_once_with(CHAT, 66)
        self.assertIn("đã kết thúc", bot.send_message.await_args.args[1])
        self.assertEqual(await self.store.active_events(CHAT), [])


if __name__ == "__main__":
    unittest.main()
