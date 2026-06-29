import asyncio
import base64
import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from PIL import Image, ImageFile, ImageOps, ImageSequence


@dataclass
class PicMirrorConfig:
    image_size_limit_mb: int = 10
    gif_size_limit_mb: int = 15
    precheck_file_size_mb: int = 100
    output_quality: int = 85
    enable_gif: bool = True
    enable_compression: bool = True
    max_compression_dimension: int = 2048
    max_gif_frames: int = 200
    max_total_pixels: int = 4000 * 4000
    processing_timeout: int = 30

    @property
    def max_image_size_bytes(self) -> int:
        return self.image_size_limit_mb * 1024 * 1024

    @property
    def max_gif_size_bytes(self) -> int:
        return self.gif_size_limit_mb * 1024 * 1024

    @property
    def precheck_file_size_bytes(self) -> int:
        return self.precheck_file_size_mb * 1024 * 1024


class PicMirrorFileUtils:
    SUPPORTED_STATIC_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    SUPPORTED_GIF_FORMAT = {".gif"}
    SUPPORTED_FORMATS = SUPPORTED_STATIC_FORMATS | SUPPORTED_GIF_FORMAT

    MAGIC_BYTES = {
        "gif": ([b"GIF87a", b"GIF89a"], 6),
        "png": (b"\x89PNG\r\n\x1a\n", 8),
        "jpeg": (b"\xff\xd8\xff", 3),
        "webp": (b"RIFF", 4, b"WEBP", 8),
        "bmp": (b"BM", 2),
    }

    @staticmethod
    def get_file_extension(url_or_path: str) -> Optional[str]:
        try:
            parsed = urlparse(url_or_path)
            match = None
            if parsed.scheme:
                match = Path(parsed.path).suffix.lower()
            else:
                match = Path(url_or_path).suffix.lower()
            if match in PicMirrorFileUtils.SUPPORTED_FORMATS:
                return match

            query_params = parse_qs(parsed.query)
            for param_name in ["format", "type", "ext"]:
                if param_name not in query_params:
                    continue
                value = query_params[param_name][0].lower()
                ext = value if value.startswith(".") else f".{value}"
                if ext in PicMirrorFileUtils.SUPPORTED_FORMATS:
                    return ext
        except Exception:
            return None
        return None

    @staticmethod
    def detect_image_format_by_magic(data: bytes) -> Optional[str]:
        if len(data) < 12:
            return None
        magic = PicMirrorFileUtils.MAGIC_BYTES
        if data[:6] in magic["gif"][0]:
            return ".gif"
        if data[:8] == magic["png"][0]:
            return ".png"
        if data[:3] == magic["jpeg"][0]:
            return ".jpg"
        if data[:4] == magic["webp"][0] and data[8:12] == magic["webp"][2]:
            return ".webp"
        if data[:2] == magic["bmp"][0]:
            return ".bmp"
        return None

    @staticmethod
    def validate_image_size(
        image_path: str, config: PicMirrorConfig
    ) -> Tuple[bool, str]:
        try:
            file_size = os.path.getsize(image_path)
            ext = PicMirrorFileUtils.get_file_extension(image_path)
            max_size = (
                config.max_gif_size_bytes
                if ext == ".gif"
                else config.max_image_size_bytes
            )
            max_size_mb = (
                config.gif_size_limit_mb if ext == ".gif" else config.image_size_limit_mb
            )
            if file_size > max_size:
                return (
                    False,
                    f"文件过大（{file_size / 1024 / 1024:.1f}MB），最大允许：{max_size_mb}MB",
                )
            return True, ""
        except Exception as e:
            return False, f"无法获取文件大小: {e}"


