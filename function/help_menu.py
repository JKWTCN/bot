"""帮助菜单模块:图片渲染 + 翻页会话 + 单功能详情.

提供以下能力(供 FeaturesMenuApplication / HelpFlipPageApplication /
HelpDetailApplication 共用):
- 收集并按分类分组所有可显示的群消息应用
- 用 matplotlib 把一页菜单渲染成图片(返回 base64)
- 维护一个内存中的翻页会话(带超时自动清理)
- 把单个应用的详情(触发/说明/可配置参数)渲染成图片

渲染与发送均沿用项目既有约定:
- 字体使用 load_static_setting("font", ...)
- 图片写入 figs/ 下唯一文件后读为 base64, 再删除原图
- 通过原始 OneBot send_msg_async 消息段发送(文字 + 图片)
"""

import base64
import logging
import os
import time

import matplotlib
matplotlib.use("Agg")  # 无界面后端,适合服务端出图
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from data.application.application_category import AppCategory
from tools.tools import load_setting, load_static_setting

# 每页展示的功能条目数(兼顾图片可读性)
ITEMS_PER_PAGE = 7

# 翻页会话过期时间(秒)
SESSION_EXPIRE_SECONDS = 120


def _font_list():
    """读取项目静态字体配置,带兜底."""
    try:
        return load_static_setting("font", ["SimHei", "Unifont"])
    except Exception:  # noqa: BLE001
        return ["SimHei", "Unifont"]


def _apply_font():
    """应用中文字体配置,避免中文乱码 / 方块."""
    plt.rcParams["font.sans-serif"] = _font_list()
    plt.rcParams["axes.unicode_minus"] = False


def _collect_displayable_apps():
    """从已注册列表中收集所有可显示的群消息应用(惰性导入避免循环依赖)."""
    from schedule.application_list import groupMessageApplicationList
    from function.help_meta_registry import apply_registry

    apps = [
        app
        for app in groupMessageApplicationList.get()
        if getattr(app.applicationInfo, "can_display", True)
    ]
    # 合并元数据注册表(触发方式 / 详情 / 分类 / 参数)
    for app in apps:
        apply_registry(app)
    return apps


def _group_apps_by_category(apps):
    """按 category 分组,顺序遵循 AppCategory.DISPLAY_ORDER."""
    buckets = {cat: [] for cat in AppCategory.DISPLAY_ORDER}
    for app in apps:
        cat = getattr(app.applicationInfo, "category", AppCategory.OTHER) or AppCategory.OTHER
        buckets.setdefault(cat, [])
        buckets[cat].append(app)
    # 过滤掉空分类,保留 DISPLAY_ORDER 中的非空项 + 未知分类
    ordered = []
    for cat in AppCategory.DISPLAY_ORDER:
        if buckets.get(cat):
            ordered.append((cat, buckets[cat]))
    # 不在预定义顺序里的分类(若有)追加到末尾
    for cat, items in buckets.items():
        if cat not in AppCategory.DISPLAY_ORDER and items:
            ordered.append((cat, items))
    return ordered


def _trigger_text(app):
    """取应用的触发说明,未填写则给默认占位."""
    t = getattr(app.applicationInfo, "trigger", "") or ""
    return t if t else "（自动触发）"


def _save_fig_to_base64(fig) -> str:
    """把 figure 写入 figs/ 下唯一文件,读取为 base64 字符串后删除原图."""
    os.makedirs("figs", exist_ok=True)
    output_path = f"figs/help_{int(time.time() * 1000)}.png"
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    with open(output_path, "rb") as image_file:
        image_data = image_file.read()
    try:
        os.remove(output_path)
    except OSError:
        pass
    return base64.b64encode(image_data).decode("utf-8")


def _truncate(text: str, width: int) -> str:
    """按显示宽度截断文本(中文按 2 计宽),超出加省略号."""
    if text is None:
        return ""
    text = str(text)
    total = 0
    out = []
    for ch in text:
        w = 2 if ord(ch) > 127 else 1
        if total + w > width:
            out.append("…")
            break
        out.append(ch)
        total += w
    return "".join(out)


