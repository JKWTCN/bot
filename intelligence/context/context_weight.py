"""
上下文权重计算器
计算消息的重要性权重,用于智能上下文筛选
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List


class ContextWeightCalculator:
    """上下文权重计算器"""

    def __init__(self, db_path: str = "bot.db", config_path: str = "intelligence_config.json"):
        """
        初始化权重计算器

        Args:
            db_path: 消息数据库路径
            config_path: 配置文件路径
        """
        self.db_path = db_path
        self.bot_name = self._get_bot_name()
        self.config = self._load_config(config_path)

    def _get_bot_name(self) -> str:
        """获取机器人名称"""
        try:
            with open("static_setting.json", "r", encoding="utf-8") as f:
                setting = json.load(f)
            return setting.get("bot_name", "乐可")
        except Exception as e:
            logging.warning(f"读取机器人名称失败: {e}")
            return "乐可"

    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("weight_factors", {})
        except Exception as e:
            logging.warning(f"加载权重配置失败: {e},使用默认配置")
            return {}

    def calculate_weights(
        self,
        messages: List[Dict],
        user_profile: Dict,
        current_message: str,
        bot_name: str = None
    ) -> List[Dict]:
        """
        计算消息重要性权重

        Args:
            messages: 原始消息列表
            user_profile: 用户画像
            current_message: 当前消息内容
            bot_name: bot名称(可选,如果不提供则使用配置中的名称)

        Returns:
            带有权重的消息列表
        """
        if bot_name:
            self.bot_name = bot_name

        now = datetime.now().timestamp()
        weighted_messages = []
        current_user_id = user_profile.get('user_id', 0)

        for msg in messages:
            weight = 1.0

            # 1. 时间衰减因子
            time_weight = self._calculate_time_weight(msg['time'], now)
            weight *= time_weight

            # 2. 用户角色因子
            user_weight = self._calculate_user_weight(msg, current_user_id)
            weight *= user_weight

            # 3. 内容长度因子
            length_weight = self._calculate_length_weight(msg['raw_message'])
            weight *= length_weight

            # 4. 特殊内容因子
            special_weight = self._calculate_special_content_weight(msg)
            weight *= special_weight

            # 5. 相关性因子
            relevance_weight = self._calculate_relevance_weight(
                msg['raw_message'],
                current_message
            )
            weight *= relevance_weight

            weighted_messages.append({
                **msg,
                'weight': round(weight, 3)
            })

        return weighted_messages

    def _calculate_time_weight(self, msg_time: int, now: int) -> float:
        """
        计算时间权重 - 指数衰减

        Args:
            msg_time: 消息时间戳
            now: 当前时间戳

        Returns:
            时间权重值
        """
        time_diff = now - msg_time

        # 从配置获取半衰期
        half_life_minutes = self.config.get('time_decay', {}).get('half_life_minutes', 30)
        half_life_seconds = half_life_minutes * 60

        if time_diff < half_life_seconds:
            return 1.0
        elif time_diff < 7200:  # 2小时
            # 线性衰减: 1.0 -> 0.1
            ratio = (time_diff - half_life_seconds) / (7200 - half_life_seconds)
            return 1.0 - ratio * 0.9
        else:
            return 0.1

    def _calculate_user_weight(self, msg: Dict, current_user_id: int) -> float:
        """
        计算用户权重

        Args:
            msg: 消息字典
            current_user_id: 当前用户ID

        Returns:
            用户权重值
        """
        # 从配置获取权重
        user_role_config = self.config.get('user_role', {})

        # 当前用户的消息
        if msg['user_id'] == current_user_id:
            return user_role_config.get('current_user', 1.5)

        # bot的消息
        elif self.bot_name in msg['sender_nickname']:
            return user_role_config.get('bot', 1.2)

        # 其他用户
        else:
            return user_role_config.get('other', 1.0)

    def _calculate_length_weight(self, message: str) -> float:
        """
        计算长度权重

        Args:
            message: 消息内容

        Returns:
            长度权重值
        """
        length = len(message)

        # 太短(<10字符): 0.7
        if length < 10:
            return 0.7
        # 适中(10-100字符): 1.0
        elif length <= 100:
            return 1.0
        # 较长(100-200字符): 0.9
        elif length <= 200:
            return 0.9
        # 很长(>200字符): 0.7
        else:
            return 0.7

    def _calculate_special_content_weight(self, msg: Dict) -> float:
        """
        计算特殊内容权重

        Args:
            msg: 消息字典

        Returns:
            特殊内容权重值
        """
        weight = 1.0
        content = msg['raw_message']

        # 包含bot名字: 1.5
        if self.bot_name in content:
            weight *= 1.5

        # 包含@: 1.3
        if '[at:' in content:
            weight *= 1.3

        # 包含图片: 1.2
        if '[图片]' in content or '[image:' in content:
            weight *= 1.2

        # 包含回复: 1.2
        if '[reply:' in content or '[回复:' in content:
            weight *= 1.2

        return weight

    def _calculate_relevance_weight(self, past_message: str, current_message: str) -> float:
        """
        计算相关性权重 (简单的关键词匹配)

        Args:
            past_message: 历史消息
            current_message: 当前消息

        Returns:
            相关性权重值
        """
        if not current_message or not past_message:
            return 1.0

        # 提取当前消息的前20个字符作为关键词
        current_words = set(current_message[:20])

        # 计算交集比例
        overlap = len(current_words & set(past_message))

        # 相关性在0.8-1.2之间
        relevance = 0.8 + min(overlap / 20, 0.4)

        return relevance
