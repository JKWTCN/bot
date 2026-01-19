"""
记忆批量处理器 (异步版本)
性能优化:
- 批量处理记忆提取
- 减少LLM调用次数
- 异步队列处理
"""
import asyncio
import logging
from collections import deque
from typing import Dict, List


class MemoryBatchProcessor:
    """记忆批量处理器 (异步版本)"""

    def __init__(self, batch_size: int = 10, interval: float = 5.0):
        self.queue = deque()
        self.batch_size = batch_size
        self.interval = interval
        self._running = False
        self._task: asyncio.Task = None

    async def add(
        self,
        user_id: int,
        message: str,
        context_type: str,
        context_id: int
    ):
        """
        添加到待处理队列

        Args:
            user_id: 用户ID
            message: 消息内容
            context_type: 上下文类型
            context_id: 上下文ID
        """
        self.queue.append({
            'user_id': user_id,
            'message': message,
            'context_type': context_type,
            'context_id': context_id
        })

        # 达到批量大小，立即处理
        if len(self.queue) >= self.batch_size:
            await self._process_batch()

    async def _process_batch(self):
        """处理一批记忆"""
        if not self.queue:
            return

        batch_size = min(len(self.queue), self.batch_size)
        batch = [self.queue.popleft() for _ in range(batch_size)]

        logging.info(f"批量处理 {len(batch)} 条记忆")

        # 逐个处理 (因为ollama不支持批量)
        from intelligence.memory.memory_manager_async import get_memory_manager

        manager = get_memory_manager()

        for item in batch:
            try:
                # 使用智能过滤
                from intelligence.memory.smart_extractor import SmartMemoryExtractor

                should_extract = await SmartMemoryExtractor.should_extract(
                    item['user_id'],
                    item['message']
                )

                if should_extract:
                    await manager.extract_and_store_memory(
                        user_id=item['user_id'],
                        message=item['message'],
                        context_type=item['context_type'],
                        context_id=item['context_id']
                    )
                else:
                    logging.debug(f"跳过低价值记忆: {item['message'][:30]}")

            except Exception as e:
                logging.error(f"记忆提取失败: {e}")

    async def start(self):
        """启动定时处理"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._periodic_process())
        logging.info("✓ 记忆批量处理器已启动")

    async def _periodic_process(self):
        """定时处理队列"""
        while self._running:
            await asyncio.sleep(self.interval)
            await self._process_batch()

    async def stop(self):
        """停止处理"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# 全局单例
_memory_batch_processor = None

def get_memory_batch_processor() -> MemoryBatchProcessor:
    """获取批量处理器单例"""
    global _memory_batch_processor
    if _memory_batch_processor is None:
        _memory_batch_processor = MemoryBatchProcessor(batch_size=10, interval=5.0)
    return _memory_batch_processor


async def init_memory_batch_processor():
    """初始化批量处理器"""
    processor = get_memory_batch_processor()
    await processor.start()
