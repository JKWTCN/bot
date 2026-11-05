"""统一检查群消息发送资格，查询失败时跳过本次发送。"""

import asyncio
from collections import OrderedDict
import json
import logging
import threading
import time
import uuid

import requests


def _napcat_url(action: str) -> str:
    # 延迟导入，避免发送守卫依赖工具模块的其他初始化逻辑。
    from tools.tools import GetNCHSPort

    return f"http://localhost:{GetNCHSPort()}/{action}"


def _fetch_group_ids() -> set[int]:
    response = requests.post(
        _napcat_url("get_group_list"),
        json={"no_cache": True},
        timeout=(3, 5),
    )
    response.raise_for_status()
    result = response.json()
    if (
        not isinstance(result, dict)
        or result.get("status") != "ok"
        or result.get("retcode") != 0
        or not isinstance(result.get("data"), list)
    ):
        raise ValueError("get_group_list 未返回有效群列表")
    return {int(group["group_id"]) for group in result["data"]}


class GroupMembershipCache:
    """跨 HTTP/WS、线程共享的群列表；通知更新不等待网络查询。"""

    def __init__(self, ttl=60.0, retry_seconds=5.0, clock=time.monotonic):
        self._ttl = ttl
        self._retry_seconds = retry_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._groups = None
        self._expires_at = 0.0
        self._retry_at = 0.0
        self._last_error = ""
        self._updates = {}
        self._generation = 0

    def _cached_result(self, group_id):
        """调用者持有状态锁；None 表示需要刷新，不代表不在群。"""
        now = self._clock()
        update = self._updates.get(group_id)
        if update is not None and now < update[1]:
            return update[0]
        if self._groups is not None and now < self._expires_at:
            return group_id in self._groups
        if now < self._retry_at:
            raise ValueError(self._last_error)
        return None

    def contains(self, group_id: int) -> bool:
        with self._lock:
            result = self._cached_result(group_id)
        if result is not None:
            return result

        # 合并并发刷新；网络请求期间释放状态锁，使退群通知立即生效。
        with self._refresh_lock:
            with self._lock:
                result = self._cached_result(group_id)
                if result is not None:
                    return result
                generation = self._generation
            try:
                groups = _fetch_group_ids()
            except (requests.RequestException, ValueError, TypeError, KeyError) as error:
                with self._lock:
                    if generation == self._generation:
                        # 失败时禁止沿用过期的在群结果，并短暂缓存错误。
                        self._groups = None
                        self._retry_at = self._clock() + self._retry_seconds
                        self._last_error = str(error)
                raise
            with self._lock:
                if generation == self._generation:
                    now = self._clock()
                    self._updates = {
                        key: update for key, update in self._updates.items()
                        if now < update[1]
                    }
                    # 通知优先于刷新结果，防止正在查询的旧名单覆盖退群/入群。
                    for key, (present, _) in self._updates.items():
                        if present:
                            groups.add(key)
                        else:
                            groups.discard(key)
                    self._groups = groups
                    self._expires_at = now + self._ttl
                    self._retry_at = 0.0
                    self._last_error = ""
                result = self._cached_result(group_id)
                if result is None:
                    raise ValueError("查询期间连接已重建，群列表需要重新确认")
                return result

    def update(self, group_id: int, present: bool):
        with self._lock:
            self._updates[group_id] = (present, self._clock() + self._ttl)
            if self._groups is not None:
                if present:
                    self._groups.add(group_id)
                else:
                    self._groups.discard(group_id)

    def invalidate(self):
        with self._lock:
            self._generation += 1
            self._groups = None
            self._expires_at = self._retry_at = 0.0
            self._updates.clear()
            self._last_error = ""


_membership_cache = GroupMembershipCache()


def update_group_membership(event: dict):
    """在应用处理通知之前更新，只采用机器人本人进退群的事件。"""
    if event.get("post_type") == "meta_event":
        if event.get("meta_event_type") == "lifecycle" and event.get("sub_type") == "connect":
            _membership_cache.invalidate()
        return
    if event.get("post_type") != "notice":
        return
    notice_type = event.get("notice_type")
    leaving = notice_type == "group_decrease" or (
        notice_type == "notify" and event.get("sub_type") == "leave"
    )
    if not leaving and notice_type != "group_increase":
        return
    try:
        group_id = int(event["group_id"])
        bot_id = int(event["self_id"])
        if group_id <= 0 or bot_id <= 0 or int(event["user_id"]) != bot_id:
            return
    except (KeyError, ValueError, TypeError):
        return
    present = notice_type == "group_increase"
    _membership_cache.update(group_id, present)
    logging.info("群发送缓存更新: group_id=%s 机器人%s", group_id, "入群" if present else "离群")


