import asyncio
import json
import os
import re
import sqlite3
import time
import urllib3

import requests
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.application.meta_application import MetaMessageApplication
from data.enumerates import ApplicationCostType, ApplicationType, MetaEventType
from data.message.group_message_info import GroupMessageInfo
from data.message.meta_message_info import MetaMessageInfo
from function.GroupConfig import get_config
from function.datebase_user import get_user_name
from function.say import ReplySay, SayGroup, SayGroupImage
from tools.tools import FindNum, HasAllKeyWords, load_static_setting

import application.steam_achievement as steam_achievement
from application.steam_achievement import (
    MAX_ACH_NOTIFICATIONS, ACH_CHECK_INTERVAL,
    check_new_achievements as _check_new_achievements,
    clear_achievement_snapshot, save_achievement_snapshot,
    add_to_blacklist,
)

# 禁用SSL警告（因为验证被禁用）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get_api_key():
    """读取 Steam Web API Key"""
    return load_static_setting("steam_web_api_key", "")


def _get_retry_times():
    """读取 Steam API 重试次数"""
    return load_static_setting("steam_retry_times", 3)


def _get_smart_intervals():
    """读取智能轮询各档间隔(秒)
    依次为: [游戏中, 12分钟内, 12分钟~3小时, 3小时~24小时, 24~48小时, 超过48小时]
    """
    raw = load_static_setting("steam_smart_poll_intervals", "60,180,300,600,1200,1800")
    if isinstance(raw, str):
        parts = [int(x.strip()) for x in raw.split(",") if x.strip()]
    else:
        parts = list(raw)
    if len(parts) < 6:
        parts = parts + [60, 180, 300, 600, 1200, 1800][len(parts):]
    return parts[:6]


def _get_poll_mode():
    """读取轮询模式: smart(智能分级) / fixed(固定间隔)"""
    mode = load_static_setting("steam_poll_mode", "smart")
    return mode if mode in ("smart", "fixed") else "smart"


def _get_fixed_interval():
    """读取固定轮询间隔(秒)"""
    return load_static_setting("steam_fixed_poll_interval", 60)


def get_steam_status(steam_ids: list):
    """
    输入：steam_ids (列表类型，例如 ["id1", "id2"])
    输出：包含玩家状态信息的列表
    """
    api_key = _get_api_key()
    ids_str = ",".join(steam_ids)

    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={ids_str}"

    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()

        players_data = data.get("response", {}).get("players", [])

        result_list = []
        for player in players_data:
            info = {
                "steamid": player.get("steamid"),
                "nickname": player.get("personaname"),
                "status_code": player.get("personastate"),
                "current_game": player.get("gameextrainfo", "未在玩游戏"),
                "gameid": player.get("gameid"),
                "lastlogoff": player.get("lastlogoff"),
                "avatarfull": player.get("avatarfull"),
                "avatar": player.get("avatar"),
            }
            result_list.append(info)

        return result_list

    except Exception as e:
        print(f"获取 Steam 状态失败: {e}")
        return []


def get_steam_status_with_retry(steam_ids: list, retry=None):
    """带指数退避重试的状态获取(同步)"""
    retry = retry if retry is not None else _get_retry_times()
    delay = 1
    for attempt in range(retry):
        result = get_steam_status(steam_ids)
        if result:
            return result
        if attempt < retry - 1:
            time.sleep(delay)
            delay *= 2
    print(f"Steam状态获取失败, 已重试{retry}次, steam_ids={steam_ids}")
    return []


