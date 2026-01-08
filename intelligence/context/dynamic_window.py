"""
动态窗口调整器
根据用户和群组的活跃度动态调整上下文窗口大小
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict


class DynamicWindowAdjuster:
    """动态窗口调整器"""

    def __init__(self, db_path: str = "bot.db", config_path: str = "intelligence_config.json"):
        """
        初始化窗口调整器

        Args:
            db_path: 消息数据库路径
            config_path: 配置文件路径
        """
        self.db_path = db_path
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("context_window", {})
        except Exception as e:
            logging.warning(f"加载窗口配置失败: {e},使用默认配置")
            return {
                'base_size': 10,
                'min_size': 5,
                'max_size': 30
            }

    def calculate_window_size(self, user_profile: Dict, group_id: int) -> int:
        """
        计算动态上下文窗口大小

        Args:
            user_profile: 用户画像
            group_id: 群组ID

        Returns:
            窗口大小(消息数量)
        """
        base_size = self.config.get('base_size', 10)

        # 1. 根据用户活跃度调整
        activity_multiplier = self._get_activity_multiplier(user_profile)

        # 2. 根据群组活跃度调整
        group_multiplier = self._get_group_activity_multiplier(group_id)

        # 3. 根据互动深度调整
        depth_multiplier = self._get_depth_multiplier(user_profile)

        # 计算最终窗口大小
        window_size = int(base_size * activity_multiplier * group_multiplier * depth_multiplier)

        # 限制在min-max之间
        min_size = self.config.get('min_size', 5)
        max_size = self.config.get('max_size', 30)

        final_size = max(min_size, min(max_size, window_size))

        logging.debug(
            f"窗口大小计算: base={base_size}, "
            f"activity_mult={activity_multiplier:.2f}, "
            f"group_mult={group_multiplier:.2f}, "
            f"depth_mult={depth_multiplier:.2f}, "
            f"final={final_size}"
        )

        return final_size

    def _get_activity_multiplier(self, user_profile: Dict) -> float:
        """
        根据用户活跃度获取调整系数

        Args:
            user_profile: 用户画像

        Returns:
            调整系数
        """
        activity = user_profile.get('activity_level', 0.5)

        if activity < 0.3:
            return 0.8  # 不活跃用户: 减少上下文
        elif activity < 0.7:
            return 1.0  # 中等活跃: 保持基础大小
        else:
            return 1.3  # 高活跃用户: 增加上下文

    def _get_group_activity_multiplier(self, group_id: int) -> float:
        """
        根据群组活跃度获取调整系数

        Args:
            group_id: 群组ID

        Returns:
            调整系数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            one_hour_ago = int((datetime.now() - timedelta(hours=1)).timestamp())

            cursor.execute("""
                SELECT COUNT(*) FROM group_message
                WHERE group_id = ? AND time >= ?
            """, (group_id, one_hour_ago))

            count = cursor.fetchone()[0]
            conn.close()

            if count < 10:
                return 0.8  # 低活跃群组
            elif count < 50:
                return 1.0  # 中等活跃
            else:
                return 1.2  # 高活跃群组

        except Exception as e:
            logging.error(f"计算群组活跃度失败: {e}")
            return 1.0

    def _get_depth_multiplier(self, user_profile: Dict) -> float:
        """
        根据互动深度获取调整系数

        Args:
            user_profile: 用户画像

        Returns:
            调整系数
        """
        depth = user_profile.get('interaction_depth', 0.5)

        # 互动深度越大,需要越多的上下文
        return 0.8 + depth * 0.4  # 0.8 - 1.2
