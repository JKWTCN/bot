"""Verify provider switches without contacting AI services or loading bot databases."""
import ast
import asyncio
import json
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from config import ai_control
from config.ollama_control import ollama_chat, ollama_enabled


class AIControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Path(self.directory.name) / 'setting.json'
        self.patcher = patch.object(ai_control, 'SETTING_PATH', self.settings)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def configure(self, **values):
        self.settings.write_text(json.dumps(values))

    def client(self):
        path = Path(__file__).resolve().parents[1] / 'intelligence/chat/llm_client.py'
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ChatLLMClient')
        namespace = dict(asyncio=asyncio, logging=logging)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec',
                     flags=__import__('__future__').annotations.compiler_flag), namespace)
        return namespace['ChatLLMClient'](types.SimpleNamespace(enable_cloud_fallback=True))

    def test_master_switch_blocks_ollama_even_when_local_enabled(self):
        self.configure(use_ai=False, use_local_ai=True)
        call = Mock()
        with patch.dict(sys.modules, {'ollama': types.SimpleNamespace(chat=call)}):
            with self.assertRaises(ai_control.AIDisabledError):
                ollama_chat(model='test')
        call.assert_not_called()

    def test_master_switch_blocks_both_provider_routes(self):
        self.configure(use_ai=False, use_local_ai=True)
        client = self.client()
        client._generate_ollama = AsyncMock()
        client._generate_openai_compatible = AsyncMock()
        with self.assertRaises(ai_control.AIDisabledError):
            asyncio.run(client.generate([]))
        client._generate_ollama.assert_not_called()
        client._generate_openai_compatible.assert_not_called()

    def test_direct_cloud_entry_is_also_guarded(self):
        self.configure(use_ai=False)
        with self.assertRaises(ai_control.AIDisabledError):
            asyncio.run(self.client()._generate_openai_compatible([], temperature=0.2, max_tokens=10))

    def test_local_switch_allows_configured_cloud_route(self):
        self.configure(use_ai=True, use_local_ai=False)
        client = self.client()
        client._generate_ollama = AsyncMock()
        client._generate_openai_compatible = AsyncMock(return_value='cloud reply')
        self.assertEqual(asyncio.run(client.generate([])), 'cloud reply')
        client._generate_ollama.assert_not_called()

    def test_disabled_features_return_without_sending_or_processing(self):
        targets = [
            ('application/chat_application.py', '_process_chat'),
            ('application/summary_application.py', 'process'),
            ('application/emoji_application.py', 'process'),
            ('application/classic_application.py', 'process'),
            ('application/miao_miao_translation.py', 'miaomiaoTranslation'),
            ('function/group_operation.py', 'replyImageMessage'),
        ]
        root = Path(__file__).resolve().parents[1]
        for filename, name in targets:
            with self.subTest(filename=filename):
                tree = ast.parse((root / filename).read_text())
                if filename.endswith('classic_application.py'):
                    tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PrivateChatApplication')
                elif filename.endswith('emoji_application.py'):
                    tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EmojiSendApplication')
                node = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
                namespace = {'ai_enabled': lambda: False}
                exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec',
                             flags=__import__('__future__').annotations.compiler_flag), namespace)
                # No dependencies are supplied: touching any processing/sending path fails.
                args = [object()] * len(node.args.args)
                self.assertIsNone(asyncio.run(namespace[name](*args)))

    def test_live_toggle_and_unreadable_settings(self):
        self.configure(use_ai=True, use_local_ai=True)
        self.assertTrue(ollama_enabled())
        self.configure(use_ai=False, use_local_ai=True)
        self.assertFalse(ollama_enabled())
        self.configure(use_ai=True, use_local_ai=True)
        call = Mock(return_value='ok')
        with patch.dict(sys.modules, {'ollama': types.SimpleNamespace(chat=call)}):
            self.assertEqual(ollama_chat(model='test'), 'ok')
        self.settings.write_text('{')
        self.assertFalse(ai_control.ai_enabled())
        self.settings.unlink()
        self.assertFalse(ai_control.ai_enabled())


if __name__ == '__main__':
    unittest.main()
