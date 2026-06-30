"""Lightweight MaiBot-style reply policy helpers.

The original MaiBot policy depends on its runtime and message abstractions. This
module keeps the useful heuristics small and local to this bot: clean noisy
message text, recognize low-value reactions, and score whether a random group
chat candidate deserves an AI reply.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence


REPLY_NECESSITY_TRIGGER_SCORE = 65
DIRECT_REQUEST_TERMS = ("帮我", "帮忙", "能不能", "可以吗", "要不要")
WEAK_REQUEST_TERMS = ("需要", "求", "看看", "试试")
QUESTION_TERMS = ("怎么", "如何", "为什么", "有没有")
OPINION_TERMS = ("你觉得", "你认为", "咋看", "有什么建议")
SHORT_REACTIONS = {
    "哈哈",
    "哈哈哈",
    "草",
    "笑死",
    "好",
    "嗯",
    "啊",
    "哦",
    "6",
    "666",
    "？",
    "?",
}
MEDIA_PLACEHOLDER_PREFIXES = (
    "[CQ:image",
    "[图片",
    "[表情包",
    "[文件]",
    "[语音",
    "[卡片",
)
IGNORED_TEXT_PREFIXES = ("【合并转发消息:", *MEDIA_PLACEHOLDER_PREFIXES, "本群发言榜")
OTHER_ASSISTANT_ADDRESSEE_PATTERN = re.compile(
    r"^(?:DeepSeek|ChatGPT|Grok|豆包|千问|元宝|通义|Kimi|Claude)[，,、\s]"
)


@dataclass(frozen=True, slots=True)
class ReplyNecessityInput:
    """Runtime snapshot needed to score a possible reply."""

    texts: Sequence[str]
    pending_count: int = 1
    trigger_threshold: int = 1
    has_at: bool = False
    has_mention: bool = False
    is_group_chat: bool = True
    recent_self_replies: int = 0
    consecutive_self_replies: int = 0
    effective_frequency: float = 1.0
    idle_seconds: float = 0.0
    idle_reached_average: bool = False


@dataclass(frozen=True, slots=True)
class ReplyNecessityScore:
    """Reply score and a compact diagnostic string for logs."""

    score: int
    detail: str


def strip_reply_noise(text: str) -> str:
    """Remove quote, mention, and media noise while keeping user text."""
    normalized_text = " ".join((text or "").split()).strip()
    if not normalized_text or normalized_text.startswith("@all"):
        return ""
    if normalized_text.startswith("[回复了") and "【合并转发消息:" in normalized_text:
        return ""
    if normalized_text.startswith(IGNORED_TEXT_PREFIXES):
        return ""

    normalized_text = re.sub(r"^\[CQ:reply[^\]]*\]\s*", "", normalized_text)
    normalized_text = re.sub(r"^\[reply\]\s*", "", normalized_text)
    normalized_text = re.sub(r"^\[回复了.+?的消息: .+?\]\s*", "", normalized_text)
    legacy_reply_match = re.search(r"\]，说：\s*(.+)$", normalized_text)
    if legacy_reply_match:
        normalized_text = legacy_reply_match.group(1)
    normalized_text = re.sub(r"^\[回复消息\]\s*", "", normalized_text)
    normalized_text = re.sub(r"^\[回复了一条消息，但原消息已无法访问\]\s*", "", normalized_text)
    normalized_text = re.sub(r"\[CQ:at,qq=\d+\]", "", normalized_text)
    normalized_text = re.sub(r"@<[^>]+>|@\S+", "", normalized_text).strip()
    if normalized_text.startswith(MEDIA_PLACEHOLDER_PREFIXES):
        return ""
    return normalized_text.strip()


def is_short_reaction_batch(texts: Sequence[str]) -> bool:
    """Return True when all non-empty texts are short reactions."""
    normalized_texts = [" ".join(text.split()).strip() for text in texts if text.strip()]
    if not normalized_texts:
        return True
    if any(len(text) > 8 for text in normalized_texts):
        return False
    return all(text in SHORT_REACTIONS for text in normalized_texts)


def has_reply_question(text: str) -> bool:
    """Detect whether the text is a real question instead of punctuation noise."""
    if not text:
        return False
    if re.fullmatch(r"[？?！!~～…\s]+[\w\u4e00-\u9fff]{1,4}[？?！!~～…\s]+", text):
        return False
    if any(term in text for term in QUESTION_TERMS):
        return True
    if re.search(r"(?<![这那没])什么", text):
        return True
    if re.search(r"[吗呢](?:[？?。！!~～…]*$)", text) and 4 <= len(text) <= 80:
        return True
    return bool(re.search(r"[？?](?:$|[。！!~～…])", text) and 4 <= len(text) <= 120)


def get_request_reason(text: str, *, is_direct_context: bool) -> str:
    """Return matched request terms, if the text asks the bot to do something."""
    if not is_direct_context and OTHER_ASSISTANT_ADDRESSEE_PATTERN.search(text):
        return ""
    direct_hits = [term for term in DIRECT_REQUEST_TERMS if term in text]
    if "能不能" in direct_hits and not (is_direct_context or text.startswith("能不能")):
        direct_hits.remove("能不能")
    if not is_direct_context:
        for weak_direct_term in ("可以吗", "要不要"):
            if weak_direct_term in direct_hits:
                direct_hits.remove(weak_direct_term)
    if direct_hits:
        return "/".join(direct_hits)
    if is_direct_context:
        weak_hits = [term for term in WEAK_REQUEST_TERMS if term in text]
        if weak_hits:
            return "/".join(weak_hits)
    return ""


def get_opinion_reason(text: str, *, is_direct_context: bool, bot_name: str = "") -> str:
    """Return matched opinion-seeking terms."""
    if "不怎么看" in text:
        return ""
    if not is_direct_context and bot_name and bot_name not in text:
        return ""
    hits = [term for term in OPINION_TERMS if term in text]
    if hits:
        return "/".join(hits)
    subject_pattern = "你"
    if bot_name:
        subject_pattern = f"(?:你|{re.escape(bot_name)})"
    if re.search(rf"{subject_pattern}.{{0,6}}怎么看|怎么看.{{0,6}}{subject_pattern}", text):
        return "怎么看"
    return ""


def score_reply_necessity(
    score_input: ReplyNecessityInput,
    *,
    bot_name: str = "",
) -> ReplyNecessityScore:
    """Calculate a deterministic score for whether a candidate should be replied to."""
    normalized_threshold = max(1, score_input.trigger_threshold)
    if score_input.has_at:
        relevance_score = 100
        relevance_reason = "@"
    elif score_input.has_mention:
        relevance_score = 80
        relevance_reason = "提及"
    elif not score_input.is_group_chat:
        relevance_score = 40
        relevance_reason = "私聊"
    else:
        relevance_score = 0
        relevance_reason = "普通"

    is_direct_context = relevance_score > 0
    cleaned_texts = [strip_reply_noise(text) for text in score_input.texts]
    combined_clean_text = "\n".join(text for text in cleaned_texts if text)
    content_score, content_reasons = _score_content(
        cleaned_texts,
        combined_clean_text,
        is_direct_context=is_direct_context,
        bot_name=bot_name,
    )
    pressure_score = min(40, int(round(40 * score_input.pending_count / normalized_threshold)))
    if score_input.idle_reached_average:
        pressure_score += 15

    presence_penalty = min(45, score_input.recent_self_replies * 15) + min(
        40,
        score_input.consecutive_self_replies * 20,
    )
    raw_score = relevance_score + content_score + pressure_score - presence_penalty
    effective_frequency = min(1.0, max(0.0, score_input.effective_frequency))
    frequency_factor = 0.5 + 0.5 * effective_frequency
    final_score = max(0, int(round(raw_score * frequency_factor)))
    detail = (
        f"最终={final_score} 原始={raw_score} "
        f"强相关={relevance_score}({relevance_reason}) "
        f"内容={content_score}({','.join(content_reasons) or '无'}) "
        f"文本长度={len(combined_clean_text)} "
        f"压力={pressure_score}(pending={score_input.pending_count}/{normalized_threshold},"
        f"idle={score_input.idle_seconds:.1f}s) "
        f"存在感=-{presence_penalty}(recent={score_input.recent_self_replies},"
        f"连续={score_input.consecutive_self_replies}) "
        f"频率={effective_frequency:.3f} 倍率={frequency_factor:.2f}"
    )
    return ReplyNecessityScore(score=final_score, detail=detail)


def should_reply_random_candidate(
    text: str,
    *,
    bot_name: str,
    trigger_threshold: int = REPLY_NECESSITY_TRIGGER_SCORE,
    effective_frequency: float = 1.0,
) -> ReplyNecessityScore:
    """Score a single random-chat candidate using conservative defaults."""
    score = score_reply_necessity(
        ReplyNecessityInput(
            texts=[text],
            pending_count=1,
            trigger_threshold=1,
            effective_frequency=effective_frequency,
        ),
        bot_name=bot_name,
    )
    if score.score < trigger_threshold:
        return score
    return score


def _score_content(
    cleaned_texts: Sequence[str],
    combined_clean_text: str,
    *,
    is_direct_context: bool,
    bot_name: str,
) -> tuple[int, list[str]]:
    content_score = 0
    content_reasons: list[str] = []
    if any(has_reply_question(text) for text in cleaned_texts):
        content_score += 15
        content_reasons.append("问题")

    request_reason = get_request_reason(
        combined_clean_text,
        is_direct_context=is_direct_context,
    )
    if request_reason:
        content_score += 20
        content_reasons.append(f"请求:{request_reason}")

    opinion_reason = get_opinion_reason(
        combined_clean_text,
        is_direct_context=is_direct_context,
        bot_name=bot_name,
    )
    if opinion_reason:
        content_score += 20
        content_reasons.append(f"征询:{opinion_reason}")

    total_text_length = len(combined_clean_text)
    if total_text_length >= 40:
        content_score += 5
        content_reasons.append("长文本")
    if total_text_length >= 120:
        content_score += 10
        content_reasons.append("较长文本")
    if is_short_reaction_batch(cleaned_texts):
        content_score -= 25
        content_reasons.append("短反应")
    return content_score, content_reasons
