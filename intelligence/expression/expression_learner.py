from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from database.db_pool import intel_db_pool


COMMON_WORDS = {
    "这个",
    "那个",
    "什么",
    "为什么",
    "怎么",
    "可以",
    "不是",
    "没有",
    "就是",
    "一下",
    "然后",
    "但是",
    "如果",
    "感觉",
}


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _extract_sentence_tail(text: str) -> str:
    clean_text = _normalize_text(text).strip("。！？!?~～…")
    if len(clean_text) < 3:
        return ""
    tail = clean_text[-4:]
    if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9喵呀啊呢吧啦哈]{2,4}", tail):
        return tail
    return ""


def _extract_jargon(text: str) -> list[str]:
    clean_text = _normalize_text(text)
    candidates = set(re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}|[\u4e00-\u9fff]{2,6}", clean_text))
    phrases: list[str] = []
    for candidate in candidates:
        if candidate in COMMON_WORDS:
            continue
        if candidate.isdigit():
            continue
        if len(candidate) <= 1 or len(candidate) > 12:
            continue
        if candidate.startswith("[") or candidate.endswith("]"):
            continue
        phrases.append(candidate)
    return phrases[:8]


def _style_features(text: str) -> list[tuple[str, str]]:
    features: list[tuple[str, str]] = []
    clean_text = _normalize_text(text)
    if not clean_text:
        return features
    if "哈哈" in clean_text or "笑死" in clean_text:
        features.append(("tone", "轻松吐槽"))
    if "？" in clean_text or "?" in clean_text:
        features.append(("punctuation", "常用问号"))
    if "！" in clean_text or "!" in clean_text:
        features.append(("punctuation", "常用感叹"))
    if "喵" in clean_text:
        features.append(("ending", "喵"))
    tail = _extract_sentence_tail(clean_text)
    if tail:
        features.append(("tail_phrase", tail))
    if len(clean_text) <= 12:
        features.append(("length", "短句"))
    elif len(clean_text) >= 60:
        features.append(("length", "长句"))
    return features[:8]


async def _upsert_style(
    *,
    group_id: int,
    user_id: int,
    style_key: str,
    style_value: str,
    example: str,
    weight_delta: float = 1.0,
) -> None:
    now = int(datetime.now().timestamp())
    await intel_db_pool.execute(
        """
        INSERT INTO expression_style (
            group_id, user_id, style_key, style_value, example,
            weight, created_at, updated_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(group_id, user_id, style_key, style_value) DO UPDATE SET
            example = excluded.example,
            weight = expression_style.weight + excluded.weight,
            updated_at = excluded.updated_at,
            last_seen_at = excluded.last_seen_at
        """,
        (
            group_id,
            user_id,
            style_key,
            style_value[:80],
            example[:200],
            weight_delta,
            now,
            now,
            now,
        ),
    )


async def _upsert_jargon(group_id: int, phrase: str, example: str) -> None:
    now = int(datetime.now().timestamp())
    await intel_db_pool.execute(
        """
        INSERT INTO group_jargon (
            group_id, phrase, example, count, created_at, updated_at, last_seen_at
        ) VALUES (?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(group_id, phrase) DO UPDATE SET
            example = excluded.example,
            count = group_jargon.count + 1,
            updated_at = excluded.updated_at,
            last_seen_at = excluded.last_seen_at
        """,
        (group_id, phrase[:80], example[:200], now, now, now),
    )


async def learn_expression_from_messages(
    *,
    group_id: int,
    user_id: int,
    current_text: str,
    context_messages: list[dict[str, Any]] | None = None,
) -> None:
    """Learn lightweight group/user expression patterns from recent messages."""
    try:
        samples: list[tuple[int, str]] = [(user_id, current_text)]
        for message in context_messages or []:
            content = str(message.get("content") or "")
            match = re.match(r"^\[(.+?)\]:\s*(.+)$", content)
            if match:
                samples.append((0, match.group(2)))
            elif message.get("role") == "user":
                samples.append((0, content))

        for sample_user_id, text in samples[:20]:
            clean_text = _normalize_text(text)
            if len(clean_text) < 2:
                continue
            for style_key, style_value in _style_features(clean_text):
                await _upsert_style(
                    group_id=group_id,
                    user_id=sample_user_id or 0,
                    style_key=style_key,
                    style_value=style_value,
                    example=clean_text,
                )
            for phrase in _extract_jargon(clean_text):
                await _upsert_jargon(group_id, phrase, clean_text)
    except Exception as exc:
        logging.debug("表达学习失败: %s", exc, exc_info=True)


async def get_expression_guidance(group_id: int, user_id: int, limit: int = 8) -> str:
    """Build a compact prompt section from learned expression patterns."""
    style_rows = await intel_db_pool.fetchall(
        """
        SELECT style_key, style_value, example, weight
        FROM expression_style
        WHERE group_id = ? AND user_id IN (?, 0)
        ORDER BY weight DESC, last_seen_at DESC
        LIMIT ?
        """,
        (group_id, user_id, max(1, limit)),
    )
    jargon_rows = await intel_db_pool.fetchall(
        """
        SELECT phrase, example, count
        FROM group_jargon
        WHERE group_id = ?
        ORDER BY count DESC, last_seen_at DESC
        LIMIT ?
        """,
        (group_id, max(1, limit)),
    )
    lines: list[str] = []
    if style_rows:
        style_text = "；".join(
            f"{row[0]}={row[1]}(例:{row[2]})" for row in style_rows[:limit]
        )
        lines.append(f"群内表达倾向: {style_text}")
    if jargon_rows:
        jargon_text = "、".join(f"{row[0]}({row[2]})" for row in jargon_rows[:limit])
        lines.append(f"群内常见词/黑话: {jargon_text}")
    if not lines:
        return ""
    return "\n".join(lines)

