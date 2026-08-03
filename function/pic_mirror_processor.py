import asyncio
import base64
import hashlib
import logging
import math
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFile, ImageFilter, ImageOps, ImageSequence


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
            "mirror_left": "左镜像",
            "mirror_right": "右镜像",
            "mirror_top": "上镜像",
            "mirror_bottom": "下镜像",
            "four_side_mirror": "四方镜像",
            "quadrant_symmetry": "四象限对称",
            "diagonal_main": "主对角线对称",
            "diagonal_anti": "副对角线对称",
            "kaleidoscope": "万花筒",
            "infinite_mirror": "无限镜像",
            "mirror_tile_horizontal": "镜像拼接",
            "water_reflection": "水面倒影",
            "mirror_blend": "镜像融合",
            "rgb_split": "RGB分离",
            "polar_planet": "小星球",
            "polar_tunnel": "极坐标隧道",
            "animated_mirror": "镜像动画",
            "random_symmetry": "随机对称",
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
        ext = (
            ".gif"
            if "animated_mirror" in mode.split("|")
            else input_ext if input_ext in PicMirrorFileUtils.SUPPORTED_FORMATS else ".png"
        )
        safe_mode = "_".join(
            part.replace(":", "-") for part in mode.split("|")
        )
        return output_dir / f"mirror_{safe_mode}_{source_hash}{ext}"

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
            resolved_mode = PicMirrorProcessor._resolve_random_operations(mode)
            with Image.open(input_path) as img:
                if not PicMirrorProcessor._check_image_size(img):
                    return False, f"图像尺寸过大，可能存在安全风险: {img.width}x{img.height}像素"

                if img.mode in ("P", "LA"):
                    img = img.convert("RGBA")
                if config.enable_compression:
                    img = PicMirrorProcessor._compress_image(img, config)

                if PicMirrorProcessor._has_operation(resolved_mode, "animated_mirror"):
                    frames = []
                    frame_count = 16
                    for index in range(frame_count):
                        phase = index / frame_count
                        frame = PicMirrorProcessor._apply_mirror(
                            img, resolved_mode, animation_phase=phase
                        )
                        frame = PicMirrorProcessor._fit_for_expansion(
                            frame, 1, 1, max_dimension=1024
                        )
                        if config.enable_compression:
                            frame = PicMirrorProcessor._compress_image(frame, config)
                        frames.append(frame.convert("RGB"))
                    frames[0].save(
                        output_path,
                        format="GIF",
                        save_all=True,
                        append_images=frames[1:],
                        duration=80,
                        loop=0,
                        optimize=True,
                    )
                    return True, "镜像动画处理成功"

                mirrored = PicMirrorProcessor._apply_mirror(img, resolved_mode)

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
            resolved_mode = PicMirrorProcessor._resolve_random_operations(mode)
            original_load_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            try:
                frames = []
                durations = []
                has_transparency = False
                processed_pixels = 0

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
                        if config.enable_compression:
                            frame_copy = PicMirrorProcessor._compress_image(
                                frame_copy, config
                            )
                        phase = (frame_count - 1) / max(1, img.n_frames - 1)
                        mirrored_frame = PicMirrorProcessor._apply_mirror(
                            frame_copy, resolved_mode, animation_phase=phase
                        )
                        if config.enable_compression:
                            mirrored_frame = PicMirrorProcessor._compress_image(
                                mirrored_frame, config
                            )
                        processed_pixels += mirrored_frame.width * mirrored_frame.height
                        if processed_pixels > config.max_total_pixels:
                            return False, "GIF处理后的总像素数过多，可能存在安全风险"
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
    def _has_operation(mode: str, operation_name: str) -> bool:
        return any(
            operation.split(":", 1)[0] == operation_name
            for operation in mode.split("|")
        )

    @staticmethod
    def _resolve_random_operations(mode: str) -> str:
        choices = ("left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top")
        return "|".join(
            secrets.choice(choices)
            if operation.split(":", 1)[0] == "random_symmetry"
            else operation
            for operation in mode.split("|")
        )

    @staticmethod
    def _apply_mirror(
        image: Image.Image, mode: str, animation_phase: Optional[float] = None
    ) -> Image.Image:
        result = image.copy()
        for operation in mode.split("|"):
            name, separator, raw_parameter = operation.partition(":")
            parameter = int(raw_parameter) if separator and raw_parameter.isdigit() else None
            result = PicMirrorProcessor._apply_operation(
                result, name, parameter, animation_phase
            )
        return result

    @staticmethod
    def _apply_operation(
        image: Image.Image,
        mode: str,
        parameter: Optional[int] = None,
        animation_phase: Optional[float] = None,
    ) -> Image.Image:
        if mode == "invert":
            return PicMirrorProcessor._invert_image(image)
        if mode == "mirror_left":
            return PicMirrorProcessor._mirror_at_edge(image, "left")
        if mode == "mirror_right":
            return PicMirrorProcessor._mirror_at_edge(image, "right")
        if mode == "mirror_top":
            return PicMirrorProcessor._mirror_at_edge(image, "top")
        if mode == "mirror_bottom":
            return PicMirrorProcessor._mirror_at_edge(image, "bottom")
        if mode == "four_side_mirror":
            return PicMirrorProcessor._four_side_mirror(image)
        if mode == "quadrant_symmetry":
            horizontal = PicMirrorProcessor._apply_operation(image, "left_to_right")
            return PicMirrorProcessor._apply_operation(horizontal, "top_to_bottom")
        if mode in ("diagonal_main", "diagonal_anti"):
            return PicMirrorProcessor._diagonal_symmetry(
                image, anti=mode == "diagonal_anti"
            )
        if mode == "kaleidoscope":
            return PicMirrorProcessor._kaleidoscope(image, parameter or 8)
        if mode == "infinite_mirror":
            return PicMirrorProcessor._infinite_mirror(image, parameter or 5)
        if mode == "mirror_tile_horizontal":
            return PicMirrorProcessor._mirror_tile(image, parameter or 4)
        if mode == "water_reflection":
            return PicMirrorProcessor._water_reflection(image)
        if mode == "mirror_blend":
            return PicMirrorProcessor._mirror_blend(image)
        if mode == "rgb_split":
            return PicMirrorProcessor._rgb_split(image)
        if mode in ("polar_planet", "polar_tunnel"):
            return PicMirrorProcessor._polar_effect(
                image, tunnel=mode == "polar_tunnel"
            )
        if mode == "animated_mirror":
            return PicMirrorProcessor._animated_mirror(image, animation_phase)
        if mode == "random_symmetry":
            random_mode = secrets.choice(
                ("left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top")
            )
            return PicMirrorProcessor._apply_operation(image, random_mode)

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
    def _four_side_mirror(image: Image.Image) -> Image.Image:
        image = PicMirrorProcessor._fit_for_expansion(image, 3, 3)
        width, height = image.size
        horizontal = ImageOps.mirror(image)
        vertical = ImageOps.flip(image)
        corner = ImageOps.flip(horizontal)
        result = Image.new(image.mode, (width * 3, height * 3))
        tiles = (
            (corner, 0, 0),
            (vertical, width, 0),
            (corner, width * 2, 0),
            (horizontal, 0, height),
            (image, width, height),
            (horizontal, width * 2, height),
            (corner, 0, height * 2),
            (vertical, width, height * 2),
            (corner, width * 2, height * 2),
        )
        for tile, x, y in tiles:
            result.paste(tile, (x, y))
        return result

    @staticmethod
    def _diagonal_symmetry(image: Image.Image, anti: bool) -> Image.Image:
        width, height = image.size
        reflected = image.transpose(Image.Transpose.TRANSPOSE)
        reflected = reflected.resize((width, height), Image.Resampling.LANCZOS)
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        if anti:
            reflected = ImageOps.flip(ImageOps.mirror(reflected))
            draw.polygon(((0, 0), (width, 0), (0, height)), fill=255)
        else:
            draw.polygon(((0, 0), (width, 0), (width, height)), fill=255)
        return Image.composite(image, reflected, mask)

    @staticmethod
    def _kaleidoscope(image: Image.Image, segments: int) -> Image.Image:
        segments = max(2, min(16, segments))
        size = min(max(image.size), 2048)
        source = ImageOps.fit(image.convert("RGBA"), (size, size))
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        center = size / 2
        radius = math.sqrt(2) * size
        sector_angle = 360 / segments

        for index in range(segments):
            start = -90 - sector_angle / 2 + index * sector_angle
            end = start + sector_angle
            points = [(center, center)]
            for angle in np.linspace(start, end, max(3, int(sector_angle) + 2)):
                radians = math.radians(angle)
                points.append(
                    (center + radius * math.cos(radians), center + radius * math.sin(radians))
                )
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).polygon(points, fill=255)
            tile = ImageOps.mirror(source) if index % 2 else source
            tile = tile.rotate(index * sector_angle, resample=Image.Resampling.BICUBIC)
            alpha_mask = Image.composite(
                tile.getchannel("A"), Image.new("L", tile.size), mask
            )
            result.paste(tile, (0, 0), alpha_mask)
        return result

    @staticmethod
    def _infinite_mirror(image: Image.Image, depth: int) -> Image.Image:
        depth = max(1, min(10, depth))
        result = image.copy()
        width, height = result.size
        source = image.copy()
        for level in range(1, depth + 1):
            scale = 0.68**level
            nested_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            nested = source.resize(nested_size, Image.Resampling.LANCZOS)
            if level % 2:
                nested = ImageOps.mirror(nested)
            position = ((width - nested.width) // 2, (height - nested.height) // 2)
            if "A" in nested.getbands():
                result.paste(nested, position, nested.getchannel("A"))
            else:
                result.paste(nested, position)
        return result

    @staticmethod
    def _mirror_tile(image: Image.Image, repetitions: int) -> Image.Image:
        repetitions = max(2, min(10, repetitions))
        image = PicMirrorProcessor._fit_for_expansion(image, repetitions, 1)
        width, height = image.size
        result = Image.new(image.mode, (width * repetitions, height))
        mirrored = ImageOps.mirror(image)
        for index in range(repetitions):
            result.paste(image if index % 2 == 0 else mirrored, (index * width, 0))
        return result

    @staticmethod
    def _water_reflection(image: Image.Image) -> Image.Image:
        image = PicMirrorProcessor._fit_for_expansion(image, 1, 2)
        source = image.convert("RGBA")
        width, height = source.size
        reflection = np.array(ImageOps.flip(source))
        amplitude = max(1, width // 80)
        for row in range(height):
            offset = int(math.sin(row / max(3, height / 12)) * amplitude)
            reflection[row] = np.roll(reflection[row], offset, axis=0)
        reflected = Image.fromarray(reflection, "RGBA").filter(
            ImageFilter.GaussianBlur(radius=max(0.5, min(width, height) / 300))
        )
        reflected_data = np.array(reflected)
        fade = np.linspace(0.67, 0, height, dtype=np.float32)[:, None]
        reflected_data[:, :, 3] = (
            reflected_data[:, :, 3].astype(np.float32) * fade
        ).astype(np.uint8)
        reflected = Image.fromarray(reflected_data, "RGBA")
        result = Image.new("RGBA", (width, height * 2), (0, 0, 0, 0))
        result.paste(source, (0, 0))
        result.paste(reflected, (0, height))
        return result

    @staticmethod
    def _mirror_blend(image: Image.Image) -> Image.Image:
        source = image.convert("RGBA")
        return Image.blend(source, ImageOps.mirror(source), 0.5)

    @staticmethod
    def _rgb_split(image: Image.Image) -> Image.Image:
        source = np.array(image.convert("RGBA"))
        shift = max(2, source.shape[1] // 40)
        result = source.copy()
        result[:, :, 0] = np.roll(source[:, :, 0], -shift, axis=1)
        result[:, :, 2] = np.roll(source[:, :, 2], shift, axis=1)
        return Image.fromarray(result, "RGBA")

    @staticmethod
    def _polar_effect(image: Image.Image, tunnel: bool) -> Image.Image:
        source = np.array(image.convert("RGBA"))
        source_height, source_width = source.shape[:2]
        size = min(max(source_width, source_height), 2048)
        yy, xx = np.indices((size, size), dtype=np.float32)
        center = (size - 1) / 2
        dx = xx - center
        dy = yy - center
        radius = np.sqrt(dx * dx + dy * dy)
        max_radius = max(1.0, center)
        angle = (np.arctan2(dy, dx) + math.pi) / (2 * math.pi)
        source_x = np.mod((angle * source_width).astype(np.int32), source_width)
        radial = np.clip(radius / max_radius, 0, 1)
        if tunnel:
            source_y = (radial * (source_height - 1)).astype(np.int32)
        else:
            source_y = ((1 - radial) * (source_height - 1)).astype(np.int32)
        result = source[source_y, source_x].copy()
        result[radius > max_radius] = (0, 0, 0, 0)
        return Image.fromarray(result, "RGBA")

    @staticmethod
    def _animated_mirror(
        image: Image.Image, animation_phase: Optional[float]
    ) -> Image.Image:
        if animation_phase is None:
            return image.copy()
        source = image.convert("RGBA")
        amount = (1 - math.cos(animation_phase * math.tau)) / 2
        return Image.blend(source, ImageOps.mirror(source), amount)

    @staticmethod
    def _mirror_at_edge(image: Image.Image, edge: str) -> Image.Image:
        x_factor = 2 if edge in ("left", "right") else 1
        y_factor = 2 if edge in ("top", "bottom") else 1
        image = PicMirrorProcessor._fit_for_expansion(image, x_factor, y_factor)
        width, height = image.size
        if edge in ("left", "right"):
            mirrored = ImageOps.mirror(image)
            result = Image.new(image.mode, (width * 2, height))
            if edge == "left":
                result.paste(mirrored, (0, 0))
                result.paste(image, (width, 0))
            else:
                result.paste(image, (0, 0))
                result.paste(mirrored, (width, 0))
            return result

        flipped = ImageOps.flip(image)
        result = Image.new(image.mode, (width, height * 2))
        if edge == "top":
            result.paste(flipped, (0, 0))
            result.paste(image, (0, height))
        else:
            result.paste(image, (0, 0))
            result.paste(flipped, (0, height))
        return result

    @staticmethod
    def _fit_for_expansion(
        image: Image.Image, x_factor: int, y_factor: int, max_dimension: int = 4096
    ) -> Image.Image:
        width, height = image.size
        scale = min(
            1.0,
            max_dimension / max(1, width * x_factor),
            max_dimension / max(1, height * y_factor),
        )
        if scale >= 1:
            return image
        size = (max(1, int(width * scale)), max(1, int(height * scale)))
        return image.resize(size, Image.Resampling.LANCZOS)

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

        if output_ext not in (".png", ".webp") and image.mode not in (
            "RGB",
            "L",
            "P",
        ):
            return image.convert("RGB")
        return image
