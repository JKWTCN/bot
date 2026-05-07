import json
from datetime import datetime, timedelta

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.database_group import GetGroupName
from function.wordcloud_utils import (
    build_word_frequency,
    detect_period,
    generate_wordcloud_base64,
    get_period_start,
    query_first_chat_datetime,
    query_group_messages,
)
from tools.tools import HasAllKeyWords, HasKeyWords, load_setting


async def SendGroupPeriodWordCloud(websocket, group_id: int, period: str, period_cn: str):
    now = datetime.now()
    start_dt = get_period_start(period)

    if period == "life":
        first_chat_dt = query_first_chat_datetime(group_id=group_id, is_group=True)
        if first_chat_dt is not None:
            start_dt = datetime(first_chat_dt.year, first_chat_dt.month, first_chat_dt.day)

    end_dt_exclusive = datetime(now.year, now.month, now.day) + timedelta(days=1)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt_exclusive.timestamp())

    bot_id = load_setting("bot_id", 0)
    bot_name = load_setting("bot_name", "乐可")

    messages_text, msg_count = query_group_messages(group_id, start_ts, end_ts, bot_id, bot_name)
    word_freq = build_word_frequency(messages_text, bot_name)

    group_name = GetGroupName(group_id)

    payload = {
        "action": "send_msg_async",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }

    if msg_count == 0 or len(word_freq) == 0:
        payload["params"]["message"].append(
            {"type": "text", "data": {"text": f"{group_name} 在{period_cn}暂无发言记录"}}
        )
    elif sum(word_freq.values()) < 5:
        payload["params"]["message"].append(
            {"type": "text", "data": {"text": f"{group_name} 的{period_cn}词汇太少，无法生成词云"}}
        )
    else:
        payload["params"]["message"].append(
            {"type": "text", "data": {"text": f"{group_name} 的{period_cn}发言词云（总消息: {msg_count}）"}}
        )

        top5 = word_freq.most_common(5)
        top5_str = ", ".join(f"{w}({c})" for w, c in top5)
        payload["params"]["message"].append(
            {"type": "text", "data": {"text": f"热词TOP5: {top5_str}"}}
        )

        title = (
            f"{group_name} {period_cn}发言词云\n"
            f"统计时间:{start_dt.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        )

        image_base64, _ = generate_wordcloud_base64(word_freq, title)
        payload["params"]["message"].append(
            {"type": "image", "data": {"file": "base64://" + image_base64.decode("utf-8")}}
        )

    await websocket.send(json.dumps(payload))


class GroupChatWordCloudApplication(GroupMessageApplication):
    def __init__(self):
        applicationInfo = ApplicationInfo("群发言词云", "查看群组的生涯/本年/本季度/本月/本周发言词云")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo) -> None:
        period, period_cn = detect_period(message.plainTextMessage)
        if period is None or period_cn is None:
            return

        await SendGroupPeriodWordCloud(
            message.websocket,
            message.groupId,
            period,
            period_cn,
        )

    def judge(self, message: GroupMessageInfo) -> bool:
        plain_text = message.plainTextMessage
        return HasKeyWords(plain_text, [load_setting("bot_name", "乐可")]) and (
            HasAllKeyWords(plain_text, ["群", "生涯", "词云"])
            or HasAllKeyWords(plain_text, ["群", "本年", "词云"])
            or HasAllKeyWords(plain_text, ["群", "本季度", "词云"])
            or HasAllKeyWords(plain_text, ["群", "本季", "词云"])
            or HasAllKeyWords(plain_text, ["群", "本月", "词云"])
            or HasAllKeyWords(plain_text, ["群", "本周", "词云"])
        )