def _draw_text_block(ax, x, y, lines, sizes, colors, line_height=0.115):
    """在 axes 上从 (x,y) 开始逐行写文本,返回下一行起始 y 坐标."""
    for line, size, color in zip(lines, sizes, colors):
        ax.text(x, y, line, fontsize=size, color=color, va="top", ha="left",
                wrap=True)
        y -= line_height
    return y


def render_menu_image(category, page, total_pages, apps, bot_name):
    """渲染某一页菜单图片,返回 base64 字符串.

    Args:
        category: 分类名
        page: 当前页(从 1 开始)
        total_pages: 总页数
        apps: 当前页要展示的应用列表
        bot_name: 机器人名,用于页脚提示
    """
    _apply_font()

    # 标题色 / 强调色
    accent = "#FF7A59"
    bg = "#FFFFFF"

    fig_height = 3.2 + 1.15 * max(len(apps), 1)
    fig, ax = plt.subplots(figsize=(9, fig_height))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    # 标题栏
    ax.text(0.3, fig_height - 0.35, f"功能帮助 · {category}",
            fontsize=20, color="#222222", fontweight="bold", va="top", ha="left")
    ax.text(9.7, fig_height - 0.35, f"第 {page}/{total_pages} 页",
            fontsize=12, color="#888888", va="top", ha="right")
    # 分隔线
    ax.plot([0.3, 9.7], [fig_height - 0.7, fig_height - 0.7],
            color=accent, linewidth=2)

    y = fig_height - 1.05
    for app in apps:
        info = app.applicationInfo
        # 每个功能用一个浅色圆角框包住
        box = FancyBboxPatch(
            (0.3, y - 0.95), 9.4, 1.0,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.0, edgecolor="#EEEEEE", facecolor="#FAFAFA",
        )
        ax.add_patch(box)
        # 名称
        ax.text(0.55, y - 0.18, _truncate(info.name, 30),
                fontsize=14, color="#1A6FB0", fontweight="bold", va="top", ha="left")
        # 触发方式
        ax.text(0.55, y - 0.5, f"触发：{_truncate(_trigger_text(app), 42)}",
                fontsize=10.5, color="#555555", va="top", ha="left")
        # 一句话说明
        ax.text(0.55, y - 0.76, f"说明：{_truncate(info.info or '—', 42)}",
                fontsize=10.5, color="#777777", va="top", ha="left")
        y -= 1.12

    # 页脚提示
    foot_y = 0.55
    ax.plot([0.3, 9.7], [foot_y + 0.3, foot_y + 0.3], color="#EEEEEE", linewidth=1)
    ax.text(0.3, foot_y + 0.12,
            f"发送「下一页 / 上一页 / 第N页」翻页",
            fontsize=10, color="#999999", va="top", ha="left")
    ax.text(9.7, foot_y + 0.12,
            f"「{bot_name} + 功能名 + 详细」查看详情",
            fontsize=10, color="#999999", va="top", ha="right")

    return _save_fig_to_base64(fig)


