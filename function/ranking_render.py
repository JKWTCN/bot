"""Offline HTML ranking cards. One reusable browser, serialized screenshots."""
import asyncio
import base64
from functools import lru_cache
from html import escape
from pathlib import Path
from string import Template
from zipfile import ZipFile

ASSETS = Path(__file__).resolve().parent.parent / "res" / "ranking"


@lru_cache(maxsize=256)
def _emoji_svg(icon: str) -> bytes | None:
    with ZipFile(ASSETS / "twemoji-svg.zip") as archive:
        try:
            return archive.read(f"{icon}.svg")
        except KeyError:
            return None


def build_ranking_html(data: dict, title: str, rank_column: str, value_column: str,
                       subtitle: str = "", unit: str = "次") -> str:
    columns = [data[key] for key in (rank_column, "昵称", "QQ", value_column)]
    if len({len(column) for column in columns}) != 1:
        raise ValueError("排名数据各列长度必须一致")
    maximum = max((max(0, int(v)) for v in columns[3]), default=0)
    rows = []
    for rank, name, user_id, value in zip(*columns):
        rank, value = int(rank), int(value)
        progress = max(0, value) / maximum * 100 if maximum else 0
        podium = f" podium-{rank}" if 1 <= rank <= 3 else ""
        rows.append(
            f'<tr class="{podium.strip()}"><td><span class="rank{podium}">{rank:02d}</span></td>'
            f'<td><div class="nickname">{escape(str(name))}</div>'
            f'<div class="qq">QQ {escape(str(user_id))}</div></td>'
            f'<td class="score"><strong>{value:,}</strong><span class="unit">{escape(unit)}</span>'
            f'<div class="track"><div style="width:{progress:.2f}%"></div></div></td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="3" class="empty">暂无排名数据</td></tr>')
    template = Template((ASSETS / "ranking.html").read_text(encoding="utf-8"))
    return template.substitute(
        css=(ASSETS / "ranking.css").read_text(encoding="utf-8"),
        title=escape(title), subtitle=escape(subtitle), rows="".join(rows),
        value_column=escape("积分" if value_column == "值" else value_column), count=len(columns[0]),
    )


class RankingRenderer:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None

    async def _start(self):
        if self._browser and self._browser.is_connected():
            return
        await self._stop()
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch(headless=True)
        except Exception as exc:
            await self._stop()
            raise RuntimeError(
                "排名浏览器启动失败；请安装 Playwright Chromium："
                "python -m playwright install chromium（Linux 另需系统依赖，见 docs/ranking_render.md）"
            ) from exc

    async def _stop(self):
        try:
            if self._browser:
                await self._browser.close()
        finally:
            self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

    async def close(self):
        async with self._lock:
            await self._stop()

    async def render(self, html: str) -> bytes:
        async with self._lock:
            await self._start()
            context = await self._browser.new_context(
                viewport={"width": 920, "height": 720}, device_scale_factor=2,
                reduced_motion="reduce", offline=True,
            )
            try:
                # Serve bundled SVGs ourselves; never fetch external nickname content.
                async def route_asset(route):
                    url = route.request.url
                    prefix = "https://ranking.local/emoji/"
                    if url.startswith(prefix) and url.endswith(".svg"):
                        icon = url[len(prefix):-4]
                        if icon and all(c in "0123456789abcdef-" for c in icon):
                            svg = _emoji_svg(icon)
                            if svg:
                                await route.fulfill(body=svg, content_type="image/svg+xml")
                                return
                    await route.abort()

                await context.route("**/*", route_asset)
                page = await context.new_page()
                page.set_default_timeout(15000)
                await page.set_content(html, wait_until="domcontentloaded")
                await page.add_script_tag(path=str(ASSETS / "twemoji.min.js"))
                await page.evaluate("""() => {
                    twemoji.parse(document.querySelector('#ranking-card'), {
                        callback: icon => 'https://ranking.local/emoji/' + icon + '.svg'
                    });
                }""")
                await page.evaluate("""async () => {
                    await document.fonts.ready;
                    await Promise.all([...document.images].map(img => img.decode().catch(() => {
                        // Preserve the full original sequence for unsupported new emoji.
                        img.replaceWith(document.createTextNode(img.alt));
                    })));
                }""")
                return await page.locator("#ranking-card").screenshot(type="png", timeout=15000)
            finally:
                await context.close()


_renderer = RankingRenderer()


async def render_ranking_base64(data: dict, **kwargs) -> bytes:
    return base64.b64encode(await _renderer.render(build_ranking_html(data, **kwargs)))


async def close_ranking_renderer():
    await _renderer.close()
