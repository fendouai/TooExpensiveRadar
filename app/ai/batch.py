from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class BatchResult:
    total: int
    successful: int
    failed: int
    results: list[dict]
    errors: list[str]


class LLMAnswer:
    def __init__(self, content: str, raw: Optional[dict] = None, model: Optional[str] = None, usage: Optional[dict] = None):
        self.content = content
        self.raw = raw or {}
        self.model = model or ""
        self.usage = usage or {}


class BatchProcessor:
    def __init__(self, max_concurrent: int = 5, batch_size: int = 20, retry_delay: float = 2.0, max_retries: int = 2):
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self._semaphore = None

    async def _get_semaphore(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    async def _process_single(self, item: dict, llm, prompt_func, parser, retries: int = 0) -> dict:
        async with (await self._get_semaphore()):
            try:
                prompt = prompt_func(item)
                response = await llm.complete(prompt)

                if isinstance(response, LLMAnswer):
                    content = response.content
                elif hasattr(response, "content"):
                    content = response.content
                else:
                    content = str(response)

                parsed = parser(content)
                return {"success": True, "data": parsed, "item": item}
            except Exception as e:
                if retries < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (retries + 1))
                    return await self._process_single(item, llm, prompt_func, parser, retries + 1)
                return {"success": False, "error": str(e), "item": item}

    async def process_batch(
        self,
        items: list[dict],
        llm,
        prompt_func,
        parser,
        show_progress: bool = False,
    ) -> BatchResult:
        tasks = [self._process_single(item, llm, prompt_func, parser) for item in items]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        errors = []
        successful = 0
        failed = 0

        for result in task_results:
            if isinstance(result, Exception):
                errors.append(str(result))
                failed += 1
            elif isinstance(result, dict):
                if result.get("success"):
                    results.append(result.get("data", {}))
                    successful += 1
                else:
                    errors.append(result.get("error", "Unknown error"))
                    failed += 1

        return BatchResult(
            total=len(items),
            successful=successful,
            failed=failed,
            results=results,
            errors=errors,
        )


class StreamingBatchProcessor(BatchProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def process_streaming(self, items: list[dict], llm, prompt_func, parser):
        for item in items:
            result = await self._process_single(item, llm, prompt_func, parser)
            yield result


def default_json_parser(content: str) -> dict:
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    return json.loads(content)


def default_text_parser(content: str) -> dict:
    return {"text": content.strip()}


def build_batch_prompt_template(template: str, item: dict) -> str:
    result = template
    for key, value in item.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls = []

    async def acquire(self):
        now = asyncio.get_event_loop().time()
        self._calls = [t for t in self._calls if now - t < self.period]

        if len(self._calls) >= self.max_calls:
            wait_time = self.period - (now - self._calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                now = asyncio.get_event_loop().time()
                self._calls = [t for t in self._calls if now - t < self.period]

        self._calls.append(now)