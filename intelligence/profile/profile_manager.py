"""
用户画像管理器
负责创建、更新和管理用户画像
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional


class ProfileManager:
    """用户画像管理器"""

    def __init__(self, db_path: str = "bot_intelligence.db"):
        """
        初始化画像管理器

        Args:
            db_path: 数据库路径,默认为bot_intelligence.db
        """
        self.db_path = db_path

    def get_or_create_profile(self, user_id: int, nickname: str = None) -> Dict:
        """
        获取或创建用户画像

        Args:
            user_id: 用户ID
            nickname: 用户昵称(可选)

        Returns:
            用户画像字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                # 读取现有画像
                profile = self._row_to_profile(cursor, result)

                # 更新最后交互时间
                cursor.execute(
                    "UPDATE user_profile SET last_interacted_at = ? WHERE user_id = ?",
                    (int(datetime.now().timestamp()), user_id)
                )
                conn.commit()

                logging.info(f"读取用户画像: user_id={user_id}")
            else:
                # 创建新画像
                now = int(datetime.now().timestamp())
                profile = {
                    'user_id': user_id,
                    'nickname': nickname or '',
                    'interests': [],
                    'topics_preference': {},
                    'interaction_style': {'formality': 0.5, 'humor': 0.5},
                    'preferred_response_length': 'medium',
                    'emoji_usage': 0.5,
                    'activity_level': 0.5,
                    'familiarity_level': 0.3,
                    'interaction_depth': 0.3,
                    'created_at': now,
                    'updated_at': now,
                    'last_interacted_at': now,
                }

                cursor.execute("""
                    INSERT INTO user_profile (
                        user_id, nickname, interests, topics_preference, interaction_style,
                        preferred_response_length, emoji_usage, activity_level,
                        familiarity_level, interaction_depth, created_at, updated_at,
                        last_interacted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    profile['nickname'],
                    json.dumps(profile['interests']),
                    json.dumps(profile['topics_preference']),
                    json.dumps(profile['interaction_style']),
                    profile['preferred_response_length'],
                    profile['emoji_usage'],
                    profile['activity_level'],
                    profile['familiarity_level'],
                    profile['interaction_depth'],
                    profile['created_at'],
                    profile['updated_at'],
                    profile['last_interacted_at']
                ))
                conn.commit()
                logging.info(f"创建新用户画像: user_id={user_id}")

            return profile

        except Exception as e:
            logging.error(f"获取用户画像失败: {e}")
            # 返回默认画像
            return self._get_default_profile(user_id, nickname)
        finally:
            conn.close()

    def update_profile(self, user_id: int, updates: Dict) -> bool:
        """
        更新用户画像

        Args:
            user_id: 用户ID
            updates: 要更新的字段字典

        Returns:
            是否更新成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 构建更新SQL
            set_clauses = []
            values = []

            for key, value in updates.items():
                if key in ['interests', 'topics_preference', 'interaction_style']:
                    value = json.dumps(value, ensure_ascii=False)
                set_clauses.append(f"{key} = ?")
                values.append(value)

            if not set_clauses:
                return False

            values.append(int(datetime.now().timestamp()))  # updated_at
            values.append(user_id)

            sql = f"""
                UPDATE user_profile
                SET {', '.join(set_clauses)}, updated_at = ?
                WHERE user_id = ?
            """

            cursor.execute(sql, values)
            conn.commit()

            logging.info(f"更新用户画像: user_id={user_id}, fields={list(updates.keys())}")
            return True

        except Exception as e:
            logging.error(f"更新用户画像失败: {e}")
            return False
        finally:
            conn.close()

    def increment_familiarity(self, user_id: int, delta: float = 0.05) -> bool:
        """
        增加用户熟悉度

        Args:
            user_id: 用户ID
            delta: 增加量,默认0.05

        Returns:
            是否更新成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 获取当前熟悉度
            cursor.execute("SELECT familiarity_level FROM user_profile WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                current = result[0]
                new_value = min(1.0, current + delta)  # 最大不超过1.0

                cursor.execute(
                    "UPDATE user_profile SET familiarity_level = ?, updated_at = ? WHERE user_id = ?",
                    (new_value, int(datetime.now().timestamp()), user_id)
                )
                conn.commit()

                logging.info(f"增加熟悉度: user_id={user_id}, {current:.2f} -> {new_value:.2f}")
                return True

            return False

        except Exception as e:
            logging.error(f"增加熟悉度失败: {e}")
            return False
        finally:
            conn.close()

    def get_activity_level(self, user_id: int) -> float:
        """
        获取用户活跃度

        Args:
            user_id: 用户ID

        Returns:
            活跃度值 (0-1)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT activity_level FROM user_profile WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                return result[0]
            return 0.5

        except Exception as e:
            logging.error(f"获取活跃度失败: {e}")
            return 0.5
        finally:
            conn.close()

    def _row_to_profile(self, cursor, row) -> Dict:
        """将数据库行转换为字典"""
        columns = [desc[0] for desc in cursor.description]
        profile = {}

        for i, col in enumerate(columns):
            value = row[i]
            if col in ['interests', 'topics_preference', 'interaction_style']:
                profile[col] = json.loads(value) if value else {} if col != 'interests' else []
            else:
                profile[col] = value

        return profile

    def _get_default_profile(self, user_id: int, nickname: str = None) -> Dict:
        """获取默认画像"""
        now = int(datetime.now().timestamp())
        return {
            'user_id': user_id,
            'nickname': nickname or '',
            'interests': [],
            'topics_preference': {},
            'interaction_style': {'formality': 0.5, 'humor': 0.5},
            'preferred_response_length': 'medium',
            'emoji_usage': 0.5,
            'activity_level': 0.5,
            'familiarity_level': 0.3,
            'interaction_depth': 0.3,
            'created_at': now,
            'updated_at': now,
            'last_interacted_at': now,
        }
