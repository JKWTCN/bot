"""Live switches shared by local and network AI providers."""

import json
from pathlib import Path


SETTING_PATH = Path(__file__).resolve().parents[1] / "setting.json"


class AIDisabledError(RuntimeError):
    pass


def setting_enabled(key: str) -> bool:
    try:
        settings = json.loads(SETTING_PATH.read_text(encoding="utf-8"))
        value = settings.get(key, True)
        return value is True or str(value).strip().lower() in {"true", "1", "yes", "on"}
    except (OSError, ValueError, AttributeError):
        # Fail closed while settings are unavailable or being written.
        return False


def ai_enabled() -> bool:
    return setting_enabled("use_ai")


def require_ai_enabled() -> None:
    if not ai_enabled():
        raise AIDisabledError("本项目的全部 AI 调用已暂停")
