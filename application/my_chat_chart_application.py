import base64
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta

import matplotlib.pyplot as plt

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.datebase_user import get_user_name
from tools.tools import HasAllKeyWords, HasKeyWords, load_setting, load_static_setting


def _get_period_start(period: str) -> datetime:
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


def _detect_period(plain_text: str):
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


def _build_date_axis(start_day: datetime, end_day: datetime, include_year: bool):
    date_keys = []
    x_labels = []
    cursor = start_day
    while cursor <= end_day:
        date_keys.append(cursor.strftime("%Y-%m-%d"))
        if include_year:
            x_labels.append(cursor.strftime("%Y-%m-%d"))
        else:
            x_labels.append(cursor.strftime("%m-%d"))
        cursor += timedelta(days=1)
    return date_keys, x_labels


def _query_user_daily_chat_count(user_id: int, group_id: int, start_ts: int, end_ts: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date(time, 'unixepoch', 'localtime') AS day, COUNT(*) AS chat_num
        FROM group_message
        WHERE user_id=? AND group_id=? AND time>=? AND time<?
        GROUP BY day
        ORDER BY day ASC
        """,
        (user_id, group_id, start_ts, end_ts),
    )
    rows = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def _query_user_first_chat_datetime(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT MIN(time) FROM group_message WHERE user_id=? AND group_id=?",
        (user_id, group_id),
    )
    row = cur.fetchone()
    conn.close()
    if row is None or row[0] is None:
        return None
    return datetime.fromtimestamp(int(row[0]))


def _draw_chat_chart_by_base64(x_labels, y_values, title: str):
    plt.rcParams["font.sans-serif"] = load_static_setting("font", ["Unifont"])
    plt.rcParams["axes.unicode_minus"] = False

    fig_width = max(8, min(24, len(x_labels) * 0.35))
    fig, ax = plt.subplots(figsize=(fig_width, 4.8))
    ax.plot(x_labels, y_values, marker="o", linewidth=1.6)
    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("发言次数")
    ax.grid(alpha=0.25)

    if len(x_labels) > 14:
        step = max(1, len(x_labels) // 14)
        for i, label in enumerate(ax.get_xticklabels()):
            if i % step != 0:
                label.set_visible(False)
    plt.xticks(rotation=35)
    plt.tight_layout()

    output_path = f"figs/my_chat_chart_{int(time.time() * 1000)}.png"
    plt.savefig(output_path, dpi=460)
    plt.close(fig)

    with open(output_path, "rb") as image_file:
        image_data = image_file.read()

    try:
        os.remove(output_path)
    except OSError:
        pass

    return base64.b64encode(image_data)


async def SendMyPeriodChatChart(websocket, user_id: int, group_id: int, period: str, period_cn: str):
    now = datetime.now()
    start_dt = _get_period_start(period)
    if period == "life":
        first_chat_dt = _query_user_first_chat_datetime(user_id, group_id)
        if first_chat_dt is not None:
            start_dt = datetime(first_chat_dt.year, first_chat_dt.month, first_chat_dt.day)
    # end_ts 取到下一天 00:00，保证当天数据纳入统计
    end_dt_exclusive = datetime(now.year, now.month, now.day) + timedelta(days=1)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt_exclusive.timestamp())

    day_count_map = _query_user_daily_chat_count(user_id, group_id, start_ts, end_ts)

    include_year = period == "life"
    date_keys, x_labels = _build_date_axis(
        start_dt, datetime(now.year, now.month, now.day), include_year
    )
    y_values = []
    for date_key in date_keys:
        y_values.append(day_count_map.get(date_key, 0))

    sender_name = get_user_name(user_id, group_id)
    total_count = sum(y_values)

    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }

    payload["params"]["message"].append(
        {
            "type": "text",
            "data": {
                "text": f"{sender_name} 的{period_cn}发言图表（总发言: {total_count}）"
            },
        }
    )

    title = (
        f"{sender_name} {period_cn}发言趋势\n"
        f"统计时间:{start_dt.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
    )

    payload["params"]["message"].append(
        {
            "type": "image",
            "data": {
                "file": "base64://"
                + _draw_chat_chart_by_base64(
                    x_labels,
                    y_values,
                    title,
                ).decode("utf-8")
            },
        }
    )

    await websocket.send(json.dumps(payload))


class MyChatChartApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("我的发言图表", "查看我的生涯/本年/本季度/本月/本周发言趋势")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        period, period_cn = _detect_period(message.plainTextMessage)
        if period is None:
            return
        if period_cn is None:
            return
        await SendMyPeriodChatChart(
            message.websocket,
            message.senderId,
            message.groupId,
            period,
            period_cn,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        plain_text = message.plainTextMessage
        return HasKeyWords(plain_text, [load_setting("bot_name", "乐可")]) and (
            HasAllKeyWords(plain_text, ["我的", "生涯", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "生涯", "发言", "图表"])
            or HasAllKeyWords(plain_text, ["我的", "本年", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "本年", "发言", "图表"])
            or HasAllKeyWords(plain_text, ["我的", "本季度", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "本季度", "发言", "图表"])
            or HasAllKeyWords(plain_text, ["我的", "本季", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "本季", "发言", "图表"])
            or HasAllKeyWords(plain_text, ["我的", "本月", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "本月", "发言", "图表"])
            or HasAllKeyWords(plain_text, ["我的", "本周", "发言", "图"])
            or HasAllKeyWords(plain_text, ["我的", "本周", "发言", "图表"])
        )