class PicMirrorProcessor:
    @staticmethod
    def get_mode_description(mode: str) -> str:
        descriptions = {
            "left_to_right": "左对称",
            "right_to_left": "右对称",
            "top_to_bottom": "上对称",
            "bottom_to_top": "下对称",
            "invert": "反色",
        }
        return descriptions.get(mode, mode)

    @staticmethod
    async def download_image(url: str, output_dir: Path, config: PicMirrorConfig) -> Optional[Path]:
        def download() -> Optional[Path]:
            response = requests.get(url, timeout=config.processing_timeout)
            response.raise_for_status()
            data = response.content
            ext = (
                PicMirrorFileUtils.detect_image_format_by_magic(data)
                or PicMirrorFileUtils.get_file_extension(url)
                or ".jpg"
            )
            path = PicMirrorProcessor._make_temp_path(output_dir, "downloaded", ext)
            path.write_bytes(data)
            return path

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, download)
        except Exception as e:
            logging.error(f"下载图片失败: {url}, {e}")
            return None

    @staticmethod
    async def decode_base64_image(
        base64_data: str, output_dir: Path, config: PicMirrorConfig
    ) -> Optional[Path]:
        def decode() -> Optional[Path]:
            raw = base64_data[len("base64://") :] if base64_data.startswith("base64://") else base64_data
            if len(raw) > min(int(config.max_image_size_bytes * 4 / 3) + 100, 20 * 1024 * 1024):
                return None
            data = base64.b64decode(raw, validate=True)
            if len(data) > config.max_image_size_bytes:
                return None
            ext = PicMirrorFileUtils.detect_image_format_by_magic(data) or ".png"
            path = PicMirrorProcessor._make_temp_path(output_dir, "base64", ext)
            path.write_bytes(data)
            return path

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, decode)
        except Exception as e:
            logging.error(f"解码base64图片失败: {e}")
            return None

    @staticmethod
    def make_output_path(output_dir: Path, source: str, mode: str, input_ext: str) -> Path:
        source_hash = hashlib.sha256(f"{source}_{mode}_{time.time()}_{secrets.token_hex(4)}".encode()).hexdigest()[:12]
        ext = input_ext if input_ext in PicMirrorFileUtils.SUPPORTED_FORMATS else ".png"
        return output_dir / f"mirror_{mode}_{source_hash}{ext}"

    @staticmethod
    async def process_image(
        input_path: str,
        output_path: str,
        mode: str,
        config: PicMirrorConfig,
    ) -> Tuple[bool, str]:
        try:
            if not Path(input_path).exists():
                return False, f"输入文件不存在: {input_path}"

            is_safe, msg = await PicMirrorProcessor._check_image_before_open_async(
                input_path, config
            )
            if not is_safe:
                return False, msg

            is_valid, error_msg = PicMirrorFileUtils.validate_image_size(input_path, config)
            if not is_valid:
                return False, error_msg

            ext = PicMirrorFileUtils.get_file_extension(input_path)
            if not ext:
                return False, "无法识别图像格式"
            if ext == ".gif" and not config.enable_gif:
                return False, "GIF处理功能已禁用"
            if ext in PicMirrorFileUtils.SUPPORTED_GIF_FORMAT:
                return await PicMirrorProcessor._process_gif(input_path, output_path, mode, config)
            if ext in PicMirrorFileUtils.SUPPORTED_STATIC_FORMATS:
                return await PicMirrorProcessor._process_static_image(input_path, output_path, mode, config)
            return False, f"不支持的图像格式: {ext}"
        except Exception as e:
            return False, f"图像处理失败: {e}"

    @staticmethod
    def _make_temp_path(output_dir: Path, prefix: str, ext: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"mirror_{prefix}_{int(time.time())}_{secrets.token_hex(4)}{ext}"

    @staticmethod
    def _check_image_size(img: Image.Image) -> bool:
        pixels = img.width * img.height
        if pixels > 10000 * 10000:
            return False
        if pixels > 5000 * 5000:
            logging.warning(f"处理大图像: {pixels}像素 ({img.width}x{img.height})")
        return True

    @staticmethod
    def _check_image_before_open(
        file_path: str, config: PicMirrorConfig
    ) -> Tuple[bool, str]:
        try:
            file_size = os.path.getsize(file_path)
            if file_size > config.precheck_file_size_bytes:
                max_size_mb = config.precheck_file_size_bytes / 1024 / 1024
                return False, f"文件过大 ({file_size / 1024 / 1024:.1f}MB > {max_size_mb:.0f}MB)"
            with open(file_path, "rb") as f:
                if not f.read(100):
                    return False, "文件为空或无法读取"
            return True, ""
        except FileNotFoundError:
            return False, "文件不存在"
        except (PermissionError, OSError) as e:
            logging.error(f"图像预检查异常: {e}")
            return False, "文件检查失败"

    @staticmethod
    async def _check_image_before_open_async(
        file_path: str, config: PicMirrorConfig
    ) -> Tuple[bool, str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: PicMirrorProcessor._check_image_before_open(file_path, config)
        )

    @staticmethod
    async def _process_static_image(
        input_path: str,
        output_path: str,
        mode: str,
        config: PicMirrorConfig,
    ) -> Tuple[bool, str]:
        def process_in_thread() -> Tuple[bool, str]:
            with Image.open(input_path) as img:
                if not PicMirrorProcessor._check_image_size(img):
                    return False, f"图像尺寸过大，可能存在安全风险: {img.width}x{img.height}像素"

                if img.mode in ("P", "LA"):
                    img = img.convert("RGBA")
                mirrored = PicMirrorProcessor._apply_mirror(img, mode)

                if config.enable_compression:
                    mirrored = PicMirrorProcessor._compress_image(mirrored, config)

                output_ext = Path(output_path).suffix.lower()
                mirrored = PicMirrorProcessor._ensure_compatible_image_mode(
                    mirrored, output_ext
                )
                if output_ext == ".png":
                    mirrored.save(output_path, optimize=True)
                elif output_ext == ".webp":
                    mirrored.save(output_path, quality=config.output_quality, method=6)
                else:
                    mirrored.save(output_path, quality=config.output_quality, optimize=True)
                return True, "图像处理成功"

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, process_in_thread)
        except Exception as e:
            return False, f"静态图像处理失败: {e}"

    @staticmethod
    async def _process_gif(
        input_path: str,
        output_path: str,
        mode: str,
        config: PicMirrorConfig,
    ) -> Tuple[bool, str]:
        def process_gif_in_thread() -> Tuple[bool, str]:
            original_load_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            try:
                frames = []
                durations = []
                has_transparency = False

                with Image.open(input_path) as img:
                    if not PicMirrorProcessor._check_image_size(img):
                        return False, f"GIF尺寸过大，可能存在安全风险: {img.width}x{img.height}像素"
                    if "transparency" in img.info:
                        has_transparency = True

                    for frame_count, frame in enumerate(ImageSequence.Iterator(img), start=1):
                        if frame_count > config.max_gif_frames:
                            return False, f"GIF帧数过多（{frame_count} > {config.max_gif_frames}），可能存在安全风险"

                        total_pixels = frame_count * frame.width * frame.height
                        if total_pixels > config.max_total_pixels:
                            return False, "GIF总像素数过多，可能存在安全风险"

                        durations.append(frame.info.get("duration", 100))
                        if "transparency" in frame.info:
                            has_transparency = True

                        frame_copy = frame.copy()
                        if frame_copy.mode != "RGBA":
                            frame_copy = frame_copy.convert("RGBA")
                        mirrored_frame = PicMirrorProcessor._apply_mirror(frame_copy, mode)
                        if config.enable_compression:
                            mirrored_frame = PicMirrorProcessor._compress_image(
                                mirrored_frame, config
                            )
                        frames.append(mirrored_frame)

                if not frames:
                    return False, "GIF没有帧数据"

                target_size = frames[0].size
                normalized_frames = []
                for frame in frames:
                    if frame.mode != "RGBA":
                        frame = frame.convert("RGBA")
                    if frame.size != target_size:
                        frame = frame.resize(target_size, Image.Resampling.LANCZOS)
                    normalized_frames.append(frame)

                palette_colors = max(
                    64, min(255, int(64 + (255 - 64) * config.output_quality / 100))
                )
                gif_frames = []
                for frame in normalized_frames:
                    alpha = frame.getchannel("A")
                    has_alpha = alpha.getextrema()[0] < 255
                    if has_alpha or has_transparency:
                        mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
                        p_frame = frame.convert("RGB").quantize(colors=palette_colors)
                        p_frame.info["transparency"] = 0
                        p_data = list(p_frame.getdata())
                        mask_data = list(mask.getdata())
                        for i, mask_value in enumerate(mask_data):
                            if mask_value > 0:
                                p_data[i] = 0
                        p_frame.putdata(p_data)
                        gif_frames.append(p_frame)
                    else:
                        gif_frames.append(
                            frame.convert("RGB").quantize(colors=palette_colors)
                        )

                durations = (durations + [100] * len(gif_frames))[: len(gif_frames)]
                save_kwargs = {
                    "save_all": True,
                    "append_images": gif_frames[1:] if len(gif_frames) > 1 else [],
                    "duration": durations,
                    "loop": 0,
                    "disposal": 2,
                }
                if has_transparency or any("transparency" in f.info for f in gif_frames):
                    save_kwargs["transparency"] = 0
                gif_frames[0].save(output_path, **save_kwargs)
                return True, "GIF处理成功"
            finally:
                ImageFile.LOAD_TRUNCATED_IMAGES = original_load_truncated

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, process_gif_in_thread)
        except Exception as e:
            return False, f"GIF处理失败: {e}"

    @staticmethod
    def _apply_mirror(image: Image.Image, mode: str) -> Image.Image:
        if mode == "invert":
            return PicMirrorProcessor._invert_image(image)

        width, height = image.size
        result = Image.new(image.mode, (width, height))
        if mode == "left_to_right":
            half_width = (width + 1) // 2
            other_half = width - half_width
            left_half = image.crop((0, 0, half_width, height))
            right_half = ImageOps.mirror(left_half)
            result.paste(left_half, (0, 0))
            if other_half > 0:
                right_piece = right_half.crop(
                    (right_half.width - other_half, 0, right_half.width, height)
                )
                result.paste(right_piece, (half_width, 0))
            return result

        if mode == "right_to_left":
            half_width = (width + 1) // 2
            other_half = width - half_width
            right_half = image.crop((other_half, 0, width, height))
            left_half = ImageOps.mirror(right_half)
            if other_half > 0:
                left_piece = left_half.crop((0, 0, other_half, height))
                result.paste(left_piece, (0, 0))
            result.paste(right_half, (other_half, 0))
            return result

        if mode == "top_to_bottom":
            half_height = (height + 1) // 2
            other_half = height - half_height
            top_half = image.crop((0, 0, width, half_height))
            bottom_half = ImageOps.flip(top_half)
            result.paste(top_half, (0, 0))
            if other_half > 0:
                bottom_piece = bottom_half.crop(
                    (0, bottom_half.height - other_half, width, bottom_half.height)
                )
                result.paste(bottom_piece, (0, half_height))
            return result

        if mode == "bottom_to_top":
            half_height = (height + 1) // 2
            other_half = height - half_height
            bottom_half = image.crop((0, other_half, width, height))
            top_half = ImageOps.flip(bottom_half)
            if other_half > 0:
                top_piece = top_half.crop((0, 0, width, other_half))
                result.paste(top_piece, (0, 0))
            result.paste(bottom_half, (0, other_half))
            return result

        return image.copy()

    @staticmethod
    def _invert_image(image: Image.Image) -> Image.Image:
        if image.mode == "RGBA":
            rgb = image.convert("RGB")
            inverted = ImageOps.invert(rgb)
            inverted.putalpha(image.getchannel("A"))
            return inverted
        if image.mode == "LA":
            rgba = image.convert("RGBA")
            return PicMirrorProcessor._invert_image(rgba)
        if image.mode == "P":
            image = image.convert("RGBA")
            return PicMirrorProcessor._invert_image(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        return ImageOps.invert(image)

    @staticmethod
    def _compress_image(image: Image.Image, config: PicMirrorConfig) -> Image.Image:
        try:
            width, height = image.size
            max_dimension = config.max_compression_dimension
            if width > max_dimension or height > max_dimension:
                ratio = min(max_dimension / width, max_dimension / height)
                new_width = max(1, int(width * ratio))
                new_height = max(1, int(height * ratio))
                return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            return image
        except (ValueError, OSError, MemoryError) as e:
            logging.warning(f"图像压缩失败，返回原图: {type(e).__name__}: {e}")
            return image

    @staticmethod
    def _ensure_compatible_image_mode(image: Image.Image, output_ext: str) -> Image.Image:
        if output_ext in [".jpg", ".jpeg"] and image.mode == "RGBA":
            alpha = image.getchannel("A")
            if alpha.getextrema() == (255, 255):
                return image.convert("RGB")
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=alpha)
            return background

        if output_ext != ".png" and image.mode not in ("RGB", "L", "P"):
            return image.convert("RGB")
        return image
