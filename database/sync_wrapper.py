"""
同步数据库操作的安全包装器
临时解决方案：将同步sqlite3操作放入线程池，避免阻塞事件循环和数据库锁定
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any


# 创建线程池专门用于同步数据库操作
_db_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="db_sync")  # 增加到10个工作线程


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """
    在线程池中运行同步数据库操作

    用法:
        result = await run_in_thread(sync_function, arg1, arg2)

    Args:
        func: 同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回值
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_db_executor, func, *args, **kwargs)
        return result
    except Exception as e:
        logging.error(f"线程池执行失败: {e}, func={func.__name__}")
        raise


def run_in_thread_sync(func: Callable, *args, **kwargs) -> Any:
    """
    同步版本的线程池执行（用于同步上下文）

    用法:
        result = run_in_thread_sync(sync_function, arg1, arg2)
    """
    import concurrent.futures

    future = _db_executor.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=30)  # 增加到30秒超时
    except concurrent.futures.TimeoutError:
        logging.error(f"线程池执行超时: func={func.__name__}")
        raise
    except Exception as e:
        logging.error(f"线程池执行失败: {e}, func={func.__name__}")
        raise


# 便捷装饰器：自动将同步函数转为异步
def async_wrap(func: Callable) -> Callable:
    """
    装饰器：将同步函数包装为异步函数

    用法:
        @async_wrap
        def sync_function(arg):
            return do_something(arg))

        # 现在可以 await 调用
        result = await sync_function(arg)
    """
    async def wrapper(*args, **kwargs):
        return await run_in_thread(func, *args, **kwargs)
    return wrapper
