import json
import logging
import os
import re
import traceback
import concurrent.futures
from threading import Lock
import asyncio

import requests
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import SayRaw, ReplySay, ReplySayImage, ReplySayTextImage
from function.GroupConfig import get_config
import random
import uuid
import cv2
import subprocess
import numpy as np

from function.group_setting import LoadGroupSetting, DumpGroupSetting
from tools.tools import HasAllKeyWords


def extract_single_frame(args):
    """提取单个帧的函数，用于多线程"""
    input_video, output_folder, time_point, frame_index, lock = args

    output_path = os.path.join(output_folder, f"frame_{frame_index+1:03d}.jpg")

    cmd = [
        "ffmpeg",
        "-y",  # 覆盖输出文件
        "-ss",
        str(time_point),  # 跳转到指定时间
        "-i",
        input_video,
        "-vframes",
        "1",  # 只提取一帧
        "-vf",
        "scale=-1:720",  # 缩放高度为720保持宽高比
        "-q:v",
        "2",  # 高质量
        "-f",
        "image2",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # 使用锁来安全地打印进度信息
    with lock:
        if result.returncode != 0:
            print(f"提取第{frame_index+1}帧时出错: {result.stderr}")
            return False
        else:
            print(f"已提取第{frame_index+1}帧 (时间点: {time_point:.2f}s)")
            return True


def extract_frames(input_video, output_folder, num_frames=16, max_workers=4):
    """使用FFmpeg多线程从视频中均匀提取指定数量的帧"""
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 获取视频时长
    try:
        # 使用FFprobe获取视频时长
        probe_cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            input_video,
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            print(f"视频时长: {duration:.2f}秒")
        else:
            # 备用方案：使用stream信息获取时长
            probe_cmd2 = [
                "ffprobe",
                "-v",
                "quiet",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "csv=p=0",
                input_video,
            ]
            result2 = subprocess.run(probe_cmd2, capture_output=True, text=True)
            if (
                result2.returncode == 0
                and result2.stdout.strip()
                and result2.stdout.strip() != "N/A"
            ):
                duration = float(result2.stdout.strip())
                print(f"视频时长: {duration:.2f}秒")
            else:
                print("无法获取视频时长，使用默认间隔提取")
                duration = None
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        duration = None

    if duration:
        # 根据视频时长均匀分布提取帧的时间点
        # 在视频的5%到95%之间均匀分布，避免开头结尾的黑屏
        start_time = duration * 0.05
        end_time = duration * 0.95
        time_span = end_time - start_time

        # 生成均匀分布的时间点
        time_points = []
        for i in range(num_frames):
            if num_frames == 1:
                time_point = duration / 2  # 如果只要1帧，取中间
            else:
                time_point = start_time + (time_span * i / (num_frames - 1))
            time_points.append(time_point)

        print(f"在以下时间点提取帧: {[f'{t:.2f}s' for t in time_points]}")
        print(f"使用 {max_workers} 个线程并行提取...")

        # 创建线程锁用于安全打印
        print_lock = Lock()

        # 准备多线程参数
        thread_args = [
            (input_video, output_folder, time_point, i, print_lock)
            for i, time_point in enumerate(time_points)
        ]

        # 使用线程池并行提取帧
        success_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(extract_single_frame, thread_args))
            success_count = sum(results)

        print(f"多线程提取完成，成功提取 {success_count}/{num_frames} 帧")

        if success_count == 0:
            print("所有帧提取都失败，尝试备用方案...")
            return extract_frames_fallback(input_video, output_folder, num_frames)

    else:
        # 备用方案：使用帧号间隔提取
        return extract_frames_fallback(input_video, output_folder, num_frames)

    print("帧提取完成")


def extract_frames_fallback(input_video, output_folder, num_frames):
    """备用的单线程提取方案"""
    print("使用备用方案：按帧号间隔提取")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-vf",
        f"select='not(mod(n\\,{max(1, 30)}))',scale=-1:720",  # 每30帧取一帧
        "-vframes",
        str(num_frames),
        "-vsync",
        "vfr",
        "-q:v",
        "2",
        "-f",
        "image2",
        os.path.join(output_folder, "frame_%03d.jpg"),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg错误: {result.stderr}")
        # 最简单的备用方案
        simple_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_video,
            "-vframes",
            str(num_frames),
            "-q:v",
            "2",
            os.path.join(output_folder, "frame_%03d.jpg"),
        ]
        subprocess.run(simple_cmd, capture_output=True, text=True)


