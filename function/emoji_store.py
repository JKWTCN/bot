"""Lightweight VLM-judged emoji collection and selection."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import hashlib
import heapq
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import sqlite3
from typing import Any

import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from function.GroupConfig import get_config
from tools.tools import (
    load_chat_ai_model,
    load_chat_ai_thinking,
    load_image_ai_model,
    load_image_ai_thinking,
)


EMOJI_DB_PATH = "bot-emoji.db"
EMOJI_DIR = Path("data") / "emoji"
BYTES_PER_MIB = 1024 * 1024
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

CONTENT_REVIEW_PROMPT = """这是一个表情包，请对这个表情包进行审核，标准如下：
1. 必须符合"符合公序良俗"的要求
2. 不能是色情、暴力、等违法违规内容，必须符合公序良俗
3. 不能是任何形式的截图，聊天记录或视频截图
4. 不要出现5个以上文字
请回答这个表情包是否满足上述要求，是则回答是，否则回答否，不要出现任何其他内容"""

TAG_PROMPT = (
    "这是一个表情包图片，请提取该表情主要表达的情绪或语气标签，"
    "最多 5 个，使用逗号分隔，返回纯文本标签列表，不要解释，不要输出其他内容。"
)

GIF_TAG_PROMPT = (
    "这是一个动态图表情包，每一张图代表了动态图的一帧。"
    "请只返回该表情包常见的情绪/场景标签，最多 5 个，"
    "使用逗号分隔，标签可为中文或英文，不要附带解释。"
)


@dataclass(slots=True)
class EmojiRecord:
    id: int
    image_hash: str
    file_name: str
    full_path: str
    image_format: str
    description: str
    query_count: int
    created_at: str
    last_used_at: str | None


@dataclass(slots=True)
class EmojiCollectResult:
    status: str
    image_hash: str = ""
    description: str = ""
    reason: str = ""


@dataclass(slots=True)
class EmojiSelectionResult:
    record: EmojiRecord | None
    reason: str = ""
    error: str = ""


def init_emoji_database() -> None:
    """Initialize emoji metadata storage."""
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emoji (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_hash TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                full_path TEXT NOT NULL,
                image_format TEXT NOT NULL,
                description TEXT NOT NULL,
                source_group_id INTEGER,
                source_user_id INTEGER,
                source_message_id INTEGER,
                is_registered INTEGER DEFAULT 1,
                is_banned INTEGER DEFAULT 0,
                query_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_emoji_available
            ON emoji(is_registered, is_banned, query_count)
            """
        )
        conn.commit()
    finally:
        conn.close()


async def collect_emoji_from_url(
    url: str,
    *,
    group_id: int,
    user_id: int,
    message_id: int,
) -> EmojiCollectResult:
    """Download, review, tag, and register an emoji image with VLM judgment."""
    init_emoji_database()
    try:
        image_bytes = await asyncio.to_thread(_download_image_bytes, url)
    except Exception as e:
        logging.warning(f"下载表情包失败: {e}")
        return EmojiCollectResult(status="failed", reason=str(e))

    max_size_mb = int(get_config("emoji_max_size_mb", group_id) or 8)
    if max_size_mb > 0 and len(image_bytes) > max_size_mb * BYTES_PER_MIB:
        return EmojiCollectResult(status="skipped", reason="size_limit")

    image_hash = hashlib.sha256(image_bytes).hexdigest()
    existing = get_emoji_by_hash(image_hash)
    if existing and _record_file_exists(existing):
        return EmojiCollectResult(
            status="duplicate",
            image_hash=image_hash,
            description=existing.description,
        )

    image_format = _detect_image_format(image_bytes)
    if image_format not in {"jpg", "jpeg", "png", "gif", "webp"}:
        return EmojiCollectResult(status="skipped", image_hash=image_hash, reason="unsupported_format")

    temp_path = _write_temp_image(image_hash, image_bytes)
    try:
        model_path, model_format = await asyncio.to_thread(_prepare_model_image, temp_path, image_format)

        if get_config("emoji_content_review", group_id):
            review_text = await _call_vlm(CONTENT_REVIEW_PROMPT, model_path)
            if "是" not in review_text or "否" in review_text or "不" in review_text:
                return EmojiCollectResult(
                    status="rejected",
                    image_hash=image_hash,
                    reason=review_text[:120],
                )

        tag_prompt = GIF_TAG_PROMPT if image_format == "gif" else TAG_PROMPT
        tag_text = await _call_vlm(tag_prompt, model_path)
        tags = _normalize_tags(tag_text)
        if not tags:
            return EmojiCollectResult(status="rejected", image_hash=image_hash, reason="empty_tags")

        final_path = _final_emoji_path(image_hash, image_format)
        os.replace(temp_path, final_path)
        await _register_or_replace_emoji(
            image_hash=image_hash,
            file_name=final_path.name,
            full_path=str(final_path),
            image_format=image_format,
            description=",".join(tags),
            group_id=group_id,
            user_id=user_id,
            message_id=message_id,
        )
        return EmojiCollectResult(
            status="registered",
            image_hash=image_hash,
            description=",".join(tags),
        )
    except Exception as e:
        logging.warning(f"表情包模型判断失败: {e}", exc_info=True)
        return EmojiCollectResult(status="failed", image_hash=image_hash, reason=str(e))
    finally:
        for path in (temp_path, Path(f"{temp_path}.jpg")):
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass


