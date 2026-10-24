"""Project-wide, live-reloadable switch for Ollama requests."""

from config.ai_control import AIDisabledError, ai_enabled, require_ai_enabled, setting_enabled


class OllamaDisabledError(AIDisabledError):
    pass


def ollama_enabled() -> bool:
    return ai_enabled() and setting_enabled("use_local_ai")


def ollama_chat(*args, **kwargs):
    require_ai_enabled()
    if not ollama_enabled():
        raise OllamaDisabledError("本项目的 Ollama 调用已暂停")
    from ollama import chat

    return chat(*args, **kwargs)
