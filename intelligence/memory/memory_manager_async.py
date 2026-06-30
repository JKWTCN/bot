"""
记忆管理器 (异步版本)
性能优化:
- 使用异步数据库连接池
- 智能过滤，避免不必要的LLM调用
"""
import hashlib
import json
import logging
import math
import re
from datetime import datetime
from typing import Any, Dict, List
from database.db_pool import intel_db_pool
from tools.tools import load_chat_ai_model, load_chat_ai_thinking


VECTOR_VERSION = "hash-ngram-v1"
VECTOR_SIZE = 128


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
            return await self.search_memories(
                user_id=user_id,
                query=current_message,
                limit=limit,
                mode="hybrid",
            )

        except Exception as e:
            logging.error(f"记忆检索失败: {e}")
            return []

    async def search_memories(
        self,
        *,
        user_id: int,
        query: str = "",
        limit: int = 5,
        mode: str = "hybrid",
        context_type: str | None = None,
        context_id: int | None = None,
        person_name: str = "",
        time_start: int | None = None,
        time_end: int | None = None,
    ) -> List[Dict]:
        """MaiBot-style memory search with lightweight hybrid retrieval."""
        normalized_mode = mode if mode in {"search", "time", "hybrid", "episode", "aggregate"} else "hybrid"
        if normalized_mode == "episode":
            return await self.search_episodes(
                user_id=user_id,
                query=query,
                limit=limit,
                context_id=context_id,
                time_start=time_start,
                time_end=time_end,
            )

        rows = await intel_db_pool.fetchall(
            """SELECT
                   id, user_id, memory_type, content, keywords,
                   importance_score, is_global, created_at, last_accessed_at,
                   content_hash, context_type, context_id, updated_at, access_count,
                   title, content_vector, vector_version, source_message_id,
                   person_name, memory_scope
               FROM long_term_memory
               WHERE (user_id = ? OR memory_scope = 'global')
               ORDER BY importance_score DESC, updated_at DESC, last_accessed_at DESC
               LIMIT ?""",
            (user_id, max(limit * 10, 30)),
        )
        memories = [self._row_to_memory(row) for row in rows]
        memories = self._filter_memory_candidates(
            memories,
            context_type=context_type,
            context_id=context_id,
            person_name=person_name,
            time_start=time_start,
            time_end=time_end,
        )
        if normalized_mode == "time" and not (time_start or time_end):
            memories.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or 0, reverse=True)
        elif normalized_mode == "aggregate":
            memories = self._aggregate_memories(memories, query=query, limit=limit)
        else:
            for memory in memories:
                memory["relevance"] = self._calculate_memory_relevance(memory, query)
            memories.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        selected = memories[: max(1, limit)]
        await self._update_access_time([m["id"] for m in selected if m.get("id")])
        return selected

    async def search_episodes(
        self,
        *,
        user_id: int,
        query: str,
        limit: int,
        context_id: int | None = None,
        time_start: int | None = None,
        time_end: int | None = None,
    ) -> List[Dict]:
        rows = await intel_db_pool.fetchall(
            """SELECT id, group_id, user_id, person_name, title, summary, keywords,
                      start_time, end_time, source_message_ids, content_vector,
                      vector_version, created_at, updated_at, access_count
               FROM memory_episode
               WHERE (user_id = ? OR user_id IS NULL OR user_id = 0)
               ORDER BY end_time DESC, updated_at DESC
               LIMIT ?""",
            (user_id, max(limit * 8, 24)),
        )
        episodes = [self._row_to_episode(row) for row in rows]
        filtered: list[dict[str, Any]] = []
        for episode in episodes:
            if context_id is not None and episode.get("group_id") not in (None, context_id):
                continue
            end_time = int(episode.get("end_time") or 0)
            if time_start is not None and end_time and end_time < time_start:
                continue
            if time_end is not None and end_time and end_time > time_end:
                continue
            episode["memory_type"] = "episode"
            episode["content"] = episode.get("summary", "")
            episode["relevance"] = self._calculate_memory_relevance(episode, query)
            filtered.append(episode)
        filtered.sort(key=lambda item: item.get("relevance", 0), reverse=True)
        selected = filtered[: max(1, limit)]
        if selected:
            ids = [item["id"] for item in selected if item.get("id")]
            placeholders = ",".join("?" * len(ids))
            await intel_db_pool.execute(
                f"UPDATE memory_episode SET access_count = COALESCE(access_count, 0) + 1 WHERE id IN ({placeholders})",
                ids,
            )
        return selected

    async def store_episode_from_messages(
        self,
        *,
        group_id: int,
        user_id: int,
        person_name: str,
        messages: list[dict[str, Any]],
    ) -> bool:
        """Store a compact recent-chat episode for later episode retrieval."""
        clean_messages: list[dict[str, Any]] = []
        for message in messages[-12:]:
            content = " ".join(str(message.get("content") or "").split())
            if not content:
                continue
            clean_messages.append(message | {"content": content})
        if len(clean_messages) < 4:
            return False

        now = int(datetime.now().timestamp())
        recent = await intel_db_pool.fetchone(
            """
            SELECT id FROM memory_episode
            WHERE group_id = ? AND updated_at >= ?
            ORDER BY updated_at DESC LIMIT 1
            """,
            (group_id, now - 1800),
        )
        if recent:
            return False

        summary_lines = [str(message.get("content") or "") for message in clean_messages[-8:]]
        summary = " / ".join(summary_lines)[:800]
        title = summary[:48]
        keywords = self._extract_keywords(summary)
        source_message_ids = [
            message.get("message_id")
            for message in clean_messages
            if message.get("message_id") is not None
        ]
        vector = json.dumps(self._build_text_vector(summary), ensure_ascii=False)
        times = [int(message.get("time") or now) for message in clean_messages]
        await intel_db_pool.execute(
            """
            INSERT INTO memory_episode (
                group_id, user_id, person_name, title, summary, keywords,
                start_time, end_time, source_message_ids, content_vector,
                vector_version, created_at, updated_at, access_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                group_id,
                user_id,
                person_name,
                title,
                summary,
                json.dumps(keywords, ensure_ascii=False),
                min(times) if times else now,
                max(times) if times else now,
                json.dumps(source_message_ids, ensure_ascii=False),
                vector,
                VECTOR_VERSION,
                now,
                now,
            ),
        )
        return True

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
            from ollama import chat
            import asyncio

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

            # 使用asyncio.to_thread执行同步ollama调用，避免阻塞事件循环
            response = await asyncio.to_thread(
                lambda: chat(
                    model=load_chat_ai_model(),
                    messages=[{'role': 'user', 'content': extraction_prompt}],
                    options={'temperature': 0.3},
                    think=load_chat_ai_thinking(),
                )
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
            normalized_content = " ".join(content.strip().split())[:500]
            content_hash = self._build_content_hash(normalized_content)
            content_vector = json.dumps(self._build_text_vector(normalized_content), ensure_ascii=False)

            await intel_db_pool.execute(
                """INSERT INTO long_term_memory (
                    user_id, memory_type, content, keywords,
                    importance_score, is_global, created_at, last_accessed_at,
                    content_hash, context_type, context_id, updated_at, access_count,
                    title, content_vector, vector_version, source_message_id,
                    person_name, memory_scope
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, memory_type, content_hash) DO UPDATE SET
                    keywords = excluded.keywords,
                    importance_score = MAX(long_term_memory.importance_score, excluded.importance_score),
                    is_global = excluded.is_global,
                    last_accessed_at = excluded.last_accessed_at,
                    context_type = excluded.context_type,
                    context_id = excluded.context_id,
                    updated_at = excluded.updated_at,
                    content_vector = excluded.content_vector,
                    vector_version = excluded.vector_version,
                    source_message_id = excluded.source_message_id,
                    person_name = COALESCE(excluded.person_name, long_term_memory.person_name),
                    memory_scope = excluded.memory_scope,
                    access_count = COALESCE(long_term_memory.access_count, 0) + 1""",
                (
                    user_id,
                    memory_type,
                    normalized_content,
                    json.dumps(keywords, ensure_ascii=False),
                    min(1.0, importance),
                    1 if is_global else 0,
                    now,
                    now,
                    content_hash,
                    context_type,
                    context_id,
                    now,
                    normalized_content[:60],
                    content_vector,
                    VECTOR_VERSION,
                    context_id if context_type == "message" else None,
                    "",
                    "person",
                )
            )

            logging.debug(f"存储记忆: user={user_id}, type={memory_type}, content={content[:30]}")
            return True

        except Exception as e:
            logging.error(f"记忆存储失败: {e}")
            return False

    def _build_content_hash(self, content: str) -> str:
        """生成用于长期记忆去重的稳定 hash。"""
        normalized = " ".join(content.strip().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _calculate_memory_relevance(self, memory: Dict, current_message: str) -> float:
        """计算记忆与当前消息的相关性"""
        relevance = 0.5

        if not current_message:
            current_message = ""

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

        # 本地哈希向量相似度
        query_vector = self._build_text_vector(current_message)
        memory_vector = self._parse_vector(memory.get("content_vector"))
        if query_vector and memory_vector:
            relevance += 0.7 * self._cosine_similarity(query_vector, memory_vector)

        content = str(memory.get("content") or memory.get("summary") or "")
        if current_message and current_message in content:
            relevance += 0.25

        # 时间衰减
        last_accessed = memory.get('last_accessed_at', 0)
        if last_accessed:
            days_since_access = (datetime.now().timestamp() - last_accessed) / 86400
            time_decay = max(0.5, 1.0 - days_since_access * 0.02)
            relevance *= time_decay

        return min(2.0, relevance)

    def _filter_memory_candidates(
        self,
        memories: list[Dict],
        *,
        context_type: str | None,
        context_id: int | None,
        person_name: str,
        time_start: int | None,
        time_end: int | None,
    ) -> list[Dict]:
        filtered: list[Dict] = []
        for memory in memories:
            if context_type and memory.get("context_type") not in (None, "", context_type):
                continue
            if context_id is not None:
                memory_context_id = memory.get("context_id")
                if memory_context_id not in (None, 0, context_id):
                    continue
            if person_name:
                haystack = " ".join(
                    str(memory.get(key) or "")
                    for key in ("person_name", "content", "keywords", "title")
                )
                if person_name not in haystack:
                    continue
            updated_at = int(memory.get("updated_at") or memory.get("created_at") or 0)
            if time_start is not None and updated_at and updated_at < time_start:
                continue
            if time_end is not None and updated_at and updated_at > time_end:
                continue
            filtered.append(memory)
        return filtered

    def _aggregate_memories(self, memories: list[Dict], *, query: str, limit: int) -> list[Dict]:
        buckets: dict[str, dict[str, Any]] = {}
        for memory in memories:
            memory_type = str(memory.get("memory_type") or "fact")
            bucket = buckets.setdefault(
                memory_type,
                {
                    "id": -len(buckets) - 1,
                    "memory_type": f"aggregate:{memory_type}",
                    "content": "",
                    "keywords": [],
                    "importance_score": 0.5,
                    "updated_at": 0,
                    "access_count": 0,
                    "_items": [],
                },
            )
            bucket["_items"].append(memory)
            bucket["updated_at"] = max(int(bucket.get("updated_at") or 0), int(memory.get("updated_at") or 0))
        aggregated: list[Dict] = []
        for bucket in buckets.values():
            items = sorted(bucket.pop("_items"), key=lambda item: item.get("importance_score") or 0, reverse=True)
            lines = [str(item.get("content") or "") for item in items[:4] if item.get("content")]
            if not lines:
                continue
            bucket["content"] = "；".join(lines)
            bucket["relevance"] = self._calculate_memory_relevance(bucket, query)
            aggregated.append(bucket)
        aggregated.sort(key=lambda item: item.get("relevance", 0), reverse=True)
        return aggregated[: max(1, limit)]

    async def _update_access_time(self, memory_ids: List[int]) -> None:
        """更新记忆的访问时间 (异步版本)"""
        if not memory_ids:
            return

        try:
            now = int(datetime.now().timestamp())
            placeholders = ','.join('?' * len(memory_ids))

            await intel_db_pool.execute(
                f"""UPDATE long_term_memory
                   SET last_accessed_at = ?,
                       access_count = COALESCE(access_count, 0) + 1
                   WHERE id IN ({placeholders})""",
                [now] + memory_ids
            )

        except Exception as e:
            logging.error(f"更新访问时间失败: {e}")

    def _row_to_memory(self, row) -> Dict:
        """将数据库行转换为字典"""
        # 需要从cursor获取列名，这里简化处理
        columns = [
            'id', 'user_id', 'memory_type', 'content', 'keywords',
            'importance_score', 'is_global', 'created_at', 'last_accessed_at',
            'content_hash', 'context_type', 'context_id', 'updated_at',
            'access_count', 'title', 'content_vector', 'vector_version',
            'source_message_id', 'person_name', 'memory_scope'
        ]
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

    def _row_to_episode(self, row) -> Dict:
        columns = [
            "id", "group_id", "user_id", "person_name", "title", "summary",
            "keywords", "start_time", "end_time", "source_message_ids",
            "content_vector", "vector_version", "created_at", "updated_at",
            "access_count",
        ]
        episode: dict[str, Any] = {}
        for index, column in enumerate(columns):
            if index >= len(row):
                continue
            value = row[index]
            if column in {"keywords", "source_message_ids"}:
                try:
                    episode[column] = json.loads(value) if value else []
                except Exception:
                    episode[column] = []
            else:
                episode[column] = value
        return episode

    def _build_text_vector(self, text: str) -> list[float]:
        if not text:
            return []
        vector = [0.0] * VECTOR_SIZE
        tokens = self._tokenize_for_vector(text)
        if not tokens:
            return []
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % VECTOR_SIZE
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return []
        return [round(value / norm, 6) for value in vector]

    def _tokenize_for_vector(self, text: str) -> list[str]:
        normalized = " ".join(text.lower().split())
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        grams = list(tokens)
        compact_cn = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
        grams.extend(compact_cn[index:index + 2] for index in range(max(0, len(compact_cn) - 1)))
        grams.extend(compact_cn[index:index + 3] for index in range(max(0, len(compact_cn) - 2)))
        return [gram for gram in grams if gram]

    def _extract_keywords(self, text: str, limit: int = 8) -> list[str]:
        tokens = self._tokenize_for_vector(text)
        counts: dict[str, int] = {}
        for token in tokens:
            if len(token) < 2:
                continue
            counts[token] = counts.get(token, 0) + 1
        return [
            token
            for token, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def _parse_vector(self, raw_vector) -> list[float]:
        if isinstance(raw_vector, list):
            return [float(value) for value in raw_vector]
        if not raw_vector:
            return []
        try:
            parsed = json.loads(raw_vector)
            if isinstance(parsed, list):
                return [float(value) for value in parsed]
        except Exception:
            return []
        return []

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return max(0.0, sum(l * r for l, r in zip(left, right)))


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


async def search_memories(
    *,
    user_id: int,
    query: str = "",
    limit: int = 5,
    mode: str = "hybrid",
    context_type: str | None = None,
    context_id: int | None = None,
    person_name: str = "",
    time_start: int | None = None,
    time_end: int | None = None,
) -> List[Dict]:
    manager = get_memory_manager()
    return await manager.search_memories(
        user_id=user_id,
        query=query,
        limit=limit,
        mode=mode,
        context_type=context_type,
        context_id=context_id,
        person_name=person_name,
        time_start=time_start,
        time_end=time_end,
    )


async def store_episode_from_messages(
    *,
    group_id: int,
    user_id: int,
    person_name: str,
    messages: list[dict[str, Any]],
) -> bool:
    manager = get_memory_manager()
    return await manager.store_episode_from_messages(
        group_id=group_id,
        user_id=user_id,
        person_name=person_name,
        messages=messages,
    )