def can_send_group(group_id, *, action: str = "send_group_msg") -> bool:
    """优先使用短期缓存，过期后刷新；进退群通知立即更新缓存。"""
    try:
        target = int(group_id)
        if target <= 0:
            raise ValueError("无效群号")
        present = _membership_cache.contains(target)
    except (requests.RequestException, ValueError, TypeError, KeyError) as error:
        logging.warning(
            "跳过群消息: action=%s group_id=%s 无法确认机器人在群内: %s",
            action, group_id, error,
        )
        return False

    if not present:
        logging.info(
            "跳过群消息: action=%s group_id=%s 机器人不在该群",
            action, group_id,
        )
        return False
    return True


def _is_group_removed_error(result) -> bool:
    if not isinstance(result, dict) or result.get("status") in ("ok", "async"):
        return False
    details = [result]
    if isinstance(result.get("data"), dict):
        details.append(result["data"])
    # NapCat 会将 QQ 的 result 包装在外层 retcode=1200/200 的错误文字中。
    for key in ("message", "wording"):
        text = result.get(key)
        if not isinstance(text, str):
            continue
        text = text.rsplit("EventRet:", 1)[-1].lstrip()
        try:
            detail, _ = json.JSONDecoder().raw_decode(text)
        except ValueError:
            continue
        if isinstance(detail, dict):
            details.append(detail)
    return any(
        str(detail.get(key)) == "110"
        for detail in details for key in ("result", "retcode")
    )


def record_group_send_result(group_id, result):
    """仅明确的 QQ 110 错误更新离群状态，其他发送错误不移除群。"""
    if not _is_group_removed_error(result):
        return
    try:
        target = int(group_id)
        if target <= 0:
            return
    except (TypeError, ValueError):
        return
    _membership_cache.update(target, False)
    logging.warning("群发送缓存更新: group_id=%s QQ 返回 110，标记机器人已离群", target)


def send_group_request(action: str, params: dict, *, timeout=(5, 30)) -> dict | None:
    """有返回值的 HTTP 群消息入口；跳过时返回 None，不伪造发送成功。"""
    if not can_send_group(params.get("group_id"), action=action):
        return None
    response = requests.post(_napcat_url(action), json=params, timeout=timeout)
    response.raise_for_status()
    result = response.json()
    record_group_send_result(params.get("group_id"), result)
    return result


def _group_message_target(payload: dict):
    action = payload.get("action", "")
    params = payload.get("params", {})
    if not isinstance(action, str) or not isinstance(params, dict):
        return None
    for suffix in ("_async", "_sync", "_rate_limited"):
        if action.endswith(suffix):
            action = action[:-len(suffix)]
            break
    if action.startswith("send_group_") or action == "set_group_sign":
        return params.get("group_id")
    if action in {"send_msg", "send_forward_msg"}:
        if params.get("message_type") != "private":
            return params.get("group_id")
    return None


class GroupCheckedWebSocket:
    """所有应用共用的发送出口，保留原连接的其他属性和方法。"""

    PENDING_RESPONSE_TTL = 300.0
    MAX_PENDING_RESPONSES = 4096

    def __init__(self, websocket, clock=time.monotonic):
        self._websocket = websocket
        self._clock = clock
        self._pending = OrderedDict()

    def __getattr__(self, name):
        return getattr(self._websocket, name)

    def _prune_pending(self):
        now = self._clock()
        while self._pending:
            token, entry = next(iter(self._pending.items()))
            if len(self._pending) <= self.MAX_PENDING_RESPONSES and now < entry[3]:
                break
            self._pending.pop(token)

    def handle_response(self, result: dict):
        """通过唯一 echo 定位发送目标，然后恢复应用原有的 echo。"""
        if "post_type" in result:
            if (result.get("meta_event_type") == "lifecycle"
                    and result.get("sub_type") == "connect"):
                self._pending.clear()
            return
        self._prune_pending()
        token = result.get("echo")
        if not isinstance(token, str):
            return
        entry = self._pending.get(token)
        if entry is None:
            return
        if result.get("status") != "async":
            self._pending.pop(token)
        group_id, had_echo, original_echo, _ = entry
        record_group_send_result(group_id, result)
        if had_echo:
            result["echo"] = original_echo
        else:
            result.pop("echo", None)

    async def send(self, message, *args, **kwargs):
        token = None
        try:
            payload = json.loads(message)
        except (ValueError, TypeError, UnicodeDecodeError):
            payload = None
        if isinstance(payload, dict):
            group_id = _group_message_target(payload)
            if group_id is not None:
                if not await asyncio.to_thread(
                    can_send_group, group_id, action=payload["action"],
                ):
                    return
                token = "group-send:" + uuid.uuid4().hex
                self._pending[token] = (
                    group_id, "echo" in payload, payload.get("echo"),
                    self._clock() + self.PENDING_RESPONSE_TTL,
                )
                self._prune_pending()
                payload["echo"] = token
                encoded = json.dumps(payload, ensure_ascii=False)
                message = encoded.encode("utf-8") if isinstance(message, (bytes, bytearray)) else encoded
        try:
            return await self._websocket.send(message, *args, **kwargs)
        except BaseException:
            if token is not None:
                self._pending.pop(token, None)
            raise