def render_detail_image(app, bot_name, group_id):
    """渲染单个应用的详情图片,返回 base64 字符串.

    展示:名称、触发方式、功能说明、详细说明/示例、可配置参数(及其当前值).
    """
    _apply_font()
    from function.GroupConfig import get_config

    info = app.applicationInfo
    accent = "#1A6FB0"
    bg = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(9, 5.6))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.6)
    ax.axis("off")

    # 标题
    ax.text(0.3, 5.35, _truncate(info.name, 26),
            fontsize=20, color="#222222", fontweight="bold", va="top", ha="left")
    ax.text(9.7, 5.35, f"{info.category}",
            fontsize=12, color="#888888", va="top", ha="right")
    ax.plot([0.3, 9.7], [5.05, 5.05], color=accent, linewidth=2)

    y = 4.7
    ax.text(0.3, y, "触发方式", fontsize=13, color=accent, fontweight="bold", va="top", ha="left")
    ax.text(0.3, y - 0.32, _truncate(_trigger_text(app), 46),
            fontsize=12, color="#333333", va="top", ha="left")

    y -= 0.78
    ax.text(0.3, y, "功能说明", fontsize=13, color=accent, fontweight="bold", va="top", ha="left")
    ax.text(0.3, y - 0.32, _truncate(info.info or "—", 46),
            fontsize=12, color="#333333", va="top", ha="left")

    y -= 0.78
    detail = getattr(info, "detail", "") or ""
    ax.text(0.3, y, "详细说明", fontsize=13, color=accent, fontweight="bold", va="top", ha="left")
    # 详情可能较长,做简单换行
    detail_text = detail if detail else "（暂无详细说明）"
    ax.text(0.3, y - 0.32, _truncate(detail_text, 88),
            fontsize=11, color="#555555", va="top", ha="left", wrap=True)

    y -= 1.0
    params = list(getattr(info, "params", []) or [])
    ax.text(0.3, y, "可配置参数", fontsize=13, color=accent, fontweight="bold", va="top", ha="left")
    if params:
        ax.text(0.3, y - 0.32,
                "（管理员）发送「.参数名.set 新值」可修改",
                fontsize=10, color="#888888", va="top", ha="left")
        py = y - 0.62
        for key in params:
            try:
                cur = get_config(key, group_id)
            except Exception:  # noqa: BLE001
                cur = "?"
            ax.text(0.45, py,
                    f"• {key} = {cur}",
                    fontsize=11, color="#333333", va="top", ha="left")
            py -= 0.32
    else:
        ax.text(0.3, y - 0.32, "该功能暂无可配置参数",
                fontsize=11, color="#999999", va="top", ha="left")

    # 页脚
    ax.plot([0.3, 9.7], [0.45, 0.45], color="#EEEEEE", linewidth=1)
    ax.text(0.3, 0.22, f"回到总菜单:发送「{bot_name} + 帮助」",
            fontsize=10, color="#999999", va="top", ha="left")

    return _save_fig_to_base64(fig)


# ---------------- 翻页会话管理 ----------------


class HelpSession:
    """单个(群,用户)的帮助翻页会话."""

    def __init__(self, category, total_pages, bot_name):
        self.category = category
        self.page = 1
        self.total_pages = total_pages
        self.bot_name = bot_name
        self.expire_at = time.time() + SESSION_EXPIRE_SECONDS

    def is_expired(self) -> bool:
        return time.time() > self.expire_at

    def touch(self):
        """续期"""
        self.expire_at = time.time() + SESSION_EXPIRE_SECONDS


# (group_id, user_id) -> HelpSession
_sessions: dict = {}


def _cleanup_expired():
    """清掉已过期的会话."""
    expired = [k for k, v in _sessions.items() if v.is_expired()]
    for k in expired:
        _sessions.pop(k, None)


def start_session(group_id, user_id, category, total_pages, bot_name) -> HelpSession:
    """开启一个翻页会话,返回会话对象."""
    _cleanup_expired()
    sess = HelpSession(category, total_pages, bot_name)
    _sessions[(group_id, user_id)] = sess
    return sess


def get_session(group_id, user_id):
    """取未过期会话,无则返回 None."""
    sess = _sessions.get((group_id, user_id))
    if sess is None or sess.is_expired():
        _sessions.pop((group_id, user_id), None)
        return None
    return sess


def flip_session(group_id, user_id, target):
    """翻页.target 可为 'next' / 'prev' / 整数页码.返回新页码或 None(无会话)."""
    sess = get_session(group_id, user_id)
    if sess is None:
        return None
    if target == "next":
        sess.page = min(sess.page + 1, sess.total_pages)
    elif target == "prev":
        sess.page = max(sess.page - 1, 1)
    elif isinstance(target, int):
        sess.page = max(1, min(target, sess.total_pages))
    else:
        return None
    sess.touch()
    return sess.page


# ---------------- 高层:获取某分类某页的应用 ----------------


