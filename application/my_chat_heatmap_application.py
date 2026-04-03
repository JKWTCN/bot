import base64
import json
import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
from scipy.interpolate import griddata

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.datebase_user import get_user_name
from tools.tools import HasAllKeyWords, HasKeyWords, load_setting, load_static_setting


# 复用现有的时间范围检测函数
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


def _query_user_weekday_hour_activity(user_id: int, group_id: int, start_ts: int, end_ts: int):
    """
    查询用户在指定时间段内按星期+小时的发言次数分布
    返回: {(weekday, hour): count} 字典
    - weekday: 0-6 (周日到周六，SQLite格式)
    - hour: 0-23
    - count: 发言次数
    """
    conn = sqlite3.connect("bot.db", timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            strftime('%w', datetime(time, 'unixepoch', 'localtime')) AS weekday,
            strftime('%H', datetime(time, 'unixepoch', 'localtime')) AS hour,
            COUNT(*) AS chat_num
        FROM group_message
        WHERE user_id=? AND group_id=? AND time>=? AND time<?
        GROUP BY weekday, hour
        ORDER BY weekday, hour
        """,
        (user_id, group_id, start_ts, end_ts),
    )
    rows = cur.fetchall()
    conn.close()
    return {(int(row[0]), int(row[1])): row[2] for row in rows}


def _build_heatmap_data(activity_data: dict):
    """
    构建完整的7×24热力矩阵
    返回: (7, 24) numpy数组，索引为[weekday][hour]
    weekday: 0-6 (周一到周日)
    hour: 0-23
    """
    # 初始化7×24零矩阵 (周一到周日, 0-23小时)
    heatmap = np.zeros((7, 24), dtype=int)

    # 填充实际数据
    for (weekday, hour), count in activity_data.items():
        # 调整weekday：SQLite返回0=周日，我们转换为0=周一
        adjusted_weekday = (weekday - 1) % 7
        heatmap[adjusted_weekday][hour] = count

    return heatmap


def _query_user_first_chat_datetime(user_id: int, group_id: int):
    """查询用户首次发言时间"""
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


def _draw_heatmap_scatter_by_base64(heatmap_data, title: str, show_annotations: bool = True, show_trendline: bool = False):
    """
    绘制热力散点图并返回base64编码

    参数：
    - heatmap_data: (7, 24) numpy数组
    - title: 图表标题
    - show_annotations: 是否显示数据标注
    - show_trendline: 是否显示趋势线
    """
    import time

    plt.rcParams["font.sans-serif"] = load_static_setting("font", ["Unifont"])
    plt.rcParams["axes.unicode_minus"] = False

    # 创建图表
    fig, ax = plt.subplots(figsize=(14, 8))

    # 准备数据
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    hours = list(range(24))

    # 生成散点坐标
    x_coords = []
    y_coords = []
    sizes = []
    colors = []

    max_count = np.max(heatmap_data) if np.max(heatmap_data) > 0 else 1

    for weekday_idx in range(7):
        for hour_idx in range(24):
            count = heatmap_data[weekday_idx][hour_idx]
            if count > 0:
                x_coords.append(hour_idx)
                y_coords.append(weekday_idx)
                # 散点大小基于发言次数，基础大小50，最大500
                sizes.append(50 + (count / max_count) * 450)
                # 颜色基于发言次数
                colors.append(count)

    # 创建颜色映射 (浅黄到深红)
    cmap = plt.cm.YlOrRd  # 黄-橙-红色阶
    norm = mcolors.Normalize(vmin=0, vmax=max_count)

    # 绘制散点
    if len(x_coords) > 0:
        scatter = ax.scatter(x_coords, y_coords, s=sizes, c=colors,
                            cmap=cmap, norm=norm, alpha=0.7, edgecolors='black', linewidth=0.5)

        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('发言次数')

    # 设置坐标轴
    ax.set_xticks(hours)
    ax.set_xticklabels([f'{h}:00-{h+1}:00' if h < 23 else '23:00-0:00' for h in hours], rotation=45)
    ax.set_yticks(range(7))
    ax.set_yticklabels(weekdays)

    ax.set_xlabel('时间 (小时)')
    ax.set_ylabel('星期')
    ax.set_title(title)
    ax.grid(True, alpha=0.3, linestyle='--')

    # 添加数据标注
    if show_annotations and len(x_coords) > 0:
        for i, (x, y) in enumerate(zip(x_coords, y_coords)):
            count = heatmap_data[y][x]
            ax.annotate(str(count), (x, y), textcoords="offset points",
                       xytext=(0, 0), ha='center', va='center',
                       fontsize=7, fontweight='bold', color='white' if count > max_count * 0.5 else 'black')

    # 添加趋势线 (多项式拟合)
    if show_trendline and len(x_coords) > 3:
        try:
            # 创建网格用于绘制平滑趋势面
            grid_x, grid_y = np.mgrid[0:23:100j, 0:6:100j]
            points = np.array([x_coords, y_coords]).T
            values = np.array([heatmap_data[y][x] for x, y in zip(x_coords, y_coords)])

            # 插值生成平滑趋势
            grid_z = griddata(points, values, (grid_x, grid_y), method='cubic')

            # 绘制等高线作为趋势线
            contour = ax.contour(grid_x, grid_y, grid_z, colors='blue', alpha=0.5, linewidths=1)
            ax.clabel(contour, inline=True, fontsize=8, fmt='%d')
        except Exception as e:
            # 如果插值失败，忽略趋势线
            pass

    plt.tight_layout()

    # 保存并转换为base64
    output_path = f"figs/my_chat_heatmap_{int(time.time() * 1000)}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    with open(output_path, "rb") as image_file:
        image_data = image_file.read()

    try:
        os.remove(output_path)
    except OSError:
        pass

    return base64.b64encode(image_data)


async def SendMyPeriodHeatmap(websocket, user_id: int, group_id: int, period: str, period_cn: str,
                             show_annotations: bool = True, show_trendline: bool = False):
    """
    发送用户时间段活跃度热力图
    """
    import time

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

    # 查询活跃度数据
    activity_data = _query_user_weekday_hour_activity(user_id, group_id, start_ts, end_ts)
    heatmap_data = _build_heatmap_data(activity_data)

    sender_name = get_user_name(user_id, group_id)
    total_count = int(np.sum(heatmap_data))

    # 找出最活跃时段
    max_count = np.max(heatmap_data)
    most_active_periods = []
    if max_count > 0:
        for i in range(7):
            for j in range(24):
                if heatmap_data[i][j] == max_count:
                    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
                    hour_range = f"{j}:00-{j+1}:00" if j < 23 else "23:00-0:00"
                    most_active_periods.append(f"{weekdays[i]} {hour_range}")

    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }

    # 检查是否有数据
    if total_count == 0:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": f"{sender_name} 在{period_cn}暂无发言记录"
                },
            }
        )
    else:
        payload["params"]["message"].append(
            {
                "type": "text",
                "data": {
                    "text": f"{sender_name} 的{period_cn}发言热力图（总发言: {total_count}）"
                },
            }
        )

        if most_active_periods:
            payload["params"]["message"].append(
                {
                    "type": "text",
                    "data": {
                        "text": f"最活跃时段: {', '.join(most_active_periods[:3])} (单时段{max_count}次)"
                    },
                }
            )

        title = (
            f"{sender_name} {period_cn}发言热力分布\n"
            f"统计时间:{start_dt.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}\n"
            f"散点大小和颜色深浅表示发言频率"
        )

        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {
                    "file": "base64://"
                    + _draw_heatmap_scatter_by_base64(
                        heatmap_data,
                        title,
                        show_annotations,
                        show_trendline
                    ).decode("utf-8")
                },
            }
        )

    await websocket.send(json.dumps(payload))


class MyChatHeatmapApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("我的发言热力图", "查看我的生涯/本年/本季度/本月/本周发言热力分布")
        # 设置优先级为 51（比折线图的 50 更高，数字越大优先级越高），确保热力图先触发
        super().__init__(applicationInfo, 51, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        period, period_cn = _detect_period(message.plainTextMessage)
        if period is None or period_cn is None:
            return

        # 检测是否需要隐藏数据标注
        show_annotations = "隐藏标注" not in message.plainTextMessage and "不显示标注" not in message.plainTextMessage

        # 检测是否需要趋势线
        show_trendline = "趋势" in message.plainTextMessage or "趋势线" in message.plainTextMessage

        await SendMyPeriodHeatmap(
            message.websocket,
            message.senderId,
            message.groupId,
            period,
            period_cn,
            show_annotations,
            show_trendline,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        plain_text = message.plainTextMessage
        return HasKeyWords(plain_text, [load_setting("bot_name", "乐可")]) and (
            HasAllKeyWords(plain_text, ["我的", "生涯", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "生涯", "发言", "热力图"])
            or HasAllKeyWords(plain_text, ["我的", "本年", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "本年", "发言", "热力图"])
            or HasAllKeyWords(plain_text, ["我的", "本季度", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "本季度", "发言", "热力图"])
            or HasAllKeyWords(plain_text, ["我的", "本季", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "本季", "发言", "热力图"])
            or HasAllKeyWords(plain_text, ["我的", "本月", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "本月", "发言", "热力图"])
            or HasAllKeyWords(plain_text, ["我的", "本周", "发言", "热力"])
            or HasAllKeyWords(plain_text, ["我的", "本周", "发言", "热力图"])
        )
