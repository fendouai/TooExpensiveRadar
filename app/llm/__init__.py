from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from app.models import LLMProvider


@dataclass
class LLMResponse:
    content: str
    raw: dict
    model: str
    tokens_used: int = 0


class BaseLLM(ABC):
    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    async def batch_complete(self, prompts: list[str], **kwargs) -> list[LLMResponse]:
        raise NotImplementedError


class ClaudeLLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241023"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.anthropic.com/v1/messages"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.api_key:
            raise ValueError("API key required")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.3),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(self.endpoint, headers=headers, json=payload)
            if res.status_code != 200:
                raise Exception(f"Claude API error: {res.status_code} {res.text}")
            data = res.json()
            return LLMResponse(
                content=data["content"][0]["text"],
                raw=data,
                model=self.model,
                tokens_used=data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
            )

    async def batch_complete(self, prompts: list[str], **kwargs) -> list[LLMResponse]:
        return [await self.complete(p, **kwargs) for p in prompts]


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.api_key:
            raise ValueError("API key required")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(self.endpoint, headers=headers, json=payload)
            if res.status_code != 200:
                raise Exception(f"OpenAI API error: {res.status_code} {res.text}")
            data = res.json()
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                raw=data,
                model=self.model,
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
            )

    async def batch_complete(self, prompts: list[str], **kwargs) -> list[LLMResponse]:
        return [await self.complete(p, **kwargs) for p in prompts]


class MiniMaxLLM(OpenAILLM):
    def __init__(self, api_key: str, model: str = "MiniMax-Text-01", base_url: str = "https://api.minimax.chat/v1"):
        super().__init__(api_key, model, base_url)


LLM_REGISTRY: dict[str, type[BaseLLM]] = {
    "claude": ClaudeLLM,
    "openai": OpenAILLM,
    "minimax": MiniMaxLLM,
    "minimax-text-01": MiniMaxLLM,
}


def get_llm(provider: str, api_key: str, model: str = "", base_url: str = "") -> BaseLLM:
    provider_lower = provider.lower()
    base_url_lower = (base_url or "").lower()

    if provider_lower in ("minimax", "minimax-text-01") or "minimax" in base_url_lower:
        return MiniMaxLLM(api_key, model or "MiniMax-M2.7", base_url or "https://api.minimax.chat/v1")
    llm_cls = LLM_REGISTRY.get(provider_lower, OpenAILLM)
    return llm_cls(api_key, model or "")