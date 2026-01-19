"""
智能模块异步数据库操作
"""
from database.db_pool import intel_db_pool


async def get_or_create_profile(user_id: int, nickname: str = None) -> dict:
    """获取或创建用户画像 (异步版本)"""
    import json
    import logging
    from datetime import datetime

    async with intel_db_pool.acquire() as conn:
        cursor = await conn.execute(
            "SELECT * FROM user_profile WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()

        if result:
            # 读取现有画像
            columns = [desc[0] for desc in cursor.description]
            profile = {}
            for i, col in enumerate(columns):
                value = result[i]
                if col in ['interests', 'topics_preference', 'interaction_style']:
                    profile[col] = json.loads(value) if value else {} if col != 'interests' else []
                else:
                    profile[col] = value

            # 更新最后交互时间
            await conn.execute(
                "UPDATE user_profile SET last_interacted_at = ? WHERE user_id = ?",
                (int(datetime.now().timestamp()), user_id)
            )
            await conn.commit()

            logging.info(f"读取用户画像: user_id={user_id}")
            return profile
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

            await conn.execute("""
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
            await conn.commit()
            logging.info(f"创建新用户画像: user_id={user_id}")
            return profile


async def update_profile(user_id: int, updates: dict) -> bool:
    """更新用户画像 (异步版本)"""
    import json
    import logging
    from datetime import datetime

    async with intel_db_pool.acquire() as conn:
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

        await conn.execute(sql, values)
        await conn.commit()

        logging.info(f"更新用户画像: user_id={user_id}, fields={list(updates.keys())}")
        return True