def create_collage(input_folder, output_path, grid_size=(4, 4)):
    """将提取的帧拼接成网格"""
    # 获取所有提取的帧
    frame_files = sorted(
        [f for f in os.listdir(input_folder) if f.startswith("frame_")]
    )

    if not frame_files:
        print("错误：没有找到提取的帧文件")
        return False

    frame_files = frame_files[: grid_size[0] * grid_size[1]]  # 确保不超过16张

    # 读取第一帧获取尺寸
    first_frame = cv2.imread(os.path.join(input_folder, frame_files[0]))
    if first_frame is None:
        print(f"错误：无法读取第一帧 {frame_files[0]}")
        return False

    h, w = first_frame.shape[:2]

    # 创建空白画布
    collage = np.zeros((h * grid_size[0], w * grid_size[1], 3), dtype=np.uint8)

    # 将帧拼接到画布上
    for i, frame_file in enumerate(frame_files):
        row = i // grid_size[1]
        col = i % grid_size[1]
        frame = cv2.imread(os.path.join(input_folder, frame_file))
        if frame is not None:
            collage[row * h : (row + 1) * h, col * w : (col + 1) * w] = frame  # type: ignore

    # 保存拼接图
    success = cv2.imwrite(output_path, collage)
    if success:
        print(f"拼接图保存到 {output_path}")
        return True
    else:
        print(f"错误：无法保存拼接图到 {output_path}")
        return False


def download_bilibili_video(
    url,
    max_duration_min=30,
    cookie_file=None,
    preferred_quality=1080,
    save_path="downloads",
):

    os.system(f"you-get {url} -o {save_path}")


def get_path_video(save_path):
    video_files = [
        f for f in os.listdir(save_path) if f.endswith((".mp4", ".mkv", ".avi"))
    ]
    return os.path.join(save_path, video_files[0]) if video_files else None


def find_bilibili_url(text):
    """
    检测文本中是否含有B站视频链接，返回匹配到的链接或空字符串

    参数:
        text (str): 要检测的文本

    返回:
        str: 匹配到的B站视频链接，如果没有则返回空字符串
    """
    # B站视频链接可能的形式:
    # 1. https://www.bilibili.com/video/BV1xx411c7mh
    # 2. https://b23.tv/av170001
    # 3. https://m.bilibili.com/video/BV1xx411c7mh
    # 4. 带有分享参数的形式: https://www.bilibili.com/video/BV1xx411c7mh?share_source=copy_web
    # 5. https:\\/\\/b23.tv\\/gl18XI0 (转义格式)
    pattern = r"(https?://(www\.|m\.)?bilibili\.com/video/(BV[\w]+)|https?://b23\.tv/[\w]+|https?:\\?/\\?/(www\.|m\.)?bilibili\.com\\?/video\\?/(BV[\w]+)|https?:\\?/\\?/b23\.tv\\?/[\w]+)"

    match = re.search(pattern, text)
    if match:
        url = match.group(0)
        # 如果是转义格式，需要去除转义字符
        if "\\/" in url:
            url = url.replace("\\/", "/")
        return url
    return ""


from bs4 import BeautifulSoup


