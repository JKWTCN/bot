"""
长期记忆管理器
负责提取、存储和检索用户的长期记忆
"""

import json
import logging
import sqlite3
import re
from datetime import datetime
from typing import Dict, List, Optional


class MemoryManager:
    """长期记忆管理器"""

    def __init__(self, db_path: str = "bot_intelligence.db"):
        """
        初始化记忆管理器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path

    def extract_and_store_memory(
        self,
        user_id: int,
        message: str,
        context_type: str,
        context_id: int
    ) -> bool:
        """
        从对话中提取并存储记忆

        Args:
            user_id: 用户ID
            message: 对话内容
            context_type: 上下文类型 (group/private)
            context_id: 上下文ID (群组ID或私聊标识)

        Returns:
            是否成功提取和存储
        """
        try:
            logging.info(f"开始提取记忆: user_id={user_id}, message={message[:30]}")

            # 使用LLM提取关键信息
            memories = self._extract_memories_with_llm(message, user_id)

            if not memories:
                logging.info(f"未从消息中提取到记忆(消息内容不重要): user_id={user_id}")
                return False

            # 存储记忆
            stored_count = 0
            for mem in memories:
                if self._store_memory(
                    user_id=user_id,
                    memory_type=mem['type'],
                    content=mem['content'],
                    keywords=mem['keywords'],
                    importance=mem['importance'],
                    is_global=mem.get('is_global', True),
                    context_type=context_type,
                    context_id=context_id
                ):
                    stored_count += 1

            logging.info(f"成功存储 {stored_count}/{len(memories)} 条记忆: user_id={user_id}")
            return stored_count > 0

        except Exception as e:
            logging.error(f"记忆提取失败: {e}", exc_info=True)
            return False

    def retrieve_relevant_memories(
        self,
        user_id: int,
        current_message: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        检索相关记忆

        Args:
            user_id: 用户ID
            current_message: 当前消息内容
            limit: 返回记忆数量上限

        Returns:
            相关记忆列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 1. 获取该用户的高重要性记忆
            cursor.execute("""
                SELECT * FROM long_term_memory
                WHERE user_id = ?
                ORDER BY importance_score DESC, last_accessed_at DESC
                LIMIT ?
            """, (user_id, limit * 3))  # 多取一些用于筛选

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return []

            # 2. 根据上下文相关性排序
            memories = []
            for row in rows:
                memory = self._row_to_memory(cursor, row)
                relevance = self._calculate_memory_relevance(memory, current_message)
                memory['relevance'] = relevance
                memories.append(memory)

            # 3. 按相关性排序并返回top N
            memories.sort(key=lambda x: x['relevance'], reverse=True)

            # 4. 更新访问时间
            self._update_access_time([m['id'] for m in memories[:limit]])

            return memories[:limit]

        except Exception as e:
            logging.error(f"记忆检索失败: {e}")
            return []

    def _extract_memories_with_llm(self, message: str, user_id: int) -> List[Dict]:
        """
        使用LLM从消息中提取记忆

        Args:
            message: 消息内容
            user_id: 用户ID

        Returns:
            提取的记忆列表
        """
        try:
            import ollama

            extraction_prompt = f"""分析以下对话,提取值得长期记忆的重要信息。

对话内容: {message}

请识别以下类型的信息:
1. preference - 用户明确表达的偏好、喜好
2. agreement - 重要约定、承诺、计划
3. fact - 关键事实、个人信息
4. event - 重要事件、经历

只提取真正重要的信息。如果内容是日常闲聊、简单的问候或无关紧要的内容,请返回空数组。

返回JSON格式:
{{
    "memories": [
        {{
            "type": "preference|agreement|fact|event",
            "content": "具体内容描述",
            "keywords": ["关键词1", "关键词2"],
            "importance": 0.8,
            "is_global": true
        }}
    ]
}}

