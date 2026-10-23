"""Exercise chat routing without importing LLM services or production databases."""
import ast
import asyncio
import json
import logging
import random
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from intelligence.chat_quality.random_chat import RandomChatLimiter, candidate_kind
from intelligence.chat_quality.reply_policy import (
    REPLY_NECESSITY_TRIGGER_SCORE, should_reply_random_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def chat_namespace():
    tree = ast.parse((ROOT / 'application/chat_application.py').read_text())
    nodes = [node for node in tree.body
             if getattr(node, 'name', '') in ('GroupChatApplication', 'load_chat_quality_config')]
    ns = dict(
        Any=object, GroupMessageApplication=object, GroupMessageInfo=object,
        RandomChatLimiter=RandomChatLimiter, candidate_kind=candidate_kind,
        should_reply_random_candidate=should_reply_random_candidate,
        REPLY_NECESSITY_TRIGGER_SCORE=REPLY_NECESSITY_TRIGGER_SCORE,
        random=random, asyncio=asyncio, json=json, logging=logging,
        get_config=lambda key, group: True,
        load_setting=lambda key, default: {'bot_name': '乐可', 'bot_id': 123}.get(key, default),
        handle_group_chat=AsyncMock(return_value=SimpleNamespace(
            should_reply=True, text='回复', emoji_path='', image_path='', target_message_id=None)),
        ReplySay=AsyncMock(), ReplySayTextImage=AsyncMock(),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'application/chat_application.py'), 'exec'), ns)
    app = ns['GroupChatApplication'].__new__(ns['GroupChatApplication'])
    app.random_limiter = RandomChatLimiter()
    return ns, app


def message(text='今天晚上吃什么？', group=765698568, reply=-1, at=None):
    return SimpleNamespace(plainTextMessage=text, groupId=group, senderId=456,
                           messageId=789, atList=at or [], replyMessageId=reply,
                           botId=123, websocket=None)


class CandidateTests(unittest.TestCase):
    def test_question_and_normal(self):
        self.assertEqual(candidate_kind('今天晚上吃什么？'), 'question')
        self.assertEqual(candidate_kind('帮我看看这个问题'), 'question')
        self.assertEqual(candidate_kind('今天晚上吃火锅'), 'normal')

    def test_noise_and_commands(self):
        for text in ('', '哈哈哈', '哈哈哈哈哈！', '[图片]', '[CQ:image,file=x]', '.random_chat.get',
                     '/help', '#天气', '？？？？', 'ChatGPT，帮我看看'):
            with self.subTest(text=text):
                self.assertEqual(candidate_kind(text), '')


class LimiterTests(unittest.TestCase):
    def test_pending_cooldown_window_and_group_isolation(self):
        now = [0.0]
        limiter = RandomChatLimiter(clock=lambda: now[0])
        cfg = {'cooldown_seconds': 90, 'window_seconds': 600, 'max_replies_per_window': 3}
        self.assertTrue(limiter.reserve(1, cfg))
        self.assertFalse(limiter.reserve(1, cfg))
        self.assertTrue(limiter.reserve(2, cfg))
        limiter.finish(1, sent=False)
        self.assertTrue(limiter.reserve(1, cfg))
        limiter.finish(1, sent=True)
        now[0] = 89
        self.assertFalse(limiter.reserve(1, cfg))
        for t in (90, 180):
            now[0] = t
            self.assertTrue(limiter.reserve(1, cfg))
            limiter.finish(1, sent=True)
        now[0] = 599
        self.assertFalse(limiter.reserve(1, cfg))
        now[0] = 600
        self.assertTrue(limiter.reserve(1, cfg))


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_scoped_and_probability_boundaries(self):
        ns, app = chat_namespace()
        self.assertTrue(ns['load_chat_quality_config'](765698568)['random_chat_policy']['enabled'])
        self.assertNotIn('random_chat_policy', ns['load_chat_quality_config'](999))
        for text, draw, expected in (
            ('今天晚上吃什么？', .199, True), ('今天晚上吃什么？', .20, False),
            ('今天晚上吃火锅', .029, True), ('今天晚上吃火锅', .03, False),
        ):
            ns, app = chat_namespace()
            with patch.object(random, 'random', return_value=draw):
                self.assertEqual(app.judge(message(text)), expected)
        with patch.object(random, 'random', return_value=.01):
            self.assertFalse(app.judge(message('帮我看看这个怎么弄？', group=999)))

    async def test_direct_bypasses_random_limit_and_switches(self):
        ns, app = chat_namespace()
        app.random_limiter.pending.add(765698568)
        self.assertTrue(app.judge(message('乐可你好')))
        self.assertTrue(app.judge(message(at=[123])))
        ns['get_config'] = lambda key, group: key != 'enable_chat'
        self.assertFalse(app.judge(message('乐可你好')))
        ns['get_config'] = lambda key, group: key != 'random_chat'
        with patch.object(random, 'random', return_value=0):
            self.assertFalse(app.judge(message()))

    async def test_sent_counts_but_wait_and_failures_release_reservation(self):
        for outcome in ('sent', 'wait', 'error', 'send_error'):
            ns, app = chat_namespace()
            msg = message()
            if outcome == 'wait':
                ns['handle_group_chat'].return_value.should_reply = False
            elif outcome == 'error':
                ns['handle_group_chat'].side_effect = RuntimeError('offline')
            elif outcome == 'send_error':
                ns['ReplySay'].side_effect = RuntimeError('socket closed')
            with patch.object(random, 'random', return_value=0):
                self.assertTrue(app.judge(msg))
                if outcome == 'send_error':
                    with self.assertRaises(RuntimeError):
                        await app.process(msg)
                else:
                    await app.process(msg)
            self.assertNotIn(msg.groupId, app.random_limiter.pending)
            self.assertEqual(len(app.random_limiter.sent[msg.groupId]), int(outcome == 'sent'))
            if outcome == 'error':
                ns['ReplySay'].assert_not_awaited()

    async def test_quote_checks_sender_and_group_before_bypassing_probability(self):
        for sender, group, replies in ((123, 765698568, 1), (456, 765698568, 0), (123, 999, 0)):
            ns, app = chat_namespace()
            msg = message(reply=50)
            fake = types.ModuleType('function.group_operation')
            fake.get_message_data = lambda message_id: {'sender': {'user_id': sender}, 'group_id': group}
            with patch.dict(sys.modules, {'function.group_operation': fake}), patch.object(random, 'random', return_value=1):
                self.assertTrue(app.judge(msg))
                await app.process(msg)
            self.assertEqual(ns['handle_group_chat'].await_count, replies)
            self.assertNotIn(msg.groupId, app.random_limiter.pending)


if __name__ == '__main__':
    unittest.main()