def parse_bilibili_video_info(url) -> dict:
    """解析B站视频页面信息"""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return {}
    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    video_info = {}

    # 获取标题
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text().replace("_哔哩哔哩_bilibili", "")
        video_info["title"] = title

    # 获取描述/简介
    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta and "content" in desc_meta.attrs:  # type: ignore
        description = desc_meta.attrs["content"]  # type: ignore
        if description:
            # 提取简介部分（通常在第一个逗号前）
            if "," in str(description):
                intro = str(description).split(",")[0]
                video_info["description"] = intro
            else:
                video_info["description"] = str(description)

            # 从描述中提取播放数据（播放量、点赞数等）
            description_full = str(description)

            # 使用正则表达式提取各种数据
            play_match = re.search(r"视频播放量 (\d+)、", description_full)
            if play_match:
                video_info["play_count"] = int(play_match.group(1))

            danmu_match = re.search(r"弹幕量 (\d+)、", description_full)
            if danmu_match:
                video_info["danmu_count"] = int(danmu_match.group(1))

            like_match = re.search(r"点赞数 (\d+)、", description_full)
            if like_match:
                video_info["like_count"] = int(like_match.group(1))

            coin_match = re.search(r"投硬币枚数 (\d+)、", description_full)
            if coin_match:
                video_info["coin_count"] = int(coin_match.group(1))

            collect_match = re.search(r"收藏人数 (\d+)、", description_full)
            if collect_match:
                video_info["collect_count"] = int(collect_match.group(1))

            share_match = re.search(r"转发人数 (\d+)", description_full)
            if share_match:
                video_info["share_count"] = int(share_match.group(1))

    # 获取作者
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta and "content" in author_meta.attrs:  # type: ignore
        author = author_meta.attrs["content"]  # type: ignore
        if author:
            video_info["author"] = str(author)

    # 获取上传时间
    upload_meta = soup.find("meta", attrs={"itemprop": "uploadDate"})
    if upload_meta and "content" in upload_meta.attrs:  # type: ignore
        upload_date = upload_meta.attrs["content"]  # type: ignore
        if upload_date:
            video_info["upload_date"] = str(upload_date)

    # 获取关键词
    keywords_meta = soup.find("meta", attrs={"name": "keywords"})
    if keywords_meta and "content" in keywords_meta.attrs:  # type: ignore
        keywords_content = keywords_meta.attrs["content"]  # type: ignore
        if keywords_content:
            keywords = str(keywords_content).split(",")
            video_info["keywords"] = keywords

    # 获取视频封面图片
    image_meta = soup.find("meta", attrs={"itemprop": "image"})
    if image_meta and "content" in image_meta.attrs:  # type: ignore
        thumbnail = image_meta.attrs["content"]  # type: ignore
        if thumbnail:
            video_info["thumbnail"] = str(thumbnail)

    return video_info


def return_video_info_display(video_info):
    return f"🎬:{video_info.get('title', '未知标题')}\n🎤:{video_info.get('author', '未知作者')}\n📝:{video_info.get('description', '未知简介')}\n📅:{video_info.get('upload_date', '未知上传时间')}\n🎥: {video_info.get('play_count', 0):,}\n💬: {video_info.get('danmu_count', 0):,}\n👍: {video_info.get('like_count', 0):,}\n🪙: {video_info.get('coin_count', 0):,}\n⭐: {video_info.get('collect_count', 0):,}\n🔗: {video_info.get('share_count', 0):,}\n"


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "referer": "https://www.bilibili.com",
}


def download_image(args):
    i, url, folder = args
    url = "https:" + url if not url.startswith("https:") else url
    try:
        img_data = requests.get(url, headers=headers).content
        with open(f"{folder}/image_{i}.jpg", "wb") as img_file:
            img_file.write(img_data)
        return f"图片 {i} 下载成功"
    except Exception as e:
        return f"图片 {i} 下载失败: {str(e)}"


def get_bvid(url: str):
    import re

    pattern = r"(BV[a-zA-Z0-9]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None


# print(get_bvid("https://www.bilibili.com/video/BV1ox4y1q7bP"))
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# opencv拼接图片到一起,然后删除底部的黑底
import cv2
import numpy as np
from PIL import Image
async def download_stitched_image_async(
    folder: str, bvurl: str, jpeg_quality=95
) -> str:
    """异步版本的 download_stitched_image"""
    loop = asyncio.get_event_loop()

    def _download_stitched_image():
        return download_stitched_image(folder, bvurl, jpeg_quality)

    # 在线程池中运行同步函数
    return await loop.run_in_executor(None, _download_stitched_image)


async def parse_bilibili_video_info_async(url: str) -> dict:
    """异步版本的 parse_bilibili_video_info"""
    loop = asyncio.get_event_loop()

    def _parse_bilibili_video_info():
        return parse_bilibili_video_info(url)

    # 在线程池中运行同步函数
    return await loop.run_in_executor(None, _parse_bilibili_video_info)


