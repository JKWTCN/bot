import os
import io
import time
import logging

import requests
from PIL import Image, ImageDraw, ImageFont

# Steam 状态监控推送图片渲染
# - 开始游戏卡片 / 结束游戏卡片
# - 头像、游戏头图、游戏名(中文名)、游戏时长、在线人数
# - 缓存目录: cache/steam_status/

CACHE_DIR = "cache/steam_status"
COVER_DIR = os.path.join(CACHE_DIR, "covers")
AVATAR_DIR = os.path.join(CACHE_DIR, "avatars")

# 画布尺寸
IMG_W, IMG_H = 512, 192
COVER_W = 140  # 头图宽度(高度填满)
AVATAR_SIZE = 64

# 配色
START_BG_TOP = (49, 80, 66)     # 开始: 深绿
START_BG_BOTTOM = (28, 35, 44)
END_BG_TOP = (44, 40, 80)       # 结束: 深蓝紫
END_BG_BOTTOM = (12, 12, 24)

COLOR_TEXT = (255, 255, 255)
COLOR_GAME = (129, 173, 81)     # 亮绿
COLOR_LABEL = (200, 255, 200)
COLOR_ACCENT = (120, 180, 255)  # 蓝色(时长/在线人数)
COLOR_TIP = (255, 200, 120)     # 结束卡片吐槽文案

# 备用字体候选(系统已有)
_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Users/icloudwar/Library/Fonts/unifont-17.0.01.otf",
    "Unifont",
    "SimHei",
]
_font_cache = {}


def _resolve_font(name, size):
    """解析字体: 优先具体路径, 失败则按字体名, 最后回退默认字体"""
    key = (name, size)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    # 1. 直接是可读路径
    if name and os.path.isfile(name):
        try:
            font = ImageFont.truetype(name, size)
        except Exception:
            font = None
    # 2. 按字体名
    if font is None:
        try:
            font = ImageFont.truetype(name, size)
        except Exception:
            pass
    # 3. 遍历候选
    if font is None:
        for cand in _FONT_CANDIDATES:
            if cand == name:
                continue
            try:
                font = ImageFont.truetype(cand, size)
                break
            except Exception:
                continue
    # 4. 默认
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def get_font(size, bold=False, prefer=None):
    """获取中文字体。prefer 可指定首选路径/名称"""
    if prefer:
        f = _resolve_font(prefer, size)
        _font_cache[(prefer, size)] = f
        return f
    # 粗体优先 Heiti Medium
    name = "/System/Library/Fonts/STHeiti Medium.ttc" if bold else None
    return _resolve_font(name, size)


def _ensure_dirs():
    for d in (CACHE_DIR, COVER_DIR, AVATAR_DIR):
        os.makedirs(d, exist_ok=True)


def _gradient_bg(img_w, img_h, color_top, color_bottom):
    """生成竖向渐变背景"""
    base = Image.new("RGB", (img_w, img_h), color_top)
    top_r, top_g, top_b = color_top
    bot_r, bot_g, bot_b = color_bottom
    for y in range(img_h):
        ratio = y / (img_h - 1) if img_h > 1 else 0
        r = int(top_r * (1 - ratio) + bot_r * ratio)
        g = int(top_g * (1 - ratio) + bot_g * ratio)
        b = int(top_b * (1 - ratio) + bot_b * ratio)
        for x in range(img_w):
            base.putpixel((x, y), (r, g, b))
    return base


def _text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_wrap(draw, text, font, max_width):
    """自动换行, 返回行列表"""
    if not text:
        return [""]
    lines = []
    line = ""
    for ch in text:
        if _text_width(draw, line + ch, font) <= max_width:
            line += ch
        else:
            lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines


def _fit_font_size(draw, text, max_w, sizes, bold=False):
    """自适应字号, 返回不超 max_w 的最大字号字体"""
    for size in sizes:
        font = get_font(size, bold=bold)
        if _text_width(draw, text, font) <= max_w:
            return font
    return get_font(sizes[-1], bold=bold)


