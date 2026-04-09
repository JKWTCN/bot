"""
猜数字游戏应用

功能：
- 管理猜数字游戏的开始、猜测、结束流程
- 积分奖励和惩罚机制
- 支持多群组独立运行
"""
import random
import math
import logging
from data.application.application import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo

from function.say import SayGroup
from function.GroupConfig import get_config
from function.guess_number_game_db import (
    start_game,
    get_game_status,
    make_guess,
    end_game,
    get_guess_records,
    get_participants,
    clear_game_records,
)
from function.datebase_other import change_point
from tools.tools import HasKeyWords, HasAllKeyWords, FindNum, load_setting


class GuessNumberGameApplication(GroupMessageApplication):
    """猜数字游戏应用类"""

    def __init__(self):
        applicationInfo = ApplicationInfo(
            "猜数字游戏",
            "互动性猜数字游戏，支持积分奖励机制"
        )
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    def judge(self, message: GroupMessageInfo) -> bool:
        """
        判断是否触发应用

        触发条件：
        1. 开始游戏：包含机器人名称 + "猜数字" + "开始"
        2. 猜测数字：包含 "猜" 或 "我猜" 后跟数字
        3. 查看状态：包含机器人名称 + "猜数字" + "状态"
        4. 结束游戏：包含机器人名称 + "猜数字" + "结束"
        """
        text = message.plainTextMessage
        bot_name = load_setting("bot_name", "乐可")

        # 检查是否启用游戏
        if not get_config("guess_number_enabled", message.groupId):
            return False

        # 开始游戏
        if HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "开始"]):
            return True

        # 查看状态
        if HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "状态"]):
            return True

        # 结束游戏
        if HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "结束"]):
            return True

        # 猜测数字（包含"猜"或"我猜"且后面有数字）
        if "猜" in text:
            guess = FindNum(text)
            if guess is not None:  # 如果找到数字
                return True

        return False

    async def process(self, message: GroupMessageInfo):
        """处理消息"""
        text = message.plainTextMessage
        bot_name = load_setting("bot_name", "乐可")
        group_id = message.groupId
        user_id = message.senderId
        websocket = message.websocket

        try:
            # 开始游戏
            if HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "开始"]):
                await self._start_game(message)

            # 查看状态
            elif HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "状态"]):
                await self._show_status(message)

            # 结束游戏
            elif HasKeyWords(text, [bot_name]) and HasAllKeyWords(text, ["猜数字", "结束"]):
                await self._end_game(message)

            # 猜测数字
            elif "猜" in text:
                guess = FindNum(text)
                if guess is not None:
                    await self._make_guess(message, guess)

        except Exception as e:
            logging.error(f"猜数字游戏处理错误: {e}", exc_info=True)
            await SayGroup(websocket, group_id, f"游戏发生错误：{str(e)}")

    async def _start_game(self, message: GroupMessageInfo):
        """开始新游戏"""
        group_id = message.groupId
        user_id = message.senderId
        websocket = message.websocket

        # 检查是否已有激活的游戏
        status = get_game_status(group_id)
        if status and status["is_active"]:
            await SayGroup(websocket, group_id,
                f"❌ 游戏已在进行中！\n"
                f"已猜 {status['guess_count']} 次\n"
                f"发送 '我猜XX' 参与游戏！"
            )
            return

        # 获取配置
        max_range = get_config("guess_number_max_range", group_id)

        # 生成随机数
        target_number = random.randint(1, max_range)

        # 开始游戏
        success = start_game(group_id, user_id, target_number)
        if not success:
            await SayGroup(websocket, group_id, "❌ 游戏启动失败！")
            return

        # 发送开始消息
        await SayGroup(websocket, group_id,
            f"🎮 猜数字游戏开始！\n"
            f"范围：1-{max_range}\n"
            f"发送 '我猜XXXX' 参与游戏！"
        )

        logging.info(f"群 {group_id} 开始猜数字游戏，目标数字：{target_number}")

    async def _make_guess(self, message: GroupMessageInfo, guess: int):
        """处理猜测"""
        group_id = message.groupId
        user_id = message.senderId
        websocket = message.websocket

        # 检查游戏是否激活
        status = get_game_status(group_id)
        if not status or not status["is_active"]:
            return  # 游戏未激活，不处理

        # 获取配置
        max_range = get_config("guess_number_max_range", group_id)
        max_guesses = get_config("guess_number_max_guesses", group_id)

        # 验证猜测范围
        if guess < 1 or guess > max_range:
            await SayGroup(websocket, group_id,
                f"❌ 请输入 1-{max_range} 之间的数字！"
            )
            return

        # 进行猜测
        result = make_guess(group_id, user_id, guess)

        if not result["success"]:
            await SayGroup(websocket, group_id, f"❌ {result['message']}")
            return

        # 检查是否达到最大猜测次数
        if result["guess_count"] >= max_guesses and result["result"] != "正确":
            # 游戏失败
            await self._game_over(message, success=False, target_number=status["target_number"])
            return

        # 显示猜测结果
        remaining = max_guesses - result["guess_count"]
        await SayGroup(websocket, group_id,
            f"[@{user_id}] {result['result']}！\n"
            f"已猜：{result['guess_count']}/{max_guesses}次 (剩余{remaining}次)"
        )

        # 如果猜中了
        if result["result"] == "正确":
            await self._game_over(message, success=True, target_number=result["target"],
                                guess_count=result["guess_count"], winner_id=user_id)

    async def _game_over(self, message: GroupMessageInfo, success: bool,
                        target_number: int, guess_count: int = 0, winner_id: int = None):
        """游戏结束处理"""
        group_id = message.groupId
        websocket = message.websocket

        # 获取配置
        max_range = get_config("guess_number_max_range", group_id)
        multiplier = get_config("guess_number_reward_multiplier", group_id)
        penalty = get_config("guess_number_penalty", group_id)

        # 获取参与者
        participants = get_participants(group_id)

        if success and winner_id:
            # 计算奖励
            reward = self._calculate_reward(guess_count, max_range, multiplier)

            # 发放奖励
            change_point(winner_id, group_id, reward)

            # 发送胜利消息
            await SayGroup(websocket, group_id,
                f"🎉 恭喜 [@{winner_id}] 猜中了！\n"
                f"正确答案是：{target_number}\n"
                f"用了 {guess_count} 次，获得 {reward} 积分！"
            )

            # 扣除其他参与者的积分
            if penalty > 0:
                for participant_id in participants:
                    if participant_id != winner_id:
                        change_point(participant_id, group_id, -penalty)

                await SayGroup(websocket, group_id,
                    f"💸 其他参与者各扣除 {penalty} 积分"
                )

        else:
            # 游戏失败
            await SayGroup(websocket, group_id,
                f"😢 游戏结束！没有人猜中！\n"
                f"正确答案是：{target_number}"
            )

            # 扣除所有参与者的积分
            if penalty > 0:
                for participant_id in participants:
                    change_point(participant_id, group_id, -penalty)

                await SayGroup(websocket, group_id,
                    f"💸 所有参与者各扣除 {penalty} 积分"
                )

        # 结束游戏
        end_game(group_id)

        logging.info(f"群 {group_id} 猜数字游戏结束，成功={success}，目标数字={target_number}")

    async def _show_status(self, message: GroupMessageInfo):
        """显示游戏状态"""
        group_id = message.groupId
        websocket = message.websocket

        status = get_game_status(group_id)

        if not status or not status["is_active"]:
            await SayGroup(websocket, group_id,
                "📊 当前没有激活的游戏\n"
                "发送 '@乐可 猜数字开始' 开始新游戏"
            )
            return

        # 获取配置
        max_range = get_config("guess_number_max_range", group_id)
        max_guesses = get_config("guess_number_max_guesses", group_id)

        # 获取最近猜测记录
        records = get_guess_records(group_id, limit=5)

        # 构建状态消息
        status_msg = (
            f"📊 游戏状态\n"
            f"范围：1-{max_range}\n"
            f"已猜：{status['guess_count']}/{max_guesses}次\n"
        )

        if records:
            status_msg += "\n最近猜测：\n"
            for record in records:
                status_msg += f"  [@{record['user_id']}] 猜 {record['guess']} → {record['result']}\n"

        await SayGroup(websocket, group_id, status_msg)

    async def _end_game(self, message: GroupMessageInfo):
        """手动结束游戏"""
        group_id = message.groupId
        user_id = message.senderId
        websocket = message.websocket

        status = get_game_status(group_id)

        if not status or not status["is_active"]:
            await SayGroup(websocket, group_id, "❌ 当前没有激活的游戏")
            return

        # 获取正确答案
        target_number = status["target_number"]

        # 结束游戏
        end_game(group_id)

        await SayGroup(websocket, group_id,
            f"🛑 游戏已手动结束\n"
            f"正确答案是：{target_number}"
        )

        logging.info(f"群 {group_id} 猜数字游戏被手动结束，目标数字={target_number}")

    def _calculate_reward(self, guess_count: int, max_range: int, multiplier: float) -> int:
        """
        根据猜测次数计算积分奖励
        奖励门槛基于二分法次数减1

        Args:
            guess_count: 猜测次数
            max_range: 数字范围
            multiplier: 奖励倍数

        Returns:
            int: 积分奖励
        """
        # 计算二分法所需次数
        binary_search_guesses = math.ceil(math.log2(max_range))

        # 奖励等级
        if guess_count <= binary_search_guesses - 1:
            base_reward = 200  # 神仙级
        elif guess_count <= binary_search_guesses + 2:
            base_reward = 100  # 优秀
        elif guess_count <= binary_search_guesses + 5:
            base_reward = 50   # 良好
        elif guess_count <= binary_search_guesses + 8:
            base_reward = 20   # 及格
        else:
            base_reward = 10   # 参与

        return int(base_reward * multiplier)
