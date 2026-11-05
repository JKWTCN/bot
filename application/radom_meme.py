import base64
import json
import logging
import asyncio
from io import BytesIO
import random
import re
from pathlib import Path

from PIL import Image
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayGroup
from function.group_message_guard import send_group_request
from tools.tools import FindNum, HasAllKeyWords, load_setting
from tools.file_list_cache import file_cache


async def SendSingleMeme(websocket, groupId: int):
    try:
        # 使用缓存获取文件列表（30分钟内不重复扫描）
        all_file = await file_cache.get_image_files(load_setting("meme_path", ""))
        logging.info("读取目录完毕")

        payload = {
            "action": "send_forward_msg",
            "params": {
                "message_type": "group",
                "group_id": groupId,
                "message": [],
            },
        }

        # 异步读取图片（不阻塞事件循环）
        dir = random.choice(all_file)
        loop = asyncio.get_event_loop()
        image_data = await loop.run_in_executor(None, lambda: open(dir, "rb").read())
        image_base64 = base64.b64encode(image_data)

        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            }
        )
        await websocket.send(json.dumps(payload))
    except Exception as e:
        logging.error(e)
        await SayGroup(websocket, groupId, f"图片发送失败了喵。")


def _meme_response_summary(result) -> str:
    """仅提取诊断字段，不把响应中的消息体或图片写入日志。"""
    if not isinstance(result, dict):
        return f"响应格式错误: {type(result).__name__}"
    details = {
        key: result.get(key)
        for key in ("status", "retcode", "message", "wording")
    }
    data = result.get("data")
    details["message_id"] = data.get("message_id") if isinstance(data, dict) else None
    summary = json.dumps(details, ensure_ascii=False)
    summary = re.sub(r"base64://[A-Za-z0-9+/=]+", "base64://[omitted]", summary)
    return summary[:1500]


class _MemeAPIError(RuntimeError):
    def __init__(self, action: str, result):
        super().__init__(f"{action} 未返回发送成功结果: {_meme_response_summary(result)}")
        # 仅明确的图片错误允许拆分。鉴权、连接故障或缺少回执不应
        # 被当作坏图逐张重发，尤其超时后的消息可能已经送达。
        self.image_failure = False
        if isinstance(result, dict) and result.get("status") == "failed":
            description = " ".join(str(result.get(key) or "") for key in ("message", "wording")).lower()
            self.image_failure = any(marker in description for marker in (
                "rich media transfer failed", "invalid image", "image upload",
                "unsupported image", "图片格式", "图片损坏", "图片上传失败",
                "无法读取图片", "上传资源失败", "上传转发消息资源失败",
                "file not found", "enoent",
            ))


def _read_meme_image(path: str) -> dict:
    image_data = Path(path).read_bytes()
    with Image.open(BytesIO(image_data)) as image:
        image.verify()
    # verify 不解码 JPEG 像素，再解码一次以过滤截断等错误。
    with Image.open(BytesIO(image_data)) as image:
        image.load()
    return {
        "type": "image",
        "data": {"file": "base64://" + base64.b64encode(image_data).decode("ascii")},
    }


def _send_meme_request(action: str, params: dict) -> bool:
    """使用有返回值的 HTTP 接口，避免把 WebSocket 写入成功当作发送成功。"""
    result = send_group_request(action, params)
    if result is None:
        return False
    if (
        not isinstance(result, dict)
        or result.get("status") != "ok"
        or result.get("retcode") != 0
        or not isinstance(result.get("data"), dict)
        or not result["data"].get("message_id")
    ):
        raise _MemeAPIError(action, result)
    logging.info(
        "梗图发送接口成功: action=%s group_id=%s message_id=%s",
        action, params.get("group_id"), result["data"]["message_id"],
    )
    return True


