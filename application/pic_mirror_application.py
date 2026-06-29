import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from data.application.application_info import ApplicationInfo
from data.application.group_message_application import GroupMessageApplication
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.group_operation import get_reply_image_url
from function.pic_mirror_processor import (
    PicMirrorConfig,
    PicMirrorFileUtils,
    PicMirrorProcessor,
)
from function.say import ReplySay, ReplySayImage, SayGroup


class PicMirrorApplication(GroupMessageApplication):
    COMMAND_DELIMITERS = {
        " ",
        "\t",
        "\n",
        "\r",
        ".",
        ",",
        "?",
        "!",
        ":",
        ";",
        "。",
        "，",
        "？",
        "！",
        "：",
        "；",
        "、",
    }
    COMMANDS = {
        "/左对称": "left_to_right",
        "左对称": "left_to_right",
        "mirror left": "left_to_right",
        "/右对称": "right_to_left",
        "右对称": "right_to_left",
        "mirror right": "right_to_left",
        "/上对称": "top_to_bottom",
        "上对称": "top_to_bottom",
        "mirror top": "top_to_bottom",
        "/下对称": "bottom_to_top",
        "下对称": "bottom_to_top",
        "mirror bottom": "bottom_to_top",
        "/反色": "invert",
        "反色": "invert",
        "颜色反转": "invert",
        "invert": "invert",
        "mirror invert": "invert",
    }
    HELP_COMMANDS = {"/对称帮助", "对称帮助", "/镜像帮助", "镜像帮助", "mirror help"}
    RATE_LIMIT_WINDOW_SECONDS = 60

    def __init__(self):
        application_info = ApplicationInfo(
            "图片镜像功能",
            "触发:左对称/右对称/上对称/下对称/反色，可带图片、回复图片或@用户头像",
        )
        super().__init__(
            application_info,
            120,
            False,
            ApplicationCostType.HIGH_TIME_LOW_PERFORMANCE,
        )
        self.config = PicMirrorConfig()
        self.data_dir = Path("groups") / "pic_mirror"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._user_request_times: dict[int, list[float]] = {}
        self._rate_limit_lock = asyncio.Lock()
        self._processing_semaphore = asyncio.Semaphore(3)

    async def process(self, message: GroupMessageInfo):
        command_text = self._extract_command_text(message)
        if self._is_help(command_text):
            await SayGroup(message.websocket, message.groupId, self._help_text())
            return

        mode = self._get_mode(command_text)
        if not mode:
            return

        allowed, error_msg = await self._check_rate_limit(message.senderId)
        if not allowed:
            await ReplySay(message.websocket, message.groupId, message.messageId, error_msg)
            return

        async with self._processing_semaphore:
            input_path = None
            try:
                source = await self._pick_image_source(message)
                if not source:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        "未找到图像喵。请发送图片、回复图片，或使用“左对称 @群友”。",
                    )
                    return

                input_path = await self._prepare_image_file(source)
                if not input_path:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        "图片读取失败了喵。",
                    )
                    return

                input_ext = input_path.suffix.lower()
                output_path = PicMirrorProcessor.make_output_path(
                    self.data_dir, source, mode, input_ext
                )
                success, result_message = await PicMirrorProcessor.process_image(
                    str(input_path),
                    str(output_path),
                    mode,
                    self.config,
                )
                if not success:
                    await ReplySay(
                        message.websocket,
                        message.groupId,
                        message.messageId,
                        f"处理失败喵：{result_message}",
                    )
                    return

                await ReplySayImage(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    str(output_path),
                )
            except Exception as e:
                logging.error(f"图片镜像处理失败: {e}", exc_info=True)
                await ReplySay(
                    message.websocket,
                    message.groupId,
                    message.messageId,
                    "图片处理失败了喵。",
                )
            finally:
                self._cleanup_temp_input(input_path)

    def judge(self, message: GroupMessageInfo) -> bool:
        command_text = self._extract_command_text(message)
        return self._is_help(command_text) or self._get_mode(command_text) is not None

    def _extract_command_text(self, message: GroupMessageInfo) -> str:
        text = (message.plainTextMessage or "").strip()
        if not text:
            return ""
        return " ".join(text.split())

    def _get_mode(self, command_text: str) -> Optional[str]:
        if not command_text:
            return None

        normalized = command_text.lower()
        for command, mode in self.COMMANDS.items():
            if self._matches_command(normalized, command.lower()):
                return mode
        return None

    def _is_help(self, command_text: str) -> bool:
        normalized = command_text.lower()
        return any(
            self._matches_command(normalized, command.lower())
            for command in self.HELP_COMMANDS
        )

    def _matches_command(self, text: str, command: str) -> bool:
        if text == command:
            return True
        if not text.startswith(command):
            return False
        if len(text) == len(command):
            return True
        return text[len(command)] in self.COMMAND_DELIMITERS

    async def _check_rate_limit(self, user_id: int) -> tuple[bool, str]:
        current_time = time.time()
        window_start = current_time - self.RATE_LIMIT_WINDOW_SECONDS

        async with self._rate_limit_lock:
            user_requests = self._user_request_times.get(user_id, [])
            recent_requests = [req_time for req_time in user_requests if req_time >= window_start]
            self._user_request_times[user_id] = recent_requests

            if len(recent_requests) >= 10:
                remaining_time = self.RATE_LIMIT_WINDOW_SECONDS - (
                    current_time - min(recent_requests)
                )
                return False, f"请求过于频繁，请{int(remaining_time)}秒后再试喵。"

            recent_requests.append(current_time)
            return True, ""

    async def _pick_image_source(self, message: GroupMessageInfo) -> Optional[str]:
        if message.atList:
            return self._avatar_url(message.atList[0])

        sources = self._extract_image_sources(message.rawMessage.get("message", []))
        if sources:
            return sources[0]

        if message.replyMessageId != -1:
            loop = asyncio.get_running_loop()
            reply_url = await loop.run_in_executor(
                None, lambda: get_reply_image_url(message.replyMessageId)
            )
            if reply_url:
                return reply_url

        return None

    def _extract_image_sources(self, message_chain: list[dict]) -> list[str]:
        sources = []
        for segment in message_chain:
            if segment.get("type") != "image":
                continue
            data = segment.get("data", {})
            for key in ["url", "file"]:
                value = data.get(key)
                if isinstance(value, str) and value:
                    sources.append(value)
                    break
        return sources

    async def _prepare_image_file(self, source: str) -> Optional[Path]:
        if source.startswith(("http://", "https://")):
            return await PicMirrorProcessor.download_image(source, self.data_dir, self.config)

        if source.startswith("base64://"):
            return await PicMirrorProcessor.decode_base64_image(
                source, self.data_dir, self.config
            )

        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            return source_path

        if PicMirrorFileUtils.get_file_extension(source):
            possible_path = self.data_dir / source_path.name
            if possible_path.exists() and possible_path.is_file():
                return possible_path

        return None

    def _cleanup_temp_input(self, input_path: Optional[Path]):
        if not input_path or not input_path.exists():
            return
        try:
            if input_path.parent == self.data_dir and input_path.name.startswith(
                ("mirror_downloaded_", "mirror_base64_")
            ):
                input_path.unlink()
        except Exception as e:
            logging.warning(f"清理图片镜像临时文件失败: {input_path}, {e}")

    def _avatar_url(self, qq: int) -> str:
        return f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"

    def _help_text(self) -> str:
        return (
            "图片镜像功能：\n"
            "左对称 / 右对称 / 上对称 / 下对称 / 反色\n"
            "用法：发送指令并带图片，或回复一张图片发送指令，或发送“左对称 @群友”处理头像。"
        )