async def get_steam_status_async(steam_ids: list):
    """
    异步版本的 Steam 状态获取函数
    使用线程池执行同步的 requests 调用，避免阻塞事件循环
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_steam_status_with_retry, steam_ids)


def get_steamid_by_vanity_url(vanity_url_name):
    """
    输入: 个性化域名后缀
    输出: 17位 SteamID64，如果未找到则返回 None
    """
    api_key = _get_api_key()
    url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"

    params = {
        "key": api_key,
        "vanityurl": vanity_url_name
    }

    try:
        response = requests.get(url, params=params, verify=False)
        data = response.json()
        if data.get("response", {}).get("success") == 1:
            steamid64 = data["response"]["steamid"]
            return steamid64
        else:
            print(f"查询失败：{data.get('response', {}).get('message', '未找到该用户')}")
            return None

    except Exception as e:
        print(f"请求异常: {e}")
        return None


async def get_steamid_by_vanity_url_async(vanity_url_name):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_steamid_by_vanity_url, vanity_url_name)


# 游戏中文名 / 封面缓存(进程级)
_game_name_cache = {}  # {gameid: 中文名}


async def get_chinese_game_name(gameid, fallback_name=None):
    """通过 Steam 商店API获取游戏中文名, 失败回退英文名"""
    if not gameid:
        return fallback_name or "未知游戏"
    gid = str(gameid)
    if gid in _game_name_cache:
        return _game_name_cache[gid]
    loop = asyncio.get_event_loop()
    name = await loop.run_in_executor(None, _fetch_game_name, gid)
    if name:
        _game_name_cache[gid] = name
        return name
    return fallback_name or "未知游戏"


def _fetch_game_name(gid):
    """同步获取游戏名: 优先中文, 再英文"""
    for lang in ("schinese", "en"):
        url = f"https://store.steampowered.com/api/appdetails?appids={gid}&l={lang}"
        try:
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code != 200:
                continue
            data = resp.json()
            info = data.get(gid, {}).get("data", {})
            name = info.get("name")
            if name:
                return name
        except Exception as e:
            print(f"获取游戏名失败: {e} (gameid={gid}, lang={lang})")
    return None


def _fetch_game_cover_url(gid):
    """获取游戏头图(header_image)url, 用于卡片封面"""
    for lang in ("schinese", "japanese", "en"):
        url = f"https://store.steampowered.com/api/appdetails?appids={gid}&l={lang}"
        try:
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code != 200:
                continue
            data = resp.json()
            info = data.get(gid, {}).get("data", {})
            header_img = info.get("header_image")
            if header_img:
                return header_img
        except Exception as e:
            print(f"获取游戏封面失败: {e} (gameid={gid})")
    return None


async def get_game_online_count(gameid):
    """通过 Steam Web API 获取当前游戏在线人数"""
    if not gameid:
        return None
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={gameid}"
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: requests.get(url, timeout=10, verify=False)
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", {}).get("player_count")
    except Exception as e:
        print(f"获取在线人数失败: {e} (gameid={gameid})")
    return None


# ==================== 数据库操作函数 ====================

DB_PATH = "db/steam_status.db"


def create_steam_binding_table():
    """创建 Steam 绑定表(含智能轮询所需字段)"""
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS steam_binding (
        user_id INTEGER,
        group_id INTEGER,
        steam_id TEXT,
        last_status TEXT,
        last_check_time INTEGER DEFAULT 0,
        game_start_time INTEGER DEFAULT 0,
        last_game_id TEXT DEFAULT '',
        pending_quit INTEGER DEFAULT 0,
        next_poll_time INTEGER DEFAULT 0,
        last_ach_check_time INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, group_id)
    )
    """)
    conn.commit()
    conn.close()

    # 为旧表补充新字段
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for col, decl in [
        ("game_start_time", "INTEGER DEFAULT 0"),
        ("last_game_id", "TEXT DEFAULT ''"),
        ("pending_quit", "INTEGER DEFAULT 0"),
        ("next_poll_time", "INTEGER DEFAULT 0"),
        ("last_ach_check_time", "INTEGER DEFAULT 0"),
    ]:
        try:
            cur.execute(f"ALTER TABLE steam_binding ADD COLUMN {col} {decl}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()

    # 成就快照表: 记录玩家在某游戏的已解锁成就集合, 用于对比新增
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS steam_achievement_snapshot (
        user_id INTEGER,
        group_id INTEGER,
        steam_id TEXT,
        appid TEXT,
        achievements_json TEXT DEFAULT '[]',
        update_time INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, group_id, appid)
    )
    """)
    conn.commit()
    conn.close()

    # 成就黑名单表: 拉取失败次数过多的游戏加入黑名单, 不再查询
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS steam_achievement_blacklist (
        appid TEXT PRIMARY KEY,
        reason TEXT DEFAULT '',
        add_time INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()


def bind_steam_id(user_id: int, group_id: int, steam_id: str):
    """绑定 Steam ID"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO steam_binding (user_id, group_id, steam_id, last_status, last_check_time)
    VALUES (?, ?, ?, NULL, 0)
    """, (user_id, group_id, steam_id))
    conn.commit()
    conn.close()


def unbind_steam_id(user_id: int, group_id: int):
    """解绑 Steam ID"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM steam_binding WHERE user_id = ? AND group_id = ?
    """, (user_id, group_id))
    conn.commit()
    conn.close()


def get_steam_binding(user_id: int, group_id: int):
    """查询单个绑定"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    SELECT steam_id FROM steam_binding WHERE user_id = ? AND group_id = ?
    """, (user_id, group_id))
    result = cur.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


def get_all_steam_bindings():
    """获取所有绑定"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    SELECT user_id, group_id, steam_id, last_status, last_check_time,
           game_start_time, last_game_id, pending_quit, next_poll_time,
           last_ach_check_time
    FROM steam_binding
    """)
    results = cur.fetchall()
    conn.close()
    return results


def update_steam_status(user_id: int, group_id: int, status_json: str, check_time: int):
    """更新 Steam 状态"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    UPDATE steam_binding
    SET last_status = ?, last_check_time = ?
    WHERE user_id = ? AND group_id = ?
    """, (status_json, check_time, user_id, group_id))
    conn.commit()
    conn.close()


def update_game_start_time(user_id: int, group_id: int, game_start_time: int):
    """更新游戏开始时间"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    UPDATE steam_binding
    SET game_start_time = ?
    WHERE user_id = ? AND group_id = ?
    """, (game_start_time, user_id, group_id))
    conn.commit()
    conn.close()


def update_binding_extra(user_id: int, group_id: int, **fields):
    """更新绑定表的扩展字段(last_game_id / pending_quit / next_poll_time / game_start_time)"""
    if not fields:
        return
    allowed = {"last_game_id", "pending_quit", "next_poll_time", "game_start_time"}
    cols = [k for k in fields.keys() if k in allowed]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values = [fields[c] for c in cols]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"UPDATE steam_binding SET {set_clause} WHERE user_id = ? AND group_id = ?",
        (*values, user_id, group_id),
    )
    conn.commit()
    conn.close()


# ==================== 状态码映射 ====================

STEAM_STATUS_MAP = {
    0: "离线",
    1: "在线",
    2: "忙碌",
    3: "离开",
    4: "深睡",
    5: "想要交易",
    6: "想要玩"
}


def get_status_text(status_code: int, current_game: str):
    """获取状态文本"""
    status = STEAM_STATUS_MAP.get(status_code, "未知")
    if current_game and current_game != "未在玩游戏":
        return f"{status} - 玩游戏中: {current_game}"
    return status


def format_duration(seconds: int) -> str:
    """格式化时长为可读字符串"""
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        else:
            return f"{hours}小时"


def get_end_tip_text(duration_min: float) -> str:
    """根据游玩时长生成结束吐槽文案"""
    if duration_min < 5:
        return "风扇都没转热就结束了？"
    elif duration_min < 10:
        return "热身一下就结束了？"
    elif duration_min < 30:
        return "这才刚进入状态喵~"
    elif duration_min < 60:
        return "歇会儿再来, 别太累了喵!"
    elif duration_min < 120:
        return "沉浸在游戏世界, 时间过得飞快!"
    elif duration_min < 300:
        return "肝到手软了喵! 注意休息~"
    elif duration_min < 600:
        return "记得吃饭呀, 别忘了吃饭这回事~"
    elif duration_min < 1200:
        return "家里电费都要被玩光了喵!"
    elif duration_min < 1800:
        return "该颁发『不眠』勋章了!"
    else:
        return "你已经和椅子合为一体了喵!"


def calc_next_poll_interval_sec(status: dict, now: int) -> int:
    """根据玩家状态计算下次轮询间隔(秒)
    status 字段: gameid, status_code(personastate), lastlogoff
    智能分级(各档间隔单位为秒):
    游戏中 / 12分钟内 / 3小时内 / 24小时内 / 48小时内 / 更久
    """
    # 固定模式
    if _get_poll_mode() == "fixed":
        return _get_fixed_interval()

    intervals = _get_smart_intervals()  # 秒
    gameid = status.get("gameid")
    status_code = status.get("status_code", 0)
    lastlogoff = status.get("lastlogoff")

    if gameid:
        return intervals[0]
    if status_code and int(status_code) > 0:
        return intervals[1]
    if lastlogoff:
        minutes_ago = (now - int(lastlogoff)) / 60
        if minutes_ago <= 12:
            return intervals[1]
        elif minutes_ago <= 180:
            return intervals[2]
        elif minutes_ago <= 1440:
            return intervals[3]
        elif minutes_ago <= 2880:
            return intervals[4]
        else:
            return intervals[5]
    return intervals[5]


# ==================== 应用一：Steam ID 绑定应用 ====================

class SteamBindingApplication(GroupMessageApplication):
    """Steam ID 绑定应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("Steam ID 绑定", "绑定你的 Steam ID 以接收状态推送")
        super().__init__(applicationInfo, 10, False, ApplicationCostType.NORMAL)
        create_steam_binding_table()

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        bot_name = load_static_setting("bot_name", "乐可")
        return (
            HasAllKeyWords(message.plainTextMessage, [bot_name, "绑定", "steam"]) or
            HasAllKeyWords(message.plainTextMessage, [bot_name, "解绑", "steam"]) or
            HasAllKeyWords(message.plainTextMessage, [bot_name, "查询", "steam"])
        )

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        # 绑定 Steam ID
        if HasAllKeyWords(message.plainTextMessage, ["绑定", "steam"]):
            steam_id = FindNum(message.plainTextMessage)
            if steam_id and steam_id != -1:
                if len(str(steam_id)) == 17:
                    bind_steam_id(message.senderId, message.groupId, str(steam_id))
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"已成功绑定 Steam ID: {steam_id}\n游戏状态变化会自动推送(智能轮询)"
                    )
                else:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"绑定失败：SteamID64 必须是 17 位数字\n"
                        f"你提供的 ID: {steam_id} ({len(str(steam_id))} 位)\n"
                        f"请提供有效的 SteamID64"
                    )
            else:
                # 没有找到有效数字，尝试提取个人域名
                vanity_pattern = r'steamcommunity\.com/id/([a-zA-Z0-9_-]+)'
                match = re.search(vanity_pattern, message.plainTextMessage)

                if match:
                    vanity_url_name = match.group(1)
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"正在查询个人域名: {vanity_url_name}..."
                    )

                    steam_id64 = await get_steamid_by_vanity_url_async(vanity_url_name)

                    if steam_id64:
                        bind_steam_id(message.senderId, message.groupId, steam_id64)
                        await ReplySay(
                            message.websocket,
                            message.groupId,
                            message.messageId,
                            f"已成功绑定 Steam ID: {steam_id64}\n"
                            f"个人域名: {vanity_url_name}\n"
                            f"游戏状态变化会自动推送(智能轮询)"
                        )
                    else:
                        await ReplySay(
                            message.websocket,
                            message.groupId,
                            message.messageId,
                            f"查询失败：未找到个人域名 '{vanity_url_name}' 对应的 Steam ID\n"
                            f"请确认域名是否正确"
                        )
                else:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        "请提供有效的 Steam ID 或个人域名\n"
                        f"格式1: 绑定 steam [17位SteamID64]\n"
                        f"格式2: 绑定 steam [个人域名链接]\n"
                        f"示例: 绑定 steam https://steamcommunity.com/id/你的域名"
                    )

        # 解绑 Steam ID
        elif HasAllKeyWords(message.plainTextMessage, ["解绑", "steam"]):
            existing_binding = get_steam_binding(message.senderId, message.groupId)
            if existing_binding:
                unbind_steam_id(message.senderId, message.groupId)
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"已解绑 Steam ID: {existing_binding}"
                )
            else:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    "你还没有绑定 Steam ID"
                )

        # 查询 Steam ID
        elif HasAllKeyWords(message.plainTextMessage, ["查询", "steam"]):
            steam_id = get_steam_binding(message.senderId, message.groupId)
            if steam_id:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    f"你已绑定 Steam ID: {steam_id}"
                )
            else:
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    "你还没有绑定 Steam ID\n使用 \"绑定 steam [你的SteamID]\" 进行绑定"
                )


