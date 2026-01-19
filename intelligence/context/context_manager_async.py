"""
智能上下文管理器 (异步版本)
性能优化: 使用异步数据库连接池
"""
import logging
from database.db_pool import bot_db_pool
from intelligence.context.context_weight import ContextWeightCalculator
from intelligence.context.dynamic_window import DynamicWindowAdjuster
from typing import Dict, List


class ContextManager:
    """智能上下文管理器 (异步版本)"""

    def __init__(self, db_path: str = "bot.db", config_path: str = "intelligence_config.json"):
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
        获取智能上下文 (异步版本)

        性能优化:
        - 使用异步连接池查询数据库
        - 不阻塞事件循环

        Args:
            user_id: 用户ID
            group_id: 群组ID
            user_profile: 用户画像
            current_message: 当前消息内容

        Returns:
            上下文结果字典
        """
        try:
            bot_name = await self._get_bot_name()

            # 1. 动态计算上下文窗口大小
            window_size = self.window_adjuster.calculate_window_size(
                user_profile=user_profile,
                group_id=group_id
            )

            # 2. 获取原始消息 (异步)
            messages = await self._get_raw_messages(user_id, group_id, window_size)

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
            max_tokens = await self._get_max_context_tokens()
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
                'summary': None,
                'window_size': window_size,
                'total_weight': total_weight
            }

        except Exception as e:
            logging.error(f"获取智能上下文失败: {e}", exc_info=True)
            return {
                'messages': [],
                'summary': None,
                'window_size': 10,
                'total_weight': 0
            }

    async def _get_raw_messages(self, user_id: int, group_id: int, limit: int) -> List[Dict]:
        """获取原始消息 (异步版本)"""
        try:
            rows = await bot_db_pool.fetchall(
                """SELECT time, user_id, sender_nickname, raw_message, group_id
                   FROM group_message
                   WHERE group_id = ?
                   AND time >= strftime('%s', 'now', '-2 hours')
                   ORDER BY time DESC
                   LIMIT ?""",
                (group_id, limit * 2)
            )

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

    def _select_messages_by_weight(
        self,
        weighted_messages: List[Dict],
        max_tokens: int,
        user_id: int,
        bot_name: str
    ) -> List[Dict]:
        """根据权重选择消息"""
        bot_user_id = self._get_bot_user_id_sync()

        # 按权重排序
        sorted_messages = sorted(weighted_messages, key=lambda x: x['weight'], reverse=True)

        selected = []
        total_tokens = 0

        for msg in sorted_messages:
            msg_user_id = msg.get('user_id')
            sender_nickname = msg.get('sender_nickname', '')

            # 判断消息角色
            if msg_user_id == bot_user_id:
                role = 'assistant'
                content = msg['raw_message']
            elif msg_user_id == user_id:
                role = 'user'
                content = msg['raw_message']
            else:
                role = 'user'
                content = f"[用户{msg_user_id}]: {msg['raw_message']}"

            # 估算token数
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

    def _get_bot_user_id_sync(self) -> int:
        """获取bot的user_id (同步版本，用于性能关键路径)"""
        try:
            import json
            with open("static_setting.json", "r", encoding="utf-8") as f:
                setting = json.load(f)
            return setting.get("bot_id", 0)
        except Exception as e:
            logging.warning(f"获取bot_id失败: {e},返回0")
            return 0

    async def _get_bot_name(self) -> str:
        """获取bot名称"""
        from config.config_cache import get_bot_config
        config = await get_bot_config()
        return config.get("bot_name", "乐可")

    async def _get_max_context_tokens(self) -> int:
        """获取最大上下文token数"""
        from config.config_cache import get_intelligence_config
        config = await get_intelligence_config()
        return config.get("personalization", {}).get("max_context_tokens", 2000)


# 全局单例
_context_manager_instance = None

async def get_context_manager() -> ContextManager:
    """获取上下文管理器单例"""
    global _context_manager_instance
    if _context_manager_instance is None:
        _context_manager_instance = ContextManager()
    return _context_manager_instance


async def get_smart_context(user_id: int, group_id: int, user_profile: Dict, current_message: str) -> Dict:
    """便捷函数：获取智能上下文"""
    manager = await get_context_manager()
    return await manager.get_smart_context(user_id, group_id, user_profile, current_message)
