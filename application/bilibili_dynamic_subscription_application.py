"""Bilibili 动态订阅、过滤与群消息推送。

中文指令需要以配置的 bot_name 开头，例如：
  乐可 订阅动态 <UID> [过滤器...]
  乐可 订阅列表
  乐可 订阅删除 <UID>

以 / 开头的 bili_* 指令不需要 bot_name。

订阅检查由 OneBot heartbeat 元事件驱动，首次订阅只记录当前动态快照，
避免把历史动态当作新动态推送。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import requests

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.application.meta_application import MetaMessageApplication
from data.application.private_message_application import PrivateMessageApplication
from data.enumerates import ApplicationCostType, MetaEventType
from data.message.group_message_info import GroupMessageInfo
from data.message.meta_message_info import MetaMessageInfo
from data.message.private_message_info import PrivateMesssageInfo
from function.datebase_user import IsAdmin, IsDeveloper
from function.say import ReplySay
from tools.tools import load_static_setting


DB_PATH = "db/bilibili_dynamic.db"
DYNAMIC_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
LIVE_API = "https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld"
QR_GENERATE_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
FINGERPRINT_API = "https://api.bilibili.com/x/frontend/finger/spi"
NAV_API = "https://api.bilibili.com/x/web-interface/nav"
TYPE_FILTERS = {"forward", "lottery", "video", "article", "draw", "live", "forward_lottery"}
TYPE_LABELS = {
    "DYNAMIC_TYPE_AV": "投稿了新视频",
    "DYNAMIC_TYPE_ARTICLE": "发布了新专栏",
    "DYNAMIC_TYPE_DRAW": "发布了新图文动态",
    "DYNAMIC_TYPE_FORWARD": "转发了新动态",
    "DYNAMIC_TYPE_WORD": "发布了新动态",
}
TYPE_TO_FILTER = {
    "DYNAMIC_TYPE_AV": "video",
    "DYNAMIC_TYPE_ARTICLE": "article",
    "DYNAMIC_TYPE_DRAW": "draw",
    "DYNAMIC_TYPE_FORWARD": "forward",
}


class BilibiliAPIError(RuntimeError):
    pass


@dataclass
class DynamicItem:
    dyn_id: str
    dyn_type: str
    up_name: str
    text: str
    title: str
    images: list[str]
    is_lottery: bool

    @property
    def url(self) -> str:
        return f"https://t.bilibili.com/{self.dyn_id}"


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def create_subscription_table() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bilibili_dynamic_subscription (
                group_id INTEGER NOT NULL,
                uid INTEGER NOT NULL,
                up_name TEXT NOT NULL DEFAULT '',
                filter_types TEXT NOT NULL DEFAULT '[]',
                filter_regex TEXT NOT NULL DEFAULT '[]',
                recent_ids TEXT NOT NULL DEFAULT '[]',
                is_live INTEGER NOT NULL DEFAULT 0,
                at_all INTEGER NOT NULL DEFAULT 0,
                live_atall INTEGER NOT NULL DEFAULT 0,
                at_users TEXT NOT NULL DEFAULT '[]',
                next_poll_time INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (group_id, uid)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bilibili_credential (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cookies TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )


def _json_list(value: Any) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _request_headers() -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
    }
    saved_cookies = _load_saved_cookies()
    cookie = _cookies_to_header(saved_cookies)
    if not cookie:
        cookie = str(load_static_setting("bilibili_cookie", "") or "").strip()
    sessdata = str(load_static_setting("bilibili_sessdata", "") or "").strip()
    if cookie:
        headers["Cookie"] = cookie
    elif sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    return headers


def _load_saved_cookies() -> dict[str, str]:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT cookies FROM bilibili_credential WHERE id=1"
            ).fetchone()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    try:
        value = json.loads(row["cookies"])
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _save_cookies(cookies: dict[str, str]) -> None:
    if not cookies.get("SESSDATA"):
        raise BilibiliAPIError("登录响应中缺少 SESSDATA，无法保存凭据")
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO bilibili_credential (id, cookies, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                cookies=excluded.cookies,
                updated_at=excluded.updated_at
            """,
            (json.dumps(cookies, ensure_ascii=False), now),
        )
        conn.execute(
            "UPDATE bilibili_dynamic_subscription SET next_poll_time=0"
        )