# ==================== 应用二：Steam 状态推送应用 ====================

class SteamStatusPushApplication(MetaMessageApplication):
    """Steam 状态推送应用(智能轮询 + 图片卡片)"""

    # 退出确认缓冲时长(秒): 玩家退出后先标记, 超过此时长仍未回来才推送退出
    QUIT_BUFFER_SEC = 180

    def __init__(self):
        applicationInfo = ApplicationInfo("Steam 状态推送", "智能轮询并推送 Steam 游戏状态变化")
        super().__init__(applicationInfo, 5, True, ApplicationCostType.NORMAL)
        create_steam_binding_table()
        # 心跳触发频率上限(秒), 仅作为心跳节流, 实际轮询由 next_poll_time 控制
        self.heartbeat_throttle = load_static_setting("steam_heartbeat_throttle", 30)
        self.last_heartbeat_time = 0
        # 成就拉取失败计数 {(appid, date): count}, 达阈值拉黑
        self._ach_fail_count = {}

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.metaEventType == MetaEventType.HEART_BEAT

    async def process(self, message: MetaMessageInfo):
        """处理心跳消息: 检查到点的绑定并推送状态变化"""
        try:
            current_time = time.time()

            # 心跳节流, 避免高频心跳下重复进入
            if current_time - self.last_heartbeat_time < self.heartbeat_throttle:
                return
            self.last_heartbeat_time = current_time

            bindings = get_all_steam_bindings()
            if not bindings:
                return

            # 只挑选到点的绑定进行查询
            due_bindings = []
            for row in bindings:
                (user_id, group_id, steam_id, last_status_json,
                 last_check, game_start_time, last_game_id,
                 pending_quit, next_poll_time, last_ach_check_time) = row
                if current_time >= (next_poll_time or 0):
                    due_bindings.append({
                        "user_id": user_id,
                        "group_id": group_id,
                        "steam_id": steam_id,
                        "last_status_json": last_status_json,
                        "game_start_time": game_start_time or 0,
                        "last_game_id": last_game_id or "",
                        "pending_quit": pending_quit or 0,
                        "last_ach_check_time": last_ach_check_time or 0,
                    })

            if not due_bindings:
                # 仍有到点前的退出确认需要检查
                await self._flush_pending_quits(bindings, message, current_time)
                return

            # 按 steam_id 分组, 减少API调用
            steam_id_map = {}
            for b in due_bindings:
                steam_id_map.setdefault(b["steam_id"], []).append(b)

            all_steam_ids = list(steam_id_map.keys())
            status_list = await get_steam_status_async(all_steam_ids)

            # 构建状态映射
            status_map = {}
            for status in status_list:
                sid = status["steamid"]
                status_map[sid] = status

            now_int = int(current_time)

            # 处理每个到点的绑定
            for steam_id, user_bindings in steam_id_map.items():
                if steam_id not in status_map:
                    # 获取失败: 安排稍后重试, 不更新状态
                    for b in user_bindings:
                        update_binding_extra(
                            b["user_id"], b["group_id"],
                            next_poll_time=now_int + 60,
                        )
                    continue

                current_status = status_map[steam_id]
                for b in user_bindings:
                    await self._process_binding(b, current_status, message, now_int)

            # 处理到点前可能已经超时的退出确认
            await self._flush_pending_quits(bindings, message, now_int)

        except KeyboardInterrupt:
            print("Steam状态检查被中断")
        except Exception as e:
            print(f"Steam状态检查出错: {e}")

    async def _process_binding(self, b: dict, current_status: dict, message, now_int: int):
        """处理单个绑定的状态变化"""
        user_id = b["user_id"]
        group_id = b["group_id"]
        steam_id = b["steam_id"]
        last_status_json = b["last_status_json"]
        game_start_time = b["game_start_time"]
        last_game_id = b["last_game_id"]
        pending_quit = b["pending_quit"]

        # 当前游戏信息
        current_game = current_status.get("current_game", "未在玩游戏")
        current_gameid = str(current_status.get("gameid") or "")
        nickname = current_status.get("nickname") or steam_id

        def is_playing(game_name):
            return bool(game_name) and game_name not in ("", None, "未在玩游戏")

        is_now_playing = is_playing(current_game)

        # 计算下次轮询时间
        next_interval = calc_next_poll_interval_sec(current_status, now_int)
        next_poll_time = now_int + next_interval

        # 首次记录: 不通知, 只记录
        if not last_status_json:
            if is_now_playing:
                update_game_start_time(user_id, group_id, now_int)
                update_binding_extra(user_id, group_id,
                                     last_game_id=current_gameid)
            update_steam_status(user_id, group_id,
                                json.dumps(current_status, ensure_ascii=False), now_int)
            update_binding_extra(user_id, group_id, next_poll_time=next_poll_time)
            return

        # 解析上次状态
        try:
            last_status = json.loads(last_status_json)
        except json.JSONDecodeError:
            last_status = {}

        last_game = last_status.get("current_game", "")
        was_playing = is_playing(last_game)

        simple_notify = get_config("simple_steam_notify", group_id)

        # ---- 状态变化判断 ----
        is_entering_game = (not was_playing and is_now_playing)
        is_exiting_game = (was_playing and not is_now_playing)
        is_switching_game = (was_playing and is_now_playing
                             and last_game != current_game)

        # 退出游戏: 进入缓冲, 不立即推送
        if is_exiting_game and not pending_quit:
            update_binding_extra(
                user_id, group_id,
                pending_quit=now_int,
                last_game_id=str(last_status.get("gameid") or ""),
            )
            # 仍要刷新状态和下次轮询
            update_steam_status(user_id, group_id,
                                json.dumps(current_status, ensure_ascii=False), now_int)
            update_binding_extra(user_id, group_id, next_poll_time=next_poll_time)
            return

        # 重新进入游戏, 且处于退出缓冲中 => 网络波动, 取消退出
        if is_now_playing and pending_quit:
            # 取消退出缓冲
            update_binding_extra(
                user_id, group_id,
                pending_quit=0,
                game_start_time=now_int,
                last_game_id=current_gameid,
            )
            update_steam_status(user_id, group_id,
                                json.dumps(current_status, ensure_ascii=False), now_int)
            update_binding_extra(user_id, group_id, next_poll_time=next_poll_time)
            # 简短提示网络波动(可选, 不发图片)
            group_nickname = get_user_name(user_id, group_id)
            await SayGroup(
                message.websocket, group_id,
                f"[{group_nickname}({nickname})] 网络波动了一下, 重新回到了游戏"
            )
            return

        # 进入游戏 / 切换游戏: 推送开始卡片(切换时把上一游戏时长结算进同一条)
        if is_entering_game or is_switching_game:
            prefix_text = ""
            if is_switching_game and game_start_time > 0:
                duration = now_int - game_start_time
                duration_text = format_duration(duration)
                group_nickname = get_user_name(user_id, group_id)
                prefix_text = (
                    f"[{group_nickname}({nickname})] {last_game} 玩了 {duration_text}, "
                )
            # 更新游戏开始时间
            game_start_time = now_int
            update_game_start_time(user_id, group_id, now_int)
            update_binding_extra(user_id, group_id, last_game_id=current_gameid)

            # 推送开始卡片(一条消息)
            await self._push_start_card(
                message, group_id, user_id, nickname, steam_id,
                current_gameid, current_game, prefix_text=prefix_text,
            )
            update_steam_status(user_id, group_id,
                                json.dumps(current_status, ensure_ascii=False), now_int)
            update_binding_extra(user_id, group_id, next_poll_time=next_poll_time)
            # 后台初始化新游戏的成就快照(不阻塞推送), 略过初始已知成就
            if current_gameid and get_config("steam_achievement_notify", group_id):
                asyncio.create_task(self._init_achievement_snapshot(
                    group_id, user_id, steam_id, current_gameid, now_int
                ))
            return

        # 正在游戏中(且游戏未变化): 按间隔检查是否有新成就解锁
        if is_now_playing and current_gameid:
            if get_config("steam_achievement_notify", group_id):
                last_ach_check = b.get("last_ach_check_time", 0)
                if now_int - last_ach_check >= ACH_CHECK_INTERVAL:
                    update_binding_extra(user_id, group_id,
                                         last_ach_check_time=now_int)
                    await self._check_and_push_achievements(
                        message, group_id, user_id, steam_id, nickname,
                        current_gameid, current_game, final=False,
                    )

        # 普通模式: 非游戏的状态变化也通知(在线/离线/忙碌等)
        if not simple_notify:
            last_code = last_status.get("status_code", 0)
            cur_code = current_status.get("status_code", 0)
            if last_code != cur_code and not (was_playing or is_now_playing):
                old_text = get_status_text(last_code, last_game)
                new_text = get_status_text(cur_code, current_game)
                group_nickname = get_user_name(user_id, group_id)
                await SayGroup(
                    message.websocket, group_id,
                    f"[{group_nickname}({nickname})] Steam 状态变化:\n{old_text} -> {new_text}"
                )

        update_steam_status(user_id, group_id,
                            json.dumps(current_status, ensure_ascii=False), now_int)
        update_binding_extra(user_id, group_id, next_poll_time=next_poll_time)

    async def _flush_pending_quits(self, bindings, message, now_int: int):
        """检查并推送超过缓冲期、确认退出的玩家"""
        for row in bindings:
            (user_id, group_id, steam_id, last_status_json,
             last_check, game_start_time, last_game_id,
             pending_quit, next_poll_time, last_ach_check_time) = row
            if not pending_quit:
                continue
            if now_int - pending_quit < self.QUIT_BUFFER_SEC:
                continue
            # 确认退出, 推送结束卡片
            try:
                last_status = json.loads(last_status_json) if last_status_json else {}
            except json.JSONDecodeError:
                last_status = {}
            nickname = last_status.get("nickname") or steam_id
            exited_game = last_status.get("current_game", "未在玩游戏")
            exited_gameid = str(last_status.get("gameid") or last_game_id or "")
            duration = now_int - (game_start_time or pending_quit)
            if duration < 0:
                duration = 0
            duration_min = duration / 60

            await self._push_end_card(
                message, group_id, user_id, nickname, steam_id,
                exited_gameid, exited_game, duration, duration_min,
            )
            # 成就最终对比(退出瞬间可能解锁成就), 然后清理快照
            if exited_gameid and get_config("steam_achievement_notify", group_id):
                await self._check_and_push_achievements(
                    message, group_id, user_id, steam_id, nickname,
                    exited_gameid, exited_game, final=True,
                )
            clear_achievement_snapshot(user_id, group_id, exited_gameid)
            # 清理退出标记和开始时间
            update_binding_extra(
                user_id, group_id,
                pending_quit=0,
                game_start_time=0,
                last_game_id="",
            )

    async def _push_start_card(self, message, group_id, user_id, nickname,
                                steam_id, gameid, game_en_name, prefix_text=""):
        """渲染并推送开始游戏卡片
        prefix_text: 切换游戏时上一游戏的结算文本前缀, 会拼到正文前面, 合并为一条消息
        """
        group_nickname = get_user_name(user_id, group_id)
        text = f"[{group_nickname}({nickname})] 开始玩"
        try:
            # 中文名 + 封面 + 在线人数 并发获取
            zh_name_task = asyncio.create_task(
                get_chinese_game_name(gameid, game_en_name)
            )
            online_task = asyncio.create_task(get_game_online_count(gameid))
            cover_url = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_game_cover_url, str(gameid)
            )
            zh_name = await zh_name_task
            online_count = await online_task

            # 补全文本中的游戏名(切换游戏时拼上结算前缀)
            if prefix_text:
                text = f"{prefix_text}开始玩 {zh_name}"
            else:
                text = f"[{group_nickname}({nickname})] 开始玩 {zh_name}"

            from application.steam_status_render import render_start_card
            img_bytes = render_start_card(
                player_name=group_nickname or nickname,
                steamid=steam_id,
                gameid=gameid,
                game_name=zh_name,
                avatar_url=None,  # 头像在状态里不一定可靠, 留空用占位
                cover_url=cover_url,
                online_count=online_count,
            )
            await self._send_image(message.websocket, group_id, img_bytes, text)
        except Exception as e:
            print(f"[Steam] 推送开始卡片失败, 降级文本: {e}")
            await SayGroup(message.websocket, group_id, text)

    async def _push_end_card(self, message, group_id, user_id, nickname,
                              steam_id, gameid, game_en_name,
                              duration_sec: int, duration_min: float):
        """渲染并推送结束游戏卡片"""
        group_nickname = get_user_name(user_id, group_id)
        duration_text = format_duration(duration_sec)
        tip_text = get_end_tip_text(duration_min)
        text = f"[{group_nickname}({nickname})] 不玩了, 本次游玩 {duration_text}"
        try:
            zh_name = await get_chinese_game_name(gameid, game_en_name)
            text = (f"[{group_nickname}({nickname})] 不玩 {zh_name} 了, "
                    f"本次游玩 {duration_text}")
            cover_url = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_game_cover_url, str(gameid)
            )
            from application.steam_status_render import render_end_card
            img_bytes = render_end_card(
                player_name=group_nickname or nickname,
                steamid=steam_id,
                gameid=gameid,
                game_name=zh_name,
                avatar_url=None,
                cover_url=cover_url,
                playtime_str=duration_text,
                tip_text=tip_text,
            )
            await self._send_image(message.websocket, group_id, img_bytes, text)
        except Exception as e:
            print(f"[Steam] 推送结束卡片失败, 降级文本: {e}")
            await SayGroup(message.websocket, group_id, text)

    async def _send_image(self, websocket, group_id, img_bytes: bytes, text: str):
        """把图片字节写入临时文件并发送, 失败降级纯文本"""
        if not img_bytes:
            await SayGroup(websocket, group_id, text)
            return
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            await SayGroupImage(websocket, group_id, tmp_path, text)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # ==================== 成就监控 ====================

    async def _init_achievement_snapshot(self, group_id, user_id, steam_id,
                                          appid, now_int: int):
        """开始游戏时初始化成就快照: 记录当前已解锁集合, 不推送"""
        try:
            api_key = _get_api_key()
            if not api_key:
                return
            loop = asyncio.get_event_loop()
            current = await loop.run_in_executor(
                None, steam_achievement.fetch_player_achievements,
                api_key, steam_id, appid
            )
            if current is not None:
                save_achievement_snapshot(user_id, group_id, steam_id, appid, current)
            update_binding_extra(user_id, group_id, last_ach_check_time=now_int)
        except Exception as e:
            print(f"[Steam成就] 初始化快照失败 appid={appid}: {e}")

    async def _check_and_push_achievements(self, message, group_id, user_id,
                                            steam_id, nickname, appid,
                                            game_en_name, final=False):
        """对比成就快照, 发现新增则推送
        final: True=游戏退出时的最终对比
        """
        if not get_config("steam_achievement_notify", group_id):
            return
        api_key = _get_api_key()
        if not api_key:
            return

        # 失败计数(进程内, 按天+appid), 达阈值则拉黑
        fail_key = (appid, time.strftime('%Y-%m-%d'))

        def on_fail(_appid):
            cnt = self._ach_fail_count.get(fail_key, 0) + 1
            self._ach_fail_count[fail_key] = cnt
            if cnt >= steam_achievement.ACH_FAIL_THRESHOLD:
                add_to_blacklist(_appid, "当天累计失败达到阈值")
                print(f"[Steam成就] 游戏 {_appid} 当天失败 {cnt} 次, 加入黑名单")

        try:
            new_set, current_set, details = await _check_new_achievements(
                api_key, user_id, group_id, steam_id, appid, on_fail=on_fail
            )
        except Exception as e:
            print(f"[Steam成就] 对比异常 appid={appid}: {e}")
            return

        if not new_set:
            return

        # 获取中文名(用于卡片标题)
        zh_name = await get_chinese_game_name(appid, game_en_name)
        group_nickname = get_user_name(user_id, group_id)

        # 限制单次推送数量, 多出则省略
        new_list = list(new_set)
        to_notify = new_list[:MAX_ACH_NOTIFICATIONS]
        extra_count = len(new_list) - len(to_notify)

        # 计算总进度
        unlocked_count = None
        if current_set is not None and details:
            unlocked_count = (len(current_set), len(details))

        # 渲染成就卡片
        img_bytes = None
        try:
            from application.steam_status_render import render_achievement_card
            img_bytes = render_achievement_card(
                player_name=group_nickname or nickname,
                game_name=zh_name,
                new_achievements=to_notify,
                details=details or {},
                unlocked_count=unlocked_count,
            )
        except Exception as e:
            print(f"[Steam成就] 渲染卡片失败, 降级文本: {e}")

        text = f"[{group_nickname}({nickname})] 在 {zh_name} 解锁了新成就!"
        if extra_count > 0:
            text += f"(另有 {extra_count} 个)"
        await self._send_image(message.websocket, group_id, img_bytes, text)
