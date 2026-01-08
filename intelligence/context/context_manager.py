"""
智能上下文管理器
替代原有的GetChatContext函数,提供智能的上下文获取能力
"""

import logging
import sqlite3
from typing import Dict, List
from intelligence.context.context_weight import ContextWeightCalculator
from intelligence.context.dynamic_window import DynamicWindowAdjuster


class ContextManager:
    """智能上下文管理器"""

    def __init__(self, db_path: str = "bot.db", config_path: str = "intelligence_config.json"):
        """
        初始化上下文管理器

        Args:
            db_path: 消息数据库路径
            config_path: 配置文件路径
        """
        self.db_path = db_path
        self.config_path = config_path
        self.weight_calculator = ContextWeightCalculator(db_path, config_path)
        self.window_adjuster = DynamicWindowAdjuster(db_path, config_path)

    async def get_smart_context(
        self,
        user_id: int,
        group_id: int,
        user_profile: Dict,
        current_message: str
    ) -> Dict:
        """
        获取智能上下文

        Args:
            user_id: 用户ID
            group_id: 群组ID
            user_profile: 用户画像
            current_message: 当前消息内容

        Returns:
            上下文结果字典,包含:
            - messages: 消息列表
            - summary: 对话摘要(暂未实现)
            - window_size: 窗口大小
            - total_weight: 总权重
        """
        try:
            # 1. 动态计算上下文窗口大小
            window_size = self.window_adjuster.calculate_window_size(
                user_profile=user_profile,
                group_id=group_id
            )

            # 2. 获取原始消息
            messages = self._get_raw_messages(user_id, group_id, window_size)

            if not messages:
                logging.info(f"未找到上下文消息: user_id={user_id}, group_id={group_id}")
                return {
                    'messages': [],
                    'summary': None,
                    'window_size': window_size,
                    'total_weight': 0
                }

            # 3. 计算每条消息的重要性权重
            weighted_messages = self.weight_calculator.calculate_weights(
                messages=messages,
                user_profile=user_profile,
                current_message=current_message
            )

            # 4. 根据权重筛选和排序
            max_tokens = self._get_max_context_tokens()
            selected_messages = self._select_messages_by_weight(
                weighted_messages,
                max_tokens=max_tokens
            )

            total_weight = sum(m['weight'] for m in weighted_messages)

            logging.info(
                f"获取智能上下文: user_id={user_id}, group_id={group_id}, "
                f"window_size={window_size}, selected={len(selected_messages)}, "
                f"total_weight={total_weight:.2f}"
            )

            return {
                'messages': selected_messages,
                'summary': None,  # 暂未实现摘要功能
                'window_size': window_size,
                'total_weight': total_weight
            }

        except Exception as e:
            logging.error(f"获取智能上下文失败: {e}", exc_info=True)
            # 返回空上下文
            return {
                'messages': [],
                'summary': None,
                'window_size': 10,
                'total_weight': 0
            }

    def _get_raw_messages(self, user_id: int, group_id: int, limit: int) -> List[Dict]:
        """
        获取原始消息

        Args:
            user_id: 用户ID
            group_id: 群组ID
            limit: 限制数量

        Returns:
            原始消息列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 获取最近的消息,时间限定在2小时内
            cursor.execute("""
                SELECT time, user_id, sender_nickname, raw_message, group_id
                FROM group_message
                WHERE group_id = ?
                AND time >= strftime('%s', 'now', '-2 hours')
                ORDER BY time DESC
                LIMIT ?
            """, (group_id, limit * 2))  # 多取一些用于筛选

            rows = cursor.fetchall()

            messages = []
            for row in reversed(rows):
                messages.append({
                    'time': row[0],
                    'user_id': row[1],
                    'sender_nickname': row[2],
                    'raw_message': row[3],
                    'group_id': row[4]
                })

            return messages

        except Exception as e:
            logging.error(f"获取原始消息失败: {e}")
            return []
        finally:
            conn.close()

    def _select_messages_by_weight(self, weighted_messages: List[Dict], max_tokens: int) -> List[Dict]:
        """
        根据权重选择消息

        Args:
            weighted_messages: 带权重的消息列表
            max_tokens: 最大token数

        Returns:
            选中的消息列表
        """
        # 按权重排序
        sorted_messages = sorted(weighted_messages, key=lambda x: x['weight'], reverse=True)

        selected = []
        total_tokens = 0

        for msg in sorted_messages:
            # 估算token数 (中文约1.5字符=1token)
            msg_tokens = len(msg['raw_message']) * 1.5

            if total_tokens + msg_tokens <= max_tokens:
                selected.append({
                    'role': 'assistant' if '乐可' in msg['sender_nickname'] else 'user',
                    'content': msg['raw_message']
                })
                total_tokens += msg_tokens
            else:
                break

        # 按时间顺序返回
        return list(reversed(selected))

    def _get_max_context_tokens(self) -> int:
        """获取最大上下文token数"""
        try:
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("personalization", {}).get("max_context_tokens", 2000)
        except:
            return 2000