def download_stitched_image(folder: str, bvurl: str, jpeg_quality=95) -> str:
    url = f"https://api.bilibili.com/x/player/videoshot?bvid={get_bvid(bvurl)}"
    response = requests.get(url, headers=headers)
    data = response.json()
    image_urls = data.get("data", {}).get("image", [])
    print(f"需要下载 {len(image_urls)} 张图片")
    os.makedirs(folder, exist_ok=True)
    # 使用线程池进行并发下载
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=min(10, len(image_urls))) as executor:
        futures = [
            executor.submit(download_image, (i, url, folder))
            for i, url in enumerate(image_urls)
        ]
        for future in as_completed(futures):
            print(future.result())

    print(f"下载完成，耗时: {time.time() - start_time:.2f} 秒")

    try:
        logging.info(f"[图片拼接] 开始处理图片拼接...")

        # 读取图片
        images = []
        failed_images = []
        for i in range(len(image_urls)):
            img_path = f"{folder}/image_{i}.jpg"
            img = cv2.imread(img_path)
            if img is not None:
                images.append(img)
                logging.info(f"[图片读取] 成功: {img_path}, 尺寸: {img.shape}")
            else:
                failed_images.append(img_path)
                logging.warning(f"[图片读取] 失败: {img_path}")

        if failed_images:
            logging.warning(f"[图片读取] 警告: {len(failed_images)} 张图片读取失败")

        if not images:
            logging.error(f"[图片拼接] 错误: 没有成功读取任何图片")
            return ""

        logging.info(f"[图片拼接] 成功读取 {len(images)} 张图片，准备拼接")

        # 显示所有图片的尺寸信息
        for i, img in enumerate(images):
            logging.info(f"[图片信息] 图片 {i}: 高度={img.shape[0]}, 宽度={img.shape[1]}, 通道={img.shape[2]}")

        # 拼接图片
        logging.info(f"[图片拼接] 开始垂直拼接...")
        stitched = np.concatenate(images, axis=0)
        logging.info(f"[图片拼接] 拼接完成，最终尺寸: {stitched.shape} (高度={stitched.shape[0]}, 宽度={stitched.shape[1]})")

        # 删除所有黑边
        logging.info(f"[黑边裁剪] 开始检测和裁剪黑边...")
        gray = cv2.cvtColor(stitched, cv2.COLOR_BGR2GRAY)
        coords = cv2.findNonZero((gray > 10).astype(np.uint8))

        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            logging.info(f"[黑边裁剪] 检测到黑边 - 边界框: x={x}, y={y}, 宽度={w}, 高度={h}")
            logging.info(f"[黑边裁剪] 裁剪前尺寸: {stitched.shape}")
            stitched = stitched[y : y + h, x : x + w]
            logging.info(f"[黑边裁剪] 裁剪后尺寸: {stitched.shape}")
        else:
            logging.info(f"[黑边裁剪] 未检测到黑边，跳过裁剪")

        # 验证图片数据
        logging.info(f"[数据验证] 检查拼接后的图片数据...")
        if stitched.size == 0:
            logging.error(f"[数据验证] 错误: 图片数据为空 (size=0)")
            return ""
        if stitched.shape[0] == 0 or stitched.shape[1] == 0:
            logging.error(f"[数据验证] 错误: 图片尺寸无效 (shape={stitched.shape})")
            return ""
        logging.info(f"[数据验证] 图片数据验证通过")

        # 检查图片尺寸，超过限制直接返回空字符串（发送纯文本）
        JPEG_MAX_DIMENSION = 65535
        height, width = stitched.shape[:2]

        logging.info(f"[格式选择] 检查图片尺寸: 宽度={width}, 高度={height}")
        logging.info(f"[格式选择] JPEG最大尺寸限制: {JPEG_MAX_DIMENSION}")

        if width > JPEG_MAX_DIMENSION or height > JPEG_MAX_DIMENSION:
            logging.warning(f"[格式选择] ⚠ 图片尺寸超过JPEG限制，将发送纯文本")
            if width > JPEG_MAX_DIMENSION:
                logging.warning(f"[格式选择] 超限原因: 宽度={width} > {JPEG_MAX_DIMENSION}")
            if height > JPEG_MAX_DIMENSION:
                logging.warning(f"[格式选择] 超限原因: 高度={height} > {JPEG_MAX_DIMENSION}")
            logging.info(f"[格式选择] ✓ 跳过图片保存，返回空字符串以发送纯文本")
            return ""

        output_format = "JPEG"
        file_extension = ".jpg"
        logging.info(f"[格式选择] ✓ 使用JPEG格式 (尺寸在限制内)")

        # 保存图片
        output_path = f"{folder}/stitched.jpg"
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        logging.info(f"[文件保存] 准备保存图片到: {output_path}")
        logging.info(f"[文件保存] JPEG质量参数: {jpeg_quality}")
        logging.info(f"[文件保存] 图片数据类型: {stitched.dtype}, 数据范围: [{stitched.min()}, {stitched.max()}]")

        success = cv2.imwrite(output_path, stitched, encode_params)
        logging.info(f"[文件保存] cv2.imwrite 返回值: {success}")

        if not success:
            logging.error(f"[文件保存] 错误: cv2.imwrite 返回 False")
            logging.error(f"[文件保存] 可能的原因: 磁盘空间不足、权限问题、路径无效、编码参数错误")
            return ""

        # 验证文件是否真的存在
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logging.info(f"[文件保存] 成功: 文件已创建，大小: {file_size} 字节 ({file_size/1024:.2f} KB)")
        else:
            logging.error(f"[文件保存] 错误: cv2.imwrite 返回 True，但文件不存在: {output_path}")
            return ""

        logging.info(f"[图片拼接] ✓ 成功完成，保存到: {output_path}")
        return output_path

    except Exception as e:
        logging.error(f"[异常] 图片拼接过程中发生异常:")
        logging.error(f"[异常] 错误类型: {type(e).__name__}")
        logging.error(f"[异常] 错误信息: {str(e)}")
        import traceback
        logging.error(f"[异常] 详细堆栈:", exc_info=True)
        return ""