def _fetch_to_cache(url, path, refresh_interval=30 * 24 * 3600):
    """下载图片到缓存, 存在且未过期则直接返回"""
    if os.path.exists(path):
        if time.time() - os.path.getmtime(path) < refresh_interval:
            return path
    try:
        resp = requests.get(url, timeout=15, verify=False)
        if resp.status_code == 200 and resp.content:
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception as e:
        logging.warning(f"[steam_render] 下载图片失败 {url}: {e}")
    return path if os.path.exists(path) else None


def get_avatar_path(steamid, avatar_url):
    _ensure_dirs()
    if not avatar_url:
        return None
    return _fetch_to_cache(avatar_url, os.path.join(AVATAR_DIR, f"{steamid}.jpg"),
                           refresh_interval=24 * 3600)


def get_cover_path(gameid, cover_url=None):
    _ensure_dirs()
    if not gameid:
        return None
    path = os.path.join(COVER_DIR, f"{gameid}.jpg")
    if os.path.exists(path):
        # 30天刷新
        if time.time() - os.path.getmtime(path) < 30 * 24 * 3600:
            return path
    if cover_url:
        if _fetch_to_cache(cover_url, path):
            return path
    return None


def _paste_rounded(img, src_path, box, radius):
    """贴入圆角图片到 img 上"""
    try:
        src = Image.open(src_path).convert("RGBA")
        src = src.resize((box[2], box[3]), Image.LANCZOS)
        mask = Image.new("L", (box[2], box[3]), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, box[2], box[3]),
                                               radius=radius, fill=255)
        src.putalpha(mask)
        img.alpha_composite(src, (box[0], box[1]))
    except Exception as e:
        logging.warning(f"[steam_render] 贴图失败 {src_path}: {e}")


def _paste_cover_fit(img, src_path, x, w, h):
    """贴入封面: 高度填满 h, 宽度按比例, 从左侧贴入"""
    try:
        src = Image.open(src_path).convert("RGBA")
        scale = h / src.height
        new_w = max(1, int(src.width * scale))
        src = src.resize((new_w, h), Image.LANCZOS)
        # 居中裁剪到目标宽度
        if new_w > w:
            left = (new_w - w) // 2
            src = src.crop((left, 0, left + w, h))
            new_w = w
        img.alpha_composite(src, (x, 0))
        return new_w
    except Exception as e:
        logging.warning(f"[steam_render] 封面贴图失败 {src_path}: {e}")
        return 0


