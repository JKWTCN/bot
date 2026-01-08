"""
对话摘要生成器
对长对话进行智能摘要,减少token消耗
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class SummaryGenerator:
    """对话摘要生成器"""

    def __init__(self, db_path: str = "bot_intelligence.db"):
        """
        初始化摘要生成器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path

    def generate_summary(
        self,
        user_id: int,
        group_id: int,
        messages: List[Dict],
        force: bool = False
    ) -> Optional[str]:
        """
        生成对话摘要

        Args:
            user_id: 用户ID
            group_id: 群组ID
            messages: 消息列表
            force: 是否强制生成(不考虑时间间隔)

        Returns:
            摘要文本,如果不需要生成则返回None
        """
        if len(messages) < 5:
            logging.debug(f"消息数量不足5条,跳过摘要生成: 当前{len(messages)}条")
            return None

        # 检查是否需要生成摘要
        if not force and not self._should_generate_summary(user_id, group_id):
            return None

        try:
            # 使用LLM生成摘要
            summary_text = self._generate_with_llm(messages)

            if not summary_text:
                return None

            # 提取关键话题和实体
            key_topics = self._extract_topics(messages)
            key_entities = self._extract_entities(messages)

            # 存储摘要
            self._store_summary(
                user_id=user_id,
                group_id=group_id,
                summary_text=summary_text,
                key_topics=key_topics,
                key_entities=key_entities,
                messages=messages
            )

            logging.info(f"生成对话摘要: user={user_id}, group={group_id}")
            return summary_text

        except Exception as e:
            logging.error(f"摘要生成失败: {e}", exc_info=True)
            return None

    def _should_generate_summary(self, user_id: int, group_id: int) -> bool:
        """
        判断是否应该生成摘要

        Args:
            user_id: 用户ID
            group_id: 群组ID

        Returns:
            是否需要生成
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 检查最近的摘要时间
            one_hour_ago = int((datetime.now() - timedelta(hours=1)).timestamp())

            cursor.execute("""
                SELECT COUNT(*) FROM conversation_summary
                WHERE user_id = ? AND group_id = ? AND created_at >= ?
            """, (user_id, group_id, one_hour_ago))

            recent_count = cursor.fetchone()[0]
            conn.close()

            # 1小时内已有摘要,不再生成
            return recent_count == 0

        except Exception as e:
            logging.error(f"检查摘要状态失败: {e}")
            return False

    def _generate_with_llm(self, messages: List[Dict]) -> Optional[str]:
        """
        使用LLM生成摘要

        Args:
            messages: 消息列表

        Returns:
            摘要文本
        """
        try:
            import ollama

            # 构建对话文本
            conversation_text = "\n".join([
                f"{msg.get('sender_nickname', '用户')}: {msg.get('raw_message', '')}"
                for msg in messages[-10:]  # 只摘要最近10条
            ])

            prompt = f"""请简要总结以下对话的核心内容,不超过50字:

{conversation_text}

摘要:"""

            response = ollama.chat(
                model='qwen3:8b',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.5, 'max_tokens': 100}
            )

            summary = response['message']['content'].strip()
            # 限制长度
            if len(summary) > 200:
                summary = summary[:200]

            return summary

        except Exception as e:
            logging.error(f"LLM摘要生成失败: {e}")
            return None

    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """
        提取关键话题

        Args:
            messages: 消息列表

        Returns:
            话题列表
        """
        # 简单的关键词提取
        topics = set()
        keywords = ['编程', '游戏', '学习', '工作', '音乐', '电影', '运动', '美食', '旅行']

        for msg in messages:
            content = msg.get('raw_message', '')
            for keyword in keywords:
                if keyword in content:
                    topics.add(keyword)

        return list(topics)[:5]  # 最多5个话题

    def _extract_entities(self, messages: List[Dict]) -> List[str]:
        """
        提取关键实体

        Args:
            messages: 消息列表

        Returns:
            实体列表
        """
        # 简单的实体提取(时间、地点等)
        entities = []

        # 提取时间相关
        for msg in messages:
            content = msg.get('raw_message', '')
            if '明天' in content or '今天' in content or '晚上' in content:
                entities.append('时间约定')
                break

        return list(set(entities))[:3]

    def _store_summary(
        self,
        user_id: int,
        group_id: int,
        summary_text: str,
        key_topics: List[str],
        key_entities: List[str],
        messages: List[Dict]
    ) -> bool:
        """
        存储摘要

        Args:
            user_id: 用户ID
            group_id: 群组ID
            summary_text: 摘要文本
            key_topics: 关键话题
            key_entities: 关键实体
            messages: 消息列表

        Returns:
            是否存储成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = int(datetime.now().timestamp())
            start_time = messages[0].get('time', now)
            end_time = messages[-1].get('time', now)

            cursor.execute("""
                INSERT INTO conversation_summary (
                    user_id, group_id, summary_text, key_topics, key_entities,
                    message_count, start_time, end_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, group_id, summary_text,
                json.dumps(key_topics, ensure_ascii=False),
                json.dumps(key_entities, ensure_ascii=False),
                len(messages), start_time, end_time, now
            ))

            conn.commit()
            conn.close()

            logging.debug(f"存储摘要: user={user_id}, summary={summary_text[:30]}")
            return True

        except Exception as e:
            logging.error(f"摘要存储失败: {e}")
            return False

    def get_recent_summary(
        self,
        user_id: int,
        group_id: int,
        hours: int = 2
    ) -> Optional[str]:
        """
        获取最近的摘要

        Args:
            user_id: 用户ID
            group_id: 群组ID
            hours: 时间范围(小时)

        Returns:
            摘要文本
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp())

            cursor.execute("""
                SELECT summary_text FROM conversation_summary
                WHERE user_id = ? AND (group_id = ? OR group_id IS NULL)
                AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id, group_id, time_threshold))

            result = cursor.fetchone()
            conn.close()

            return result[0] if result else None

        except Exception as e:
            logging.error(f"获取摘要失败: {e}")
            return None
