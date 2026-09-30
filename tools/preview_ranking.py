"""Generate sample cards without accessing the bot database."""
import asyncio
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from function.ranking_render import close_ranking_renderer, render_ranking_base64


async def main():
    output = Path(__file__).resolve().parent.parent / "figs" / "ranking_preview"
    output.mkdir(parents=True, exist_ok=True)
    names = ["云朵 ☁️", "乐可 👍🏽", "一家人 👨‍👩‍👧‍👦", "旅行者 🇨🇳", "<script>alert('昵称')</script>", "这是一个很长的中文昵称用于检查自动换行和表格对齐，继续展示完整昵称而不遮挡右侧的统计数字☁️🌈"]
    try:
        for filename, count, points in [("chat", 6, False), ("full", 20, False), ("empty", 0, False), ("points", 6, True)]:
            rank_key, value_key = ("积分排名", "值") if points else ("排名", "今日次数")
            data = {rank_key: list(range(1, count + 1)), "昵称": [names[i % len(names)] for i in range(count)], "QQ": [100001 + i for i in range(count)], value_key: [max(0, 1234 - i * 100) for i in range(count)]}
            result = await render_ranking_base64(data, title="积分排名" if points else "水群排名", subtitle="本群积分榜" if points else "今日发言榜", rank_column=rank_key, value_column=value_key, unit="分" if points else "次")
            path = output / f"{filename}.png"
            path.write_bytes(base64.b64decode(result))
            print(path)
    finally:
        await close_ranking_renderer()


if __name__ == "__main__":
    asyncio.run(main())
