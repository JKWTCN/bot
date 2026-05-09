import logging
import os
import re

import requests

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.GroupConfig import get_config, set_config
from function.datebase_user import IsAdmin
from function.group_operation import get_reply_image_url
from function.say import ReplySay, ReplySayImage, SayGroup
from tools.tools import HasKeyWords, load_setting


def _bible_image_dir(group_id: int) -> str:
    path = f"groups/{group_id}/bible"
    os.makedirs(path, exist_ok=True)
    return path


def _extract_keywords(text: str) -> list[str]:
    return re.findall(r"\(([^)]+)\)", text)


class BibleManageApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "圣经管理", "绑定/解绑/列出群圣经关键词与图片"
        )
        super().__init__(applicationInfo, 100, False, ApplicationCostType.NORMAL)

    def judge(self, message: GroupMessageInfo) -> bool:
        bot_name = load_setting("bot_name", "乐可")
        return HasKeyWords(message.plainTextMessage, [bot_name]) and HasKeyWords(
            message.plainTextMessage, ["圣经绑定", "圣经解绑", "圣经列表"]
        )

    async def process(self, message: GroupMessageInfo):
        text = message.plainTextMessage
        group_id = message.groupId
        sender_id = message.senderId
        websocket = message.websocket
        message_id = message.messageId

        if "圣经绑定" in text:
            await self._bind(websocket, group_id, sender_id, message_id, message.replyMessageId, text)
        elif "圣经解绑" in text:
            await self._unbind(websocket, group_id, sender_id, message_id, text)
        elif "圣经列表" in text:
            await self._list(websocket, group_id, message_id)

    async def _bind(self, websocket, group_id, sender_id, message_id, reply_message_id, text):
        if not IsAdmin(sender_id, group_id):
            await ReplySay(websocket, group_id, message_id, "只有管理员才能绑定圣经喵。")
            return

        if reply_message_id == -1:
            await ReplySay(websocket, group_id, message_id, "请引用一条含图片的消息来绑定喵。")
            return

        keywords = _extract_keywords(text)
        if not keywords:
            await ReplySay(websocket, group_id, message_id, "请用括号指定关键词，例如：(草)(我草) 喵。")
            return

        image_url = get_reply_image_url(reply_message_id)
        if image_url is None:
            await ReplySay(websocket, group_id, message_id, "引用的消息里没有图片喵。")
            return

        # 下载图片，以第一个关键词命名
        image_dir = _bible_image_dir(group_id)
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", keywords[0])
        image_path = os.path.join(image_dir, f"{safe_name}.jpg")
        try:
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()
            with open(image_path, "wb") as f:
                f.write(resp.content)
        except Exception as e:
            logging.error(f"圣经图片下载失败: {e}")
            await ReplySay(websocket, group_id, message_id, "图片下载失败了喵，请稍后再试。")
            return

        bible: dict = get_config("bible", group_id) or {}
        for kw in keywords:
            bible[kw] = image_path
        set_config("bible", bible, group_id)

        kw_str = "、".join(f"({kw})" for kw in keywords)
        await ReplySay(websocket, group_id, message_id, f"已绑定关键词 {kw_str} 喵！")

    async def _unbind(self, websocket, group_id, sender_id, message_id, text):
        if not IsAdmin(sender_id, group_id):
            await ReplySay(websocket, group_id, message_id, "只有管理员才能解绑圣经喵。")
            return

        keywords = _extract_keywords(text)
        if not keywords:
            await ReplySay(websocket, group_id, message_id, "请用括号指定要解绑的关键词，例如：(草) 喵。")
            return

        bible: dict = get_config("bible", group_id) or {}
        removed = []
        for kw in keywords:
            if kw not in bible:
                continue
            image_path = bible.pop(kw)
            # 若无其他关键词引用同一文件则删除
            if image_path not in bible.values():
                try:
                    os.remove(image_path)
                except Exception as e:
                    logging.warning(f"圣经图片删除失败: {e}")
            removed.append(kw)

        if not removed:
            await ReplySay(websocket, group_id, message_id, "这些关键词没有绑定记录喵。")
            return

        set_config("bible", bible, group_id)
        kw_str = "、".join(f"({kw})" for kw in removed)
        await ReplySay(websocket, group_id, message_id, f"已解绑关键词 {kw_str} 喵！")

    async def _list(self, websocket, group_id, message_id):
        bible: dict = get_config("bible", group_id) or {}
        if not bible:
            await ReplySay(websocket, group_id, message_id, "本群还没有绑定任何圣经喵。")
            return

        lines = [f"本群圣经关键词列表（共 {len(bible)} 条）："]
        for kw, path in bible.items():
            lines.append(f"  ({kw}) → {os.path.basename(path)}")
        await ReplySay(websocket, group_id, message_id, "\n".join(lines))


class BibleApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo(
            "圣经触发", "群消息命中关键词时回复对应图片"
        )
        super().__init__(applicationInfo, 50, True, ApplicationCostType.NORMAL)

    def judge(self, message: GroupMessageInfo) -> bool:
        bible: dict = get_config("bible", message.groupId) or {}
        if not bible:
            return False
        return any(kw in message.plainTextMessage for kw in bible)

    async def process(self, message: GroupMessageInfo):
        bible: dict = get_config("bible", message.groupId) or {}
        for kw, image_path in bible.items():
            if kw in message.plainTextMessage:
                if os.path.exists(image_path):
                    await ReplySayImage(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        image_path,
                    )
                else:
                    logging.warning(f"圣经图片文件不存在: {image_path}")
                return
