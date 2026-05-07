import base64
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta

import jieba
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from wordcloud import WordCloud

from tools.tools import load_static_setting

# 中文停用词集
STOP_WORDS = {
    # 结构助词
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "个",
    "上", "也", "这", "么", "那", "他", "她", "它", "们", "你", "把", "被", "让",
    "给", "到", "说", "会", "对", "出", "能", "行", "好",
    # 语气词
    "吗", "吧", "啊", "呢", "哦", "嗯", "哈", "呀", "啦", "哎", "唉",
    # 连接词
    "要", "没", "又", "与", "及", "其", "之", "等", "很", "为", "还", "以", "于",
    "从", "去", "来", "过", "下", "中", "大", "小",
    # 常见口语填充
    "觉得", "可以", "什么", "怎么", "这个", "那个", "现在", "可能", "已经",
    "应该", "因为", "所以", "但是", "还是", "而且", "如果", "虽然", "然后",
    "一下", "一个", "时候", "知道", "这样", "那样", "这么", "那么",
    "真的", "就是", "不是", "没有", "只是", "或者", "这样",
    # QQ 聊天噪音
    "qwq", "www", "awa", "orz", "lol", "lmao", "hmm", "hhh", "hh",
    "表情包", "图片", "链接", "视频",
    # 代词/量词
    "自己", "他们", "我们", "你们", "大家", "些", "多", "少",
}

_font_path_cache = None


def _find_font_path() -> str:
    """查找可用的中文字体文件路径"""
    global _font_path_cache
    if _font_path_cache is not None:
        return _font_path_cache

    font_names = load_static_setting("font", ["Unifont"])
    if isinstance(font_names, str):
        font_names = [font_names]

    for name in font_names:
        try:
            path = fm.findfont(fm.FontProperties(family=name))
            if path and not path.endswith(".dict") and os.path.exists(path):
                _font_path_cache = path
                return path
        except Exception:
            continue

    # 回退：扫描系统字体路径
    fallback_dirs = [
        "/System/Library/Fonts",
        "/Library/Fonts",
        os.path.expanduser("~/Library/Fonts"),
        "/usr/share/fonts",
    ]
    fallback_names = [
        "PingFang.ttc", "STHeiti Light.ttc", "SimHei.ttf",
        "NotoSansCJK-Regular.ttc", "WenQuanYi Micro Hei.ttf",
    ]
    for d in fallback_dirs:
        if not os.path.isdir(d):
            continue
        for fn in fallback_names:
            fp = os.path.join(d, fn)
            if os.path.exists(fp):
                _font_path_cache = fp
                return fp
        # 尝试任意 ttf/ttc
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.endswith((".ttf", ".ttc")):
                    _font_path_cache = os.path.join(root, f)
                    return _font_path_cache

    raise FileNotFoundError("找不到可用的中文字体文件")


def get_period_start(period: str) -> datetime:
    now = datetime.now()
    if period == "year":
        return datetime(now.year, 1, 1)
    if period == "quarter":
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        return datetime(now.year, quarter_start_month, 1)
    if period == "month":
        return datetime(now.year, now.month, 1)
    if period == "life":
        return datetime(now.year, now.month, now.day)
    # week
    return datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())


def detect_period(plain_text: str):
    if "生涯" in plain_text:
        return "life", "生涯"
    if "本年" in plain_text:
        return "year", "本年"
    if "本季度" in plain_text or "本季" in plain_text:
        return "quarter", "本季度"
    if "本月" in plain_text:
        return "month", "本月"
    if "本周" in plain_text:
        return "week", "本周"
    return None, None


def clean_message_text(raw_message: str, bot_name: str) -> str:
    """清洗单条消息文本"""
    text = raw_message
    # 移除 CQ 码
    text = re.sub(r"\[CQ:[^\]]*\]", "", text)
    # 移除 URL
    text = re.sub(r"https?://\S+", "", text)
    # 移除 bot 名称
    text = text.replace(bot_name, "")
    # 只保留中文和英文字母
    text = re.sub(r"[^一-龥a-zA-Z]", "", text)
    return text.strip()


def segment_and_filter(text: str, bot_name: str) -> list:
    """分词并过滤停用词"""
    words = jieba.lcut(text)
    filtered = []
    for w in words:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in STOP_WORDS:
            continue
        if w == bot_name:
            continue
        # 过滤短英文词
        if w.isascii() and len(w) < 3:
            continue
        filtered.append(w)
    return filtered


def query_user_messages(user_id: int, group_id: int, start_ts: int, end_ts: int, bot_id: int, bot_name: str) -> tuple:
    """查询用户消息，返回 (原始文本拼接, 消息条数)"""
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT raw_message FROM group_message WHERE user_id=? AND group_id=? AND time>=? AND time<?",
        (user_id, group_id, start_ts, end_ts),
    )
    rows = cur.fetchall()
    conn.close()
    # 过滤以 bot 名开头的命令消息
    messages = []
    for (raw,) in rows:
        stripped = raw.strip()
        if stripped.startswith(bot_name):
            continue
        messages.append(raw)
    return " ".join(messages), len(messages)


def query_group_messages(group_id: int, start_ts: int, end_ts: int, bot_id: int, bot_name: str) -> tuple:
    """查询群消息（排除 bot），返回 (原始文本拼接, 消息条数)"""
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT raw_message FROM group_message WHERE group_id=? AND time>=? AND time<? AND user_id!=? LIMIT 50000",
        (group_id, start_ts, end_ts, bot_id),
    )
    rows = cur.fetchall()
    conn.close()
    messages = []
    for (raw,) in rows:
        stripped = raw.strip()
        if stripped.startswith(bot_name):
            continue
        messages.append(raw)
    return " ".join(messages), len(messages)


def query_first_chat_datetime(user_id: int = None, group_id: int = None, is_group: bool = False) -> datetime:
    """查询首次发言时间"""
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    if is_group:
        cur.execute("SELECT MIN(time) FROM group_message WHERE group_id=?", (group_id,))
    else:
        cur.execute(
            "SELECT MIN(time) FROM group_message WHERE user_id=? AND group_id=?",
            (user_id, group_id),
        )
    row = cur.fetchone()
    conn.close()
    if row is None or row[0] is None:
        return None
    return datetime.fromtimestamp(int(row[0]))


def build_word_frequency(messages_text: str, bot_name: str) -> Counter:
    """从消息文本构建词频"""
    cleaned = clean_message_text(messages_text, bot_name)
    if not cleaned:
        return Counter()
    words = segment_and_filter(cleaned, bot_name)
    return Counter(words)


def generate_wordcloud_base64(word_frequencies: Counter, title: str) -> tuple:
    """生成词云图片并返回 (base64_bytes, top5_words_list)"""
    plt.rcParams["font.sans-serif"] = load_static_setting("font", ["Unifont"])
    plt.rcParams["axes.unicode_minus"] = False

    font_path = _find_font_path()

    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=800,
        background_color="white",
        max_words=150,
        colormap="viridis",
        collocations=False,
        margin=10,
    )
    wc.generate_from_frequencies(word_frequencies)

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(wc, interpolation="bilinear")
    ax.set_title(title, fontsize=14)
    ax.axis("off")
    plt.tight_layout()

    output_path = f"figs/wordcloud_{int(time.time() * 1000)}.png"
    os.makedirs("figs", exist_ok=True)
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    with open(output_path, "rb") as f:
        image_data = f.read()

    try:
        os.remove(output_path)
    except OSError:
        pass

    top5 = word_frequencies.most_common(5)
    return base64.b64encode(image_data), top5
