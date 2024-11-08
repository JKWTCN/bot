import asyncio
import datetime
import logging
import math
import os
import random
import time
import websockets
import json
from Class.Group_member import (
    Group_member,
    get_user_info,
    get_user_name,
    updata_user_info,
)
from bot_database import (
    add_unwelcome,
    change_point,
    daily_check_in,
    find_point,
    get_last_time_get_group_member_list,
    get_statistics,
    in_unwelcome,
    recharge_privte,
    write_message,
)
from chat import chat
from kohlrabi import BuyKohlrabi, ClearKohlrabi, GetNowPrice, SellKohlrabi, ShowHand
import luck_dog
from easter_egg import (
    cute,
    kfc_v_me_50,
    sex_img,
)
from rankings import ranking_point_payload
from private import cxgl
from group_operate import poor_point, get_group_member_list, kick_member
from random_meme import (
    send_meme_merge_forwarding,
    send_radom_http_cat,
    send_random_meme,
    ten_random_meme,
    twenty_random_meme,
    MemeStatistics,
)

from russian_roulette import russian, russian_pve, russian_pve_shot
from tarot_cards import (
    daily_paper,
    daily_word,
    drawing,
    get_cos,
    photo_new,
    return_trarot_cards,
    radom_waifu,
    radom_real,
    one_word,
)
from tools import dump_setting, load_setting, nomoral_qq_avatar, red_qq_avatar
from vcode import check_validation_timeout, update_vcode, verify, welcome_verify
from welcome_to_newyork import (
    ban_new,
    return_function,
    welcom_new_no_admin,
    welcome_new,
)

import re


