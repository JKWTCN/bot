from enum import Enum
import queue
import threading
import logging
import asyncio


# class ConsumingTimeType(Enum):
#     """高耗时任务类型"""

#     CHAT = 1
#     COLDREPLAY = 2
#     REPLYIMAGEMESSAGE = 3
#     SAYPRIVTECHATNOCONTEXT = 4
#     MIAOMIAOTRANSLATION = 5


async def process_queue():
    """处理队列中的任务"""
    print("处理线程开始启动")
    while True:
        try:
            task = consuming_time_process_queue.get()
            if task is None:  # 用于停止线程的信号
                continue
            # websocket, param1, param2, param3, text, taskType = task
            coro = task()
            await coro
            # print(f"开始启动耗时任务类型{taskType}")
        except Exception as e:
            logging.error(f"处理队列任务时出错: {e}", exc_info=True)


# 创建耗时任务队列和处理线程
consuming_time_process_queue = queue.Queue()


# 启动处理线程
def start_processing_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# 创建新的事件循环
processing_loop = asyncio.new_event_loop()
processing_thread = threading.Thread(
    target=start_processing_loop, args=(processing_loop,), daemon=True
)
processing_thread.start()

# 启动处理协程
asyncio.run_coroutine_threadsafe(process_queue(), processing_loop)
