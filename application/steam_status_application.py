import asyncio
import json
import os
import re
import sqlite3
import time

import requests
from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.application.meta_application import MetaMessageApplication
from data.enumerates import ApplicationCostType, ApplicationType, MetaEventType
from data.message.group_message_info import GroupMessageInfo
from data.message.meta_message_info import MetaMessageInfo
from function.datebase_user import get_user_name
from function.say import ReplySay, SayGroup
from tools.tools import FindNum, HasAllKeyWords, load_static_setting, load_setting


def get_steam_status(steam_ids: list):
    """
    输入：steam_ids (列表类型，例如 ["id1", "id2"])
    输出：包含玩家状态信息的列表
    """
    # 1. 从配置文件中加载API密钥
    api_key = load_static_setting("steam_web_api_key", "")
    # 2. 将列表转换为逗号分隔的字符串
    ids_str = ",".join(steam_ids)

    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={ids_str}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()

        players_data = data.get("response", {}).get("players", [])

        # 3. 构造结果列表
        result_list = []
        for player in players_data:
            info = {
                "steamid": player.get("steamid"),
                "nickname": player.get("personaname"),
                "status_code": player.get("personastate"),
                "current_game": player.get("gameextrainfo", "未在玩游戏")
            }
            result_list.append(info)

            # 打印调试信息
            print(f"玩家: {info['nickname']} | 状态码: {info['status_code']} | 游戏: {info['current_game']}")

        return result_list

    except Exception as e:
        print(f"获取 Steam 状态失败: {e}")
        return []


