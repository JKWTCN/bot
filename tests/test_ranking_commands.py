"""Exercise the registered ranking code without importing unrelated bot services."""
import ast
import base64
from datetime import datetime, timedelta
import json
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parent.parent


def ranking_namespace():
    # Execute the actual entry-point definitions, isolated from module-level imports
    # that otherwise load external services and the production database.
    source = ast.parse((ROOT / 'application/classic_application.py').read_text())
    names = {
        'ShowTableByBase64', 'ShowRankingByBase64', 'GetLifeChatRecord',
        'GetNowChatRecord', 'GetPeriodStartTimestamp', 'GetPeriodChatRecord',
        'GetYearChatRecord', 'GetQuarterChatRecord', 'GetMonthChatRecord',
        'GetWeekChatRecord', 'ranking_point_payload', 'RankingApplication',
    }
    nodes = [n for n in source.body if getattr(n, 'name', None) in names]
    connection = MagicMock()
    connection.cursor.return_value.fetchall.return_value = [(100001, 123)]
    renderer = AsyncMock(return_value=b'UE5H')
    namespace = {
        'datetime': datetime, 'timedelta': timedelta, 'time': time, 'json': json,
        'sqlite3': SimpleNamespace(connect=MagicMock(return_value=connection)),
        'GroupMessageApplication': object, 'GroupMessageInfo': object,
        'render_ranking_base64': renderer, 'GetNowDay': lambda: '2026-09-30',
        'get_user_name': lambda user, group: '云朵 ☁️',
        'HasAllKeyWords': lambda text, keys: all(key in text for key in keys),
        'find_points_ranking': lambda: (True, [SimpleNamespace(user_id=100001, point=123)]),
        'IsInGroup': lambda user, group: True,
        'get_user_info': lambda user, group: (True, SimpleNamespace(card='云朵 ☁️', nickname='用户')),
        'find_value': lambda kind, group: (False, None),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'application/classic_application.py'), 'exec'), namespace)
    return namespace, connection, renderer


class RegisteredRankingCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_registered_ranking_commands_await_html_renderer(self):
        self.assertIn('RegisterApplication(classic_application.RankingApplication())',
                      (ROOT / 'registered_application_list.py').read_text())
        cases = [
            ('乐可水群排名', '今日次数', '水群排名'),
            ('乐可生涯水群排名', '生涯次数', '水群排名'),
            ('乐可本年水群排名', '本年次数', '本年水群排名'),
            ('乐可本季度水群排名', '本季度次数', '本季度水群排名'),
            ('乐可本季水群排名', '本季度次数', '本季度水群排名'),
            ('乐可本月水群排名', '本月次数', '本月水群排名'),
            ('乐可本周水群排名', '本周次数', '本周水群排名'),
            ('乐可排名', '值', '积分排名'),
        ]
        for command, value_key, title in cases:
            with self.subTest(command=command):
                namespace, connection, renderer = ranking_namespace()
                app = namespace['RankingApplication'].__new__(namespace['RankingApplication'])
                websocket = SimpleNamespace(send=AsyncMock())
                message = SimpleNamespace(plainTextMessage=command, groupId=123, websocket=websocket)
                await app.process(message)
                renderer.assert_awaited_once()
                self.assertEqual(renderer.call_args.kwargs['value_column'], value_key)
                self.assertEqual(renderer.call_args.kwargs['title'], title)
                self.assertEqual(renderer.call_args.args[0]['昵称'], ['云朵 ☁️'])
                if value_key not in ('今日次数', '生涯次数', '值'):
                    self.assertIn('统计时间:', renderer.call_args.kwargs['subtitle'])
                websocket.send.assert_awaited_once()
                payload = json.loads(websocket.send.call_args.args[0])
                self.assertEqual(payload['params']['message'][0]['data']['file'], 'base64://UE5H')
                if value_key != '值':
                    connection.close.assert_called_once()

    async def test_actual_water_command_generates_png(self):
        from function.ranking_render import RankingRenderer, build_ranking_html
        browser = RankingRenderer()
        async def render(data, **kwargs):
            return base64.b64encode(await browser.render(build_ranking_html(data, **kwargs)))
        try:
            for command in ["水群排名", "本月水群排名", "排名"]:
                namespace, _, _ = ranking_namespace()
                namespace["render_ranking_base64"] = render
                app = namespace["RankingApplication"].__new__(namespace["RankingApplication"])
                websocket = SimpleNamespace(send=AsyncMock())
                await app.process(SimpleNamespace(plainTextMessage=command, groupId=123, websocket=websocket))
                payload = json.loads(websocket.send.call_args.args[0])
                image = payload["params"]["message"][0]["data"]["file"]
                self.assertTrue(image.startswith("base64://"))
                self.assertEqual(base64.b64decode(image.removeprefix("base64://"))[:8], b"\x89PNG\r\n\x1a\n")
        finally:
            await browser.close()

    async def test_empty_actual_chat_entry_points_send_empty_card(self):
        for command in ['水群排名', '生涯水群排名', '本周水群排名']:
            with self.subTest(command=command):
                namespace, connection, renderer = ranking_namespace()
                connection.cursor.return_value.fetchall.return_value = []
                app = namespace['RankingApplication'].__new__(namespace['RankingApplication'])
                websocket = SimpleNamespace(send=AsyncMock())
                await app.process(SimpleNamespace(plainTextMessage=command, groupId=123, websocket=websocket))
                renderer.assert_awaited_once()
                self.assertEqual(renderer.call_args.args[0]['昵称'], [])
                websocket.send.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