def _cookies_to_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items() if value)


def _login_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _request_headers()["User-Agent"],
            "Referer": "https://www.bilibili.com/",
        }
    )
    timeout = max(3, int(load_static_setting("bilibili_dynamic_request_timeout", 20)))
    try:
        response = session.get(FINGERPRINT_API, timeout=timeout)
        payload = response.json()
        data = payload.get("data") or {}
        if payload.get("code") == 0:
            if data.get("b_3"):
                session.cookies.set("buvid3", str(data["b_3"]), domain=".bilibili.com")
            if data.get("b_4"):
                session.cookies.set("buvid4", str(data["b_4"]), domain=".bilibili.com")
    except Exception as exc:
        logging.warning("获取 Bilibili 设备标识失败，将继续扫码登录: %s", exc)
    return session


def _generate_login_qr(session: requests.Session) -> tuple[str, str]:
    timeout = max(3, int(load_static_setting("bilibili_dynamic_request_timeout", 20)))
    response = session.get(QR_GENERATE_API, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise BilibiliAPIError(payload.get("message") or "申请登录二维码失败")
    data = payload.get("data") or {}
    key = str(data.get("qrcode_key") or "")
    url = str(data.get("url") or "")
    if not key or not url:
        raise BilibiliAPIError("登录二维码响应缺少必要字段")
    return key, url


def _poll_login_qr(session: requests.Session, qrcode_key: str) -> tuple[int, str]:
    timeout = max(3, int(load_static_setting("bilibili_dynamic_request_timeout", 20)))
    response = session.get(
        QR_POLL_API, params={"qrcode_key": qrcode_key}, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise BilibiliAPIError(payload.get("message") or "查询扫码状态失败")
    data = payload.get("data") or {}
    return int(data.get("code", -1)), str(data.get("message") or "")


def _validate_login(session: requests.Session) -> dict[str, Any]:
    timeout = max(3, int(load_static_setting("bilibili_dynamic_request_timeout", 20)))
    response = session.get(NAV_API, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    if payload.get("code") != 0 or not data.get("isLogin"):
        raise BilibiliAPIError("扫码完成，但登录凭据校验失败")
    return data


def _create_qr_image(url: str, path: str) -> None:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("缺少 qrcode 依赖，请重新安装 control/requirements.txt") from exc
    image = qrcode.make(url)
    image.save(path)


async def _send_private_text(websocket, user_id: int, text: str) -> None:
    payload = {
        "action": "send_msg_async",
        "params": {"user_id": user_id, "message": text},
    }
    await websocket.send(json.dumps(payload, ensure_ascii=False))


async def _send_private_qr(
    websocket, user_id: int, message_id: int, text: str, image_path: str
) -> None:
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    payload = {
        "action": "send_msg_async",
        "params": {
            "user_id": user_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {"type": "text", "data": {"text": text}},
                {"type": "image", "data": {"file": f"base64://{encoded}"}},
            ],
        },
    }
    await websocket.send(json.dumps(payload, ensure_ascii=False))


async def _run_login_flow(message: PrivateMesssageInfo, login_lock: asyncio.Lock) -> None:
    if login_lock.locked():
        await _send_private_text(
            message.websocket,
            message.senderId,
            "已有 Bilibili 扫码登录正在进行，请先完成或等待二维码过期",
        )
        return

    async with login_lock:
        qr_path = ""
        try:
            session = await asyncio.to_thread(_login_session)
            qrcode_key, login_url = await asyncio.to_thread(
                _generate_login_qr, session
            )
            fd, qr_path = tempfile.mkstemp(prefix="bilibili-login-", suffix=".png")
            os.close(fd)
            await asyncio.to_thread(_create_qr_image, login_url, qr_path)
            await _send_private_qr(
                message.websocket,
                message.senderId,
                message.messageId,
                "请使用 Bilibili App 扫码并确认登录。二维码约 3 分钟后失效。\n",
                qr_path,
            )

            deadline = time.monotonic() + 180
            confirmed_notice_sent = False
            while time.monotonic() < deadline:
                status, status_message = await asyncio.to_thread(
                    _poll_login_qr, session, qrcode_key
                )
                if status == 0:
                    user_info = await asyncio.to_thread(_validate_login, session)
                    cookies = requests.utils.dict_from_cookiejar(session.cookies)
                    await asyncio.to_thread(_save_cookies, cookies)
                    user_name = str(user_info.get("uname") or "未知用户")
                    user_id = str(user_info.get("mid") or "")
                    identity = f"{user_name}（UID: {user_id}）" if user_id else user_name
                    await _send_private_text(
                        message.websocket,
                        message.senderId,
                        f"✅ Bilibili 登录成功：{identity}\n动态订阅将在下次心跳立即恢复检查。",
                    )
                    return
                if status == 86038:
                    await _send_private_text(
                        message.websocket,
                        message.senderId,
                        "❌ 登录二维码已失效，请重新执行 /bili_login。",
                    )
                    return
                if status == 86090 and not confirmed_notice_sent:
                    confirmed_notice_sent = True
                    await _send_private_text(
                        message.websocket,
                        message.senderId,
                        "已扫码，请在 Bilibili App 中确认登录。",
                    )
                elif status not in (86101, 86090):
                    raise BilibiliAPIError(
                        f"未知扫码状态 {status}: {status_message or '无详细信息'}"
                    )
                await asyncio.sleep(2)

            await _send_private_text(
                message.websocket,
                message.senderId,
                "❌ 登录超时，请重新执行 /bili_login。",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.exception("Bilibili 扫码登录失败")
            await _send_private_text(
                message.websocket,
                message.senderId,
                f"❌ Bilibili 登录失败：{exc}",
            )
        finally:
            if qr_path:
                try:
                    os.unlink(qr_path)
                except FileNotFoundError:
                    pass


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    timeout = max(3, int(load_static_setting("bilibili_dynamic_request_timeout", 20)))
    response = requests.get(url, params=params, headers=_request_headers(), timeout=timeout)
    if response.status_code == 412:
        raise BilibiliAPIError(
            "Bilibili 风控拦截了请求（HTTP 412）；"
            "请私聊执行 /bili_login，或在 static_setting.json 配置有效的 bilibili_cookie"
        )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        code = payload.get("code")
        message = payload.get("message") or payload.get("msg") or "未知错误"
        hint = (
            "；请私聊执行 /bili_login，或配置有效的 bilibili_cookie"
            if code in (-101, -352)
            else ""
        )
        raise BilibiliAPIError(f"Bilibili API 返回 {code}: {message}{hint}")
    return payload.get("data") or {}


def fetch_dynamics(uid: int) -> tuple[str, list[DynamicItem]]:
    data = _get_json(DYNAMIC_API, {"host_mid": uid, "offset": ""})
    result: list[DynamicItem] = []
    up_name = ""
    for raw in data.get("items") or []:
        parsed = _parse_dynamic(raw)
        if parsed is not None:
            result.append(parsed)
            up_name = up_name or parsed.up_name
    return up_name, result


def fetch_live(uid: int) -> dict[str, Any] | None:
    data = _get_json(LIVE_API, {"mid": uid})
    if not data:
        return None
    return {
        "is_live": int(data.get("liveStatus") or 0) == 1,
        "title": str(data.get("title") or "直播中"),
        "room_id": str(data.get("roomid") or ""),
        "url": str(data.get("url") or ""),
    }


async def fetch_dynamics_async(uid: int) -> tuple[str, list[DynamicItem]]:
    return await asyncio.to_thread(fetch_dynamics, uid)


async def fetch_live_async(uid: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(fetch_live, uid)


def _parse_dynamic(raw: dict[str, Any]) -> DynamicItem | None:
    dyn_id = str(raw.get("id_str") or raw.get("id") or "")
    if not dyn_id:
        return None
    dyn_type = str(raw.get("type") or "")
    modules = raw.get("modules") or {}
    author = modules.get("module_author") or {}
    dynamic = modules.get("module_dynamic") or {}
    major = dynamic.get("major") or {}
    desc = dynamic.get("desc") or {}

    up_name = str(author.get("name") or "未知UP主")
    text = str(desc.get("text") or "").strip()
    title = ""
    images: list[str] = []
    major_type = str(major.get("type") or "")

    if major_type == "MAJOR_TYPE_ARCHIVE":
        archive = major.get("archive") or {}
        title = str(archive.get("title") or "")
        text = text or str(archive.get("desc") or "")
        if archive.get("cover"):
            images.append(str(archive["cover"]))
    elif major_type == "MAJOR_TYPE_DRAW":
        draw = major.get("draw") or {}
        images.extend(str(pic.get("src")) for pic in draw.get("items") or [] if pic.get("src"))
    elif major_type == "MAJOR_TYPE_ARTICLE":
        article = major.get("article") or {}
        title = str(article.get("title") or "")
        text = text or str(article.get("desc") or "")
        images.extend(str(url) for url in article.get("covers") or [] if url)
    elif major_type == "MAJOR_TYPE_OPUS":
        opus = major.get("opus") or {}
        title = str(opus.get("title") or "")
        summary = opus.get("summary") or {}
        text = text or str(summary.get("text") or "")
        images.extend(str(pic.get("url")) for pic in opus.get("pics") or [] if pic.get("url"))

    additional = dynamic.get("additional") or {}
    additional_type = str(additional.get("type") or "")
    combined = f"{title}\n{text}"
    is_lottery = additional_type == "ADDITIONAL_TYPE_UPOWER_LOTTERY" or bool(
        re.search(r"互动抽奖|转发抽奖|抽奖详情", combined)
    )
    return DynamicItem(dyn_id, dyn_type, up_name, text, title, images, is_lottery)


def _is_filtered(item: DynamicItem, filter_types: list[str], filter_regex: list[str]) -> bool:
    item_filter = TYPE_TO_FILTER.get(item.dyn_type)
    if item_filter and item_filter in filter_types:
        return True
    if item.is_lottery and "lottery" in filter_types:
        return True
    if item.dyn_type == "DYNAMIC_TYPE_FORWARD" and item.is_lottery and "forward_lottery" in filter_types:
        return True
    content = f"{item.title}\n{item.text}"
    for pattern in filter_regex:
        try:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        except re.error:
            logging.warning("跳过无效的 Bilibili 动态过滤正则: %s", pattern)
    return False


def _parse_command(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    bot_name = str(load_static_setting("bot_name", "乐可") or "").strip()
    has_bot_name = bool(bot_name and stripped.startswith(bot_name))
    if has_bot_name:
        stripped = stripped[len(bot_name):].lstrip(" ，,：:")
        commands = (
            ("login", r"B站登录"),
            ("list", r"订阅列表"),
            ("delete", r"订阅删除"),
            ("subscribe", r"订阅动态"),
        )
    else:
        commands = (
            ("login", r"/bili_login"),
            ("list", r"/bili_sub_list"),
            ("delete", r"/bili_sub_del"),
            ("subscribe", r"/bili_sub"),
        )
    for name, pattern in commands:
        match = re.fullmatch(pattern + r"(?:\s+(.*))?", stripped, re.IGNORECASE)
        if match:
            return name, (match.group(1) or "").strip()
    return None


def _parse_sub_args(raw: str) -> tuple[int, list[str], list[str], set[str]]:
    parts = raw.split()
    if not parts or not parts[0].isdigit():
        raise ValueError("请提供正确的 B站 UID")
    uid = int(parts[0])
    if uid <= 0:
        raise ValueError("UID 必须是正整数")
    filter_types: list[str] = []
    filter_regex: list[str] = []
    options: set[str] = set()
    for value in parts[1:]:
        lowered = value.lower()
        if lowered in TYPE_FILTERS:
            filter_types.append(lowered)
        elif lowered in {"at_all", "live_atall", "at_sub", "unat_sub"}:
            options.add(lowered)
        else:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"无效正则表达式 {value!r}: {exc}") from exc
            filter_regex.append(value)
    return uid, list(dict.fromkeys(filter_types)), list(dict.fromkeys(filter_regex)), options


async def _send_group_segments(websocket, group_id: int, segments: list[dict[str, Any]]) -> None:
    payload = {
        "action": "send_msg_async",
        "params": {"group_id": group_id, "message": segments},
    }
    await websocket.send(json.dumps(payload, ensure_ascii=False))


def _at_segments(row: sqlite3.Row, live: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if bool(row["at_all"]) or (live and bool(row["live_atall"])):
        result.append({"type": "at", "data": {"qq": "all"}})
    for user_id in _json_list(row["at_users"]):
        result.append({"type": "at", "data": {"qq": user_id}})
    if result:
        result.append({"type": "text", "data": {"text": "\n"}})
    return result


async def _push_dynamic(websocket, row: sqlite3.Row, item: DynamicItem) -> None:
    action = TYPE_LABELS.get(item.dyn_type, "发布了新动态")
    body_parts = [f"📣 UP主「{item.up_name or row['up_name']}」{action}"]
    if item.title:
        body_parts.append(item.title)
    if item.text and item.text != item.title:
        max_length = max(100, int(load_static_setting("bilibili_dynamic_text_limit", 500)))
        body_parts.append(item.text[:max_length] + ("…" if len(item.text) > max_length else ""))
    body_parts.append(item.url)
    segments = _at_segments(row)
    segments.append({"type": "text", "data": {"text": "\n".join(body_parts)}})
    for image_url in item.images[:3]:
        segments.append({"type": "image", "data": {"file": image_url}})
    await _send_group_segments(websocket, int(row["group_id"]), segments)


async def _push_live(websocket, row: sqlite3.Row, live: dict[str, Any]) -> None:
    name = row["up_name"] or str(row["uid"])
    url = live.get("url") or (
        f"https://live.bilibili.com/{live['room_id']}" if live.get("room_id") else ""
    )
    text = f"🔴 UP主「{name}」开播了！\n{live.get('title') or '直播中'}"
    if url:
        text += f"\n{url}"
    segments = _at_segments(row, live=True)
    segments.append({"type": "text", "data": {"text": text}})
    await _send_group_segments(websocket, int(row["group_id"]), segments)


class BilibiliDynamicSubscriptionApplication(GroupMessageApplication):
    def __init__(self):
        info = ApplicationInfo(
            "B站动态订阅",
            "订阅 UP 主动态与直播并自动推送",
            trigger="bot名 + 中文指令，或 /bili_sub 等斜杠指令",
            detail=(
                "过滤器支持 forward、lottery、video、article、draw、live、"
                "forward_lottery 和正则表达式；at_sub 可让推送时 @自己。"
            ),
            category="实用",
        )
        super().__init__(info, 70, False, ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE)
        create_subscription_table()

    def judge(self, message: GroupMessageInfo) -> bool:
        return _parse_command(message.plainTextMessage) is not None

    async def process(self, message: GroupMessageInfo):
        parsed = _parse_command(message.plainTextMessage)
        if parsed is None:
            return
        command, args = parsed
        if command == "login":
            await self._login(message)
        elif command == "list":
            await self._list(message)
        elif command == "delete":
            await self._delete(message, args)
        else:
            await self._subscribe(message, args)

    async def _login(self, message: GroupMessageInfo) -> None:
        await ReplySay(
            message.websocket,
            message.groupId,
            message.messageId,
            "为避免登录二维码泄露，请由机器人开发者私聊机器人执行 /bili_login。",
        )

    async def _subscribe(self, message: GroupMessageInfo, args: str) -> None:
        try:
            uid, filter_types, filter_regex, options = _parse_sub_args(args)
        except ValueError as exc:
            await ReplySay(message.websocket, message.groupId, message.messageId, str(exc))
            return
        if {"at_all", "live_atall"} & options and not IsAdmin(message.senderId, message.groupId):
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                "权限不足：只有群管理员可以设置 at_all 或 live_atall",
            )
            return

        try:
            up_name, dynamics = await fetch_dynamics_async(uid)
        except Exception as exc:
            logging.error("初始化 Bilibili 动态订阅失败 UID=%s: %s", uid, exc)
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                f"订阅失败：无法获取该 UID 的动态（{exc}）",
            )
            return
        try:
            live = await fetch_live_async(uid)
        except Exception as exc:
            logging.warning("初始化 Bilibili 直播状态失败 UID=%s: %s", uid, exc)
            live = None

        now = int(time.time())
        recent_ids = [item.dyn_id for item in dynamics]
        is_live = int(bool(live and live.get("is_live")))
        with _connect() as conn:
            old = conn.execute(
                "SELECT * FROM bilibili_dynamic_subscription WHERE group_id=? AND uid=?",
                (message.groupId, uid),
            ).fetchone()
            at_users = set(_json_list(old["at_users"]) if old else [])
            if "at_sub" in options:
                at_users.add(str(message.senderId))
            if "unat_sub" in options:
                at_users.discard(str(message.senderId))
            at_all = int("at_all" in options) if (not old or "at_all" in options) else int(old["at_all"])
            live_atall = int("live_atall" in options) if (not old or "live_atall" in options) else int(old["live_atall"])
            conn.execute(
                """
                INSERT INTO bilibili_dynamic_subscription
                    (group_id, uid, up_name, filter_types, filter_regex, recent_ids,
                     is_live, at_all, live_atall, at_users, next_poll_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id, uid) DO UPDATE SET
                    up_name=excluded.up_name,
                    filter_types=excluded.filter_types,
                    filter_regex=excluded.filter_regex,
                    recent_ids=excluded.recent_ids,
                    is_live=excluded.is_live,
                    at_all=excluded.at_all,
                    live_atall=excluded.live_atall,
                    at_users=excluded.at_users,
                    next_poll_time=excluded.next_poll_time,
                    updated_at=excluded.updated_at
                """,
                (
                    message.groupId, uid, up_name or (old["up_name"] if old else ""),
                    json.dumps(filter_types, ensure_ascii=False),
                    json.dumps(filter_regex, ensure_ascii=False),
                    json.dumps(recent_ids, ensure_ascii=False), is_live, at_all,
                    live_atall, json.dumps(sorted(at_users)), now, now, now,
                ),
            )

        filters = filter_types + filter_regex
        suffix = f"\n过滤条件：{'、'.join(filters)}" if filters else ""
        action = "更新" if old else "订阅"
        await ReplySay(
            message.websocket,
            message.groupId,
            message.messageId,
            f"{action}成功：{up_name or uid}（UID: {uid}）{suffix}",
        )

    async def _list(self, message: GroupMessageInfo) -> None:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bilibili_dynamic_subscription WHERE group_id=? ORDER BY created_at, uid",
                (message.groupId,),
            ).fetchall()
        if not rows:
            text = "本群暂无 B站动态订阅"
        else:
            lines = ["本群 B站动态订阅："]
            for index, row in enumerate(rows, 1):
                filters = _json_list(row["filter_types"]) + _json_list(row["filter_regex"])
                extra = f"｜过滤：{'、'.join(filters)}" if filters else ""
                if row["at_all"]:
                    extra += "｜@全体"
                if _json_list(row["at_users"]):
                    extra += "｜@订阅者"
                lines.append(f"{index}. {row['up_name'] or '未知UP主'}（{row['uid']}）{extra}")
            text = "\n".join(lines)
        await ReplySay(message.websocket, message.groupId, message.messageId, text)

    async def _delete(self, message: GroupMessageInfo, args: str) -> None:
        uid_text = args.split(maxsplit=1)[0] if args else ""
        if not uid_text.isdigit():
            await ReplySay(message.websocket, message.groupId, message.messageId, "请提供正确的 B站 UID")
            return
        with _connect() as conn:
            cursor = conn.execute(
                "DELETE FROM bilibili_dynamic_subscription WHERE group_id=? AND uid=?",
                (message.groupId, int(uid_text)),
            )
        text = "删除成功" if cursor.rowcount else "未找到指定的订阅"
        await ReplySay(message.websocket, message.groupId, message.messageId, text)


class BilibiliLoginApplication(PrivateMessageApplication):
    """仅允许机器人开发者在私聊中完成 Bilibili 扫码登录。"""

    def __init__(self):
        info = ApplicationInfo(
            "B站扫码登录",
            "通过私聊二维码登录 Bilibili",
            can_display=False,
        )
        super().__init__(info, 70, False, ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE)
        create_subscription_table()
        self._login_lock = asyncio.Lock()

    def judge(self, message: PrivateMesssageInfo) -> bool:
        parsed = _parse_command(message.plainTextMessage)
        return parsed is not None and parsed[0] == "login"

    async def process(self, message: PrivateMesssageInfo):
        if not IsDeveloper(message.senderId):
            await _send_private_text(
                message.websocket,
                message.senderId,
                "权限不足：仅机器人开发者可以执行 /bili_login",
            )
            return
        await _run_login_flow(message, self._login_lock)


class BilibiliDynamicPushApplication(MetaMessageApplication):
    def __init__(self):
        info = ApplicationInfo("B站动态推送", "后台轮询并推送已订阅的 B站动态", can_display=False)
        super().__init__(info, 6, True, ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE)
        create_subscription_table()
        self._last_heartbeat = 0.0
        self._lock = asyncio.Lock()

    def judge(self, message: MetaMessageInfo) -> bool:
        return message.metaEventType == MetaEventType.HEART_BEAT

    async def process(self, message: MetaMessageInfo):
        throttle = max(5, int(load_static_setting("bilibili_dynamic_heartbeat_throttle", 30)))
        now = time.time()
        if now - self._last_heartbeat < throttle or self._lock.locked():
            return
        self._last_heartbeat = now
        async with self._lock:
            await self._poll(message.websocket, int(now))

    async def _poll(self, websocket, now: int) -> None:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bilibili_dynamic_subscription WHERE next_poll_time<=? ORDER BY uid",
                (now,),
            ).fetchall()
        if not rows:
            return
        grouped: dict[int, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(int(row["uid"]), []).append(row)

        interval = max(30, int(load_static_setting("bilibili_dynamic_check_interval", 300)))
        for uid, targets in grouped.items():
            try:
                up_name, dynamics = await fetch_dynamics_async(uid)
            except Exception as exc:
                logging.error("轮询 Bilibili 动态失败 UID=%s: %s", uid, exc)
                self._set_next_poll(targets, now + min(interval, 60))
                continue
            try:
                live = await fetch_live_async(uid)
            except Exception as exc:
                logging.warning("轮询 Bilibili 直播状态失败 UID=%s: %s", uid, exc)
                live = None
            for row in targets:
                try:
                    await self._process_target(websocket, row, up_name, dynamics, live, now, interval)
                except Exception:
                    logging.exception("推送 Bilibili 动态失败 group=%s uid=%s", row["group_id"], uid)

    @staticmethod
    def _set_next_poll(rows: list[sqlite3.Row], next_poll: int) -> None:
        with _connect() as conn:
            conn.executemany(
                "UPDATE bilibili_dynamic_subscription SET next_poll_time=? WHERE group_id=? AND uid=?",
                [(next_poll, row["group_id"], row["uid"]) for row in rows],
            )

    async def _process_target(
        self,
        websocket,
        row: sqlite3.Row,
        up_name: str,
        dynamics: list[DynamicItem],
        live: dict[str, Any] | None,
        now: int,
        interval: int,
    ) -> None:
        recent = _json_list(row["recent_ids"])
        recent_set = set(recent)
        if recent:
            new_items = [item for item in dynamics if item.dyn_id not in recent_set]
        else:
            new_items = []
        limit = max(1, int(load_static_setting("bilibili_dynamic_limit", 5)))
        filter_types = _json_list(row["filter_types"])
        filter_regex = _json_list(row["filter_regex"])
        for item in reversed(new_items[:limit]):
            if not _is_filtered(item, filter_types, filter_regex):
                await _push_dynamic(websocket, row, item)

        was_live = bool(row["is_live"])
        is_live = bool(live.get("is_live")) if live is not None else was_live
        if is_live and not was_live and "live" not in filter_types:
            await _push_live(websocket, row, live or {})

        cache_size = max(5, int(load_static_setting("bilibili_recent_dynamic_cache", 30)))
        latest_ids = [item.dyn_id for item in dynamics]
        merged_ids = list(dict.fromkeys(latest_ids + recent))[:cache_size]
        with _connect() as conn:
            conn.execute(
                """
                UPDATE bilibili_dynamic_subscription
                SET up_name=?, recent_ids=?, is_live=?, next_poll_time=?, updated_at=?
                WHERE group_id=? AND uid=?
                """,
                (
                    up_name or row["up_name"], json.dumps(merged_ids), int(is_live),
                    now + interval, now, row["group_id"], row["uid"],
                ),
            )
