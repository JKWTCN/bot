from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from tools.tools import (
    load_chat_ai_model,
    load_chat_ai_thinking,
    load_image_ai_model,
    load_image_ai_thinking,
    load_static_setting,
)

from .models import ChatConfig, ModelMessage


@dataclass(slots=True)
class LLMResult:
    content: str
    model_name: str
    provider: str


def strip_thinking(content: str) -> str:
    """Remove common reasoning tags/fields from local model output."""
    text = re.sub(r"<think>[\s\S]*?</think>", "", content or "").strip()
    text = re.sub(r"^\s*思考[:：][\s\S]*?(?:回答[:：]|回复[:：])", "", text).strip()
    return text


class ChatLLMClient:
    """Single gateway for Ollama-first chat calls."""

    def __init__(self, config: ChatConfig):
        self.config = config

    async def generate(
        self,
        messages: list[ModelMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        use_image_model: bool = False,
    ) -> LLMResult:
        try:
            return await self._generate_ollama(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                use_image_model=use_image_model,
            )
        except Exception as exc:
            logging.error("Ollama 调用失败: %s", exc, exc_info=True)
            if self.config.enable_cloud_fallback:
                return await self._generate_openai_compatible(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

    async def _generate_ollama(
        self,
        messages: list[ModelMessage],
        *,
        temperature: float,
        max_tokens: int | None,
        use_image_model: bool,
    ) -> LLMResult:
        from ollama import chat

        model = load_image_ai_model() if use_image_model else load_chat_ai_model()
        thinking = load_image_ai_thinking() if use_image_model else load_chat_ai_thinking()
        payload = [message.to_ollama() for message in messages]
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        def _call() -> Any:
            return chat(
                model=model,
                messages=payload,
                options=options,
                think=thinking,
            )

        response = await asyncio.wait_for(
            asyncio.to_thread(_call),
            timeout=float(self.config.request_timeout_seconds),
        )
        content = strip_thinking(response["message"]["content"])
        if not content:
            raise RuntimeError("模型返回空内容")
        return LLMResult(content=content, model_name=model, provider="ollama")

    async def _generate_openai_compatible(
        self,
        messages: list[ModelMessage],
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResult:
        from openai import OpenAI

        model = load_static_setting("open_ai_model", load_chat_ai_model())
        api_key = load_static_setting("open_ai_api_key", "")
        base_url = load_static_setting("open_ai_base_url", "")
        if not api_key or not base_url:
            raise RuntimeError("OpenAI 兼容 fallback 未配置 api_key/base_url")

        plain_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "tool"
        ]

        def _call() -> str:
            client = OpenAI(base_url=base_url, api_key=api_key)
            completion = client.chat.completions.create(
                model=model,
                messages=plain_messages,
                temperature=temperature,
                max_tokens=max_tokens or self.config.reply_max_tokens,
            )
            return completion.choices[0].message.content or ""

        content = strip_thinking(
            await asyncio.wait_for(
                asyncio.to_thread(_call),
                timeout=float(self.config.request_timeout_seconds),
            )
        )
        if not content:
            raise RuntimeError("OpenAI 兼容 fallback 返回空内容")
        return LLMResult(content=content, model_name=model, provider="openai-compatible")

