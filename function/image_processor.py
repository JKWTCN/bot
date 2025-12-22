import base64
import hashlib
import io
import json
import logging
import os
import queue
import sqlite3
import threading
import traceback
import requests
from typing import Optional, Tuple

# 创建任务队列和处理线程
image_process_queue = queue.Queue()


def process_queue():
    """处理队列中的任务"""
    while True:
        try:
            task = image_process_queue.get()
            if task is None:  # 用于停止线程的信号
                break
            file_path, file_md5, message, websocket = task
            logging.info(
                f"开始处理队列中的图片: {file_path},目前队列长度: {image_process_queue.qsize()}"
            )
            text_message = ""
            for i in message["message"]:
                match i["type"]:
                    case "image":
                        file = i["data"]["file"]
                        url = i["data"]["url"]
                        imagePath = getImagePathByFile(file, url)
                        fileMd5 = calculate_md5(imagePath)
                        description = get_description_by_md5(fileMd5)
                        if description is None:
                            status, description = getImageDescriptionByFile(imagePath)
                            if status:
                                insert_md5(file_md5, description)
                                logging.info(f"图片描述已存入MD5数据库: {description}")
                                text_message += f"[图片内容:{description}]"
                            else:
                                text_message += f"[图片]"
                        else:
                            text_message += f"[图片内容:{description}]"
                    case "text":
                        text_message += i["data"]["text"]

            # 导入避免循环依赖
            from function.database_message import write_message
            write_message(message, text_message)
            logging.info(f"写入主数据库中的消息内容: {text_message}")

            image_process_queue.task_done()
        except Exception as e:
            logging.error(f"处理队列任务时出错: {e}")
        # 删除图片
        try:
            if 'imagePath' in locals():
                os.remove(imagePath)
                logging.info(f"已删除临时图片文件:{imagePath}")
        except Exception as e:
            logging.error(f"删除临时图片文件失败:{imagePath},错误:{e}")


# 启动处理线程
processing_thread = threading.Thread(target=process_queue, daemon=True)
processing_thread.start()


db_path = "bot-image.db"


def calculate_md5(file_path: str) -> str:
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_description_by_md5(md5: str) -> Optional[str]:
    """
    根据 MD5 值从数据库中获取对应的描述信息
    :param md5: 要查询的 MD5 值
    :return: 如果找到返回描述字符串,未找到返回 None
    """
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT description FROM md5 WHERE md5 = ? LIMIT 1", (md5,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()


def is_md5_exists(md5: str) -> bool:
    """
    判断给定的MD5是否存在于数据库中
    :param md5: 要查询的MD5值
    :return: 存在返回True,否则返回False
    """
    if not os.path.exists(db_path):
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1 FROM md5 WHERE md5 = ? LIMIT 1", (md5,))
        return cursor.fetchone() is not None
    finally:
        conn.close()


def insert_md5(md5: str, description: str = "[图片]") -> None:
    """
    将MD5和description写入数据库
    :param md5: 要插入的MD5值
    :param description: 描述信息
    """
    # 确保数据库和表存在
    init_database()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO md5 (md5, description) VALUES (?, ?)", (md5, description)
        )
        conn.commit()
    finally:
        conn.close()


def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS md5 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                md5 TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    finally:
        conn.close()


def getImageDescriptionByFile(imagePath: str) -> Tuple[bool, str]:
    """获取图片描述"""
    status, description = describe_image(imagePath)
    return status, description


def getImagePathByFile(file: str, url: str) -> str:
    """根据文件ID和URL下载图片并保存到本地"""
    resp = requests.get(url)
    image_data = resp.content

    # 保存二进制数据
    save_path = "./images"
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # 修正：使用文件写入方式保存二进制数据
    file_path = os.path.join(save_path, file)
    with open(file_path, "wb") as f:
        f.write(image_data)
    return file_path


def image_to_base64(image_path: str) -> str:
    """将图片转换为base64编码字符串"""
    with open(image_path, "rb") as file:
        # 读取文件内容并转换为Base64编码
        base64_encoded_data = base64.b64encode(file.read())
        # 在Python 3中,b64encode返回的是bytes类型,需要解码为字符串
        base64_encoded_str = base64_encoded_data.decode("utf-8")
    return base64_encoded_str


def describe_image(image_path: str, ollama_url: str = "http://localhost:11434") -> Tuple[bool, str]:
    """
    使用Ollama的qwen3-vl:8b模型描述图片

    参数:
        image_path: 图片文件路径
        ollama_url: Ollama服务地址,默认为本地11434端口

    返回:
        (是否成功, 模型生成的图片描述或错误信息)
    """
    try:
        import ollama

        # 使用ollama包调用，图像应该在消息的images字段中
        response = ollama.chat(
            model='qwen3-vl:8b',
            messages=[{
                'role': 'user',
                'content': '请描述一下子这张图片,不要有多余的话,简练一点.谢谢.',
                'images': [image_path]
            }]
        )

        description = response['message']['content']
        return True, description

    except Exception as e:
        logging.error(f"调用Ollama时出错: {str(e)}")
        return False, f"调用Ollama时出错: {str(e)}"


def process_image_message(message: dict, websocket) -> Optional[str]:
    """
    处理图片消息的主函数

    参数:
        message: 消息字典
        websocket: websocket连接对象

    返回:
        如果需要立即处理返回文本消息，如果需要异步处理返回None
    """
    text_message = ""

    for i in message["message"]:
        match i["type"]:
            case "image":
                file = i["data"]["file"]
                url = i["data"]["url"]
                imagePath = getImagePathByFile(file, url)
                fileMd5 = calculate_md5(imagePath)

                # 检查是否需要图片解析
                from function.GroupConfig import get_config
                needDescription = get_config("image_parsing", message["group_id"])

                if needDescription:
                    description = get_description_by_md5(fileMd5)
                    if description is None:
                        # MD5未命中，加入处理队列
                        logging.info(
                            f"{message['group_id']}:图片MD5未命中,加入处理队列:{imagePath}"
                        )
                        # 将任务加入队列（包含原始消息和websocket）
                        image_process_queue.put((imagePath, fileMd5, message, websocket))
                        return None  # 异步处理，不立即返回
                    else:
                        text_message += f"[图片内容:{description}]"
                        # 删除临时图片
                        if os.path.exists(imagePath):
                            os.remove(imagePath)
                            logging.info(f"已删除临时图片文件:{imagePath}")
                else:
                    logging.info(f"{message['group_id']}:本群未开启图片识别")
                    text_message += f"[图片]"
                    # 删除临时图片
                    if os.path.exists(imagePath):
                        os.remove(imagePath)
                        logging.info(f"已删除临时图片文件:{imagePath}")

            case "text":
                text_message += i["data"]["text"]

    return text_message