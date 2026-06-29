import asyncio
import json
import os
import sqlite3
import time

import requests

# Steam 成就监控模块
# - 拉取玩家在某游戏的已解锁成就集合
# - 拉取游戏成就 schema(名称/描述/图标)
# - 拉取全局解锁率
# - 快照对比, 发现新增成就
# - 黑名单机制: 拉取失败次数过多的游戏跳过

DB_PATH = "db/steam_status.db"
MAX_ACH_NOTIFICATIONS = 5      # 单次最多推送的成就数
ACH_FAIL_THRESHOLD = 10        # 当天累计失败次数阈值, 达到则拉黑
ACH_CHECK_INTERVAL = 1200      # 游戏中成就对比间隔(秒), 20分钟


# ==================== API 拉取 ====================

def _to_icon_url(appid, val):
    """把 Steam 返回的图标相对路径补全为完整 URL"""
    if not val:
        return None
    if val.startswith("http://") or val.startswith("https://"):
        return val
    return f"https://cdn.akamaihd.net/steamcommunity/public/images/apps/{appid}/{val}.jpg"


def fetch_player_achievements(api_key, steamid, appid):
    """获取玩家在某游戏的已解锁成就 apiname 集合
    多语言(schinese/english/en)轮换重试, 返回 set 或 None(失败/无成就/隐私)
    """
    if is_blacklisted(appid):
        return None
    url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    for lang in ("schinese", "english", "en"):
        params = {
            "key": api_key,
            "steamid": steamid,
            "appid": appid,
            "l": lang,
        }
        try:
            resp = requests.get(url, params=params, timeout=15, verify=False)
            if resp.status_code == 401:
                # 隐私设置, 无法获取
                return None
            if resp.status_code != 200:
                continue
            data = resp.json()
            achievements = data.get("playerstats", {}).get("achievements")
            if not achievements:
                continue
            unlocked = {a["apiname"] for a in achievements if a.get("achieved", 0) == 1}
            # 必须带描述才算有效(否则可能返回了空壳)
            if any(a.get("description") for a in achievements):
                return unlocked
        except Exception as e:
            print(f"[steam_achievement] 拉取玩家成就异常 appid={appid}: {e}")
            continue
    return None


def fetch_achievement_schema(api_key, steamid, appid):
    """获取游戏成就 schema: apiname -> {name, description, icon, icon_gray}
    优先 GetSchemaForGame, 失败(HTTP400)降级用 GetPlayerAchievements 拿名称/描述
    返回 dict 或 None
    """
    if is_blacklisted(appid):
        return None
    lang_list = ("schinese", "english", "en")
    for lang in lang_list:
        url = (f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/"
               f"?appid={appid}&key={api_key}&l={lang}")
        try:
            resp = requests.get(url, timeout=15, verify=False)
            if resp.status_code == 400:
                # schema 拿不到, 降级用玩家成就接口
                return _fetch_schema_via_player(api_key, steamid, appid, lang_list)
            if resp.status_code != 200:
                continue
            schema = resp.json()
            ach_list = (schema.get("game", {})
                        .get("availableGameStats", {})
                        .get("achievements", []))
            if not ach_list:
                continue
            details = {}
            for a in ach_list:
                details[a["name"]] = {
                    "name": a.get("displayName", a["name"]),
                    "description": a.get("description", ""),
                    "icon": _to_icon_url(appid, a.get("icon")),
                    "icon_gray": _to_icon_url(appid, a.get("icongray")),
                }
            if any(d.get("description") for d in details.values()):
                # 补全局解锁率
                _merge_global_percent(appid, details)
                return details
        except Exception as e:
            print(f"[steam_achievement] 拉取成就schema异常 appid={appid}: {e}")
            continue
    return None


def _fetch_schema_via_player(api_key, steamid, appid, lang_list):
    """降级: 通过玩家成就接口拿成就名称/描述(无图标)"""
    url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    for lang in lang_list:
        params = {"key": api_key, "steamid": steamid, "appid": appid, "l": lang}
        try:
            resp = requests.get(url, params=params, timeout=15, verify=False)
            if resp.status_code != 200:
                continue
            data = resp.json()
            ach_list = data.get("playerstats", {}).get("achievements")
            if not ach_list:
                continue
            details = {}
            for a in ach_list:
                details[a["apiname"]] = {
                    "name": a.get("name", a["apiname"]),
                    "description": a.get("description", ""),
                    "icon": None,
                    "icon_gray": None,
                }
            if any(d.get("description") for d in details.values()):
                _merge_global_percent(appid, details)
                return details
        except Exception as e:
            print(f"[steam_achievement] 降级拉取成就异常 appid={appid}: {e}")
    return None


