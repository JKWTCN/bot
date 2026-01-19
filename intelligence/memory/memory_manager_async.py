"""
记忆管理器 (异步版本)
性能优化:
- 使用异步数据库连接池
- 智能过滤，避免不必要的LLM调用
"""
import json
import logging
from datetime import datetime
from typing import Dict, List
from database.db_pool import intel_db_pool


class MemoryManager:
    """长期记忆管理器 (异步版本)"""

    def __init__(self, db_path: str = "bot_intelligence.db"):
        self.db_path = db_path

    async def retrieve_relevant_memories(
        self,
        user_id: int,
        current_message: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        检索相关记忆 (异步版本)

        性能优化:
        - 使用异步连接池
        - 使用索引加速查询
        """
        try:
            # 获取高重要性记忆
            rows = await intel_db_pool.fetchall(
                """SELECT * FROM long_term_memory
                   WHERE user_id = ?
                   ORDER BY importance_score DESC, last_accessed_at DESC
                   LIMIT ?""",
                (user_id, limit * 3)
            )

            if not rows:
                return []

            # 转换为字典并计算相关性
            memories = []
            for row in rows:
                # 将行转换为字典
                memory = self._row_to_memory(row)
                relevance = self._calculate_memory_relevance(memory, current_message)
                memory['relevance'] = relevance
                memories.append(memory)

            # 按相关性排序
            memories.sort(key=lambda x: x['relevance'], reverse=True)

            # 更新访问时间
            await self._update_access_time([m['id'] for m in memories[:limit]])

            return memories[:limit]

        except Exception as e:
            logging.error(f"记忆检索失败: {e}")
            return []

    async def extract_and_store_memory(
        self,
        user_id: int,
        message: str,
        context_type: str,
        context_id: int
    ) -> bool:
        """
        从对话中提取并存储记忆 (异步版本)

        性能优化:
        - 异步LLM调用
        - 异步数据库写入
        """
        try:
            logging.info(f"开始提取记忆: user_id={user_id}, message={message[:30]}")

            # 使用LLM提取关键信息
            memories = await self._extract_memories_with_llm(message, user_id)

            if not memories:
                logging.info(f"未从消息中提取到记忆: user_id={user_id}")
                return False

            # 存储记忆
            stored_count = 0
            for mem in memories:
                if await self._store_memory(
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

    async def _extract_memories_with_llm(self, message: str, user_id: int) -> List[Dict]:
        """使用LLM从消息中提取记忆"""
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

            # 同步调用ollama (因为ollama库不支持异步)
            response = ollama.chat(
                model='qwen3:8b',
                messages=[{'role': 'user', 'content': extraction_prompt}],
                options={'temperature': 0.3}
            )

            # 解析结果
            content = response['message']['content']
            import re
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
        """验证记忆是否有效"""
        required_fields = ['type', 'content', 'keywords', 'importance']
        for field in required_fields:
            if field not in memory:
                return False

        if memory['importance'] < 0.3:
            return False

        if len(memory['content']) < 5 or len(memory['content']) > 500:
            return False

        return True

    async def _store_memory(
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
        """存储单条记忆 (异步版本)"""
        try:
            now = int(datetime.now().timestamp())

            await intel_db_pool.execute(
                """INSERT INTO long_term_memory (
                    user_id, memory_type, content, keywords,
                    importance_score, is_global, created_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    memory_type,
                    content[:500],
                    json.dumps(keywords, ensure_ascii=False),
                    min(1.0, importance),
                    1 if is_global else 0,
                    now,
                    now
                )
            )

            logging.debug(f"存储记忆: user={user_id}, type={memory_type}, content={content[:30]}")
            return True

        except Exception as e:
            logging.error(f"记忆存储失败: {e}")
            return False

    def _calculate_memory_relevance(self, memory: Dict, current_message: str) -> float:
        """计算记忆与当前消息的相关性"""
        relevance = 0.5

        # 关键词匹配
        memory_keywords = memory.get('keywords', [])
        message_lower = current_message.lower()

        matched_keywords = 0
        for keyword in memory_keywords:
            if keyword.lower() in message_lower:
                matched_keywords += 1
                relevance += 0.15

        # 重要性加权
        importance = memory.get('importance_score', 0.5)
        relevance *= (0.5 + importance)

        # 时间衰减
        last_accessed = memory.get('last_accessed_at', 0)
        if last_accessed:
            days_since_access = (datetime.now().timestamp() - last_accessed) / 86400
            time_decay = max(0.5, 1.0 - days_since_access * 0.02)
            relevance *= time_decay

        return min(1.0, relevance)

    async def _update_access_time(self, memory_ids: List[int]) -> None:
        """更新记忆的访问时间 (异步版本)"""
        if not memory_ids:
            return

        try:
            now = int(datetime.now().timestamp())
            placeholders = ','.join('?' * len(memory_ids))

            await intel_db_pool.execute(
                f"""UPDATE long_term_memory
                   SET last_accessed_at = ?
                   WHERE id IN ({placeholders})""",
                [now] + memory_ids
            )

        except Exception as e:
            logging.error(f"更新访问时间失败: {e}")

    def _row_to_memory(self, row) -> Dict:
        """将数据库行转换为字典"""
        # 需要从cursor获取列名，这里简化处理
        columns = ['id', 'user_id', 'memory_type', 'content', 'keywords',
                  'importance_score', 'is_global', 'created_at', 'last_accessed_at']
        memory = {}

        for i, col in enumerate(columns):
            if i < len(row):
                value = row[i]
                if col == 'keywords':
                    memory[col] = json.loads(value) if value else []
                elif col == 'is_global':
                    memory[col] = bool(value)
                else:
                    memory[col] = value

        return memory


# 全局单例
_memory_manager_instance = None

def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例"""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance


async def retrieve_relevant_memories(user_id: int, current_message: str, limit: int = 5) -> List[Dict]:
    """便捷函数：检索相关记忆"""
    manager = get_memory_manager()
    return await manager.retrieve_relevant_memories(user_id, current_message, limit)
