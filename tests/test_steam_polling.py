"""Validate polling without importing bot services or touching live databases/APIs."""
import ast
import asyncio
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock

SOURCE = Path(__file__).resolve().parents[1] / 'application/steam_status_application.py'


def namespace(settings=None):
    settings = settings or {}
    names = {
        '_get_smart_intervals', '_get_fixed_interval', '_get_poll_mode',
        '_get_retry_times', 'calc_next_poll_interval_sec',
        'calc_poll_budget_interval', 'get_active_steam_bindings',
        'SteamStatusPushApplication',
    }
    nodes = [node for node in ast.parse(SOURCE.read_text()).body
             if getattr(node, 'name', None) in names]
    ns = {
        'asyncio': asyncio, 'json': json, 'math': math,
        'time': SimpleNamespace(time=lambda: 10000),
        'requests': SimpleNamespace(post=MagicMock()),
        'GetNCHSPort': lambda: 27433,
        'load_static_setting': lambda name, default: settings.get(name, default),
        'update_steam_status': MagicMock(), 'update_binding_extra': MagicMock(),
        'reset_steam_tracking': MagicMock(),
        'MetaMessageApplication': object, 'MetaMessageInfo': object,
        'get_all_steam_bindings': MagicMock(return_value=[]),
        'get_steam_status_async': AsyncMock(return_value=[]),
        'get_config': lambda *args: False,
        'clear_achievement_snapshot': MagicMock(),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


def binding(user=1, group=10, steam='s1', pending=0, due=0):
    return (user, group, steam, '{}', 0, 100, '123', pending, due, 0)


def response(data=None, **overrides):
    payload = {'status': 'ok', 'retcode': 0, 'data': data}
    payload.update(overrides)
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)


class MembershipTests(unittest.TestCase):
    def test_bot_and_user_must_both_be_in_group(self):
        ns = namespace()
        post = ns['requests'].post
        post.side_effect = [response([{'group_id': 10}]), response([{'user_id': 1}])]
        live = binding()
        result = ns['get_active_steam_bindings']([live, binding(user=2), binding(group=20)])
        self.assertEqual(result, [live])
        self.assertEqual(post.call_count, 2)  # Shared group queried once; absent group never queried.
        self.assertEqual(post.call_args.kwargs['json'], {'group_id': 10, 'no_cache': True})
        self.assertEqual(ns['reset_steam_tracking'].call_count, 2)

    def test_failed_group_lookup_preserves_binding_and_skips_everything(self):
        for payload in [response(None), response([], retcode=1), response([], status='failed')]:
            ns = namespace()
            ns['requests'].post.return_value = payload
            self.assertEqual(ns['get_active_steam_bindings']([binding()]), [])
            ns['reset_steam_tracking'].assert_not_called()

    def test_member_failure_does_not_block_other_groups(self):
        ns = namespace()
        ns['requests'].post.side_effect = [
            response([{'group_id': 10}, {'group_id': 20}]),
            TimeoutError('unavailable'), response([{'user_id': 1}]),
        ]
        valid = binding(group=20)
        self.assertEqual(ns['get_active_steam_bindings']([binding(), valid]), [valid])
        ns['reset_steam_tracking'].assert_not_called()


class TrackingResetTests(unittest.TestCase):
    def test_reset_preserves_binding_and_only_clears_its_snapshots(self):
        import sqlite3
        import tempfile
        from contextlib import closing
        nodes = [node for node in ast.parse(SOURCE.read_text()).body
                 if getattr(node, 'name', None) in {
                     'create_steam_binding_table', 'bind_steam_id', 'reset_steam_tracking',
                 }]
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / 'steam.db')
            ns = {'sqlite3': sqlite3, 'closing': closing, 'DB_PATH': db_path,
                  'os': SimpleNamespace(makedirs=MagicMock())}
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
            ns['create_steam_binding_table']()
            ns['bind_steam_id'](1, 10, 's1')
            ns['bind_steam_id'](2, 10, 's2')
            with closing(sqlite3.connect(db_path)) as conn, conn:
                conn.execute("UPDATE steam_binding SET last_status='{}', pending_quit=1")
                conn.executemany(
                    "INSERT INTO steam_achievement_snapshot (user_id, group_id, appid) VALUES (?, ?, ?)",
                    [(1, 10, '123'), (1, 10, '456'), (2, 10, '123')],
                )
            ns['reset_steam_tracking'](1, 10)
            with closing(sqlite3.connect(db_path)) as conn:
                self.assertEqual(conn.execute(
                    "SELECT steam_id, last_status, pending_quit FROM steam_binding ORDER BY user_id"
                ).fetchall(), [('s1', None, 0), ('s2', '{}', 1)])
                self.assertEqual(conn.execute(
                    "SELECT user_id FROM steam_achievement_snapshot"
                ).fetchall(), [(2,)])