def _render_card(
    kind, player_name, avatar_path, cover_path, game_name,
    playtime_str=None, online_count=None, tip_text=None,
):
    """
    渲染一张状态卡片
    kind: "start" | "end"
    返回 PNG bytes
    """
    img = _gradient_bg(
        IMG_W, IMG_H,
        START_BG_TOP if kind == "start" else END_BG_TOP,
        START_BG_BOTTOM if kind == "start" else END_BG_BOTTOM,
    ).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 1. 左侧封面图
    cover_used_w = 0
    if cover_path and os.path.exists(cover_path):
        cover_used_w = _paste_cover_fit(img, cover_path, 0, COVER_W, IMG_H)
    if cover_used_w == 0:
        # 无封面: 画一块占位色块
        draw.rectangle([0, 0, 8, IMG_H], fill=(80, 90, 100, 255))
        cover_used_w = 8

    # 文本区域
    margin = 20
    text_x = cover_used_w + margin
    text_area_w = IMG_W - text_x - margin

    # 2. 玩家名(自适应字号)
    font_player = _fit_font_size(draw, player_name or "未知玩家",
                                 text_area_w, range(26, 14, -1), bold=True)
    name_y = 22
    draw.text((text_x, name_y), player_name or "未知玩家",
              font=font_player, fill=COLOR_TEXT)

    # 3. 头像(玩家名右侧, 不与玩家名重叠时显示)
    if avatar_path and os.path.exists(avatar_path):
        avatar_x = IMG_W - AVATAR_SIZE - margin
        _paste_rounded(img, avatar_path,
                       (avatar_x, name_y, AVATAR_SIZE, AVATAR_SIZE),
                       radius=AVATAR_SIZE // 5)

    # 4. 状态标签
    label = "正在玩" if kind == "start" else "不玩了"
    label_color = COLOR_LABEL if kind == "start" else (255, 170, 170)
    font_label = get_font(20, bold=True)
    label_y = name_y + 38
    draw.text((text_x, label_y), label, font=font_label, fill=label_color)

    # 5. 游戏名(多行)
    font_game = get_font(22, bold=True)
    game_y = label_y + 30
    game_lines = _text_wrap(draw, game_name or "未知游戏", font_game, text_area_w)
    for i, line in enumerate(game_lines[:2]):  # 最多2行
        draw.text((text_x, game_y + i * 30), line, font=font_game, fill=COLOR_GAME)

    # 6. 游戏时长 / 结束时间
    if kind == "start":
        # 时长信息行
        info_parts = []
        if playtime_str:
            info_parts.append(playtime_str)
        if online_count is not None:
            info_parts.append(f"在线 {online_count} 人")
        if info_parts:
            font_info = get_font(16)
            info_y = game_y + min(len(game_lines), 2) * 30 + 6
            draw.text((text_x, info_y), "  ".join(info_parts),
                      font=font_info, fill=COLOR_ACCENT)
    else:
        # 结束: 时长 + 吐槽文案
        font_info = get_font(16)
        info_y = game_y + min(len(game_lines), 2) * 30 + 6
        if playtime_str:
            draw.text((text_x, info_y), playtime_str, font=font_info, fill=COLOR_ACCENT)
        if tip_text:
            font_tip = get_font(15)
            # 吐槽文案可能较长, 换行
            tip_lines = _text_wrap(draw, tip_text, font_tip, text_area_w)
            tip_y = info_y + 24
            for i, line in enumerate(tip_lines[:2]):
                draw.text((text_x, tip_y + i * 22), line,
                          font=font_tip, fill=COLOR_TIP)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def render_start_card(player_name, steamid, gameid, game_name,
                      avatar_url=None, cover_url=None,
                      playtime_str=None, online_count=None):
    """渲染开始游戏卡片, 返回 PNG bytes"""
    avatar_path = get_avatar_path(steamid, avatar_url)
    cover_path = get_cover_path(gameid, cover_url)
    return _render_card("start", player_name, avatar_path, cover_path,
                        game_name, playtime_str=playtime_str,
                        online_count=online_count)


def render_end_card(player_name, steamid, gameid, game_name,
                    avatar_url=None, cover_url=None,
                    playtime_str=None, tip_text=None):
    """渲染结束游戏卡片, 返回 PNG bytes"""
    avatar_path = get_avatar_path(steamid, avatar_url)
    cover_path = get_cover_path(gameid, cover_url)
    return _render_card("end", player_name, avatar_path, cover_path,
                        game_name, playtime_str=playtime_str,
                        tip_text=tip_text)


# ==================== 成就卡片 ====================

ACH_CARD_W = 420
ACH_ICON_SIZE = 64
ACH_CARD_GAP = 14
ACH_CARD_RADIUS = 9
ACH_CARD_BASE_BG = (35, 38, 46)
ACH_CARD_INNER_BG = (38, 44, 56)
ACH_PROGRESS_TRACK = (60, 62, 70)
ACH_PROGRESS_FILL = (26, 159, 255)
ACH_BG = (20, 26, 33)
ACH_COLOR_RARE = (255, 220, 60)   # 稀有成就(解锁率<10%)金色

_ICON_CACHE_DIR = os.path.join(CACHE_DIR, "ach_icons")
_ach_icon_lock = None


def _get_ach_icon(icon_url, apiname):
    """下载并缓存成就图标, 返回本地路径或 None"""
    if not icon_url:
        return None
    _ensure_dirs()
    os.makedirs(_ICON_CACHE_DIR, exist_ok=True)
    # 用 url 末段做文件名, 兜底用 apiname
    fname = apiname + ".jpg"
    path = os.path.join(_ICON_CACHE_DIR, fname)
    return _fetch_to_cache(icon_url, path, refresh_interval=30 * 24 * 3600)


def _draw_rounded_card(img, x0, y0, x1, y1, radius, fill):
    """在 img 上画一个圆角填充卡片"""
    w, h = x1 - x0, y1 - y0
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, w - 1, h - 1),
                                           radius=radius, fill=fill)
    img.alpha_composite(card, (x0, y0))


def _draw_rounded_bar(draw, x0, y0, x1, y1, radius, fill):
    """画圆角进度条"""
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=fill)