def get_categories_with_counts():
    """返回 [(category, app_count), ...] 供分类总览."""
    apps = _collect_displayable_apps()
    grouped = _group_apps_by_category(apps)
    return [(cat, len(items)) for cat, items in grouped]


def get_page_apps(category, page):
    """返回 (apps_in_page, total_pages).page 从 1 开始."""
    apps = _collect_displayable_apps()
    grouped = dict(_group_apps_by_category(apps))
    items = grouped.get(category, [])
    total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    return items[start:start + ITEMS_PER_PAGE], total_pages


def find_app_by_name(keyword):
    """按名称模糊匹配一个可显示的应用,找不到返回 None.

    匹配优先级:完全相等 > 名称包含关键词 > 关键词包含名称.
    """
    apps = _collect_displayable_apps()
    kw = keyword.strip()
    if not kw:
        return None
    for app in apps:
        if app.applicationInfo.name == kw:
            return app
    for app in apps:
        if kw in app.applicationInfo.name:
            return app
    for app in apps:
        if app.applicationInfo.name in kw:
            return app
    return None


# ---------------- 发送 ----------------


async def send_image_b64(websocket, group_id, image_b64, caption=""):
    """发送一张 base64 图片(可选附带文字)到群,沿用 send_msg_async 模式."""
    import json

    message = []
    if caption:
        message.append({"type": "text", "data": {"text": caption}})
    message.append({"type": "image", "data": {"file": "base64://" + image_b64}})

    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": message,
        },
    }
    await websocket.send(json.dumps(payload))


async def send_menu_page(websocket, group_id, user_id, category, page, bot_name, start_sess=True):
    """渲染并发送某分类某页的菜单图片.返回是否成功."""
    apps, total_pages = get_page_apps(category, page)
    if not apps:
        return False
    try:
        img_b64 = render_menu_image(category, page, total_pages, apps, bot_name)
    except Exception:  # noqa: BLE001
        logging.exception("渲染帮助菜单失败 category=%s page=%s", category, page)
        return False
    if start_sess:
        start_session(group_id, user_id, category, total_pages, bot_name)
    await send_image_b64(websocket, group_id, img_b64)
    return True


async def send_app_detail(websocket, group_id, app, bot_name):
    """渲染并发送单个应用的详情图片."""
    try:
        img_b64 = render_detail_image(app, bot_name, group_id)
    except Exception:  # noqa: BLE001
        logging.exception("渲染应用详情失败 app=%s", getattr(app.applicationInfo, "name", "?"))
        return False
    await send_image_b64(websocket, group_id, img_b64)
    return True


async def send_category_overview(websocket, group_id, bot_name):
    """发送所有分类总览(纯文本),作为「帮助」的入口."""
    cats = get_categories_with_counts()
    if not cats:
        await _send_text(websocket, group_id, "暂无可显示的功能喵。")
        return
    lines = ["📚 功能帮助 · 分类总览", ""]
    for cat, count in cats:
        lines.append(f"• {cat}（{count} 个功能）")
    lines.append("")
    lines.append("查看某个分类:发送「{bot} + 帮助 + 分类名」".format(bot=bot_name))
    lines.append("例如:{bot} + 帮助 + 图片".format(bot=bot_name))
    lines.append("查看功能详情:发送「{bot} + 功能名 + 详细」".format(bot=bot_name))
    await _send_text(websocket, group_id, "\n".join(lines))


async def _send_text(websocket, group_id, text):
    """发送纯文本到群."""
    import json

    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [{"type": "text", "data": {"text": text}}],
        },
    }
    await websocket.send(json.dumps(payload))


def parse_page_command(text: str):
    """从文本中解析翻页指令.

    返回:
        ('next', None) / ('prev', None) / ('page', n) / None
    """
    t = text.strip()
    if t in ("下一页", "下页", "next", "下一张"):
        return "next", None
    if t in ("上一页", "上页", "上一张", "prev", "back"):
        return "prev", None
    # 第N页 / N页 / page N
    import re

    m = re.search(r"第?\s*(\d+)\s*页", t)
    if m:
        return "page", int(m.group(1))
    return None