import cv2
import shutil
import os
from PIL import Image

def compact_restitched_image(input_path, output_path, target_cols=8):
    """
    安全地重新排列图像块。
    支持原地覆盖，确保即使出错也不会产生 0KB 文件。
    """
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    
    # 临时文件路径（仅用于原地覆盖时的安全过渡）
    temp_output = output_path + ".tmp.jpg"
    
    try:
        # 1. 尝试读取和识别
        img_cv = cv2.imread(input_path)
        if img_cv is None:
            raise ValueError(f"OpenCV 无法读取图片: {input_path}")

        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        blocks = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 20 and h > 20:
                blocks.append((x, y, w, h))
        
        if not blocks:
            raise ValueError("未检测到有效内容块")

        # 排序逻辑
        avg_h = sum([b[3] for b in blocks]) / len(blocks)
        blocks.sort(key=lambda b: (int(b[1] / (avg_h / 2)), b[0]))

        # 2. 内存中绘图
        max_w = max([b[2] for b in blocks])
        max_h = max([b[3] for b in blocks])
        total_count = len(blocks)
        rows = (total_count + target_cols - 1) // target_cols
        
        new_img = Image.new('RGB', (max_w * target_cols, max_h * rows), (0, 0, 0))
        source_pil = Image.open(input_path)
        
        for i, (x, y, w, h) in enumerate(blocks):
            row_idx = i // target_cols
            col_idx = i % target_cols
            cell = source_pil.crop((x, y, x + w, y + h))
            new_img.paste(cell, (col_idx * max_w, row_idx * max_h))

        # 3. 安全写入
        # 如果是原地覆盖，先写到临时文件，防止 save 过程崩溃导致 0KB
        save_target = temp_output if abs_input == abs_output else output_path
        new_img.save(save_target, quality=95)

        # 4. 如果使用了临时文件，进行替换
        if abs_input == abs_output:
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                # 在 Windows 上替换已存在文件需要先删除原文件或使用 os.replace
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_output, output_path)
        
        print(f"处理成功: {output_path}")

    except Exception as e:
        print(f"遇到错误: {e}")
        
        # 清理可能产生的 0KB 临时文件
        if os.path.exists(temp_output):
            os.remove(temp_output)

        # Fallback 逻辑
        if abs_input != abs_output:
            print("正在恢复原图到目标路径...")
            shutil.copy2(input_path, output_path)
        else:
            print("原地覆盖模式下出错，已保护原始文件不受影响。")

class BiliBiliParsingApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("BiliBili解析", "解析BiliBili视频链接")
        super().__init__(applicationInfo, 10, True, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        isCardMessage = False
        display_text = ""
        # 检查是否是卡片消息
        for k in message.rawMessage["message"]:
            try:
                if k["type"] == "json":
                    # qq卡片消息解析
                    now_json = json.loads(k["data"]["data"])
                    if "meta" in now_json:
                        if "detail_1" in now_json["meta"]:
                            if "qqdocurl" in now_json["meta"]["detail_1"]:
                                qqdocurl = now_json["meta"]["detail_1"]["qqdocurl"]
                                r = requests.get(qqdocurl)
                                no_get_params_url = r.url.split("?")[0]
                                logging.info(f"解析结果:{no_get_params_url}")
                                isCardMessage = True
                                break
            except Exception as e:
                logging.info(f"不是卡片消息: {e}")
        if not isCardMessage:
            no_get_params_url = find_bilibili_url(f"{message.rawMessage}")
            if "b23" in no_get_params_url:
                r = requests.get(no_get_params_url)
                no_get_params_url = r.url.split("?")[0]
                display_text += f"{no_get_params_url}\n"

        uuid_str = str(uuid.uuid4())
        folder = f"downloads/{uuid_str}"

        # 并发执行下载图片和解析视频信息
        image_task = download_stitched_image_async(folder, no_get_params_url)
        info_task = parse_bilibili_video_info_async(no_get_params_url)

        # 等待两个任务完成
        image_path, parsed_info = await asyncio.gather(image_task, info_task)
        # compact_restitched_image(image_path, image_path, target_cols=8)
        
        if isCardMessage:
            display_text += f"{no_get_params_url}\n"
        display_text += return_video_info_display(parsed_info)
        if image_path != "":
            if isCardMessage:
                await ReplySayTextImage(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    display_text,
                    image_path,
                )
            else:
                # 如果不是卡片消息，直接发送图片
                await ReplySayTextImage(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    display_text,
                    image_path,
                )
        else:
            # 图片解析不成功,直接发送文本
            await ReplySay(
                message.websocket,
                message.groupId,
                message.messageId,
                display_text,
            )
        # 清理临时文件
        import shutil

        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"清理临时文件失败: {e}")
        # input_video = download_bilibili_video(
        #     url=no_get_params_url,
        #     max_duration_min=30,
        #     cookie_file="cookie.txt",
        #     preferred_quality=1080,
        #     save_path=f"downloads/{uuid_str}",
        # )
        # output_video = get_path_video(f"downloads/{uuid_str}")
        # if output_video is None:
        #     print("错误：未找到下载的视频文件")
        #     return

        # output_folder = f"downloads/{uuid_str}/output"
        # output_collage = f"downloads/{uuid_str}/collage.jpg"

        # # 提取帧
        # extract_frames(output_video, output_folder)

        # # 检查是否成功提取了帧
        # if not os.path.exists(output_folder) or not os.listdir(output_folder):
        #     print("错误：没有成功提取到视频帧")
        #     return

        # # 创建拼图
        # success = create_collage(output_folder, output_collage)

        # if success:
        #     if isCardMessage:
        #         await ReplySayTextImage(
        #             message.websocket,
        #             message.groupId,
        #             message.messageId,
        #             display_text,
        #             output_collage,
        #         )
        #     else:
        #         # 如果不是卡片消息，直接发送图片
        #         await ReplySayTextImage(
        #             message.websocket,
        #             message.groupId,
        #             message.messageId,
        #             display_text,
        #             output_collage,
        #         )
        # else:
        #     print("创建拼接图失败")

    def judge(self, message: GroupMessageInfo) -> bool:
        return LoadGroupSetting("bilibili_parsing", message.groupId, True) and (find_bilibili_url(f"{message.rawMessage}") != "" or HasAllKeyWords(f"{message.rawMessage}", ["QQ小程序", "哔哩哔哩"]))  # type: ignore
