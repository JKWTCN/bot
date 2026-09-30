import asyncio
from unittest.mock import patch
import struct
import unittest

from function.ranking_render import (
    RankingRenderer, _emoji_svg, build_ranking_html,
)


def sample(names):
    return {"排名": list(range(1, len(names) + 1)), "昵称": names,
            "QQ": [100001 + i for i in range(len(names))],
            "今日次数": [100 - i for i in range(len(names))]}


def html(data):
    return build_ranking_html(data, "水群排名", "排名", "今日次数", "今日发言榜")


class RankingHTMLTests(unittest.TestCase):
    def test_untrusted_names_are_text_and_sequences_are_preserved(self):
        result = html(sample(['<img src="https://example.com">', "☁️👍🏽👨‍👩‍👧‍👦🇨🇳"]))
        self.assertIn('&lt;img src=&quot;https://example.com&quot;&gt;', result)
        self.assertNotIn('<img src="https://example.com">', result)
        self.assertIn("☁️👍🏽👨‍👩‍👧‍👦🇨🇳", result)


class RankingScreenshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_screenshots_browser_reuse_and_cleanup(self):
        renderer = RankingRenderer()
        try:
            with patch("function.ranking_render._emoji_svg", wraps=_emoji_svg) as assets:
                first = await renderer.render(html(sample(["云 ☁️", "👍🏽👨‍👩‍👧‍👦🇨🇳"])))
                requested = {call.args[0] for call in assets.call_args_list}
                self.assertTrue({"2601", "1f44d-1f3fd", "1f468-200d-1f469-200d-1f467-200d-1f466", "1f1e8-1f1f3"} <= requested)
            browser = renderer._browser
            empty, full = await asyncio.gather(
                renderer.render(html(sample([]))),
                renderer.render(html(sample(["很长的昵称" * 8] * 20))),
            )
            self.assertIs(renderer._browser, browser)
            heights = []
            for png in (first, empty, full):
                self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
                width, height = struct.unpack(">II", png[16:24])
                self.assertEqual(width, 1760)
                heights.append(height)
            self.assertGreater(heights[2], heights[0])
            self.assertGreater(heights[0], heights[1])
            self.assertEqual(browser.contexts, [])
        finally:
            await renderer.close()
        self.assertIsNone(renderer._browser)
        self.assertIsNone(renderer._playwright)


if __name__ == "__main__":
    unittest.main()
