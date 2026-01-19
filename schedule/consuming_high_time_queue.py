"""
高耗时任务队列处理 (纯异步版本)
性能优化: 移除threading，使用纯asyncio实现
"""
import asyncio
import logging


# 全局任务队列
consuming_time_process_queue: asyncio.Queue = None


async def process_queue():
    """
    处理队列中的高耗时任务

    使用 asyncio.Queue 而非 threading.Queue
    使用协程而非线程
    """
    print("✓ 异步任务处理器已启动")
    while True:
        try:
            # 从队列获取任务 (异步等待)
            task_func = await consuming_time_process_queue.get()

            if task_func is None:
                continue

            # 执行任务
            await task_func()

        except Exception as e:
            logging.error(f"处理队列任务时出错: {e}", exc_info=True)
        finally:
            # 标记任务完成
            if consuming_time_process_queue:
                consuming_time_process_queue.task_done()


async def init_task_queue():
    """初始化任务队列和处理器"""
    global consuming_time_process_queue
    consuming_time_process_queue = asyncio.Queue(maxsize=1000)

    # 启动后台任务处理器
    # 创建多个工作协程以提高并发处理能力
    for i in range(3):  # 3个并发处理器
        asyncio.create_task(process_queue())

    print(f"✓ 异步任务队列已初始化 (maxsize=1000, workers=3)")


async def submit_high_time_task(task_func):
    """
    提交高耗时任务到队列

    Args:
        task_func: 异步函数(无参数)
    """
    if consuming_time_process_queue is None:
        await init_task_queue()

    try:
        await asyncio.wait_for(
            consuming_time_process_queue.put(task_func),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logging.error("任务队列已满，任务提交失败")


# 兼容旧API的同步包装器
def submit_high_time_task_sync(task_func):
    """
    同步代码提交任务的包装器
    (建议在新代码中直接使用 await submit_high_time_task())
    """
    asyncio.create_task(task_func())
