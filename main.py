import asyncio
import datetime
from enum import Enum
import logging
import os
import random
import time
import traceback
import requests
import websockets
import json
import asyncio
import queue
import threading
from Class.Group_member import (
    Group_member,
    IsDeveloper,
    get_user_info,
    get_user_name,
    updata_user_info,
    update_group_member_list,
    IsAdmin,
    BotIsAdmin,
)
from bot_database import (
    add_unwelcome,
    change_point,
    daily_check_in,
    find_point,
    get_statistics,
    in_unwelcome,
    recharge_privte,
    write_message,
)
from chat import (
    AddAtPunishList,
    AtPunish,
    BoringReply,
    HuffingReplay,
    ColdReplay,
    DelAtPunish,
    FlyReply,
    GetColdGroupStatus,
    GetGroupDecreaseMessageStatus,
    GiveGift,
    Joke,
    SayImgReply,
    SwitchColdGroupChat,
    SwitchGroupDecreaseMessage,
    UpdateColdGroup,
    chat,
    incWhoAtMe,
    getWhoAtMe,
    display_think,
    robot_reply,
    run_or_shot,
    switch_model,
    replyImageMessage,
    getImageInfo,
    chatNoContext,
)
from drifting_bottles import (
    is_comment_write,
    pick_drifting_bottles_radom,
    throw_drifting_bottles,
    write_bottles_uuid_message_id,
)
from e_mail import send_log_email
from kohlrabi import (
    BuyKohlrabi,
    ClearKohlrabi,
    GetNowPrice,
    SellKohlrabi,
    ShowHand,
    SellKohlrabiAll,
)
from level import get_level, set_level
import luck_dog
from easter_egg import (
    cute,
    cute2,
    cute3,
    kfc_v_me_50,
    sex_img,
)
from rankings import ranking_point_payload
from private import cxgl, WhoAskPants, get_cx_str
from group_operate import (
    KickMemberAndRejectAddRequest,
    poor_point,
    get_group_list,
    kick_member,
    SetGroupWholeBan,
    SetGroupWholeNoBan,
    DeleteEssenceMsg,
    SetEssenceMsg,
    update_group_info,
    GetMessage,
    GetGroupName,
)
from random_meme import (
    send_meme_merge_forwarding,
    send_radom_http_cat,
    send_random_meme,
    MemeStatistics,
)

from russian_roulette import russian, russian_pve, russian_pve_shot
from tarot_cards import (
    radom_cat,
    radom_cat_gif,
    daily_paper,
    daily_word,
    drawing,
    get_cos,
    photo_new,
    return_trarot_cards,
    radom_waifu,
    radom_real,
    one_word,
    SoCute,
    SoHappy,
    SoSad,
    AnswerBook,
)
from tools import (
    GetLocalIP,
    HasChinese,
    ReplySay,
    dump_setting,
    getTemper,
    is_today,
    load_setting,
    nomoral_qq_avatar,
    red_qq_avatar,
    GetLogTime,
    GetSleepSeconds,
    GetSystemInfoTable,
    HasKeyWords,
    say,
    HasAllKeyWords,
    SayAndAt,
    FindNum,
    SayPrivte,
    delete_msg,
    SayAndAtDefense,
    SayAndAtImage,
)
from vcode import (
    check_validation_timeout,
    update_vcode,
    verify,
    welcome_verify,
    delete_vcode,
    find_vcode,
    verify_fail_say,
)
from welcome_to_newyork import (
    ban_new,
    banNormal,
    return_function,
    welcom_new_no_admin,
    welcome_new,
)
from GroupConfig import get_config, set_config, manage_config, GroupConfigError
from chat_rewards import SendRewards
from chat_record import AddChatRecord, GetNowChatRecord, GetLifeChatRecord
import re
from replyYou import incReplyYouTimes, addWhoReplyYou, getReplyYouTimes


class SenderInfo:
    user_id: int
    nickname: str
    card: str
    role: str
    displayName: str


class MessageInfo:
    user_id: int
    time: int
    message_id: int
    raw_message: str
    group_id: int
    self_id: int
    has_at = False
    at_ids = []
    has_image = False
    image_id: str
    text_message = ""
    has_reply = False
    reply_id: int


from enum import Enum


class ConsumingTimeType(Enum):
    """高耗时任务类型"""

    CHAT = 1
    COLDREPLAY = 2
    REPLYIMAGEMESSAGE = 3
    SAYPRIVTECHATNOCONTEXT = 4
    MIAOMIAOTRANSLATION = 5


async def process_queue():
    """处理队列中的任务"""
    print("处理线程开始启动")
    while True:
        try:
            task = consuming_time_process_queue.get()
            if task is None:  # 用于停止线程的信号
                continue
            websocket, param1, param2, param3, text, taskType = task
            print(f"开始启动耗时任务类型{taskType}")
            match taskType:
                case ConsumingTimeType.CHAT:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    await chat(websocket, user_id, group_id, message_id, text)
                case ConsumingTimeType.COLDREPLAY:
                    await ColdReplay(websocket)
                case ConsumingTimeType.REPLYIMAGEMESSAGE:
                    group_id = param1
                    reply_id = param2
                    message_id = param3
                    await replyImageMessage(
                        websocket,
                        group_id,
                        reply_id,
                        message_id,
                        text,
                    )
                case ConsumingTimeType.SAYPRIVTECHATNOCONTEXT:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    await SayPrivte(
                        websocket,
                        user_id,
                        chatNoContext(text),
                    )
                case ConsumingTimeType.MIAOMIAOTRANSLATION:
                    user_id = param1
                    group_id = param2
                    message_id = param3
                    from chat import miaomiaoTranslation

                    await miaomiaoTranslation(websocket, user_id, group_id, message_id)

            # processing_thread.task_done()
        except Exception as e:
            logging.error(f"处理队列任务时出错: {e}")


# 创建耗时任务队列和处理线程
consuming_time_process_queue = queue.Queue()


# 启动处理线程
def start_processing_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# 创建新的事件循环
processing_loop = asyncio.new_event_loop()
processing_thread = threading.Thread(
    target=start_processing_loop, args=(processing_loop,), daemon=True
)
processing_thread.start()

# 启动处理协程
asyncio.run_coroutine_threadsafe(process_queue(), processing_loop)