async def select_emoji_for_context(
    *,
    group_id: int,
    context_texts: list[str],
    request_text: str,
) -> EmojiSelectionResult:
    """Let VLM choose a suitable emoji from a labeled candidate grid."""
    init_emoji_database()
    records = list_available_emojis()
    if not records:
        return EmojiSelectionResult(record=None, error="当前表情包库为空喵。")

    candidate_count = int(get_config("emoji_candidate_count", group_id) or 25)
    candidate_count = max(1, min(candidate_count, 36, len(records)))
    candidates = _sample_candidate_emojis(records, request_text, candidate_count)
    grid_bytes, rows, columns = await asyncio.to_thread(_build_candidate_grid, candidates)
    grid_path = EMOJI_DIR / f"candidate_{hashlib.md5(grid_bytes).hexdigest()}.png"
    grid_path.write_bytes(grid_bytes)
    try:
        prompt = _build_selection_prompt(
            emoji_count=len(candidates),
            rows=rows,
            columns=columns,
            context_texts=context_texts,
            request_text=request_text,
        )
        response_text = await _call_vlm(prompt, grid_path)
        selection = _parse_selection_response(response_text, len(candidates))
        if selection is None:
            return EmojiSelectionResult(
                record=None,
                error=f"模型没有选出有效表情喵: {response_text[:80]}",
            )
        record = candidates[selection["emoji_index"] - 1]
        update_emoji_usage(record.image_hash)
        return EmojiSelectionResult(record=record, reason=selection.get("reason", ""))
    except Exception as e:
        logging.warning(f"表情包选择失败: {e}", exc_info=True)
        return EmojiSelectionResult(record=None, error=f"表情包选择失败喵: {e}")
    finally:
        if grid_path.exists():
            try:
                grid_path.unlink()
            except OSError:
                pass


def extract_image_urls(raw_message: dict) -> list[str]:
    """Extract image URLs from OneBot message segments."""
    urls: list[str] = []
    for segment in raw_message.get("message", []):
        if segment.get("type") != "image":
            continue
        url = segment.get("data", {}).get("url")
        if url:
            urls.append(url)
    return urls