async def _send_meme_images(group_id: int, items: list) -> int:
    """图片错误时拆分失败批次；跳过失败单图，已成功批次不再发送。"""
    pending = [items]
    sent_count = 0
    while pending:
        batch = pending.pop()
        try:
            sent = await asyncio.to_thread(
                _send_meme_request,
                "send_group_msg",
                {"group_id": group_id, "message": [image for _, image in batch]},
            )
            if not sent:
                break
        except Exception as error:
            if isinstance(error, _MemeAPIError) and error.image_failure:
                if len(batch) == 1:
                    logging.warning(
                        "跳过发送失败的梗图: group_id=%s path=%s error=%s",
                        group_id, batch[0][0], error,
                    )
                else:
                    logging.warning(
                        "梗图多图消息图片传输失败，拆分批次继续发送: group_id=%s count=%s error=%s",
                        group_id, len(batch), error,
                    )
                    middle = len(batch) // 2
                    # 栈先放右半批，确保成功发送的图片仍保持原来的顺序。
                    pending.extend([batch[middle:], batch[:middle]])
                continue
            if not sent_count:
                raise
            logging.error(
                "梗图发送中断，保留已成功张数: group_id=%s sent=%s error=%s",
                group_id, sent_count, error,
            )
            break
        sent_count += len(batch)
    return sent_count


async def SendMemeMergeForwarding(websocket, group_id: int, nums: int) -> int:
    """优先合并转发，失败后发送普通多图消息并跳过坏图，返回成功张数。"""
    try:
        # 使用缓存获取文件列表（已过滤扩展名，30分钟内不重复扫描）
        all_file = await file_cache.get_image_files(load_setting("meme_path", ""))
        logging.info("读取目录完毕")

        # 确保不超过可用文件数量
        actual_nums = min(nums, len(all_file))
        if actual_nums <= 0:
            await SayGroup(websocket, group_id, "没有可发送的梗图喵。")
            return 0

        # 使用 random.sample() 单次多连内无重复选择
        selected_files = random.sample(all_file, actual_nums)
        items = []
        for path in selected_files:
            try:
                image = await asyncio.to_thread(_read_meme_image, path)
            except Exception as error:
                logging.warning("跳过无法读取或损坏的梗图: path=%s error=%s", path, error)
                continue
            items.append((path, image))
        if not items:
            await SayGroup(websocket, group_id, "选中的梗图都无法读取或已损坏喵。")
            return 0
        images = [image for _, image in items]

        nodes = [
            {
                "type": "node",
                "data": {
                    "user_id": load_setting("bot_id", 0),
                    "nickname": "乐可",
                    "content": [image],
                },
            }
            for image in images
        ]
        try:
            sent = await asyncio.to_thread(
                _send_meme_request,
                "send_forward_msg",
                {
                    "message_type": "group",
                    "group_id": group_id,
                    "messages": nodes,
                },
            )
        except Exception as error:
            logging.warning(
                "梗图合并转发失败，回退为单条多图消息: group_id=%s error=%s",
                group_id, error,
            )
            sent_count = await _send_meme_images(group_id, items)
            if not sent_count:
                await SayGroup(websocket, group_id, "图片发送失败了喵。")
            logging.info(
                "梗图发送完成: group_id=%s selected=%s sent=%s unsent=%s",
                group_id, actual_nums, sent_count, actual_nums - sent_count,
            )
            return sent_count
        return len(items) if sent else 0
    except Exception:
        logging.exception("梗图发送失败: group_id=%s", group_id)
        await SayGroup(websocket, group_id, "图片发送失败了喵。")
        return 0


class RadomMemeApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("随机梗图功能", "触发:梗图X连")
        super().__init__(applicationInfo, 10, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        num = FindNum(message.plainTextMessage)
        import math

        num = math.trunc(num)
        if num > 50:
            await SayGroup(
                message.websocket,
                message.groupId,
                "最大50连喵！",
            )
        elif num == -1:
            await SendSingleMeme(message.websocket, message.groupId)
        else:
            nums = num
            sent_nums = await SendMemeMergeForwarding(
                message.websocket,
                message.groupId,
                nums,
            )
            if sent_nums:
                await SayGroup(
                    message.websocket,
                    message.groupId,
                    "梗图{}连发货了喵，请好好享用喵。".format(sent_nums),
                )

    def judge(self, message: GroupMessageInfo) -> bool:
        """判断消息是否符合触发条件"""
        return HasAllKeyWords(
            message.plainTextMessage, [load_setting("bot_name", "乐可"), "梗图"]
        )