async def echo(websocket, path):
    async for message in websocket:
        message = json.loads(message)
        setting = load_setting()
        if "post_type" in message:
            match message["post_type"]:
                case "message":
                    match message["message_type"]:
                        # 群聊消息
                        case "group":
                            sender = message["sender"]
                            sender_name = sender["card"]
                            group_id = message["group_id"]
                            if len(sender["card"]) == 0:
                                sender_name = sender["nickname"]
                            write_message(message)
                            print(
                                "{}:{}({})在{}群里说:{}".format(
                                    message["time"],
                                    sender_name,
                                    sender["user_id"],
                                    group_id,
                                    message["raw_message"],
                                )
                            )
                            logging.info(
                                "{}({})在{}群里说:{}".format(
                                    sender_name,
                                    sender["user_id"],
                                    group_id,
                                    message["raw_message"],
                                )
                            )
                            # 0.5% 的概率复读
                            if random.random() < 0.005:
                                payload = {
                                    "action": "send_group_msg",
                                    "params": {
                                        "group_id": group_id,
                                        "message": message["raw_message"],
                                    },
                                }
                                await websocket.send(json.dumps(payload))
                            if (
                                "[CQ:at,qq={}]".format(setting["developers_list"][0])
                                in message["raw_message"]
                                or "[CQ:at,qq={}]".format(setting["developers_list"][1])
                                in message["raw_message"]
                            ) and "reply" not in message["raw_message"]:
                                if (
                                    sender["user_id"] not in setting["developers_list"]
                                    and sender["user_id"] not in setting["admin_list"]
                                    and group_id in setting["admin_group_list"]
                                ):
                                    await websocket.send(
                                        json.dumps(
                                            ban_new(sender["user_id"], group_id, 60)
                                        )
                                    )
                                    await websocket.send(
                                        json.dumps(
                                            say(
                                                group_id,
                                                "{},不要随便艾特☁️喵，禁言你了喵。".format(
                                                    sender_name
                                                ),
                                            )
                                        )
                                    )
                                elif (
                                    sender["user_id"] not in setting["developers_list"]
                                    and sender["user_id"] in setting["admin_list"]
                                    and group_id in setting["admin_group_list"]
                                ):
                                    for i in range(100):
                                        time.sleep(0.1)
                                        result = re.search(
                                            "\d+", message["raw_message"]
                                        )
                                        payload = {
                                            "action": "send_msg",
                                            "params": {
                                                "group_id": group_id,
                                                "message": [
                                                    {
                                                        "type": "at",
                                                        "data": {
                                                            "qq": sender["user_id"]
                                                        },
                                                    },
                                                    {
                                                        "type": "text",
                                                        "data": {
                                                            "text": "不要随便艾特☁️喵。"
                                                        },
                                                    },
                                                ],
                                            },
                                            "echo": "defense",
                                        }
                                        await websocket.send(json.dumps(payload))
                            if (
                                re.search(
                                    r"CQ:reply,id=\d+]好好好", message["raw_message"]
                                )
                                and sender["user_id"] in setting["developers_list"]
                            ):
                                message_id = re.search(
                                    r"\d+", message["raw_message"]
                                ).group()
                                payload = {
                                    "action": "get_msg",
                                    "params": {
                                        "message_id": message_id,
                                    },
                                    "echo": "applaud",
                                }
                                await websocket.send(json.dumps(payload))

                            # 新入群验证
                            if "{}_{}.jpg".format(
                                sender["user_id"], group_id
                            ) in os.listdir("./vcode"):
                                if "看不清" in message["raw_message"]:
                                    if "{}_{}.jpg".format(
                                        sender["user_id"], group_id
                                    ) in os.listdir("./vcode"):
                                        update_vcode(sender["user_id"], group_id)
                                        await websocket.send(
                                            json.dumps(
                                                welcome_verify(
                                                    sender["user_id"], group_id
                                                )
                                            )
                                        )
                                else:
                                    (mod, times) = verify(
                                        sender["user_id"],
                                        group_id,
                                        message["raw_message"],
                                    )
                                    if mod:
                                        # 通过验证
                                        await websocket.send(
                                            json.dumps(
                                                ban_new(sender["user_id"], group_id, 60)
                                            )
                                        )
                                        await websocket.send(
                                            json.dumps(
                                                welcome_new(sender["user_id"], group_id)
                                            )
                                        )
                                    elif times > 0:
                                        await websocket.send(
                                            json.dumps(
                                                say(
                                                    group_id,
                                                    '{},验证码输入错误，你还有{}次机会喵。如果看不清记得说"乐可，看不清"喵。'.format(
                                                        sender_name, times
                                                    ),
                                                )
                                            )
                                        )
                                    elif times <= 0:
                                        await websocket.send(
                                            json.dumps(
                                                kick_member(sender["user_id"], group_id)
                                            )
                                        )
                                        await websocket.send(
                                            json.dumps(
                                                say(
                                                    group_id,
                                                    "{},验证码输入错误，你没有机会了喵。有缘江湖相会了喵。".format(
                                                        sender_name
                                                    ),
                                                )
                                            )
                                        )
                            else:
                                match message["message"][0]["type"]:
                                    case "text":
                                        if group_id in setting["admin_group_list"]:
                                            # 2%的概率派发50积分
                                            if random.random() < 0.02:
                                                now_point = find_point(
                                                    sender["user_id"]
                                                )
                                                change_point(
                                                    sender["user_id"],
                                                    group_id,
                                                    now_point + 50,
                                                )
                                                payload = {
                                                    "action": "send_group_msg",
                                                    "params": {
                                                        "group_id": group_id,
                                                        "message": "恭喜群友{}获得乐可派发的水群积分！积分{}->{}。".format(
                                                            sender_name,
                                                            now_point,
                                                            now_point + 50,
                                                        ),
                                                    },
                                                }
                                                await websocket.send(
                                                    json.dumps(payload)
                                                )
                                        # print(message["message"][0]["data"]["text"])
                                        if sender["user_id"] == setting[
                                            "miaomiao_group_member"
                                        ] and (
                                            "喵"
                                            not in message["message"][0]["data"]["text"]
                                            or "喵" not in message["raw_message"]
                                        ):
                                            await websocket.send(
                                                json.dumps(
                                                    ban_new(
                                                        sender["user_id"], group_id, 60
                                                    )
                                                )
                                            )
                                            await websocket.send(
                                                json.dumps(
                                                    say(
                                                        group_id,
                                                        "{},你因为说话不带喵被禁言了喵。".format(
                                                            sender_name
                                                        ),
                                                    )
                                                )
                                            )
                                            await websocket.send(
                                                json.dumps(
                                                    ban_new(
                                                        sender["user_id"], group_id, 0
                                                    )
                                                )
                                            )
                                        if (
                                            datetime.datetime.now().day == 25
                                            and group_id in setting["admin_group_list"]
                                            and sender["user_id"]
                                            not in setting["developers_list"]
                                        ):
                                            if (
                                                "喵"
                                                not in message["message"][0]["data"][
                                                    "text"
                                                ]
                                            ):
                                                if (
                                                    sender["user_id"]
                                                    not in setting["admin_list"]
                                                ):
                                                    await websocket.send(
                                                        json.dumps(
                                                            ban_new(
                                                                sender["user_id"],
                                                                group_id,
                                                                60,
                                                            )
                                                        )
                                                    )
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id,
                                                                "{},每月25号是本群喵喵日，你因为说话不带喵被禁言了喵。".format(
                                                                    sender_name
                                                                ),
                                                            )
                                                        )
                                                    )
                                                    # await websocket.send(json.dumps(ban_new(sender["user_id"], group_id, 0)))
                                                else:
                                                    await websocket.send(
                                                        json.dumps(
                                                            cxgl(
                                                                group_id,
                                                                sender["user_id"],
                                                            )
                                                        )
                                                    )
                                        if message["message"][0]["data"][
                                            "text"
                                        ].startswith("可乐"):
                                            # await websocket.send(
                                            #     json.dumps(
                                            #         ban_new(sender["user_id"], group_id, 60)
                                            #     )
                                            # )
                                            await websocket.send(
                                                json.dumps(
                                                    say(
                                                        group_id,
                                                        "抗议！！！抗议！！！人家叫乐可喵，不叫可乐喵！！！！",
                                                    )
                                                )
                                            )
                                        if message["message"][0]["data"][
                                            "text"
                                        ].startswith("乐可"):
                                            if (
                                                "功能"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        return_function(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "每日一句"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        daily_word(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "查询黑名单"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                user_id = re.search(
                                                    r"\d+",
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ],
                                                ).group()
                                                if user_id in list(
                                                    setting["blacklist"].keys()
                                                ):
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id,
                                                                "{}在黑名单中，原因:{}。".format(
                                                                    user_id,
                                                                    setting[
                                                                        "blacklist"
                                                                    ][user_id],
                                                                ),
                                                            )
                                                        )
                                                    )
                                                else:
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id,
                                                                "{}不在黑名单中".format(
                                                                    user_id
                                                                ),
                                                            )
                                                        )
                                                    )
                                            elif (
                                                "今天吃"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        ban_new(
                                                            sender["user_id"],
                                                            group_id,
                                                            60,
                                                        )
                                                    )
                                                )
                                                await websocket.send(
                                                    json.dumps(
                                                        SayAndAt(
                                                            sender["user_id"],
                                                            group_id,
                                                            ",今天吃大嘴巴子🖐喵。",
                                                        )
                                                    )
                                                )
                                            elif (
                                                "挑战你"
                                                in message["message"][0]["data"]["text"]
                                                or "午时已到"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        russian_pve(
                                                            sender["user_id"],
                                                            group_id,
                                                            sender_name,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "开枪"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        russian_pve_shot(
                                                            sender["user_id"],
                                                            group_id,
                                                            sender_name,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "梗图"
                                                in message["message"][0]["data"]["text"]
                                                and "统计"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(MemeStatistics(group_id))
                                                )
                                            elif (
                                                "统计"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        get_statistics(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "排名"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        ranking_point_payload(group_id)
                                                    )
                                                )
                                            elif (
                                                "低保"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        poor_point(
                                                            sender["user_id"],
                                                            group_id,
                                                            sender_name,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "抽签"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        drawing(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "抽"
                                                in message["message"][0]["data"]["text"]
                                                and "连"
                                                in message["message"][0]["data"]["text"]
                                                and "梗图"
                                                not in message["message"][0]["data"][
                                                    "text"
                                                ]
                                            ):
                                                num = FindNum(message["raw_message"])
                                                import math

                                                num = math.trunc(num)
                                                if num > 100:
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id, "最大100连喵!"
                                                            )
                                                        )
                                                    )
                                                else:
                                                    await websocket.send(
                                                        json.dumps(
                                                            luck_dog.luck_choice_mut(
                                                                sender["user_id"],
                                                                sender_name,
                                                                group_id,
                                                                num,
                                                            )
                                                        )
                                                    )
                                            elif (
                                                "抽奖"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        luck_dog.luck_choice_mut(
                                                            sender["user_id"],
                                                            sender_name,
                                                            group_id,
                                                            1,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "价格"
                                                in message["message"][0]["data"]["text"]
                                                and "大头菜"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                user_id = sender["user_id"]
                                                await websocket.send(
                                                    json.dumps(
                                                        say(
                                                            group_id,
                                                            f"当前大头菜价格为:{GetNowPrice()}积分喵,你的积分为{find_point(user_id)}喵。",
                                                        )
                                                    )
                                                )
                                            elif (
                                                "买入"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                num = FindNum(
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ]
                                                )
                                                import math

                                                num = math.trunc(num)
                                                if num >= 1:
                                                    await websocket.send(
                                                        json.dumps(
                                                            BuyKohlrabi(
                                                                sender["user_id"],
                                                                group_id,
                                                                num,
                                                            )
                                                        )
                                                    )
                                            elif (
                                                "梭哈"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        ShowHand(
                                                            sender["user_id"],
                                                            group_id,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "卖出"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                num = FindNum(
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ]
                                                )
                                                import math

                                                num = math.trunc(num)
                                                if num >= 1:
                                                    await websocket.send(
                                                        json.dumps(
                                                            SellKohlrabi(
                                                                sender["user_id"],
                                                                group_id,
                                                                num,
                                                            )
                                                        )
                                                    )
                                            elif (
                                                "梗图二十"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        send_meme_merge_forwarding(
                                                            group_id, 20
                                                        )
                                                    )
                                                )
                                            elif (
                                                "梗图十"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        send_meme_merge_forwarding(
                                                            group_id, 10
                                                        )
                                                    )
                                                )
                                            elif (
                                                "梗图"
                                                in message["message"][0]["data"]["text"]
                                                and "连"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                num = FindNum(
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ]
                                                )
                                                import math

                                                num = math.trunc(num)
                                                if num > 100:
                                                    # nums=100
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id,
                                                                "最大100连喵！",
                                                            )
                                                        )
                                                    )
                                                else:
                                                    nums = num
                                                    for i in range(
                                                        math.trunc(nums / 20.0)
                                                    ):
                                                        await websocket.send(
                                                            json.dumps(
                                                                send_meme_merge_forwarding(
                                                                    group_id, 20
                                                                )
                                                            )
                                                        )
                                                    if nums > 20:
                                                        await websocket.send(
                                                            json.dumps(
                                                                send_meme_merge_forwarding(
                                                                    group_id, nums % 20
                                                                )
                                                            )
                                                        )
                                                    await websocket.send(
                                                        json.dumps(
                                                            say(
                                                                group_id,
                                                                "梗图{}连发货了喵，请好好享用喵。".format(
                                                                    nums
                                                                ),
                                                            )
                                                        )
                                                    )
                                            elif (
                                                "装弹"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        russian(
                                                            message["message"][0][
                                                                "data"
                                                            ]["text"],
                                                            sender["user_id"],
                                                            group_id,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "反击"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                if (
                                                    sender["user_id"]
                                                    in setting["developers_list"]
                                                ):
                                                    for i in range(100):
                                                        time.sleep(0.1)
                                                        result = re.search(
                                                            "\d+",
                                                            message["raw_message"],
                                                        )
                                                        qq = int(result.group())
                                                        if qq is not None:
                                                            payload = {
                                                                "action": "send_msg",
                                                                "params": {
                                                                    "group_id": group_id,
                                                                    "message": [
                                                                        {
                                                                            "type": "at",
                                                                            "data": {
                                                                                "qq": qq
                                                                            },
                                                                        },
                                                                    ],
                                                                },
                                                                "echo": "defense",
                                                            }
                                                            await websocket.send(
                                                                json.dumps(payload)
                                                            )
                                            elif (
                                                "随机梗图"
                                                in message["message"][0]["data"]["text"]
                                                or "梗图"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        send_random_meme(group_id)
                                                    )
                                                )
                                            elif (
                                                "涩"
                                                in message["message"][0]["data"]["text"]
                                                and "兑换"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        sex_img(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "cos"
                                                in message["message"][0]["data"]["text"]
                                                or "COS"
                                                in message["message"][0]["data"]["text"]
                                                or "涩图"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        get_cos(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "二次元"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        radom_waifu(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "三次元"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        radom_real(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "一言"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        one_word(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "随机HTTP猫猫"
                                                in message["message"][0]["data"]["text"]
                                                or "随机http猫猫"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        send_radom_http_cat(group_id)
                                                    )
                                                )
                                            elif (
                                                "运势"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        luck_dog.luck_dog(
                                                            sender["user_id"],
                                                            sender_name,
                                                            group_id,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "签到"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        daily_check_in(
                                                            sender["user_id"],
                                                            sender_name,
                                                            group_id,
                                                        )
                                                    )
                                                )
                                            elif (
                                                "V我50"
                                                in message["message"][0]["data"]["text"]
                                                or "v我50"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                # if sender["user_id"] in [
                                                #     1505617447,
                                                #     3070004098,
                                                # ]:
                                                #     await websocket.send(
                                                #         json.dumps(
                                                #             bot_database.recharge(
                                                #                 sender["user_id"],
                                                #                 group_id,
                                                #                 50,
                                                #             )
                                                #         )
                                                #     )
                                                # else:
                                                await websocket.send(
                                                    json.dumps(kfc_v_me_50(group_id))
                                                )
                                            # print("{} {}".format(type(sender["user_id"]),sender["user_id"]))
                                            elif (
                                                "塔罗牌"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        return_trarot_cards(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "晚安"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                payload = {
                                                    "action": "send_group_msg",
                                                    "params": {
                                                        "group_id": group_id,
                                                        "message": "{},晚安，好梦喵。(∪.∪ )...zzz".format(
                                                            sender_name
                                                        ),
                                                    },
                                                }
                                                await websocket.send(
                                                    json.dumps(payload)
                                                )
                                            elif (
                                                "日报"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        daily_paper(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "看世界"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        photo_new(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "打响指"
                                                in message["message"][0]["data"]["text"]
                                            ) and sender["user_id"] in setting[
                                                "admin_list"
                                            ]:
                                                await websocket.send(
                                                    json.dumps(
                                                        say(
                                                            group_id,
                                                            "{},你确定吗？此功能会随机清除一半的群友,如果确定的话,请在5分钟内说“乐可,清楚明白”。如果取消的话,请说“乐可,取消”。".format(
                                                                get_user_name(
                                                                    sender["user_id"],
                                                                    group_id,
                                                                )
                                                            ),
                                                        )
                                                    )
                                                )
                                                await websocket.send(
                                                    json.dumps(red_qq_avatar())
                                                )
                                                setting["thanos_time"] = time.time()
                                                setting["is_thanos"] = True
                                                dump_setting(setting)
                                            elif (
                                                "清楚明白"
                                                in message["message"][0]["data"]["text"]
                                                and sender["user_id"]
                                                in setting["admin_list"]
                                                and setting["is_thanos"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(
                                                        cxgl(
                                                            sender["user_id"], group_id
                                                        )
                                                    )
                                                )
                                            elif (
                                                "取消"
                                                in message["message"][0]["data"]["text"]
                                                and sender["user_id"]
                                                in setting["admin_list"]
                                                and setting["is_thanos"]
                                            ):
                                                await websocket.send(
                                                    json.dumps(nomoral_qq_avatar())
                                                )
                                                setting["is_thanos"] = False
                                                dump_setting(setting)
                                                await websocket.send(
                                                    json.dumps(
                                                        say(
                                                            group_id,
                                                            "乐可不是紫薯精喵。",
                                                        )
                                                    )
                                                )
                                            elif (
                                                "早"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                payload = {
                                                    "action": "send_group_msg",
                                                    "params": {
                                                        "group_id": group_id,
                                                        "message": "{},早上好喵！ヾ(•ω•`)o".format(
                                                            sender_name
                                                        ),
                                                    },
                                                }
                                                await websocket.send(
                                                    json.dumps(payload)
                                                )
                                            else:
                                                await websocket.send(
                                                    json.dumps(
                                                        chat(
                                                            group_id,
                                                            sender_name,
                                                            message["message"][0][
                                                                "data"
                                                            ]["text"],
                                                        )
                                                    )
                                                )
                                    case "at":
                                        rev_id = message["message"][0]["data"]["qq"]
                                        group_id = message["group_id"]
                                        print(
                                            "{}:{}({})@ {}".format(
                                                message["time"],
                                                sender_name,
                                                sender["user_id"],
                                                rev_id,
                                            )
                                        )

                                        logging.info(
                                            "{}({})@ {}".format(
                                                sender_name,
                                                sender["user_id"],
                                                rev_id,
                                            )
                                        )
                                        if str(rev_id) == str(setting["bot_id"]):
                                            if (
                                                group_id in setting["admin_group_list"]
                                                and sender["user_id"]
                                                not in setting["admin_list"]
                                            ):
                                                await websocket.send(
                                                    ban_new(
                                                        sender["user_id"],
                                                        group_id,
                                                        60,
                                                    )
                                                )
                                            await websocket.send(
                                                json.dumps(
                                                    say(
                                                        group_id,
                                                        "请不要艾特乐可喵,请以乐可开头说提示语喵，比如“乐可，统计。”。",
                                                    )
                                                )
                                            )
                                    case _:
                                        # print(message)
                                        pass
                        case "private":
                            print(
                                "{}:{}({})私聊说:{}".format(
                                    message["time"],
                                    message["sender"]["nickname"],
                                    message["user_id"],
                                    message["raw_message"],
                                )
                            )
                            logging.info(
                                "{}({})私聊说:{}".format(
                                    message["sender"]["nickname"],
                                    message["user_id"],
                                    message["raw_message"],
                                )
                            )
                            if (
                                "抽" in message["raw_message"]
                                and "连" in message["raw_message"]
                            ):
                                num = FindNum(message["raw_message"])
                                import math

                                num = math.trunc(num)
                                if num > 100:
                                    await websocket.send(
                                        json.dumps(SayPrivte(group_id, "最大100连喵!"))
                                    )
                                else:
                                    await websocket.send(
                                        json.dumps(
                                            luck_dog.LuckChoiceMutPrivate(
                                                message["user_id"], num
                                            )
                                        )
                                    )
                            elif "抽奖" in message["raw_message"]:
                                await websocket.send(
                                    json.dumps(
                                        luck_dog.LuckChoiceMutPrivate(
                                            message["user_id"], 1
                                        )
                                    )
                                )
                            if message["user_id"] in setting["developers_list"]:
                                if message["raw_message"].startswith("更新群友列表"):
                                    for group in setting["group_list"]:
                                        await websocket.send(
                                            json.dumps(get_group_member_list(group))
                                        )
                                if message["raw_message"].startswith("积分"):
                                    result = re.search("\d+", message["raw_message"])
                                    # print(result.group())
                                    await websocket.send(
                                        json.dumps(
                                            recharge_privte(
                                                message["user_id"],
                                                group_id,
                                                int(result.group()),
                                            )
                                        )
                                    )

                case "notice":
                    match message["notice_type"]:
                        # 有新人入群
                        case "group_increase":
                            user_id = message["user_id"]
                            group_id = message["group_id"]
                            print(
                                "{}:{}加入入群{}".format(
                                    message["time"], user_id, group_id
                                )
                            )
                            logging.info("{}加入入群{}".format(user_id, group_id))
                            if user_id != setting["bot_id"]:
                                if group_id in setting["admin_group_list"]:
                                    if str(user_id) in setting["blacklist"].keys():
                                        await websocket.send(
                                            json.dumps(kick_member(user_id, group_id))
                                        )
                                        await websocket.send(
                                            json.dumps(
                                                say(
                                                    group_id,
                                                    "{},你已因{}被本群拉黑，无法加入本群".format(
                                                        user_id,
                                                        setting["blacklist"][
                                                            str(user_id)
                                                        ],
                                                    ),
                                                )
                                            )
                                        )
                                    else:
                                        (is_in_unwelcome, quit_time) = in_unwelcome(
                                            user_id, group_id
                                        )
                                        if is_in_unwelcome:
                                            await websocket.send(
                                                json.dumps(
                                                    ban_new(user_id, group_id, 60)
                                                )
                                            )
                                            await websocket.send(
                                                json.dumps(
                                                    say(
                                                        group_id,
                                                        "世界上是没有后悔药的，开弓也是没有回头箭的。{},已于{}已经做出了自己的选择".format(
                                                            user_id,
                                                            time.strftime(
                                                                "%Y-%m-%d %H:%M:%S",
                                                                quit_time,
                                                            ),
                                                        ),
                                                    )
                                                )
                                            )
                                            payload = {
                                                "action": "set_group_kick",
                                                "params": {
                                                    "group_id": setting[
                                                        "admin_group_main"
                                                    ],
                                                    "user_id": user_id,
                                                },
                                            }
                                            await websocket.send(json.dumps(payload))
                                        else:
                                            await websocket.send(
                                                json.dumps(
                                                    welcome_verify(user_id, group_id)
                                                )
                                            )
                                else:
                                    await websocket.send(
                                        json.dumps(
                                            welcom_new_no_admin(user_id, group_id)
                                        )
                                    )
                        # 有人离开了
                        case "group_decrease":
                            user_id = message["user_id"]
                            group_id = message["group_id"]
                            if (
                                message["sub_type"] == "leave"
                                and group_id in setting["admin_group_list"]
                            ):
                                print(
                                    "{}:{}离开了群{}。\n".format(
                                        message["time"], user_id, group_id
                                    )
                                )
                                res, user_info = get_user_info(
                                    message["user_id"], group_id
                                )
                                if user_info.card != "":
                                    sender_name = user_info.card
                                else:
                                    sender_name = user_info.nickname
                                add_unwelcome(user_id, message["time"], group_id)
                                await websocket.send(
                                    json.dumps(
                                        say(
                                            group_id,
                                            "{}({})离开了群{}。\n十个小兵人，外出去吃饭；\n一个被呛死，还剩九个人。\n九个小兵人，熬夜熬得深；\n一个睡过头，还剩八个人。\n八个小兵人，动身去德文；\n一个要留下，还剩七个人。\n七个小兵人，一起去砍柴；\n一个砍自己，还剩六个人。\n六个小兵人，无聊玩蜂箱；\n一个被蛰死，还剩五个人。\n五个小兵人，喜欢学法律；\n一个当法官，还剩四个人。\n四个小兵人，下海去逞能；\n一个葬鱼腹，还剩三个人。\n三个小兵人，进了动物园；\n一个遭熊袭，还剩两个人。\n两个小兵人，外出晒太阳；\n一个被晒焦，还剩一个人。\n这个小兵人，孤单又影只；\n投缳上了吊，一个也没剩。".format(
                                                sender_name, user_id, group_id
                                            ),
                                        )
                                    )
                                )
                                logging.info("{}离开了群{}".format(user_id, group_id))
                case "meta_event":
                    # OneBot元事件
                    if "meta_event_type" in message:
                        match message["meta_event_type"]:
                            case "lifecycle":
                                match message["sub_type"]:
                                    case "connect":
                                        print("{}:已连接".format(message["time"]))
                                    case _:
                                        pass
                            case "heartbeat":
                                if (
                                    time.time() - setting["thanos_time"] > 300
                                    and setting["is_thanos"]
                                ):
                                    await websocket.send(
                                        json.dumps(nomoral_qq_avatar())
                                    )
                                    setting["is_thanos"] = False
                                    setting["thanos_time"] = time.time()
                                    dump_setting(setting)
                                    await websocket.send(
                                        json.dumps(say(group_id, "乐可不是紫薯精喵。"))
                                    )
                                if (
                                    time.time() - get_last_time_get_group_member_list()
                                    > 86400
                                ):
                                    await websocket.send(
                                        json.dumps(
                                            get_group_member_list(
                                                setting["admin_group_main"]
                                            )
                                        )
                                    )
                                # 定期检测新入群友验证码
                                for i in os.listdir("./vcode"):
                                    user_id = i.split(".")[0].split("_")[0]
                                    group_id = i.split(".")[0].split("_")[1]
                                    if check_validation_timeout(
                                        user_id,
                                        setting["admin_group_main"],
                                    ):
                                        res, user_info = get_user_info(
                                            user_id, group_id
                                        )
                                        if user_info.card != "":
                                            sender_name = user_info.card
                                        else:
                                            sender_name = user_info.nickname
                                        await websocket.send(
                                            json.dumps(ban_new(user_id, group_id, 60))
                                        )
                                        await websocket.send(
                                            json.dumps(
                                                say(
                                                    setting["admin_group_main"],
                                                    "f{sender_name}的验证码已过期，已自动踢出喵！",
                                                )
                                            )
                                        )
                                # 0.2% 的概率乐可卖萌
                                if random.random() < 0.002:
                                    await websocket.send(json.dumps(cute(group_id)))
                                # 定期清理过期的大头菜
                                ClearKohlrabi()
                            case _:
                                print(message)
                    else:
                        print(message)
                case "request":
                    # 请求事件
                    print(message)
        elif "echo" in message:
            match message["echo"]:
                case "update_group_member_list":
                    print("{}:开始更新群友列表！".format(time.time()))
                    for group_member in message["data"]:
                        # print(group_member)
                        user = Group_member()
                        user.init_by_dict(group_member)
                        updata_user_info(user)
                        if (
                            (
                                (
                                    time.time() - user.last_sent_time > 5184000
                                    and user.join_time == user.last_sent_time
                                )
                                or time.time() - user.last_sent_time > 7776000
                            )
                            and user.group_id in setting["admin_group_list"]
                            and user.group_id not in setting["sepcial_group"]
                        ):
                            print(
                                "{}({}),最后发言时间:{}".format(
                                    user.nickname,
                                    user.user_id,
                                    time.strftime(
                                        "%Y-%m-%d %H:%M:%S",
                                        time.localtime(user.last_sent_time),
                                    ),
                                )
                            )
                            logging.info(
                                "{}因两个月未活跃被请出群聊".format(user.user_id)
                            )
                            payload = {
                                "action": "set_group_kick",
                                "params": {
                                    "group_id": group_member["group_id"],
                                    "user_id": user.user_id,
                                },
                            }
                            await websocket.send(json.dumps(payload))
                            await websocket.send(
                                json.dumps(
                                    say(
                                        setting["admin_group_main"],
                                        "{}({})，乐可要踢掉你了喵！\n原因:三个月无活跃或两个月未活跃且从未活跃过。\n其最后发言时间为:{}".format(
                                            user.nickname,
                                            user.user_id,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        ),
                                    )
                                )
                            )
                case "defense":
                    delete_msg(message["data"]["message_id"])
                case "applaud":
                    sender_id = message["data"]["sender"]["user_id"]
                    message_id = message["data"]["message_id"]
                    group_id = message["data"]["group_id"]
                    now_point = find_point(sender_id)
                    change_point(sender_id, group_id, now_point + 100)
                    res, user_info = get_user_info(sender_id, group_id)
                    if user_info.card != "":
                        sender_name = user_info.card
                    else:
                        sender_name = user_info.nickname
                    payload = {
                        "action": "send_group_msg",
                        "params": {
                            "group_id": group_id,
                            "message": [
                                {"type": "reply", "data": {"id": message_id}},
                                {
                                    "type": "text",
                                    "data": {
                                        "text": "{},受到☁️赞扬,积分:{}->{}".format(
                                            sender_name, now_point, now_point + 100
                                        )
                                    },
                                },
                            ],
                        },
                    }
                    await websocket.send(json.dumps(payload))
                case _:
                    print(message)
        else:
            if "status" in message:
                match message["status"]:
                    case "ok":
                        pass
                    case "_":
                        print(message)
            else:
                print(message)


def SayPrivte(user_id: int, text: str):
    payload = {
        "action": "send_msg",
        "params": {
            "user_id": user_id,
            "message": text,
        },
        "echo": "123",
    }
    return payload


def say(group_id: int, text: str):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": text,
        },
        "echo": "123",
    }
    return payload


def SayAndAt(user_id: int, group_id: int, text: str):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": text}},
            ],
        },
    }
    return payload


def delete_msg(message_id: int):
    payload = {
        "action": "delete_msg",
        "params": {
            "message_id": message_id,
        },
    }
    return payload


def FindNum(text: str):
    result = re.search("\d+", text)
    num = int(result.group())
    return num


# def beijing(sec, what):
#     beijing_time = datetime.datetime.now() + datetime.timedelta(hours=8)
#     return beijing_time.timetuple()


# logging.Formatter.converter = beijing

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"
logging.basicConfig(
    filename="log/my.log", level=logging.INFO, format=LOG_FORMAT, datefmt=DATE_FORMAT
)
asyncio.get_event_loop().run_until_complete(websockets.serve(echo, "0.0.0.0", 27431))
asyncio.get_event_loop().run_forever()