def _merge_global_percent(appid, details):
    """把全局解锁率合并进 details(给每个成就补 percent 字段)"""
    url = (f"https://api.steampowered.com/ISteamUserStats/"
           f"GetGlobalAchievementPercentagesForApp/v2/?gameid={appid}")
    try:
        resp = requests.get(url, timeout=15, verify=False)
        if resp.status_code != 200:
            return
        stats = resp.json()
        percents = {}
        for a in (stats.get("achievementpercentages", {}).get("achievements", [])):
            percents[a["name"]] = a.get("percent")
        for apiname, d in details.items():
            d["percent"] = percents.get(apiname)
    except Exception as e:
        print(f"[steam_achievement] 拉取全局解锁率异常 appid={appid}: {e}")


# ==================== DB: 快照 / 黑名单 ====================

def _connect():
    return sqlite3.connect(DB_PATH)


def get_achievement_snapshot(user_id, group_id, appid):
    """读取某玩家在某游戏的成就快照, 返回 set(可能为空)"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT achievements_json FROM steam_achievement_snapshot "
        "WHERE user_id=? AND group_id=? AND appid=?",
        (user_id, group_id, str(appid)),
    )
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return set()
    try:
        return set(json.loads(row[0]))
    except json.JSONDecodeError:
        return set()


def save_achievement_snapshot(user_id, group_id, steam_id, appid, ach_set):
    """保存成就快照"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO steam_achievement_snapshot "
        "(user_id, group_id, steam_id, appid, achievements_json, update_time) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, group_id, steam_id, str(appid),
         json.dumps(list(ach_set), ensure_ascii=False), int(time.time())),
    )
    conn.commit()
    conn.close()


def clear_achievement_snapshot(user_id, group_id, appid):
    """删除某玩家在某游戏的成就快照(游戏结束时清理)"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM steam_achievement_snapshot "
        "WHERE user_id=? AND group_id=? AND appid=?",
        (user_id, group_id, str(appid)),
    )
    conn.commit()
    conn.close()


def is_blacklisted(appid):
    """查询某游戏是否在成就黑名单"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM steam_achievement_blacklist WHERE appid=?",
                (str(appid),))
    res = cur.fetchone()
    conn.close()
    return res is not None


def add_to_blacklist(appid, reason=""):
    """加入成就黑名单"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO steam_achievement_blacklist (appid, reason, add_time) "
        "VALUES (?, ?, ?)",
        (str(appid), reason, int(time.time())),
    )
    conn.commit()
    conn.close()


# ==================== 对比逻辑 ====================

async def check_new_achievements(api_key, user_id, group_id, steam_id, appid,
                                  on_fail=None):
    """对比快照, 返回 (new_set, current_set, details)
    - new_set: 本次新增解锁的成就 apiname 集合
    - current_set: 当前全部已解锁集合
    - details: schema 字典(名称/描述/图标/解锁率), 拉取失败为 None
    on_fail: 失败时回调(用于累计失败计数), 接收 appid
    """
    if is_blacklisted(appid):
        return (set(), None, None)

    loop = asyncio.get_event_loop()
    current = await loop.run_in_executor(
        None, fetch_player_achievements, api_key, steam_id, appid
    )
    if current is None:
        if on_fail:
            on_fail(appid)
        return (set(), None, None)

    prev = get_achievement_snapshot(user_id, group_id, appid)
    new_set = current - prev

    # 更新快照(无论是否有新增, 都刷新为最新)
    save_achievement_snapshot(user_id, group_id, steam_id, appid, current)

    if not new_set:
        return (set(), current, None)

    # 有新增: 拉 schema 补全名称/描述/图标
    details = await loop.run_in_executor(
        None, fetch_achievement_schema, api_key, steam_id, appid
    )
    return (new_set, current, details)
