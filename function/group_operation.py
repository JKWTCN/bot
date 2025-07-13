import json
import logging
import sqlite3

import requests

from function.GroupConfig import get_config
from function.say import ReplySay
from function.say import chatNoContext
from function.datebase_user import delete_user_info
from data.message.group_message_info import GroupMessageInfo


from function.datebase_user import get_user_info


def IsInGroup(user_id: int, group_id: int):
    res, user = get_user_info(user_id, group_id)
    return res


# 设置群聊精华信息
async def SetEssenceMsg(websocket, message_id: int):
    payload = {
        "action": "set_essence_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))


# 移除群聊精华信息
async def DeleteEssenceMsg(websocket, message_id: int):
    payload = {
        "action": "delete_essence_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))


def GetGroupMessageSenderId(messageId: int) -> int:
    payload = {
        "message_id": messageId,
    }
    response = requests.post("http://localhost:27433/get_msg", json=payload)
    data = response.json()
    return data["sender"]["user_id"]


# 踢人
async def kick_member(websocket, user_id: int, group_id: int):
    # todo 测试完成后恢复此函数
    # payload = {
    #     "action": "set_group_kick",
    #     "params": {
    #         "user_id": user_id,
    #         "group_id": group_id,
    #     },
    # }
    # # print(payload)
    # delete_user_info(user_id, group_id)
    # await websocket.send(json.dumps(payload))
    logging.info(f"踢人: {user_id} from {group_id}")
    pass


async def delete_msg(websocket, message_id: int):
    print(f"正在撤回消息:message_id{message_id}")
    payload = {
        "action": "delete_msg",
        "params": {
            "message_id": message_id,
        },
    }
    await websocket.send(json.dumps(payload))


async def replyImageMessage(
    websocket, group_id: int, message_id: int, need_replay_message_id: int, text: str
):
    """强制回复图片消息"""
    imageInfo = ""
    try:
        # 连接数据库
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        # 执行查询
        cursor.execute(
            """
            SELECT raw_message 
            FROM group_message 
            WHERE message_id = ?
        """,
            (message_id,),
        )

        # 获取结果
        result = cursor.fetchone()

        if result:
            texts = []
            imageInfo = result[0]
            if imageInfo == "[图片]":
                if get_config("image_parsing", group_id):
                    await ReplySay(
                        websocket,
                        group_id,
                        need_replay_message_id,
                        "图片好像丢了喵,才不是乐可的疏忽喵,最好重新发送图片喵。",
                    )
                else:
                    await ReplySay(
                        websocket,
                        group_id,
                        need_replay_message_id,
                        "本群未开启图片解析功能喵。",
                    )
            else:
                texts.append(imageInfo)
                texts.append(text)
                await ReplySay(
                    websocket,
                    group_id,
                    need_replay_message_id,
                    chatNoContext(texts),
                )
        else:
            await ReplySay(
                websocket,
                group_id,
                need_replay_message_id,
                "此消息还在识别喵,请稍后再回复喵。",
            )

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return None

    finally:
        # 确保连接被关闭
        if conn:
            conn.close()


async def banNormal(websocket, user_id: int, group_id: int, duration: int):
    """禁言群友(对管理无效,也不会提示)"""
    from function.datebase_user import IsAdmin

    if IsAdmin(user_id, group_id):
        pass
    else:
        payload = {
            "action": "set_group_ban",
            "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
        }
        await websocket.send(json.dumps(payload))


async def ban_new(websocket, user_id: int, group_id: int, duration: int):
    from function.datebase_user import IsAdmin

    if IsAdmin(user_id, group_id):
        payload = {
            "action": "send_msg_async",
            "params": {
                "group_id": group_id,
                "message": "我，打管理?真的假的?",
            },
        }
        await websocket.send(json.dumps(payload))
    else:
        payload = {
            "action": "set_group_ban",
            "params": {"group_id": group_id, "user_id": user_id, "duration": duration},
        }
        await websocket.send(json.dumps(payload))


async def ReplySayGroup(websocket, group_id: int, message_id: int, text: str):
    """引用回复

    Args:
        websocket (websocket): 回复的webstocket
        group_id (int): 发言的群号
        message_id (int): 引用回复的消息ID
        text (str): 发言的纯文字内容
    """
    payload = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "reply", "data": {"id": message_id}},
                {
                    "type": "text",
                    "data": {"text": text},
                },
            ],
        },
    }
    await websocket.send(json.dumps(payload))