如果没有任何重要信息,返回: {{"memories": []}}
"""

            response = ollama.chat(
                model='qwen3:8b',
                messages=[{'role': 'user', 'content': extraction_prompt}],
                options={'temperature': 0.3}  # 降低温度以获得更稳定的提取
            )

            # 解析结果
            content = response['message']['content']

            # 提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                logging.debug(f"LLM未返回有效JSON: {content[:100]}")
                return []

            result = json.loads(json_match.group())
            memories = result.get('memories', [])

            # 验证和清理记忆
            valid_memories = []
            for mem in memories:
                if self._validate_memory(mem):
                    valid_memories.append(mem)

            return valid_memories

        except Exception as e:
            logging.error(f"LLM记忆提取失败: {e}")
            return []

    def _validate_memory(self, memory: Dict) -> bool:
        """
        验证记忆是否有效

        Args:
            memory: 记忆字典

        Returns:
            是否有效
        """
        # 检查必需字段
        required_fields = ['type', 'content', 'keywords', 'importance']
        for field in required_fields:
            if field not in memory:
                return False

        # 检查重要性阈值
        if memory['importance'] < 0.3:
            return False

        # 检查内容长度
        if len(memory['content']) < 5 or len(memory['content']) > 500:
            return False

        return True

    def _store_memory(
        self,
        user_id: int,
        memory_type: str,
        content: str,
        keywords: List[str],
        importance: float,
        is_global: bool,
        context_type: str,
        context_id: int
    ) -> bool:
        """
        存储单条记忆

        Args:
            user_id: 用户ID
            memory_type: 记忆类型
            content: 记忆内容
            keywords: 关键词列表
            importance: 重要性
            is_global: 是否全局记忆
            context_type: 上下文类型
            context_id: 上下文ID

        Returns:
            是否存储成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = int(datetime.now().timestamp())

            cursor.execute("""
                INSERT INTO long_term_memory (
                    user_id, memory_type, content, keywords,
                    importance_score, is_global, created_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, memory_type, content[:500],  # 限制内容长度
                json.dumps(keywords, ensure_ascii=False),
                min(1.0, importance),  # 重要性不超过1.0
                1 if is_global else 0,
                now, now
            ))

            conn.commit()
            conn.close()

            logging.debug(f"存储记忆: user={user_id}, type={memory_type}, content={content[:30]}")
            return True

        except Exception as e:
            logging.error(f"记忆存储失败: {e}")
            return False

    def _calculate_memory_relevance(self, memory: Dict, current_message: str) -> float:
        """
        计算记忆与当前消息的相关性

        Args:
            memory: 记忆字典
            current_message: 当前消息

        Returns:
            相关性分数 (0-1)
        """
        relevance = 0.5  # 基础相关性

        # 1. 关键词匹配
        memory_keywords = memory.get('keywords', [])
        message_lower = current_message.lower()

        matched_keywords = 0
        for keyword in memory_keywords:
            if keyword.lower() in message_lower:
                matched_keywords += 1
                relevance += 0.15  # 每个匹配关键词增加0.15

        # 2. 重要性加权
        importance = memory.get('importance_score', 0.5)
        relevance *= (0.5 + importance)  # 重要性影响相关性

        # 3. 时间衰减 (最近确认的记忆权重更高)
        last_accessed = memory.get('last_accessed_at', 0)
        if last_accessed:
            days_since_access = (datetime.now().timestamp() - last_accessed) / 86400
            time_decay = max(0.5, 1.0 - days_since_access * 0.02)  # 每天衰减2%
            relevance *= time_decay

        return min(1.0, relevance)

    def _update_access_time(self, memory_ids: List[int]) -> None:
        """
        更新记忆的访问时间

        Args:
            memory_ids: 记忆ID列表
        """
        if not memory_ids:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = int(datetime.now().timestamp())
            placeholders = ','.join('?' * len(memory_ids))

            cursor.execute(f"""
                UPDATE long_term_memory
                SET last_accessed_at = ?
                WHERE id IN ({placeholders})
            """, [now] + memory_ids)

            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"更新访问时间失败: {e}")

    def _row_to_memory(self, cursor, row) -> Dict:
        """将数据库行转换为字典"""
        columns = [desc[0] for desc in cursor.description]
        memory = {}

        for i, col in enumerate(columns):
            value = row[i]
            if col == 'keywords':
                memory[col] = json.loads(value) if value else []
            elif col == 'is_global':
                memory[col] = bool(value)
            else:
                memory[col] = value

        return memory