def get_steamid_by_vanity_url(vanity_url_name):
    """
    
    输入: 个性化域名后缀 (例如 https://steamcommunity.com/id/asdjasodiajiosd/ 的是 'asdjasodiajiosd')
    输出: 17位 SteamID64，如果未找到则返回 None
    """
    api_key = load_static_setting("steam_web_api_key", "")
    url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    
    params = {
        "key": api_key,
        "vanityurl": vanity_url_name
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # success 为 1 表示查询成功
        if data.get("response", {}).get("success") == 1:
            steamid64 = data["response"]["steamid"]
            return steamid64
        else:
            print(f"查询失败: {data.get('response', {}).get('message', '未找到该用户')}")
            return None
            
    except Exception as e:
        print(f"请求异常: {e}")
        return None

async def get_steam_status_async(steam_ids: list):
    """
    异步版本的 Steam 状态获取函数
    使用线程池执行同步的 requests 调用，避免阻塞事件循环
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_steam_status, steam_ids)


# ==================== 数据库操作函数 ====================

DB_PATH = "db/steam_status.db"


def create_steam_binding_table():
    """创建 Steam 绑定表"""
    # 确保 db 目录存在
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
        PRIMARY KEY (user_id, group_id)
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
    SELECT user_id, group_id, steam_id, last_status, last_check_time
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


# ==================== 应用一：Steam ID 绑定应用 ====================

class SteamBindingApplication(GroupMessageApplication):
    """Steam ID 绑定应用"""

    def __init__(self):
        applicationInfo = ApplicationInfo("Steam ID 绑定", "绑定你的 Steam ID 以接收状态推送")
        super().__init__(applicationInfo, 10, False, ApplicationCostType.NORMAL)
        create_steam_binding_table()

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断是否触发应用"""
        bot_name = load_setting("bot_name", "乐可")
        return (
            HasAllKeyWords(message.plainTextMessage, [bot_name, "绑定", "steam"]) or
            HasAllKeyWords(message.plainTextMessage, [bot_name, "解绑", "steam"]) or
            HasAllKeyWords(message.plainTextMessage, [bot_name, "查询", "steam"])
        )

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        # 绑定 Steam ID
        if HasAllKeyWords(message.plainTextMessage, ["绑定", "steam"]):
            # 先尝试提取 SteamID64（17位数字）
            steam_id = FindNum(message.plainTextMessage)

            if steam_id and steam_id != -1:
                # 验证是否为有效的 SteamID64（17位数字）
                if len(str(steam_id)) == 17:
                    # 直接使用 SteamID64
                    bind_steam_id(message.senderId, message.groupId, str(steam_id))
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"已成功绑定 Steam ID: {steam_id}\n每 10 秒会检查一次状态变化并推送"
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
                # 匹配格式：https://steamcommunity.com/id/xxxxx 或 steamcommunity.com/id/xxxxx
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

                    # 异步查询 SteamID64
                    loop = asyncio.get_event_loop()
                    steam_id64 = await loop.run_in_executor(
                        None,
                        get_steamid_by_vanity_url,
                        vanity_url_name
                    )

                    if steam_id64:
                        bind_steam_id(message.senderId, message.groupId, steam_id64)
                        await ReplySay(
                            message.websocket,
                            message.groupId,
                            message.messageId,
                            f"已成功绑定 Steam ID: {steam_id64}\n"
                            f"个人域名: {vanity_url_name}\n"
                            f"每 10 秒会检查一次状态变化并推送"
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
    """Steam 状态推送应用"""

    CHECK_INTERVAL = 60  # 检查间隔（秒）

    def __init__(self):
        applicationInfo = ApplicationInfo("Steam 状态推送", "定期检查并推送 Steam 状态变化")
        super().__init__(applicationInfo, 5, True, ApplicationCostType.NORMAL)
        create_steam_binding_table()
        self.last_check_time = 0

    def judge(self, message: MetaMessageInfo) -> bool:
        """判断是否触发应用"""
        return message.metaEventType == MetaEventType.HEART_BEAT

    async def process(self, message: MetaMessageInfo):
        """处理心跳消息"""
        try:
            current_time = time.time()

            # 检查是否超过间隔时间
            if current_time - self.last_check_time < self.CHECK_INTERVAL:
                return

            self.last_check_time = current_time

            # 获取所有绑定
            bindings = get_all_steam_bindings()
            if not bindings:
                return

            # 按 steam_id 分组，减少 API 调用
            steam_id_map = {}  # {steam_id: [(user_id, group_id, last_status, last_check_time)]}
            for user_id, group_id, steam_id, last_status, last_check_time in bindings:
                if steam_id not in steam_id_map:
                    steam_id_map[steam_id] = []
                steam_id_map[steam_id].append((user_id, group_id, last_status, last_check_time))

            # 批量获取状态（使用异步版本）
            all_steam_ids = list(steam_id_map.keys())
            status_list = await get_steam_status_async(all_steam_ids)

            # 构建状态映射
            status_map = {}  # {steam_id: {nickname, status_code, current_game}}
            for status in status_list:
                steam_id = status["steamid"]
                status_map[steam_id] = {
                    "nickname": status["nickname"],
                    "status_code": status["status_code"],
                    "current_game": status["current_game"]
                }

            # 检查状态变化并推送
            for steam_id, user_bindings in steam_id_map.items():
                if steam_id not in status_map:
                    continue

                current_status = status_map[steam_id]
                new_status_json = json.dumps(current_status, ensure_ascii=False)

                for user_id, group_id, last_status_json, last_check in user_bindings:
                    # 检查状态是否变化
                    if last_status_json:
                        try:
                            last_status = json.loads(last_status_json)
                            # 比较状态码和游戏
                            if (last_status["status_code"] != current_status["status_code"] or
                                last_status["current_game"] != current_status["current_game"]):

                                # 状态发生变化，发送通知
                                old_status_text = get_status_text(
                                    last_status["status_code"],
                                    last_status["current_game"]
                                )
                                new_status_text = get_status_text(
                                    current_status["status_code"],
                                    current_status["current_game"]
                                )

                                # 获取群昵称
                                group_nickname = get_user_name(user_id, group_id)

                                await SayGroup(
                                    message.websocket,
                                    group_id,
                                    f"[{group_nickname}({current_status['nickname']})] Steam 状态变化:\n"
                                    f"{old_status_text} -> {new_status_text}"
                                )
                        except json.JSONDecodeError:
                            # JSON 解析错误，忽略
                            pass
                    else:
                        # 首次记录，不发送通知，只记录到数据库
                        pass

                    # 更新数据库中的状态（无论是否变化都需要更新）
                    update_steam_status(user_id, group_id, new_status_json, int(current_time))

        except (KeyboardInterrupt, Exception) as e:
            # 优雅地处理中断和其他异常
            if isinstance(e, KeyboardInterrupt):
                print("Steam状态检查被中断")
            else:
                print(f"Steam状态检查出错: {e}")