class IntervalTests(unittest.TestCase):
    def test_five_second_minimum_and_defaults(self):
        ns = namespace()
        self.assertEqual(ns['calc_next_poll_interval_sec']({'gameid': '123'}, 10000), 5)
        self.assertEqual(ns['calc_next_poll_interval_sec']({'status_code': 1}, 10000), 5)
        self.assertEqual(ns['calc_next_poll_interval_sec']({}, 10000), 600)
        ns = namespace({'steam_poll_mode': 'fixed', 'steam_fixed_poll_interval': 1})
        self.assertEqual(ns['calc_next_poll_interval_sec']({}, 0), 5)
        ns = namespace({'steam_smart_poll_intervals': '0,1,2'})
        self.assertEqual(ns['_get_smart_intervals'](), [5, 5, 5, 60, 300, 600])

    def test_budget_grows_with_unique_users_and_reserves_other_requests(self):
        ns = namespace()
        for count, expected in [(1, 5), (100, 5), (101, 7), (1000, 33)]:
            rows = [binding(user=i, steam=str(i)) for i in range(count)]
            interval = ns['calc_poll_budget_interval'](rows + rows)
            self.assertEqual(interval, expected)
            self.assertLessEqual(math.ceil(count / 100) * 86400 * 3 / interval, 80000)


class HeartbeatTests(unittest.IsolatedAsyncioTestCase):
    def make_app(self, ns):
        app = ns['SteamStatusPushApplication'].__new__(ns['SteamStatusPushApplication'])
        app.last_heartbeat_time = 0
        app.heartbeat_throttle = 5
        app._budget_interval = 5
        app._poll_lock = asyncio.Lock()
        return app

    async def test_invalid_bindings_never_trigger_steam_or_pending_quits(self):
        ns = namespace()
        ns['get_all_steam_bindings'].return_value = [binding(pending=1)]
        ns['requests'].post.return_value = response([])
        app = self.make_app(ns)
        app._flush_pending_quits = AsyncMock()
        await app.process(SimpleNamespace())
        ns['get_steam_status_async'].assert_not_awaited()
        app._flush_pending_quits.assert_not_awaited()

    async def test_requests_are_deduplicated_batched_and_then_dispatched(self):
        ns = namespace()
        rows = [binding(user=i, steam=str(i)) for i in range(201)]
        rows.append(binding(user=500, group=20, steam='0'))
        ns['get_all_steam_bindings'].return_value = rows
        ns['get_active_steam_bindings'] = MagicMock(return_value=rows)
        ns['get_steam_status_async'].side_effect = lambda ids: [{'steamid': sid} for sid in ids]
        app = self.make_app(ns)
        app._process_binding = AsyncMock()
        app._flush_pending_quits = AsyncMock()
        await app.process(SimpleNamespace())
        calls = ns['get_steam_status_async'].await_args_list
        self.assertEqual([len(call.args[0]) for call in calls], [100, 100, 1])
        self.assertEqual(app._process_binding.await_count, 202)
        # A second heartbeat inside the five-second window cannot poll again.
        await app.process(SimpleNamespace())
        self.assertEqual(ns['get_steam_status_async'].await_count, 3)

    async def test_pending_quits_are_filtered_even_when_no_status_query_is_due(self):
        ns = namespace()
        rows = [binding(pending=1, due=20000), binding(user=2, pending=1, due=20000)]
        ns['get_all_steam_bindings'].return_value = rows
        ns['get_active_steam_bindings'] = MagicMock(return_value=rows[:1])
        app = self.make_app(ns)
        app._push_end_card = AsyncMock()
        await app.process(SimpleNamespace())
        ns['get_steam_status_async'].assert_not_awaited()
        app._push_end_card.assert_awaited_once()
        self.assertEqual(app._push_end_card.call_args.args[2], 1)

    async def test_first_observation_uses_budget_floor(self):
        ns = namespace()
        app = self.make_app(ns)
        app._budget_interval = 33
        b = dict(user_id=1, group_id=10, steam_id='s1', last_status_json=None,
                 game_start_time=0, last_game_id='', pending_quit=0)
        await app._process_binding(b, {'gameid': '123'}, SimpleNamespace(), 10000)
        self.assertEqual(ns['update_binding_extra'].call_args.kwargs['next_poll_time'], 10033)


if __name__ == '__main__':
    unittest.main()
