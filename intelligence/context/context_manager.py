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
            # 获取bot名称
            bot_name = self._get_bot_name()

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
                current_message=current_message,
                bot_name=bot_name
            )

            # 4. 根据权重筛选和排序
            max_tokens = self._get_max_context_tokens()
            selected_messages = self._select_messages_by_weight(
                weighted_messages,
                max_tokens=max_tokens,
                user_id=user_id,
                bot_name=bot_name
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

    def _select_messages_by_weight(
        self,
        weighted_messages: List[Dict],
        max_tokens: int,
        user_id: int,
        bot_name: str
    ) -> List[Dict]:
        """
        根据权重选择消息,并正确区分消息角色

        Args:
            weighted_messages: 带权重的消息列表
            max_tokens: 最大token数
            user_id: 当前用户ID
            bot_name: bot名称

        Returns:
            选中的消息列表,包含群组对话但区分角色
        """
        # 获取bot的user_id
        bot_user_id = self._get_bot_user_id()

        # 按权重排序
        sorted_messages = sorted(weighted_messages, key=lambda x: x['weight'], reverse=True)

        selected = []
        total_tokens = 0

        for msg in sorted_messages:
            msg_user_id = msg.get('user_id')
            sender_nickname = msg.get('sender_nickname', '')

            # 判断消息角色
            if msg_user_id == bot_user_id:
                # bot的消息
                role = 'assistant'
                content = msg['raw_message']
            elif msg_user_id == user_id:
                # 当前用户的消息
                role = 'user'
                content = msg['raw_message']
            else:
                # 其他用户的消息:添加昵称前缀,让LLM知道是别人说的
                role = 'user'
                content = f"[{sender_nickname}]: {msg['raw_message']}"

            # 估算token数 (中文约1.5字符=1token)
            msg_tokens = len(content) * 1.5

            if total_tokens + msg_tokens <= max_tokens:
                selected.append({
                    'role': role,
                    'content': content
                })
                total_tokens += msg_tokens
            else:
                break

        # 按时间顺序返回
        return list(reversed(selected))

    def _get_bot_user_id(self) -> int:
        """获取bot的user_id"""
        try:
            import json
            with open("static_setting.json", "r", encoding="utf-8") as f:
                setting = json.load(f)
            return setting.get("bot_id", 0)
        except Exception as e:
            logging.warning(f"获取bot_id失败: {e},返回0")
            return 0

    def _get_bot_name(self) -> str:
        """获取bot名称"""
        try:
            import json
            with open("static_setting.json", "r", encoding="utf-8") as f:
                setting = json.load(f)
            return setting.get("bot_name", "乐可")
        except Exception as e:
            logging.warning(f"获取bot名称失败: {e},使用默认名称'乐可'")
            return "乐可"

    def _get_max_context_tokens(self) -> int:
        """获取最大上下文token数"""
        try:
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("personalization", {}).get("max_context_tokens", 2000)
        except:
            return 2000