def list_available_emojis() -> list[EmojiRecord]:
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, image_hash, file_name, full_path, image_format, description,
                   query_count, created_at, last_used_at
            FROM emoji
            WHERE is_registered = 1 AND is_banned = 0
            ORDER BY query_count ASC, updated_at DESC
            """
        )
        records = [_row_to_record(row) for row in cursor.fetchall()]
        return [record for record in records if _record_file_exists(record)]
    finally:
        conn.close()


def get_emoji_by_hash(image_hash: str) -> EmojiRecord | None:
    if not os.path.exists(EMOJI_DB_PATH):
        return None
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, image_hash, file_name, full_path, image_format, description,
                   query_count, created_at, last_used_at
            FROM emoji
            WHERE image_hash = ? AND is_registered = 1 AND is_banned = 0
            LIMIT 1
            """,
            (image_hash,),
        )
        row = cursor.fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def update_emoji_usage(image_hash: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE emoji
            SET query_count = query_count + 1,
                last_used_at = ?,
                updated_at = ?
            WHERE image_hash = ?
            """,
            (now, now, image_hash),
        )
        conn.commit()
    finally:
        conn.close()


def _download_image_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _write_temp_image(image_hash: str, image_bytes: bytes) -> Path:
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = EMOJI_DIR / f"{image_hash}.tmp"
    temp_path.write_bytes(image_bytes)
    return temp_path


def _final_emoji_path(image_hash: str, image_format: str) -> Path:
    extension = "jpg" if image_format == "jpeg" else image_format
    return EMOJI_DIR / f"{image_hash}.{extension}"


def _detect_image_format(image_bytes: bytes) -> str:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            return (image.format or "").lower()
    except Exception:
        return ""


def _prepare_model_image(path: Path, image_format: str) -> tuple[Path, str]:
    if image_format != "gif":
        return path, image_format

    preview_path = Path(f"{path}.jpg")
    with Image.open(path) as image:
        image.seek(0)
        frame = image.convert("RGB")
        frame.save(preview_path, format="JPEG", quality=92)
    return preview_path, "jpg"


async def _call_vlm(prompt: str, image_path: Path) -> str:
    from ollama import chat

    def _call() -> str:
        response = chat(
            model=load_image_ai_model(),
            messages=[{"role": "user", "content": prompt, "images": [str(image_path)]}],
            options={"temperature": 0.2},
            think=load_image_ai_thinking(),
        )
        content = response["message"]["content"]
        return re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

    return await asyncio.to_thread(_call)


async def _call_text_llm(prompt: str) -> str:
    from ollama import chat

    def _call() -> str:
        response = chat(
            model=load_chat_ai_model(),
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
            think=load_chat_ai_thinking(),
        )
        content = response["message"]["content"]
        return re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

    return await asyncio.to_thread(_call)


def _normalize_tags(raw_text: str) -> list[str]:
    raw_text = re.sub(r"[`\"'\[\]{}]", "", raw_text or "")
    parts = re.split(r"[,，、;；\r\n\t ]+", raw_text.strip())
    tags: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = part.strip("。.!！?？：:")
        if not tag:
            continue
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(tag)
        if len(tags) >= 5:
            break
    return tags


async def _register_or_replace_emoji(
    *,
    image_hash: str,
    file_name: str,
    full_path: str,
    image_format: str,
    description: str,
    group_id: int,
    user_id: int,
    message_id: int,
) -> None:
    max_count = int(get_config("emoji_max_count", group_id) or 500)
    if max_count > 0 and len(list_available_emojis()) >= max_count:
        replaced = await _replace_one_emoji_by_llm(group_id, description)
        if not replaced:
            raise RuntimeError("表情包库已满,模型决定不替换旧表情")

    now = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO emoji (
                image_hash, file_name, full_path, image_format, description,
                source_group_id, source_user_id, source_message_id,
                is_registered, is_banned, query_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?)
            ON CONFLICT(image_hash) DO UPDATE SET
                file_name = excluded.file_name,
                full_path = excluded.full_path,
                image_format = excluded.image_format,
                description = excluded.description,
                source_group_id = excluded.source_group_id,
                source_user_id = excluded.source_user_id,
                source_message_id = excluded.source_message_id,
                is_registered = 1,
                is_banned = 0,
                updated_at = excluded.updated_at
            """,
            (
                image_hash,
                file_name,
                full_path,
                image_format,
                description,
                group_id,
                user_id,
                message_id,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


async def _replace_one_emoji_by_llm(group_id: int, new_description: str) -> bool:
    candidates = list_available_emojis()[:20]
    if not candidates:
        return False

    lines = []
    for index, record in enumerate(candidates, start=1):
        lines.append(
            f"编号: {index}\n描述: {record.description}\n使用次数: {record.query_count}\n添加时间: {record.created_at}\n"
        )
    prompt = (
        f"乐可的可发送表情包数量已满({len(list_available_emojis())}/{get_config('emoji_max_count', group_id)})，"
        "需要决定是否取消注册一个旧表情包来为新表情包腾出名额。\n\n"
        f"新表情包信息：\n描述: {new_description}\n\n"
        f"现有表情包列表：\n{''.join(lines)}\n"
        "请决定：\n"
        "1. 是否要取消注册某个现有表情包来为新表情包腾出名额？\n"
        "2. 如果要取消注册，应该取消注册哪一个(给出编号)？\n"
        "请只回答：'不取消注册'或'取消注册编号X'(X为表情包编号)。"
    )
    decision = await _call_text_llm(prompt)
    if "不取消注册" in decision or "不删除" in decision:
        return False
    match = re.search(r"(?:取消注册|删除)编号(\d+)", decision)
    if not match:
        return False
    index = int(match.group(1)) - 1
    if index < 0 or index >= len(candidates):
        return False
    _unregister_emoji(candidates[index].image_hash)
    return True


def _unregister_emoji(image_hash: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(EMOJI_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE emoji SET is_registered = 0, updated_at = ? WHERE image_hash = ?",
            (now, image_hash),
        )
        conn.commit()
    finally:
        conn.close()


def _sample_candidate_emojis(
    records: list[EmojiRecord],
    request_text: str,
    candidate_count: int,
) -> list[EmojiRecord]:
    ranked = _rank_by_tag_similarity(records, request_text)
    if ranked:
        top_pool = [record for record, _score in ranked[: max(candidate_count * 2, candidate_count)]]
        if len(top_pool) > candidate_count:
            return random.sample(top_pool, candidate_count)
        return top_pool
    return random.sample(records, candidate_count) if len(records) > candidate_count else records


def _rank_by_tag_similarity(records: list[EmojiRecord], request_text: str) -> list[tuple[EmojiRecord, float]]:
    request_tags = _normalize_tags(request_text)
    if not request_tags:
        return []
    scored: list[tuple[EmojiRecord, float]] = []
    for record in records:
        tags = _normalize_tags(record.description)
        if not tags:
            continue
        score = max(_string_similarity(request_tag, tag) for request_tag in request_tags for tag in tags)
        if score > 0:
            scored.append((record, score))
    return heapq.nlargest(len(scored), scored, key=lambda item: item[1])


def _string_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    max_len = max(len(left), len(right))
    distance = _levenshtein_distance(left, right)
    return 1 - distance / max_len


def _levenshtein_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _build_candidate_grid(candidates: list[EmojiRecord]) -> tuple[bytes, int, int]:
    tile_size = 256
    gap = 12
    rows, columns = _calculate_grid_shape(len(candidates))
    canvas = Image.new(
        "RGBA",
        (tile_size * columns + gap * (columns - 1), tile_size * rows + gap * (rows - 1)),
        color=(255, 255, 255, 255),
    )
    for index, record in enumerate(candidates, start=1):
        tile = _build_labeled_tile(record.full_path, index, tile_size)
        row = (index - 1) // columns
        column = (index - 1) % columns
        canvas.paste(tile, (column * (tile_size + gap), row * (tile_size + gap)), tile)

    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG")
    return output.getvalue(), rows, columns


def _calculate_grid_shape(candidate_count: int) -> tuple[int, int]:
    best_columns = candidate_count
    best_rows = 1
    best_score: tuple[int, int] | None = None
    for columns in range(1, candidate_count + 1):
        rows = math.ceil(candidate_count / columns)
        score = (abs(columns - rows), rows * columns - candidate_count)
        if best_score is None or score < best_score:
            best_score = score
            best_columns = columns
            best_rows = rows
    return best_rows, best_columns


def _build_labeled_tile(image_path: str, index: int, tile_size: int) -> Image.Image:
    try:
        with Image.open(image_path) as raw_image:
            if getattr(raw_image, "is_animated", False):
                raw_image.seek(0)
            image = raw_image.convert("RGBA")
    except Exception:
        image = Image.new("RGBA", (tile_size, tile_size), color=(245, 245, 245, 255))

    image.thumbnail((tile_size, tile_size))
    tile = Image.new("RGBA", (tile_size, tile_size), color=(255, 255, 255, 255))
    tile.paste(image, ((tile_size - image.width) // 2, (tile_size - image.height) // 2), image)

    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default()
    badge_size = 56
    badge_margin = 14
    draw.rounded_rectangle(
        (badge_margin, badge_margin, badge_margin + badge_size, badge_margin + badge_size),
        radius=8,
        fill=(0, 0, 0, 180),
    )
    label = str(index)
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            badge_margin + (badge_size - (bbox[2] - bbox[0])) / 2,
            badge_margin + (badge_size - (bbox[3] - bbox[1])) / 2 - 1,
        ),
        label,
        fill=(255, 255, 255, 255),
        font=font,
    )
    return tile


def _build_selection_prompt(
    *,
    emoji_count: int,
    rows: int,
    columns: int,
    context_texts: list[str],
    request_text: str,
) -> str:
    context = "\n".join(context_texts[-5:]).strip() or "无"
    return (
        "你需要根据上下文和当前语气,选择一个合适的表情包来发送。\n"
        f"当前用户请求: {request_text or '发送一个合适的表情包'}\n"
        f"最近聊天上下文:\n{context}\n\n"
        f"其中包含一张 {rows}x{columns} 的表情包拼图，一共 {emoji_count} 个位置。\n"
        f"每张小图左上角都有一个较大的序号，范围是 1 到 {emoji_count}。\n"
        "你需要从这些图里选出最适合当前语境的一张表情包。\n"
        "你必须返回一个 JSON 对象，不要输出任何 JSON 之外的内容。\n"
        '返回格式为：{"emoji_index":1,"reason":"简短理由"}'
    )


def _parse_selection_response(raw_text: str, candidate_count: int) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw_text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    try:
        emoji_index = int(data.get("emoji_index", 0))
    except (TypeError, ValueError):
        return None
    if not 1 <= emoji_index <= candidate_count:
        return None
    return {"emoji_index": emoji_index, "reason": str(data.get("reason", "")).strip()}


def _row_to_record(row: tuple) -> EmojiRecord:
    return EmojiRecord(
        id=row[0],
        image_hash=row[1],
        file_name=row[2],
        full_path=row[3],
        image_format=row[4],
        description=row[5],
        query_count=row[6],
        created_at=row[7],
        last_used_at=row[8],
    )


def _record_file_exists(record: EmojiRecord) -> bool:
    path = Path(record.full_path)
    return path.exists() and path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def image_file_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