async def echo(websocket, message):
    try:
        message = json.loads(message)
        if "post_type" in message:
            match message["post_type"]:
                case "message":
                    match message["message_type"]:
                        # 群聊消息
                        case "group":
                            # 以下是艾特惩罚 痛苦虽小折磨永存
                            await AtPunish(websocket)
                            sender = message["sender"]
                            sender_name = sender["card"]
                            group_id = message["group_id"]
                            user_id = message["user_id"]
                            message_id = message["message_id"]
                            group_name = GetGroupName(group_id)
                            raw_message = message["raw_message"]
                            sender_id = sender["user_id"]
                            if len(sender["card"]) == 0:
                                sender_name = sender["nickname"]
                            senderInfo = SenderInfo()
                            senderInfo.user_id = int(message["sender"]["user_id"])
                            senderInfo.nickname = message["sender"]["nickname"]
                            senderInfo.card = message["sender"]["card"]
                            senderInfo.role = message["sender"]["role"]
                            if len(senderInfo.card) == 0:
                                senderInfo.displayName = senderInfo.nickname
                            else:
                                senderInfo.displayName = senderInfo.card
                            messageInfo = MessageInfo()
                            messageInfo.user_id = int(message["user_id"])
                            messageInfo.time = int(message["time"])
                            messageInfo.message_id = int(message["message_id"])
                            messageInfo.raw_message = message["raw_message"]
                            messageInfo.group_id = int(message["group_id"])
                            messageInfo.self_id = int(message["self_id"])
                            # 增加水群次数
                            AddChatRecord(user_id, group_id)
                            messageInfo.at_ids = []
                            messageInfo.has_at = False
                            text_message = ""
                            # ai回复过标志
                            chatFlag = False
                            plainTextMessage = ""
                            is_plainTextMessage = True
                            hasTextMessage = False
                            for i in message["message"]:
                                match i["type"]:
                                    case "at":
                                        messageInfo.has_at = True
                                        messageInfo.at_ids.append(int(i["data"]["qq"]))
                                        text_message += f"{senderInfo.displayName}@{get_user_name(int(i['data']['qq']), group_id)}"
                                        is_plainTextMessage = False
                                    case "reply":
                                        messageInfo.has_reply = True
                                        messageInfo.reply_id = int(i["data"]["id"])
                                        # reply统计
                                        incReplyYouTimes(user_id, group_id)
                                        addWhoReplyYou(
                                            user_id, int(i["data"]["id"]), group_id
                                        )
                                        is_plainTextMessage = False
                                    case "image":
                                        messageInfo.has_image = True
                                        text_message += "[图片]"
                                        is_plainTextMessage = False
                                    case "text":
                                        plainTextMessage += i["data"]["text"]
                                        text_message += i["data"]["text"]
                                        hasTextMessage = True
                                        pass
                            if not messageInfo.has_image:
                                write_message(message, text_message)
                            # 是其他机器人就拉闸,避免无限循环。
                            if user_id in load_setting()[
                                "other_bots"
                            ] or user_id in get_config("no_reply_list", group_id):
                                print(f"机器人ID:{user_id},其他机器人不理睬。")
                                return
                            print(
                                "{}:{}({})在{}({})群里说:{}".format(
                                    message["time"],
                                    sender_name,
                                    user_id,
                                    group_name,
                                    group_id,
                                    message["raw_message"],
                                )
                            )
                            from tools import check_all_miao

                            if (
                                check_all_miao(plainTextMessage)
                                and is_plainTextMessage
                                and hasTextMessage
                                and "喵" in plainTextMessage
                            ):
                                consuming_time_process_queue.put(
                                    (
                                        websocket,
                                        user_id,
                                        group_id,
                                        message_id,
                                        "",
                                        ConsumingTimeType.MIAOMIAOTRANSLATION,
                                    )
                                )

                            if set(messageInfo.at_ids) & set(
                                get_config("hate_at_list", group_id)
                            ):
                                at_ids = set(messageInfo.at_ids) & set(
                                    get_config("hate_at_list", group_id)
                                )
                                for at_id in at_ids:
                                    incWhoAtMe(user_id, at_id)
                                    nowAtNums = getWhoAtMe(user_id, at_id)
                                    if BotIsAdmin(group_id) and not IsAdmin(
                                        user_id, group_id
                                    ):
                                        if nowAtNums > 3:
                                            await banNormal(
                                                user_id, group_id, 60 * nowAtNums
                                            )
                                            await ReplySay(
                                                websocket,
                                                group_id,
                                                message_id,
                                                f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，禁言你{nowAtNums}分钟了喵，引用记得删除艾特喵。",
                                            )
                                        else:
                                            await ReplySay(
                                                websocket,
                                                group_id,
                                                message_id,
                                                f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，事不过三喵,你还有{3-nowAtNums}次机会喵，引用记得删除艾特喵。",
                                            )
                                    else:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            f"{get_user_name(user_id,group_id)},你是第{nowAtNums}次艾特{get_user_name(at_id,group_id)}了喵,{get_user_name(at_id,group_id)}不喜欢被艾特喵，引用记得删除艾特喵。",
                                        )

                            if messageInfo.has_reply:
                                if "#image#" in text_message:
                                    now_text = text_message.replace("#image#", "")
                                    consuming_time_process_queue.put(
                                        (
                                            websocket,
                                            group_id,
                                            messageInfo.reply_id,
                                            message_id,
                                            now_text,
                                            ConsumingTimeType.REPLYIMAGEMESSAGE,
                                        )
                                    )
                                elif "#info#" in text_message:
                                    await getImageInfo(
                                        websocket,
                                        group_id,
                                        messageInfo.reply_id,
                                        message_id,
                                    )

                            log = "{}({})在{}({})群里说:{}".format(
                                sender_name,
                                user_id,
                                group_name,
                                group_id,
                                message["raw_message"],
                            )
                            if text_message.startswith("#carrotbuy#"):
                                from stockMarket import buyStock, BuyError

                                tmpMessage = text_message.replace("#carrotbuy#", "")
                                match buyStock(
                                    user_id,
                                    group_id,
                                    tmpMessage.split(" ")[0],
                                    float(tmpMessage.split(" ")[1]),
                                ):
                                    case BuyError.STOCK_NOT_FOUND:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "胡萝卜代码未找到喵,比如600519.SH喵。",
                                        )
                                    case BuyError.NOT_ENOUGH_POINT:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "积分不足喵。",
                                        )
                                    case BuyError.BUY_SUCCESS:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "购买成功喵。",
                                        )
                            elif text_message.startswith("#carrotsell#"):
                                from stockMarket import sellStock, SellError

                                tmpMessage = text_message.replace("#carrotsell#", "")
                                match sellStock(
                                    user_id,
                                    group_id,
                                    tmpMessage.split(" ")[0],
                                    float(tmpMessage.split(" ")[1]),
                                ):
                                    case SellError.STOCK_NOT_FOUND:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "胡萝卜代码未找到喵,比如600519.SH喵。",
                                        )
                                    case SellError.NOT_ENOUGH_STOCK:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "积分不足喵。",
                                        )
                                    case SellError.SELL_SUCCESS:
                                        await ReplySay(
                                            websocket,
                                            group_id,
                                            message_id,
                                            "出售成功喵。",
                                        )
                            elif text_message.startswith("#carrotme#"):
                                from stockMarket import showStockInfoMe

                                await showStockInfoMe(
                                    websocket, user_id, group_id, message_id
                                )
                            if raw_message.startswith(".") and IsAdmin(
                                sender_id, group_id
                            ):
                                print(message["message"][0]["data"]["text"])
                                argStatus, newArg = manage_config(
                                    message["message"][0]["data"]["text"], group_id
                                )
                                if argStatus:
                                    await say(
                                        websocket,
                                        group_id,
                                        f"操作成功喵,当前该参数的值为:{newArg}",
                                    )
                                else:

                                    match newArg:
                                        case GroupConfigError.NO_OPPATION_Type:
                                            text = "设置失败喵,设置名称错误喵。"
                                        case GroupConfigError.UNKNOW_DATA_TYPE:
                                            text = "设置失败喵,数据类型错误喵。"
                                        case GroupConfigError.UNKNOW_OPPATION_ARG:
                                            text = "设置失败喵,操作类型错误喵。"
                                    await ReplySay(
                                        websocket,
                                        group_id,
                                        message_id,
                                        text,
                                    )
                            has_sensitive = False
                            for i in get_config("sensitive_words", group_id):
                                if i in text_message and i not in "[图片]@":
                                    has_sensitive = True
                            if (
                                has_sensitive
                                and BotIsAdmin(group_id)
                                and not IsAdmin(user_id, group_id)
                            ):
                                await ReplySay(
                                    websocket,
                                    group_id,
                                    message_id,
                                    f"触发本群违禁词规则喵，禁言{get_config("sensitive_ban_sec", group_id)}秒喵！",
                                )
                                await ban_new(
                                    websocket,
                                    user_id,
                                    group_id,
                                    get_config("sensitive_ban_sec", group_id),
                                )
                                if get_config("sensitive_withdrawn", group_id):
                                    await delete_msg(websocket, message_id)
                            logging.info(log)
                            # 解析b站链接
                            if get_config("bilibili_parsing", group_id):
                                for k in message["message"]:
                                    if k["type"] == "json":
                                        # qq卡片消息解析
                                        now_json = json.loads(k["data"]["data"])
                                        if "meta" in now_json:
                                            if "detail_1" in now_json["meta"]:
                                                if (
                                                    "qqdocurl"
                                                    in now_json["meta"]["detail_1"]
                                                ):
                                                    qqdocurl = now_json["meta"][
                                                        "detail_1"
                                                    ]["qqdocurl"]
                                                    r = requests.get(qqdocurl)
                                                    no_get_params_url = r.url.split(
                                                        "?"
                                                    )[0]
                                                    logging.info(
                                                        f"解析结果:{no_get_params_url}"
                                                    )
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message_id,
                                                        no_get_params_url,
                                                    )
                            if GetColdGroupStatus(group_id):
                                # 如果是更新冷群
                                UpdateColdGroup(
                                    user_id,
                                    group_id,
                                    message["message_id"],
                                    message["raw_message"],
                                )
                            if IsAdmin(load_setting()["bot_id"], group_id):
                                # 2%的概率派发50积分
                                if random.random() < 0.02:
                                    now_point = find_point(user_id)
                                    change_point(
                                        user_id,
                                        group_id,
                                        now_point + 50,
                                    )
                                    all_num, today_num = SendRewards(user_id, group_id)
                                    await say(
                                        websocket,
                                        group_id,
                                        f"恭喜群友{sender_name}获得乐可派发的水群积分！积分{now_point}->{now_point + 50}。\n总共:{all_num}次,今日:{today_num}次",
                                    )
                            # 真的是有够无聊
                            if user_id in load_setting()["boring"]:
                                await BoringReply(
                                    websocket, user_id, group_id, message_id
                                )
                            if user_id in load_setting()["huffing"]:
                                await HuffingReplay(
                                    websocket, user_id, group_id, message_id
                                )
                            if user_id in load_setting()["fly"]:
                                await FlyReply(websocket, user_id, group_id, message_id)
                            # 如果有人欺负乐可
                            if HasAllKeyWords(raw_message, ["乐可"]) and HasKeyWords(
                                raw_message,
                                ["sb", "SB", "傻逼", "透透", "透", "打你", "艹"],
                            ):
                                await robot_reply(
                                    websocket, user_id, group_id, message_id
                                )
                            # 1% 的概率复读
                            if random.random() < 0.01:
                                payload = {
                                    "action": "send_group_msg",
                                    "params": {
                                        "group_id": group_id,
                                        "message": message["raw_message"],
                                    },
                                }
                                await websocket.send(json.dumps(payload))
                            # 1% 的概率回复(胡言乱语)
                            if random.random() < 0.01:
                                chatFlag = True
                                sender_name = get_user_name(user_id, group_id)
                                consuming_time_process_queue.put(
                                    (
                                        websocket,
                                        user_id,
                                        group_id,
                                        message_id,
                                        "",
                                        ConsumingTimeType.CHAT,
                                    )
                                )

                            # 艾特事件处理
                            if "[CQ:at,qq=" in message["raw_message"]:
                                at_id = re.findall(
                                    r"\[CQ:at,qq=(\d+)]", message["raw_message"]
                                )
                                if at_id != None:
                                    at_id = int(at_id[0])
                                else:
                                    at_id = re.findall(
                                        r"\[CQ:at,qq=-(\d+)]", message["raw_message"]
                                    )
                                    at_id = int(at_id[0])
                                # (乐可是管理) 艾特其他人
                                if (
                                    IsAdmin(load_setting()["bot_id"], group_id)
                                ) and at_id != load_setting()["bot_id"]:
                                    rev_name = get_user_name(at_id, group_id)
                                    if "解除禁言" in message["raw_message"]:
                                        logging.info(
                                            f"{group_id}:{sender_name}({user_id})解除禁言了{rev_name}({at_id})"
                                        )
                                        await ban_new(websocket, at_id, group_id, 0)
                                        right_at = True
                                    elif "禁言" in message["raw_message"]:
                                        logging.info(
                                            f"{group_id}:{sender_name}({user_id})禁言了{rev_name}({at_id})"
                                        )
                                        await ban_new(websocket, at_id, group_id, 1800)
                                        right_at = True
                                    elif "说再见" in message["raw_message"]:
                                        if not IsAdmin(user_id, group_id):
                                            logging.info(
                                                f"{group_id}:{sender_name}({user_id})踢出了{rev_name}({at_id})"
                                            )
                                            await kick_member(
                                                websocket, at_id, group_id
                                            )
                                            right_at = True
                                    elif HasKeyWords(
                                        raw_message, ["晋升"]
                                    ) and IsDeveloper(user_id):
                                        set_level(
                                            at_id,
                                            group_id,
                                            get_level(at_id, group_id) + 1,
                                        )
                                        change_point(at_id, group_id, 0)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"晋升成功,{get_user_name(at_id,group_id)}({at_id})的等级提升为{get_level(at_id, group_id)}级,积分清零喵。",
                                        )
                                        right_at = True
                                    elif HasKeyWords(
                                        raw_message, ["惩罚取消", "取消惩罚"]
                                    ) and (
                                        (
                                            user_id != at_id
                                            and IsAdmin(user_id, group_id)
                                        )
                                        or IsDeveloper(user_id)
                                    ):
                                        DelAtPunish(at_id, group_id)
                                        logging.info(
                                            f"{group_id}:{sender_name}({user_id})取消了{rev_name}({at_id})的惩罚"
                                        )
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{rev_name}({at_id})的惩罚被{sender_name}({user_id})取消了,快谢谢人家喵！",
                                        )
                                        await ban_new(websocket, at_id, group_id, 0)
                                        right_at = True
                                    elif HasKeyWords(
                                        raw_message, ["送你", "V你", "v你"]
                                    ):
                                        num = re.findall(r"\d+", raw_message)
                                        if len(num) >= 2:
                                            num = int(num[1])
                                        else:
                                            num = 0
                                        await GiveGift(
                                            websocket, user_id, group_id, at_id, num
                                        )
                                        right_at = True
                                    elif HasKeyWords(
                                        raw_message, ["你是GAY", "你是gay"]
                                    ) and IsAdmin(user_id, group_id):
                                        # todo 修复bug
                                        # if at_id not in load_setting["boring"]:
                                        #     _setting = load_setting()
                                        #     _setting["boring"].append(at_id)
                                        #     dump_setting(_setting)
                                        # await say(
                                        #     websocket,
                                        #     group_id,
                                        #     f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                                        # )
                                        pass
                                    elif HasKeyWords(
                                        raw_message, ["你不是GAY", "你不是gay"]
                                    ) and IsAdmin(user_id, group_id):
                                        _setting = load_setting()
                                        while at_id in load_setting()["boring"]:
                                            _setting["boring"].remove(at_id)
                                        dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                                        )
                                    elif HasKeyWords(
                                        raw_message, ["不要哈气"]
                                    ) and IsAdmin(user_id, group_id):
                                        _setting = load_setting()
                                        while at_id in load_setting()["huffing"]:
                                            _setting["huffing"].remove(at_id)
                                        dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},乐可停止追杀你了喵！",
                                        )
                                    elif HasKeyWords(raw_message, ["哈气"]) and IsAdmin(
                                        user_id, group_id
                                    ):
                                        _setting = load_setting()
                                        if at_id not in load_setting()["huffing"]:
                                            _setting["huffing"].append(at_id)
                                            dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},乐可要追杀你了喵！",
                                        )
                                    elif HasKeyWords(
                                        raw_message,
                                        [
                                            "不要装",
                                        ],
                                    ) and IsAdmin(user_id, group_id):
                                        _setting = load_setting()
                                        if at_id not in load_setting()["fly"]:
                                            _setting["fly"].append(at_id)
                                            dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},不要再装了喵。",
                                        )
                                    elif HasKeyWords(
                                        raw_message,
                                        [
                                            "可以装",
                                        ],
                                    ) and IsAdmin(user_id, group_id):
                                        while at_id in load_setting()["fly"]:
                                            _setting["fly"].remove(at_id)
                                        dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},可以开始装了喵。",
                                        )
                                    elif (
                                        HasKeyWords(
                                            raw_message, ["打他", "打它", "打她"]
                                        )
                                        and (user_id != at_id or IsDeveloper(user_id))
                                        and IsAdmin(user_id, group_id)
                                    ):
                                        AddAtPunishList(
                                            at_id,
                                            group_id,
                                            load_setting()["defense_times"],
                                        )
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(user_id, group_id)},乐可要开始打你了喵！",
                                        )
                                        right_at = True
                                    elif HasKeyWords(
                                        message["raw_message"], ["通过验证", "验证通过"]
                                    ):
                                        right_at = True
                                        (mod, vcode_str) = find_vcode(at_id, group_id)
                                        if mod:
                                            (mod, times) = verify(
                                                at_id,
                                                group_id,
                                                vcode_str,
                                            )
                                            if mod:
                                                # 通过验证
                                                if BotIsAdmin(group_id):
                                                    if (
                                                        group_id
                                                        == load_setting()[
                                                            "admin_group_main"
                                                        ]
                                                    ):
                                                        await ban_new(
                                                            websocket,
                                                            at_id,
                                                            group_id,
                                                            60,
                                                        )
                                                        await welcome_new(
                                                            websocket, at_id, group_id
                                                        )
                                                    else:
                                                        await welcom_new_no_admin(
                                                            websocket, at_id, group_id
                                                        )
                                                else:
                                                    await welcom_new_no_admin(
                                                        websocket, at_id, group_id
                                                    )
                                    # elif (
                                    #     at_id in load_setting()["developers_list"]
                                    #     # and "reply" not in message["raw_message"]
                                    #     and user_id
                                    #     not in get_config("no_reply_list", group_id)
                                    # ):
                                    #     if (
                                    #         not IsAdmin(user_id, group_id)
                                    #         and BotIsAdmin(group_id)
                                    #         and not IsDeveloper(user_id)
                                    #         and get_config("dont_at_me", group_id)
                                    #     ):
                                    #         AddWhoAtMe(user_id)
                                    #         now_num = GetWhoAtMe(user_id)
                                    #         if now_num >= 3:
                                    #             await ban_new(
                                    #                 websocket,
                                    #                 user_id,
                                    #                 group_id,
                                    #                 60 * GetWhoAtMe(user_id),
                                    #             )
                                    #             await say(
                                    #                 websocket,
                                    #                 group_id,
                                    #                 f"{sender_name},不要随便艾特☁️喵，引用记得删除艾特,你已经是{GetWhoAtMe(user_id)}次了，禁言你{GetWhoAtMe(user_id)}分钟了喵。",
                                    #             )
                                    #         elif now_num >= 75:
                                    #             await ban_new(
                                    #                 websocket,
                                    #                 user_id,
                                    #                 group_id,
                                    #                 60 * GetWhoAtMe(user_id),
                                    #             )
                                    #             await say(
                                    #                 websocket,
                                    #                 group_id,
                                    #                 f"{sender_name},不要随便艾特☁️喵，引用记得删除艾特,你已经是{GetWhoAtMe(user_id)}次了，禁言你{GetWhoAtMe(user_id)}分钟了喵。超过85次会被直接踢出本群并且拉黑喵。",
                                    #             )
                                    #         elif now_num >= 85:
                                    #             await say(
                                    #                 websocket,
                                    #                 group_id,
                                    #                 f"{sender_name},不要随便艾特☁️喵，引用记得删除艾特,你已经是{GetWhoAtMe(user_id)}次了，再也不见喵",
                                    #             )
                                    #             await KickMemberAndRejectAddRequest(
                                    #                 websocket, user_id, group_id
                                    #             )
                                    #         else:
                                    #             await say(
                                    #                 websocket,
                                    #                 group_id,
                                    #                 f"{sender_name},不要随便艾特☁️喵，引用记得删除艾特。你被警告了喵,事不过三,你现在是第{now_num}次,超过后会直接被禁言喵。",
                                    #             )

                                    #     elif (
                                    #         user_id not in load_setting()["developers_list"]
                                    #         and IsAdmin(user_id, group_id)
                                    #         and BotIsAdmin(group_id)
                                    #         and get_config("dont_at_me", group_id)
                                    #     ):
                                    #         AddWhoAtMe(user_id)
                                    #         # now_num = GetWhoAtMe(user_id)
                                    #         # sender_name = get_user_name(
                                    #         #     user_id, group_id
                                    #         # )
                                    #         # if now_num >= 3:
                                    #         #     await SayAndAt(
                                    #         #         websocket,
                                    #         #         user_id,
                                    #         #         group_id,
                                    #         #         f"{sender_name},不要随便艾特☁️喵,引用记得删除艾特,管理员惩罚{load_setting()["defense_times"]*now_num}次喵。",
                                    #         #     )
                                    #         #     # if now_num <= 20:
                                    #         #     # SayAndAt(
                                    #         #     #     websocket,
                                    #         #     #     user_id,
                                    #         #     #     group_id,
                                    #         #     #     f"{sender_name},不要随便艾特☁️喵,引用记得删除艾特,管理员惩罚{load_setting()["defense_times"]*now_num}次喵。",
                                    #         #     # )
                                    #         #     # else:
                                    #         #     #     SayAndAt(
                                    #         #     #         websocket,
                                    #         #     #         user_id,
                                    #         #     #         group_id,
                                    #         #     #         f"{sender_name},你是个巨婴嘛?引用记得删除艾特,现在已经是第{now_num}次了！！！管理员惩罚{load_setting()["defense_times"]}次。",
                                    #         #     #     )
                                    #         #     AddAtPunishList(
                                    #         #         user_id, group_id, 100 * now_num
                                    #         #     )
                                    #         # else:
                                    #         #     await say(
                                    #         #         websocket,
                                    #         #         group_id,
                                    #         #         f"{sender_name},不要随便艾特☁️喵，引用记得删除艾特,你被警告了喵,事不过三,你现在是第{now_num}次,超过后会施加{load_setting()["defense_times"]}*总艾特次数的艾特惩罚。",
                                    #         #     )
                                    #         pass
                                # 乐可不需要是管理的时候，艾特其他成员
                                elif at_id != load_setting()["bot_id"]:
                                    if HasKeyWords(raw_message, ["送你", "V你", "v你"]):
                                        num = re.findall(r"\d+", raw_message)
                                        if len(num) >= 2:
                                            num = int(num[1])
                                        else:
                                            num = 0
                                        await GiveGift(
                                            websocket, user_id, group_id, at_id, num
                                        )
                                        right_at = True
                                    elif HasKeyWords(
                                        raw_message, ["你是GAY", "你是gay"]
                                    ) and IsAdmin(user_id, group_id):
                                        # todo 修复bug
                                        # _setting = load_setting()
                                        # if at_id not in load_setting()["boring"]:
                                        #     _setting["boring"].append(at_id)
                                        #     dump_setting(_setting)
                                        # await say(
                                        #     websocket,
                                        #     group_id,
                                        #     f"{get_user_name(at_id, group_id)},GAY追杀令喵!!!!",
                                        # )
                                        pass
                                    elif HasKeyWords(
                                        raw_message, ["你不是GAY", "你不是gay"]
                                    ) and IsAdmin(user_id, group_id):
                                        _setting = load_setting()
                                        while at_id in load_setting()["boring"]:
                                            _setting["boring"].remove(at_id)
                                        dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},GAY追杀令取消了喵。",
                                        )
                                    elif HasKeyWords(
                                        raw_message, ["不要哈气"]
                                    ) and IsAdmin(user_id, group_id):
                                        _setting = load_setting()
                                        while at_id in load_setting()["huffing"]:
                                            _setting["huffing"].remove(at_id)
                                        dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},乐可停止追杀你了喵！",
                                        )
                                    elif HasKeyWords(raw_message, ["哈气"]) and IsAdmin(
                                        user_id, group_id
                                    ):
                                        _setting = load_setting()
                                        if at_id not in load_setting()["huffing"]:
                                            _setting["huffing"].append(at_id)
                                            dump_setting(_setting)
                                        await say(
                                            websocket,
                                            group_id,
                                            f"{get_user_name(at_id, group_id)},乐可要追杀你了喵！",
                                        )
                                # 管理艾特乐可
                                elif (
                                    IsAdmin(user_id, group_id) or IsDeveloper(user_id)
                                ) and at_id == load_setting()["bot_id"]:
                                    # 管理员功能 at乐可
                                    if "解除全体禁言" in message["raw_message"]:
                                        logging.info(
                                            f"{group_id}:{sender_name}({user_id})解除了全体禁言"
                                        )
                                        await SetGroupWholeNoBan(websocket, group_id)
                                    elif "全体禁言" in message["raw_message"]:
                                        logging.info(
                                            f"{group_id}:{sender_name}({user_id})全体禁言"
                                        )
                                        await SetGroupWholeBan(websocket, group_id)
                                    elif HasAllKeyWords(
                                        message["raw_message"], ["开启", "退群提醒"]
                                    ):
                                        now_status = GetGroupDecreaseMessageStatus(
                                            group_id
                                        )
                                        sender_name = get_user_name(user_id, group_id)
                                        group_name = GetGroupName(group_id)
                                        logging.info(
                                            f"{group_name}({group_id}):{sender_name}({user_id})尝试开启退群提醒。"
                                        )
                                        if not now_status:
                                            SwitchGroupDecreaseMessage(group_id)
                                        await say(
                                            websocket,
                                            group_id,
                                            "本群已经开启退群提醒喵。",
                                        )
                                    elif HasAllKeyWords(
                                        message["raw_message"], ["关闭", "退群提醒"]
                                    ):
                                        now_status = GetGroupDecreaseMessageStatus(
                                            group_id
                                        )
                                        sender_name = get_user_name(user_id, group_id)
                                        group_name = GetGroupName(group_id)
                                        logging.info(
                                            f"{group_name}({group_id}):{sender_name}({user_id})尝试关闭退群提醒。"
                                        )
                                        i = 0
                                        if now_status:
                                            SwitchGroupDecreaseMessage(group_id)
                                        await say(
                                            websocket,
                                            group_id,
                                            "本群已经关闭退群提醒喵。",
                                        )
                                    elif HasAllKeyWords(
                                        message["raw_message"], ["开启", "冷群回复"]
                                    ):
                                        now_status = GetColdGroupStatus(group_id)
                                        sender_name = get_user_name(user_id, group_id)
                                        group_name = GetGroupName(group_id)
                                        logging.info(
                                            f"{group_name}({group_id}):{sender_name}({user_id})尝试开启冷群回复。"
                                        )
                                        if not now_status:
                                            SwitchColdGroupChat(group_id)
                                        await say(
                                            websocket,
                                            group_id,
                                            "本群已经开启冷群回复喵。",
                                        )
                                    elif HasAllKeyWords(
                                        message["raw_message"], ["关闭", "冷群回复"]
                                    ):
                                        now_status = GetColdGroupStatus(group_id)
                                        sender_name = get_user_name(user_id, group_id)
                                        group_name = GetGroupName(group_id)
                                        logging.info(
                                            f"{group_name}({group_id}):{sender_name}({user_id})尝试关闭冷群回复。"
                                        )
                                        i = 0
                                        delete_list = []
                                        _setting = load_setting()
                                        for group in _setting["cold_group_king"]:
                                            if group["group_id"] == group_id:
                                                delete_list.append(i)
                                            i += 1
                                        for _ in delete_list:
                                            del _setting["cold_group_king"][_]
                                        dump_setting(_setting)
                                        if now_status:
                                            SwitchColdGroupChat(group_id)
                                        await say(
                                            websocket,
                                            group_id,
                                            "本群已经关闭冷群回复喵。",
                                        )
                                    elif HasKeyWords(
                                        message["raw_message"],
                                        ["throw"],
                                    ):
                                        if HasKeyWords(
                                            message["raw_message"], ["[CQ:image"]
                                        ):
                                            await say(
                                                websocket,
                                                group_id,
                                                f"{get_user_name(user_id, group_id)},暂时不支持图片喵。",
                                            )
                                        else:
                                            match = re.search(
                                                r"throw\s*([\s\S]*)$",
                                                message["raw_message"],
                                            )
                                            if match:
                                                print(match.group(1))
                                                uid = await throw_drifting_bottles(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    match.group(1),
                                                )
                                                write_bottles_uuid_message_id(
                                                    message_id, uid, group_id
                                                )
                                    elif HasKeyWords(
                                        message["raw_message"],
                                        [
                                            "捡漂流瓶",
                                            "捞漂流瓶",
                                        ],
                                    ):
                                        await pick_drifting_bottles_radom(
                                            websocket, user_id, group_id
                                        )
                                    else:
                                        if not chatFlag:
                                            consuming_time_process_queue.put(
                                                (
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    message_id,
                                                    "请不要艾特乐可喵,请以乐可开头说提示语喵，比如“乐可，功能。”。",
                                                    ConsumingTimeType.CHAT,
                                                )
                                            )
                                        # await say(
                                        #     websocket,
                                        #     group_id,
                                        #     f"{sender_name},请不要艾特乐可喵,请以乐可开头说提示语喵，比如“乐可，功能。”。",
                                        # )
                                elif at_id == load_setting()["bot_id"]:
                                    if HasKeyWords(
                                        message["raw_message"],
                                        ["throw"],
                                    ):
                                        if HasKeyWords(
                                            message["raw_message"], ["[CQ:image"]
                                        ):
                                            await say(
                                                websocket,
                                                group_id,
                                                f"{get_user_name(user_id, group_id)},暂时不支持图片喵。",
                                            )
                                        else:
                                            match = re.search(
                                                r"throw\s*([\s\S]*)$",
                                                message["raw_message"],
                                            )
                                            if match:
                                                print(match.group(1))
                                                uid = await throw_drifting_bottles(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    match.group(1),
                                                )
                                                write_bottles_uuid_message_id(
                                                    message_id, uid, group_id
                                                )
                                    elif HasKeyWords(
                                        message["raw_message"],
                                        [
                                            "捡漂流瓶",
                                            "捞漂流瓶",
                                        ],
                                    ):
                                        await pick_drifting_bottles_radom(
                                            websocket, user_id, group_id
                                        )
                                    else:
                                        if not chatFlag:
                                            consuming_time_process_queue.put(
                                                (
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    message_id,
                                                    "请不要艾特乐可喵,请以乐可开头说提示语喵，比如“乐可，功能。”。",
                                                    ConsumingTimeType.CHAT,
                                                )
                                            )

                                        # await say(
                                        #     websocket,
                                        #     group_id,
                                        #     f"{sender_name},请不要艾特乐可喵,请以乐可开头说提示语喵，比如“乐可，功能。”。",
                                        # )
                            if "CQ:reply,id=" in message["raw_message"]:
                                await is_comment_write(
                                    websocket, user_id, group_id, message["raw_message"]
                                )

                            # 复读大拇哥和忠诚、o/、O/
                            # if (
                            #     "[CQ:face,id=76]" in message["raw_message"]
                            #     or "[CQ:face,id=282]" in message["raw_message"]
                            #     or "o/" in message["raw_message"]
                            #     or "O/" in message["raw_message"]
                            #     or "👍🏻" in message["raw_message"]
                            # ) and ".com" not in message["raw_message"]:
                            #     if user_id in load_setting()["cxqy"]:
                            #         await websocket.send(
                            #             json.dumps(
                            #                 say(
                            #                     group_id,
                            #                     "小马于{}说:".format(
                            #                         datetime.datetime.now().strftime(
                            #                             "%Y年%m月%d日%H时%M分%S秒"
                            #                         )
                            #                     ),
                            #                 )
                            #             )
                            #         )
                            #     payload = {
                            #         "action": "send_group_msg",
                            #         "params": {
                            #             "group_id": group_id,
                            #             "message": message["raw_message"],
                            #         },
                            #     }
                            #     await websocket.send(json.dumps(payload))
                            if (
                                re.search(
                                    r"CQ:reply,id=\d+]好好好", message["raw_message"]
                                )
                                and user_id in load_setting()["developers_list"]
                            ):
                                message_id = re.findall(
                                    r"CQ:reply,id=(\d+)", message["raw_message"]
                                )[0]
                                await GetMessage(websocket, message_id, "applaud")
                            elif re.search(
                                r"CQ:reply,id=\d+]加精", message["raw_message"]
                            ):
                                message_id = re.findall(
                                    r"CQ:reply,id=(\d+)", message["raw_message"]
                                )[0]
                                await SetEssenceMsg(websocket, message_id)
                            elif re.search(
                                r"CQ:reply,id=\d+]移除加精", message["raw_message"]
                            ) and IsAdmin(user_id, group_id):
                                message_id = re.findall(
                                    r"CQ:reply,id=(\d+)", message["raw_message"]
                                )[0]
                                await DeleteEssenceMsg(websocket, message_id)
                            elif re.search(r"CQ:reply,id=\d+]", message["raw_message"]):
                                message_id = re.findall(
                                    r"CQ:reply,id=(\d+)", message["raw_message"]
                                )[0]
                                if HasAllKeyWords(
                                    message["raw_message"], ["看到", "了", "你"]
                                ) and HasKeyWords(message["raw_message"], ["吗", "嘛"]):
                                    await GetMessage(websocket, message_id, "so_cute")

                            # 新入群验证
                            if "{}_{}.jpg".format(user_id, group_id) in os.listdir(
                                "./vcode"
                            ):
                                if "看不清" in message["raw_message"]:
                                    if "{}_{}.jpg".format(
                                        user_id, group_id
                                    ) in os.listdir("./vcode"):
                                        update_vcode(user_id, group_id)
                                        await welcome_verify(
                                            websocket, user_id, group_id
                                        )

                                else:
                                    (mod, times) = verify(
                                        user_id,
                                        group_id,
                                        message["raw_message"],
                                    )
                                    if mod:
                                        # 通过验证
                                        if (
                                            group_id
                                            == load_setting()["admin_group_main"]
                                        ):
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                60,
                                            )
                                            await welcome_new(
                                                websocket, user_id, group_id
                                            )
                                        else:
                                            await welcom_new_no_admin(
                                                websocket, user_id, group_id
                                            )
                                    elif times > 0:
                                        await verify_fail_say(
                                            websocket, user_id, group_id, times
                                        )

                                    elif times <= 0:
                                        if not IsAdmin(user_id, group_id):
                                            await kick_member(
                                                websocket, user_id, group_id
                                            )
                                            await say(
                                                websocket,
                                                group_id,
                                                "{},验证码输入错误，你没有机会了喵。有缘江湖相会了喵。".format(
                                                    sender_name
                                                ),
                                            )
                            else:
                                match message["message"][0]["type"]:
                                    case "text":
                                        # print(message["message"][0]["data"]["text"])
                                        if (
                                            user_id
                                            in get_config("kotomitako", group_id)
                                            and (
                                                "喵" not in message["raw_message"]
                                                or (
                                                    "我" in message["raw_message"]
                                                    and "咱"
                                                    not in message["raw_message"]
                                                )
                                            )
                                            and "[CQ:image"
                                            not in message["raw_message"]
                                            and BotIsAdmin(group_id)
                                            and HasChinese(message["raw_message"])
                                        ):
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                60,
                                            )
                                            if (
                                                "我" in message["raw_message"]
                                                and "咱" not in message["raw_message"]
                                                and "喵" in message["raw_message"]
                                            ):
                                                await ReplySay(
                                                    websocket,
                                                    group_id,
                                                    message_id,
                                                    "{},你作为本群的香香软软小南梁，因为不用咱自称被禁言了喵。".format(
                                                        sender_name
                                                    ),
                                                )
                                            elif (
                                                "咱" in message["raw_message"]
                                                and "喵" not in message["raw_message"]
                                            ):
                                                await ReplySay(
                                                    websocket,
                                                    group_id,
                                                    message_id,
                                                    "{},你作为本群的香香软软小南梁，因为说话不带喵被禁言了喵。".format(
                                                        sender_name
                                                    ),
                                                )
                                            else:
                                                await ReplySay(
                                                    websocket,
                                                    group_id,
                                                    message_id,
                                                    "{},你作为本群的香香软软小南梁，因为说话不用咱自称而且不带喵被禁言了喵。".format(
                                                        sender_name
                                                    ),
                                                )
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                0,
                                            )
                                        elif (
                                            user_id in get_config("catgirl", group_id)
                                            and "喵" not in message["raw_message"]
                                            and "[CQ:image"
                                            not in message["raw_message"]
                                            and BotIsAdmin(group_id)
                                            and HasChinese(message["raw_message"])
                                        ):
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                60,
                                            )
                                            await ReplySay(
                                                websocket,
                                                group_id,
                                                message_id,
                                                "{},你因为说话不带喵被禁言了喵。".format(
                                                    sender_name
                                                ),
                                            )
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                0,
                                            )

                                        if (
                                            BotIsAdmin(group_id)
                                            and get_config("cat_day_date", group_id)
                                            != -1
                                            and user_id
                                            not in load_setting()["other_bots"]
                                        ):
                                            if (
                                                "喵" not in message["raw_message"]
                                                and "[CQ:image"
                                                not in message["raw_message"]
                                                and "[CQ:reply"
                                                not in message["raw_message"]
                                                and HasChinese(message["raw_message"])
                                                and datetime.datetime.now().day
                                                == get_config("cat_day_date", group_id)
                                            ):
                                                if not IsAdmin(user_id, group_id):
                                                    await ban_new(
                                                        websocket,
                                                        user_id,
                                                        group_id,
                                                        60,
                                                    )
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message["message_id"],
                                                        "{},每月{}号是本群喵喵日,你因为说话不带喵被禁言了喵。".format(
                                                            sender_name,
                                                            get_config(
                                                                "cat_day_date", group_id
                                                            ),
                                                        ),
                                                    )
                                                elif not get_config(
                                                    "cat_day_ignore_admin", group_id
                                                ):
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message["message_id"],
                                                        "{},每月{}号是本群喵喵日,你因为说话不带喵被艾特惩罚3次了喵。".format(
                                                            get_cx_str(user_id),
                                                            get_config(
                                                                "cat_day_date", group_id
                                                            ),
                                                        ),
                                                    )
                                                    AddAtPunishList(
                                                        user_id, group_id, 3
                                                    )
                                        if message["message"][0]["data"][
                                            "text"
                                        ].startswith("可乐"):
                                            await cute2(
                                                websocket,
                                                group_id,
                                            )
                                        # 早上好
                                        if (
                                            HasKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["早安", "早上好", "早"],
                                            )
                                            and datetime.datetime.now().hour < 10
                                            and datetime.datetime.now().hour >= 6
                                        ):
                                            await SayImgReply(
                                                websocket,
                                                user_id,
                                                group_id,
                                                message_id,
                                                "早上好喵！",
                                                "res/good_morning.jpg",
                                            )

                                        if message["message"][0]["data"][
                                            "text"
                                        ].startswith("乐可"):
                                            if (
                                                "功能"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await return_function(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                )
                                            elif (
                                                "每日一句"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await daily_word(
                                                    websocket, user_id, group_id
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
                                                    load_setting()["blacklist"].keys()
                                                ):
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        "{}在黑名单中，原因:{}。".format(
                                                            user_id,
                                                            load_setting()["blacklist"][
                                                                user_id
                                                            ],
                                                        ),
                                                    )

                                                else:
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        "{}不在黑名单中".format(
                                                            user_id
                                                        ),
                                                    )
                                            elif HasKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["捡漂流瓶", "捞漂流瓶"],
                                            ):
                                                await pick_drifting_bottles_radom(
                                                    websocket, user_id, group_id
                                                )
                                            elif (
                                                "吃什么"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await ban_new(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    60,
                                                )
                                                await SayAndAt(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    ",吃大嘴巴子🖐喵。",
                                                )

                                            elif (
                                                "胖次"
                                                in message["message"][0]["data"]["text"]
                                                or "胖茨"
                                                in message["message"][0]["data"]["text"]
                                            ) and (
                                                "云"
                                                in message["message"][0]["data"]["text"]
                                                or "☁️"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await WhoAskPants(websocket, group_id)
                                            elif (
                                                "挑战你"
                                                in message["message"][0]["data"]["text"]
                                                or "午时已到"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await russian_pve(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    sender_name,
                                                )

                                            elif (
                                                "开枪"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await russian_pve_shot(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    sender_name,
                                                )

                                            elif (
                                                "梗图"
                                                in message["message"][0]["data"]["text"]
                                                and "统计"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await MemeStatistics(
                                                    websocket, group_id
                                                )
                                            elif (
                                                "统计"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await get_statistics(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                )
                                            elif HasAllKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["生涯", "水群", "排名"],
                                            ):
                                                await GetLifeChatRecord(
                                                    websocket, group_id
                                                )
                                            elif (
                                                "水群排名"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await GetNowChatRecord(
                                                    websocket, group_id
                                                )
                                            elif (
                                                "排名"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await ranking_point_payload(
                                                    websocket, group_id
                                                )
                                            elif (
                                                "低保"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await poor_point(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                )

                                            elif (
                                                "抽签"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await drawing(
                                                    websocket, user_id, group_id
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
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        "最大100连喵!",
                                                    )

                                                else:
                                                    await luck_dog.luck_choice_mut(
                                                        websocket,
                                                        user_id,
                                                        sender_name,
                                                        group_id,
                                                        num,
                                                    )
                                            elif (
                                                "抽奖"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await luck_dog.luck_choice_mut(
                                                    websocket,
                                                    user_id,
                                                    sender_name,
                                                    group_id,
                                                    1,
                                                )
                                            elif (
                                                "积分"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"{sender_name},积分可通过抽奖、签到、在有权限的群水群和大头菜贸易获得喵。",
                                                )

                                            elif (
                                                "价格"
                                                in message["message"][0]["data"]["text"]
                                                and "大头菜"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                user_id = user_id
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"当前大头菜价格为: {GetNowPrice()} 喵,\n你的积分为 {find_point(user_id)} 喵。",
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
                                                    await BuyKohlrabi(
                                                        websocket,
                                                        user_id,
                                                        group_id,
                                                        num,
                                                    )
                                            elif HasAllKeyWords(
                                                raw_message, ["跑路", "梭哈"]
                                            ) and BotIsAdmin(group_id):
                                                await run_or_shot(
                                                    websocket, user_id, group_id
                                                )
                                            elif (
                                                "梭哈"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await ShowHand(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                )

                                            elif (
                                                "卖出"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                if (
                                                    "全部"
                                                    in message["message"][0]["data"][
                                                        "text"
                                                    ]
                                                ):
                                                    await SellKohlrabiAll(
                                                        websocket, user_id, group_id
                                                    )
                                                else:
                                                    num = FindNum(
                                                        message["message"][0]["data"][
                                                            "text"
                                                        ]
                                                    )
                                                    import math

                                                    num = math.trunc(num)
                                                    if num >= 1:
                                                        await SellKohlrabi(
                                                            websocket,
                                                            user_id,
                                                            group_id,
                                                            num,
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
                                                if num > 100 and not IsDeveloper(
                                                    user_id
                                                ):
                                                    # nums=100
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        "最大100连喵！",
                                                    )

                                                else:
                                                    nums = num
                                                    await send_meme_merge_forwarding(
                                                        websocket,
                                                        group_id,
                                                        nums,
                                                    )
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        "梗图{}连发货了喵，请好好享用喵。".format(
                                                            nums
                                                        ),
                                                    )

                                            elif (
                                                "装弹"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await russian(
                                                    websocket,
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ],
                                                    user_id,
                                                    group_id,
                                                )

                                            elif (
                                                "反击"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                if (
                                                    user_id
                                                    in load_setting()["developers_list"]
                                                ):
                                                    result = re.search(
                                                        r"\d+",
                                                        message["raw_message"],
                                                    )
                                                    qq = int(result.group())
                                                    if qq is not None:
                                                        SayAndAt(
                                                            websocket,
                                                            qq,
                                                            group_id,
                                                            f"惩罚性艾特{load_setting()["defense_times"]}次。",
                                                        )
                                                        AddAtPunishList(
                                                            qq,
                                                            group_id,
                                                            load_setting()[
                                                                "defense_times"
                                                            ],
                                                        )
                                            elif (
                                                "随机梗图"
                                                in message["message"][0]["data"]["text"]
                                                or "梗图"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await send_random_meme(
                                                    websocket, group_id
                                                )
                                            elif HasKeyWords(raw_message, ["睡眠套餐"]):
                                                if BotIsAdmin(group_id) and not IsAdmin(
                                                    user_id, group_id
                                                ):
                                                    say(
                                                        websocket,
                                                        group_id,
                                                        f"{get_user_name(user_id,group_id)}睡眠套餐已开启,明天早上6点见。",
                                                    )
                                                    await ban_new(
                                                        websocket,
                                                        user_id,
                                                        group_id,
                                                        GetSleepSeconds(),
                                                    )
                                                elif BotIsAdmin(group_id) and IsAdmin(
                                                    user_id, group_id
                                                ):
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message["message_id"],
                                                        "惩罚性艾特1000次。",
                                                    )
                                                    AddAtPunishList(
                                                        qq,
                                                        group_id,
                                                        1000,
                                                    )

                                            elif (
                                                "涩"
                                                in message["message"][0]["data"]["text"]
                                                and "兑换"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await sex_img(
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                )
                                            elif HasKeyWords(raw_message, ["丢骰子"]):
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"你的骰子结果是{random.randint(1,6)}",
                                                )
                                            elif (
                                                "cos"
                                                in message["message"][0]["data"]["text"]
                                                or "COS"
                                                in message["message"][0]["data"]["text"]
                                                or "涩图"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await get_cos(
                                                    websocket, user_id, group_id
                                                )
                                            elif HasKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["打我"],
                                            ):
                                                await ReplySay(
                                                    websocket,
                                                    group_id,
                                                    message_id,
                                                    "此功能进入了维护模式喵！暂时无法调用喵！",
                                                )
                                                # AddAtPunishList(
                                                #     user_id,
                                                #     group_id,
                                                #     load_setting()["defense_times"],
                                                # )
                                                # await ban_new(
                                                #     websocket,
                                                #     user_id,
                                                #     group_id,
                                                #     60 * 30,
                                                # )
                                                # await say(
                                                #     websocket,
                                                #     group_id,
                                                #     "口球塞上~乐可要开始打你了喵。",
                                                # )
                                            elif HasKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["再也不见", "重开"],
                                            ):
                                                if BotIsAdmin(group_id) and not IsAdmin(
                                                    user_id, group_id
                                                ):
                                                    await kick_member(
                                                        websocket, user_id, group_id
                                                    )
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message["message_id"],
                                                        "再见,再也不见。",
                                                    )
                                                elif BotIsAdmin(group_id) and IsAdmin(
                                                    user_id, group_id
                                                ):
                                                    await ReplySay(
                                                        websocket,
                                                        group_id,
                                                        message["message_id"],
                                                        "惩罚性艾特1000次。",
                                                    )
                                                    AddAtPunishList(
                                                        qq,
                                                        group_id,
                                                        1000,
                                                    )

                                            elif (
                                                "二次元"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await radom_waifu(
                                                    websocket, user_id, group_id
                                                )

                                            elif (
                                                "三次元"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await radom_real(
                                                    websocket, user_id, group_id
                                                )

                                            elif (
                                                "一言"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await one_word(
                                                    websocket, user_id, group_id
                                                )

                                            elif (
                                                "随机HTTP猫猫"
                                                in message["message"][0]["data"]["text"]
                                                or "随机http猫猫"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await send_radom_http_cat(
                                                    websocket, group_id
                                                )

                                            elif (
                                                "运势"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await luck_dog.luck_dog(
                                                    websocket,
                                                    user_id,
                                                    sender_name,
                                                    group_id,
                                                )

                                            elif (
                                                "签到"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await daily_check_in(
                                                    websocket,
                                                    user_id,
                                                    sender_name,
                                                    group_id,
                                                )
                                            elif (
                                                "V我50"
                                                in message["message"][0]["data"]["text"]
                                                or "v我50"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await kfc_v_me_50(websocket, group_id)
                                            elif (
                                                "塔罗牌"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await return_trarot_cards(
                                                    websocket, user_id, group_id
                                                )

                                            elif (
                                                "晚安"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                now_hour = (
                                                    datetime.datetime.now().strftime(
                                                        "%H"
                                                    )
                                                )
                                                now_hour = int(now_hour)
                                                if now_hour >= 22:
                                                    if IsAdmin(user_id, group_id):
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
                                                    else:
                                                        payload = {
                                                            "action": "send_group_msg",
                                                            "params": {
                                                                "group_id": group_id,
                                                                "message": "{},明天早上六点见喵,晚安，好梦喵。(∪.∪ )...zzz".format(
                                                                    sender_name
                                                                ),
                                                            },
                                                        }
                                                        await websocket.send(
                                                            json.dumps(payload)
                                                        )
                                                        await ban_new(
                                                            websocket,
                                                            user_id,
                                                            group_id,
                                                            GetSleepSeconds(),
                                                        )

                                                else:
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        f"{sender_name},还没到晚上10点喵,睡的有点早喵。",
                                                    )

                                            elif (
                                                "日报"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await daily_paper(
                                                    websocket, user_id, group_id
                                                )
                                            elif (
                                                "随机猫猫动图"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await radom_cat_gif(websocket, group_id)
                                            elif (
                                                "随机猫猫"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await radom_cat(websocket, group_id)
                                            elif HasKeyWords(raw_message, ["切换模型"]):
                                                now_model = switch_model()
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"切换模型成功，当前模型为{now_model}喵。",
                                                )
                                            elif HasKeyWords(
                                                raw_message, ["切换思考显示"]
                                            ):
                                                now_think_display = display_think()
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"切换思考显示，当前思考显示为{now_think_display}喵。",
                                                )

                                            elif (
                                                "看世界"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await photo_new(
                                                    websocket, user_id, group_id
                                                )

                                            elif (
                                                (
                                                    "打响指"
                                                    in message["message"][0]["data"][
                                                        "text"
                                                    ]
                                                )
                                                and IsAdmin(user_id, group_id)
                                                and BotIsAdmin(group_id)
                                            ):
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    "{},你确定吗？此功能会随机清除一半的群友,如果确定的话,请在5分钟内说“乐可,清楚明白”。如果取消的话,请说“乐可,取消”。".format(
                                                        get_user_name(
                                                            user_id,
                                                            group_id,
                                                        )
                                                    ),
                                                )

                                                await red_qq_avatar(websocket)
                                                _setting = load_setting()
                                                _setting["thanos_time"] = time.time()
                                                _setting["is_thanos"] = True
                                                dump_setting(_setting)
                                            elif (
                                                "清楚明白"
                                                in message["message"][0]["data"]["text"]
                                                and IsAdmin(user_id, group_id)
                                                and load_setting()["is_thanos"]
                                            ):
                                                await cxgl(websocket, user_id, group_id)
                                            elif (
                                                "取消"
                                                in message["message"][0]["data"]["text"]
                                                and IsAdmin(user_id, group_id)
                                                and load_setting()["is_thanos"]
                                            ):
                                                await nomoral_qq_avatar(websocket)
                                                _setting = load_setting()
                                                _setting["is_thanos"] = False
                                                dump_setting(_setting)
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    "乐可不是紫薯精喵。",
                                                )
                                            elif (
                                                "环境温度"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                (
                                                    cpu_temper,
                                                    cpu_temper_max,
                                                    gpu_temper,
                                                ) = getTemper()
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"CPU:{cpu_temper}/{cpu_temper_max}°C,GPU:{gpu_temper}°C,环境温度:{"错误,请检查传感器"}",
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
                                            elif (
                                                "喜报"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                text = re.findall(
                                                    r"喜报\s*([\s\S]*)$",
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ],
                                                )
                                                if len(text) != 0:
                                                    text = text[0]
                                                    await SoHappy(
                                                        websocket, group_id, text
                                                    )
                                            elif (
                                                "悲报"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                text = re.findall(
                                                    r"悲报\s*([\s\S]*)$",
                                                    message["message"][0]["data"][
                                                        "text"
                                                    ],
                                                )
                                                if len(text) != 0:
                                                    text = text[0]
                                                    await SoSad(
                                                        websocket, group_id, text
                                                    )
                                            elif (
                                                "答案之书"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await AnswerBook(
                                                    websocket, user_id, group_id
                                                )
                                            elif HasKeyWords(
                                                raw_message,
                                                ["throw", "THROW", "丢漂流瓶"],
                                            ):
                                                if HasKeyWords(
                                                    message["raw_message"],
                                                    ["[CQ:image"],
                                                ):
                                                    await say(
                                                        websocket,
                                                        group_id,
                                                        f"{get_user_name(user_id, group_id)},暂时不支持图片喵。",
                                                    )
                                                else:
                                                    match = re.search(
                                                        r"throw\s*([\s\S]*)$",
                                                        message["raw_message"],
                                                    )
                                                    if match:
                                                        print(match.group(1))
                                                        uid = await throw_drifting_bottles(
                                                            websocket,
                                                            user_id,
                                                            group_id,
                                                            match.group(1),
                                                        )
                                                        write_bottles_uuid_message_id(
                                                            message_id, uid, group_id
                                                        )
                                            elif (
                                                "status"
                                                in message["message"][0]["data"]["text"]
                                            ):
                                                await GetSystemInfoTable(
                                                    websocket, group_id
                                                )
                                            elif HasKeyWords(
                                                message["message"][0]["data"]["text"],
                                                ["获取IP", "获取ip"],
                                            ):
                                                await say(
                                                    websocket,
                                                    group_id,
                                                    f"本机IP:{GetLocalIP()}",
                                                )

                                            elif HasKeyWords(raw_message, ["笑话"]):
                                                await Joke(websocket, group_id)
                                            elif HasAllKeyWords(
                                                raw_message, ["乐可", "可爱"]
                                            ) and not HasKeyWords(raw_message, ["可乐"]):
                                                await cute3(websocket, group_id)
                                            else:
                                                if not chatFlag:
                                                    consuming_time_process_queue.put(
                                                        (
                                                            websocket,
                                                            user_id,
                                                            group_id,
                                                            message_id,
                                                            "",
                                                            ConsumingTimeType.CHAT,
                                                        )
                                                    )
                                        elif HasAllKeyWords(
                                            raw_message, ["乐可", "可爱"]
                                        ) and not HasKeyWords(raw_message, ["可乐"]):
                                            await cute3(websocket, group_id)
                                        elif (
                                            HasKeyWords(raw_message, ["乐可"])
                                            and not chatFlag
                                        ):
                                            sender_name = get_user_name(
                                                user_id, group_id
                                            )
                                            consuming_time_process_queue.put(
                                                (
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    message_id,
                                                    "",
                                                    ConsumingTimeType.CHAT,
                                                )
                                            )
                                    case "at":
                                        rev_id = message["message"][0]["data"]["qq"]
                                        group_id = message["group_id"]
                                        print(
                                            "{}:{}({})@ {}".format(
                                                message["time"],
                                                sender_name,
                                                user_id,
                                                rev_id,
                                            )
                                        )
                                        logging.info(
                                            "{}({})@ {}".format(
                                                sender_name,
                                                user_id,
                                                rev_id,
                                            )
                                        )
                                    case _:
                                        if (
                                            HasKeyWords(raw_message, ["乐可"])
                                            and not chatFlag
                                        ):
                                            sender_name = get_user_name(
                                                user_id, group_id
                                            )
                                            consuming_time_process_queue.put(
                                                (
                                                    websocket,
                                                    user_id,
                                                    group_id,
                                                    message_id,
                                                    "",
                                                    ConsumingTimeType.CHAT,
                                                )
                                            )
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
                                HasKeyWords(message["raw_message"], ["更新列表"])
                                and message["user_id"]
                                in load_setting()["developers_list"]
                            ):
                                await get_group_list(websocket)
                                await SayPrivte(
                                    websocket, message["user_id"], "更新列表成功喵！"
                                )
                            elif (
                                message["raw_message"].startswith("积分")
                                and message["user_id"]
                                in load_setting()["developers_list"]
                            ):
                                result = re.search(r"\d+", message["raw_message"])
                                # print(result.group())
                                await recharge_privte(
                                    websocket,
                                    message["user_id"],
                                    0,
                                    int(result.group()),
                                )
                                await SayPrivte(
                                    websocket, message["user_id"], "更新积分成功喵！"
                                )
                            elif (
                                HasKeyWords(message["raw_message"], ["发送日志"])
                                and message["user_id"]
                                in load_setting()["developers_list"]
                            ):
                                send_log_email()
                                await SayPrivte(
                                    websocket, message["user_id"], "发送日志成功喵！"
                                )
                            else:
                                text_message = ""
                                for i in message["message"]:
                                    match i["type"]:
                                        case "image":
                                            text_message += "[图片]"
                                        case "text":
                                            text_message += i["data"]["text"]
                                            pass
                                texts = []
                                texts.append(text_message)
                                consuming_time_process_queue.put(
                                    (
                                        websocket,
                                        user_id,
                                        group_id,
                                        message_id,
                                        texts,
                                        ConsumingTimeType.SAYPRIVTECHATNOCONTEXT,
                                    )
                                )

                case "notice":
                    if "sub_type" in message:
                        match message["sub_type"]:
                            case "poke":
                                # 谁拍的
                                user_id = message["user_id"]
                                # 拍谁
                                target_id = message["target_id"]
                                if target_id == load_setting()["bot_id"]:
                                    # logging.info(message)
                                    await cute3(websocket, message["group_id"])
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
                            if user_id != load_setting()["bot_id"]:
                                if BotIsAdmin(group_id):
                                    if (
                                        str(user_id)
                                        in load_setting()["blacklist"].keys()
                                        and group_id
                                        == load_setting()["admin_group_main"]
                                    ):
                                        if not IsAdmin(user_id, group_id):
                                            await SayAndAt(
                                                websocket,
                                                user_id,
                                                group_id,
                                                "你已因{},被本群拉黑，无法加入本群".format(
                                                    load_setting()["blacklist"][
                                                        str(user_id)
                                                    ],
                                                ),
                                            )
                                            await kick_member(
                                                websocket, user_id, group_id
                                            )

                                    else:
                                        (is_in_unwelcome, quit_time) = in_unwelcome(
                                            user_id, group_id
                                        )
                                        if (
                                            is_in_unwelcome
                                            and group_id
                                            == load_setting()["admin_group_main"]
                                        ):
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                60,
                                            )
                                            text = [
                                                "若言离更合，覆水已难收。",
                                                "世界上是没有后悔药的，开弓也是没有回头箭的。",
                                            ]
                                            await SayAndAt(
                                                websocket,
                                                user_id,
                                                group_id,
                                                f"{random.choice(text)}",
                                            )
                                            logging.info(
                                                f"{get_user_name(user_id, group_id)}({user_id}),因为{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(quit_time))}退出过群现在想重新加入而被踢出。"
                                            )
                                            # await kick_member(websocket, user_id, group_id)
                                            await KickMemberAndRejectAddRequest(
                                                websocket, user_id, group_id
                                            )
                                        else:
                                            await welcome_verify(
                                                websocket, user_id, group_id
                                            )

                                else:
                                    await welcom_new_no_admin(
                                        websocket, user_id, group_id
                                    )
                        # 有人离开了
                        case "group_decrease":
                            user_id = message["user_id"]
                            group_id = message["group_id"]
                            if message["sub_type"] == "leave" and get_config(
                                "group_decrease_reminder", group_id
                            ):
                                print(
                                    "{}:{}离开了群{}。\n".format(
                                        message["time"], user_id, group_id
                                    )
                                )
                                sender_name = get_user_name(user_id, group_id)
                                group_name = GetGroupName(group_id)
                                # add_unwelcome(user_id, message["time"], group_id)
                                text = [
                                    "十个小兵人，外出去吃饭；\n一个被呛死，还剩九个人。\n九个小兵人，熬夜熬得深；\n一个睡过头，还剩八个人。\n八个小兵人，动身去德文；\n一个要留下，还剩七个人。\n七个小兵人，一起去砍柴；\n一个砍自己，还剩六个人。\n六个小兵人，无聊玩蜂箱；\n一个被蛰死，还剩五个人。\n五个小兵人，喜欢学法律；\n一个当法官，还剩四个人。\n四个小兵人，下海去逞能；\n一个葬鱼腹，还剩三个人。\n三个小兵人，进了动物园；\n一个遭熊袭，还剩两个人。\n两个小兵人，外出晒太阳；\n一个被晒焦，还剩一个人。\n这个小兵人，孤单又影只；\n投缳上了吊，一个也没剩。",
                                    "天要下雨，娘要嫁人，由他去吧。",
                                    "祝他成功。",
                                ]
                                await say(
                                    websocket,
                                    group_id,
                                    "{}({})离开了群{}({})。\n{}".format(
                                        sender_name,
                                        user_id,
                                        group_name,
                                        group_id,
                                        random.choice(text),
                                    ),
                                )
                                logging.info(
                                    f"{sender_name}({user_id})离开了群{group_name}({group_id})"
                                )

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
                                # todo 冷群了回复
                                # consuming_time_process_queue.put(
                                #     (
                                #         websocket,
                                #         0,
                                #         0,
                                #         0,
                                #         "",
                                #         ConsumingTimeType.COLDREPLAY,
                                #     )
                                # )
                                _setting = load_setting()
                                if (
                                    time.time() - load_setting()["thanos_time"] > 300
                                    and load_setting()["is_thanos"]
                                ):
                                    await nomoral_qq_avatar(websocket)
                                    _setting["is_thanos"] = False
                                    _setting["thanos_time"] = time.time()
                                    dump_setting(_setting)
                                    await say(websocket, group_id, "乐可不是紫薯精喵。")
                                # 定期更新群友列表
                                if (
                                    time.time() - load_setting()["last_update_time"]
                                    > 300
                                ):
                                    await get_group_list(websocket)
                                    # for group in load_setting()["group_list"]:
                                    #     await get_group_member_list(websocket, group)
                                for delete_message in load_setting()[
                                    "delete_message_list"
                                ]:
                                    await delete_msg(websocket, delete_message)
                                _setting = load_setting()
                                _setting["delete_message_list"] = []
                                dump_setting(_setting)
                                # 定期检测新入群友验证码
                                for i in os.listdir("./vcode"):
                                    user_id = i.split(".")[0].split("_")[0]
                                    group_id = i.split(".")[0].split("_")[1]
                                    if check_validation_timeout(
                                        user_id,
                                        group_id,
                                    ):
                                        sender_name = get_user_name(user_id, group_id)
                                        if not IsAdmin(user_id, group_id):
                                            await ban_new(
                                                websocket,
                                                user_id,
                                                group_id,
                                                60,
                                            )
                                            await say(
                                                websocket,
                                                group_id,
                                                f"{sender_name}的验证码已过期，已自动踢出喵！",
                                            )
                                            await kick_member(
                                                websocket, user_id, group_id
                                            )
                                        delete_vcode(user_id, group_id)
                                # 0.2% 的概率乐可卖萌
                                if random.random() < 0.002:
                                    await cute(websocket, group_id)
                                # 定期清理过期的大头菜
                                ClearKohlrabi()
                                for index, user in enumerate(
                                    load_setting()["alarm_member"]
                                ):
                                    if (
                                        (
                                            datetime.datetime.now().hour
                                            == user["time_hour"]
                                            and datetime.datetime.now().minute
                                            >= user["time_minute"]
                                        )
                                        or datetime.datetime.now().hour
                                        > user["time_hour"]
                                    ) and not is_today(time.time(), user["time"]):
                                        if "res" in user:
                                            await SayAndAtImage(
                                                websocket,
                                                user["user_id"],
                                                user["group_id"],
                                                user["text"],
                                                user["res"],
                                            )
                                        else:
                                            await SayAndAt(
                                                websocket,
                                                user["user_id"],
                                                user["group_id"],
                                                user["text"],
                                            )
                                        _setting = load_setting()
                                        _setting["alarm_member"][index][
                                            "time"
                                        ] = time.time()
                                        dump_setting(_setting)
                            case _:
                                print(message)
                    else:
                        print(message)
                case "request":
                    # 请求事件
                    print(message)
        elif "echo" in message:
            matches = re.search(r"\|(\S+)\|(\d+)\|(\d+)", message["echo"])
            if matches:
                print(message)
                uuid = matches.group(1)
                user_id = matches.group(2)
                message_id = message["data"]["message_id"]
                group_id = matches.group(3)
                print(f"{uuid}|{user_id}|{message_id}|{group_id}")
                write_bottles_uuid_message_id(message_id, uuid, group_id)
            match message["echo"]:
                case "update_group_member_list":
                    # print(
                    #     "{}:开始更新{}({})群友列表！".format(
                    #         time.time(), message["group_name"], message["group_id"]
                    #     )
                    # )
                    for group_member in message["data"]:
                        user = Group_member()
                        user.init_by_dict(group_member)
                        updata_user_info(user)
                        group_id = user.group_id
                        name = get_user_name(user.user_id, user.group_id)
                        if get_config("kick_time_sec", user.group_id) != -1:
                            timeout = get_config("kick_time_sec", user.group_id)
                            if (
                                time.time() - user.last_sent_time > timeout
                                and BotIsAdmin(user.group_id)
                                and timeout != -1
                                and timeout >= 30 * 24 * 3600
                            ):
                                if not IsAdmin(user.user_id, user.group_id):
                                    print(
                                        "{}({})因{}个月未活跃被请出群聊{}({}),最后发言时间:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,
                                            GetGroupName(user.group_id),
                                            user.group_id,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        )
                                    )
                                    logging.info(
                                        "{}({})因{}个月未活跃被请出群聊{}({}),最后发言时间:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,
                                            GetGroupName(user.group_id),
                                            user.group_id,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        )
                                    )
                                    await say(
                                        websocket,
                                        user.group_id,
                                        "{}({})，乐可要踢掉你了喵！\n原因:{}个月未活跃。\n最后发言时间为:{}".format(
                                            name,
                                            user.user_id,
                                            timeout / 2592000,
                                            time.strftime(
                                                "%Y-%m-%d %H:%M:%S",
                                                time.localtime(user.last_sent_time),
                                            ),
                                        ),
                                    )
                                    await kick_member(
                                        websocket, user.user_id, user.group_id
                                    )
                case "delete_message_list":
                    _setting = load_setting()
                    _setting["delete_message_list"].append(
                        message["data"]["message_id"]
                    )
                    dump_setting(_setting)
                case "defense":
                    # print(message)
                    await delete_msg(websocket, message["data"]["message_id"])
                case "get_group_list":
                    print("开始更新群列表")
                    logging.info("开始更新群列表")
                    # print(message["data"])
                    for group in message["data"]:
                        logging.info(
                            f"正在更新群:{group["group_name"]}({group["group_id"]})"
                        )
                        update_group_info(
                            group["group_id"],
                            group["group_name"],
                            group["member_count"],
                            group["max_member_count"],
                        )
                        if group["group_id"] not in load_setting()["group_list"]:
                            _setting = load_setting()
                            _setting["group_list"].append(group["group_id"])
                            dump_setting(_setting)
                        await update_group_member_list(websocket, group["group_id"])
                    _setting = load_setting()
                    _setting["last_update_time"] = time.time()
                    dump_setting(_setting)
                    print("更新全部群列表完毕")
                    logging.info("更新全部群列表完毕")
                case "so_cute":
                    # print(message)
                    group_id = message["data"]["group_id"]
                    sender_id = message["data"]["sender"]["user_id"]
                    await SoCute(websocket, sender_id, group_id)
                case "applaud":
                    sender_id = message["data"]["sender"]["user_id"]
                    message_id = message["data"]["message_id"]
                    group_id = message["data"]["group_id"]
                    now_point = find_point(sender_id)
                    change_point(sender_id, group_id, now_point + 100)
                    sender_name = get_user_name(sender_id, group_id)
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
        elif "action" in message:
            if "message_id" in message:
                group_id = message["group_id"]
                message_id = message["message_id"]
                re_text = message["message"]
                await ReplySay(
                    websocket,
                    group_id,
                    message_id,
                    re_text,
                )
        else:

            if "status" in message:
                match message["status"]:
                    case "ok":
                        pass
                    case "_":
                        print(message)
            else:
                print(message)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


# def beijing(sec, what):
#     beijing_time = datetime.datetime.now() + datetime.timedelta(hours=8)
#     return beijing_time.timetuple()


# logging.Formatter.converter = beijing


# async def main():
#     async with websockets.serve(echo, "0.0.0.0", 27431):
#         await asyncio.get_running_loop().create_future()  # run forever


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"
now = GetLogTime()
today = datetime.datetime.today()
if not os.path.exists(f"log/{today.year}"):
    os.makedirs(f"log/{today.year}")
if not os.path.exists(f"log/{today.year}/{today.month}"):
    os.makedirs(f"log/{today.year}/{today.month}")
logging.basicConfig(
    filename=f"log/{today.year}/{today.month}/{now}.log",
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    encoding="utf-8",
)


async def handle_client(websocket):
    """
    处理客户端连接的函数
    注意：新版本的 websockets 库不再需要 path 参数
    """
    client_ip = websocket.remote_address[0]
    print(f"客户端 {client_ip} 已连接")

    try:
        async for message in websocket:
            # 使用 asyncio.create_task 来并发处理消息
            asyncio.create_task(process_message(message, websocket))
    except websockets.exceptions.ConnectionClosed:
        print(f"客户端 {client_ip} 断开连接")
    except Exception as e:
        print(
            f"处理客户端 {client_ip} 时发生错误: {e} line:{traceback.extract_tb(e.__traceback__)[0][1]}"
        )


async def process_message(message, websocket):
    try:
        await echo(websocket, message)
    except Exception as e:
        print(f"处理消息时出错: {e},line:{traceback.extract_tb(e.__traceback__)[0][1]}")


async def main():
    # 启动WebSocket服务器
    async with websockets.serve(
        handle_client,
        "localhost",
        27431,
        ping_interval=None,  # 禁用自动ping/pong以简化示例
    ):
        print("WebSocket 服务器已启动，监听 ws://localhost:27431")

        # 保持服务器运行
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    asyncio.run(main())