def _wrap_to_lines(draw, text, font, max_width):
    """自动换行"""
    if not text:
        return [""]
    lines = []
    line = ""
    for ch in text:
        if _text_width(draw, line + ch, font) <= max_width:
            line += ch
        else:
            lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines


def render_achievement_card(player_name, game_name, new_achievements,
                             details, unlocked_count=None):
    """渲染成就卡片
    - new_achievements: 本次新增的成就 apiname 列表(顺序即展示顺序)
    - details: apiname -> {name, description, icon, icon_gray, percent}
    - unlocked_count: (已解锁数, 总数) 或 None
    返回 PNG bytes; 若无可展示成就返回 None
    """
    if not new_achievements:
        return None
    padding_v = 18
    padding_h = 18

    font_title = get_font(20, bold=True)
    font_game = get_font(12)
    font_name = get_font(16, bold=True)
    font_desc = get_font(13)
    font_percent = get_font(12)

    # 测量标题区高度
    dummy = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy)
    title_text = f"{player_name} 解锁了新成就"
    title_h = dummy_draw.textbbox((0, 0), title_text, font=font_title)[3]
    game_h = dummy_draw.textbbox((0, 0), game_name or "", font=font_game)[3]
    progress_bar_h = 12
    header_h = title_h + 8 + game_h + progress_bar_h + 24

    # 预计算每个成就卡片的高度
    text_area_w = (ACH_CARD_W - padding_h * 2 - ACH_ICON_SIZE - 16 - 18)
    card_heights = []
    card_texts = []  # [(name_lines, desc_lines, percent_str, percent_num)]
    for apiname in new_achievements:
        detail = details.get(apiname) if details else None
        if not detail:
            card_heights.append(ACH_ICON_SIZE + 24)
            card_texts.append((["未知成就"], [""], "未知", 0))
            continue
        name = detail.get("name", apiname)
        desc = detail.get("description", "") or ""
        percent = detail.get("percent")
        try:
            percent_num = float(percent) if percent is not None else 0.0
        except (ValueError, TypeError):
            percent_num = 0.0
        percent_str = f"{percent_num:.1f}%" if percent is not None else "未知"
        # 用 dummy_draw 测量换行
        name_lines = _wrap_to_lines(dummy_draw, name, font_name, text_area_w)
        desc_lines = _wrap_to_lines(dummy_draw, desc, font_desc, text_area_w)
        card_h = max(ACH_ICON_SIZE + 24,
                      len(name_lines) * 22 + len(desc_lines) * 18 + 60)
        card_heights.append(card_h)
        card_texts.append((name_lines, desc_lines, percent_str, percent_num))

    total_h = (padding_v + header_h + padding_v +
               sum(card_heights) + ACH_CARD_GAP * max(0, len(card_heights) - 1) +
               padding_v)

    img = Image.new("RGBA", (ACH_CARD_W, total_h), ACH_BG + (255,))
    draw = ImageDraw.Draw(img)

    # 标题
    draw.text((padding_h, padding_v), title_text, font=font_title,
              fill=(255, 255, 255))
    # 游戏名(标题下方, 淡色)
    draw.text((padding_h, padding_v + title_h + 8), game_name or "未知游戏",
              font=font_game, fill=(160, 160, 160))

    # 全局进度条(标题区底部)
    bar_x = padding_h
    bar_y = padding_v + title_h + 8 + game_h + 12
    bar_w = ACH_CARD_W - padding_h * 2
    _draw_rounded_bar(draw, bar_x, bar_y, bar_x + bar_w, bar_y + progress_bar_h,
                      radius=progress_bar_h // 2, fill=ACH_PROGRESS_TRACK)
    if unlocked_count and unlocked_count[1]:
        pct = int(unlocked_count[0] / unlocked_count[1] * 100)
        fill_w = int(bar_w * pct / 100)
        if fill_w > 0:
            _draw_rounded_bar(draw, bar_x, bar_y, bar_x + fill_w,
                              bar_y + progress_bar_h,
                              radius=progress_bar_h // 2, fill=ACH_PROGRESS_FILL)
        prog_text = f"{unlocked_count[0]}/{unlocked_count[1]} ({pct}%)"
        pw = _text_width(draw, prog_text, font_percent)
        draw.text((bar_x + bar_w - pw - 6, bar_y - 2), prog_text,
                  font=font_percent, fill=(142, 207, 255))

    # 成就卡片
    y = padding_v + header_h + padding_v
    for idx, apiname in enumerate(new_achievements):
        detail = details.get(apiname) if details else None
        name_lines, desc_lines, percent_str, percent_num = card_texts[idx]
        card_h = card_heights[idx]
        card_x0 = padding_h
        card_x1 = ACH_CARD_W - padding_h
        card_y0 = int(y)
        card_y1 = int(y + card_h)
        rare = percent_num < 10

        # 卡片背景(稀有成就用金色描边)
        _draw_rounded_card(img, card_x0, card_y0, card_x1, card_y1,
                           ACH_CARD_RADIUS, ACH_CARD_BASE_BG + (255,))
        if rare:
            ImageDraw.Draw(img).rounded_rectangle(
                (card_x0 + 1, card_y0 + 1, card_x1 - 2, card_y1 - 2),
                radius=ACH_CARD_RADIUS, outline=ACH_COLOR_RARE, width=3)

        # 图标
        icon_path = None
        if detail:
            icon_path = _get_ach_icon(detail.get("icon"), apiname)
            if not icon_path:
                icon_path = _get_ach_icon(detail.get("icon_gray"), apiname)
        icon_x = card_x0 + 12
        icon_y = card_y0 + (card_h - ACH_ICON_SIZE) // 2
        if icon_path and os.path.exists(icon_path):
            try:
                icon = Image.open(icon_path).convert("RGBA")
                icon = icon.resize((ACH_ICON_SIZE, ACH_ICON_SIZE), Image.LANCZOS)
                mask = Image.new("L", (ACH_ICON_SIZE, ACH_ICON_SIZE), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    (0, 0, ACH_ICON_SIZE, ACH_ICON_SIZE), 12, fill=255)
                icon.putalpha(mask)
                img.alpha_composite(icon, (icon_x, icon_y))
            except Exception:
                # 图标损坏, 画占位块
                _draw_rounded_bar(draw, icon_x, icon_y,
                                  icon_x + ACH_ICON_SIZE, icon_y + ACH_ICON_SIZE,
                                  radius=12, fill=(60, 66, 78))
        else:
            _draw_rounded_bar(draw, icon_x, icon_y,
                              icon_x + ACH_ICON_SIZE, icon_y + ACH_ICON_SIZE,
                              radius=12, fill=(60, 66, 78))

        # 文本
        text_x = icon_x + ACH_ICON_SIZE + 16
        text_y = card_y0 + 10
        for i, line in enumerate(name_lines):
            draw.text((text_x, text_y + i * 22), line, font=font_name,
                      fill=(255, 255, 255))
        desc_y = text_y + len(name_lines) * 22 + 2
        for i, line in enumerate(desc_lines):
            draw.text((text_x, desc_y + i * 18), line, font=font_desc,
                      fill=(187, 187, 187))

        # 单成就解锁率条(卡片底部)
        pct_y = desc_y + len(desc_lines) * 18 + 6
        label = "全球解锁率"
        lw = _text_width(draw, label, font_percent)
        draw.text((text_x, pct_y), label, font=font_percent,
                  fill=ACH_COLOR_RARE if rare else (142, 207, 255))
        bar_x2 = text_x + lw + 6
        bar_y2 = pct_y + 4
        bar_end = card_x1 - 48
        if bar_end > bar_x2:
            _draw_rounded_bar(draw, bar_x2, bar_y2, bar_end, bar_y2 + 10,
                              radius=5, fill=ACH_PROGRESS_TRACK)
            fw = int((bar_end - bar_x2) * percent_num / 100)
            if fw > 0:
                _draw_rounded_bar(draw, bar_x2, bar_y2, bar_x2 + fw, bar_y2 + 10,
                                  radius=5, fill=ACH_PROGRESS_FILL)
        draw.text((bar_end + 6, pct_y), percent_str, font=font_percent,
                  fill=ACH_COLOR_RARE if rare else (142, 207, 255))

        y += card_h + ACH_CARD_GAP

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
