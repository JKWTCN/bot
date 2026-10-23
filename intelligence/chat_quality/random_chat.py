"""Group-scoped random-chat selection and in-flight rate limiting."""
from collections import defaultdict, deque
import re
import time

from .reply_policy import (
    get_request_reason, has_reply_question, is_short_reaction_batch,
    strip_reply_noise, OTHER_ASSISTANT_ADDRESSEE_PATTERN,
)


def candidate_kind(text: str) -> str:
    text = strip_reply_noise(text)
    if (not text or len(text) < 4 or is_short_reaction_batch([text])
            or re.fullmatch(r"[哈呵嘿嘻啊哦嗯]+[！!。~～…]*", text)
            or re.match(r"^[./!！#。／]", text)
            or not re.search(r"[\w\u4e00-\u9fff]", text)
            or OTHER_ASSISTANT_ADDRESSEE_PATTERN.search(text)):
        return ""
    if has_reply_question(text) or get_request_reason(text, is_direct_context=False):
        return "question"
    return "normal"


class RandomChatLimiter:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.sent = defaultdict(deque)
        self.pending = set()

    def reserve(self, group_id: int, config: dict) -> bool:
        now = self.clock()
        history = self.sent[group_id]
        window = max(1.0, float(config.get("window_seconds", 600)))
        while history and now - history[0] >= window:
            history.popleft()
        if group_id in self.pending:
            return False
        if history and now - history[-1] < float(config.get("cooldown_seconds", 90)):
            return False
        if len(history) >= int(config.get("max_replies_per_window", 3)):
            return False
        self.pending.add(group_id)
        return True

    def finish(self, group_id: int, *, sent: bool):
        self.pending.discard(group_id)
        if sent:
            self.sent[group_id].append(self.clock())
