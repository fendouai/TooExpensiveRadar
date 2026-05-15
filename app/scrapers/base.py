from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ScrapedItem:
    platform: str
    source_url: str
    author: str
    author_metadata: dict
    content: str
    raw_content: str
    metadata: dict


class BaseScraper(ABC):
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    async def scrape(self, **kwargs) -> list[ScrapedItem]:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> bool:
        raise NotImplementedError

    def normalize_content(self, text: str) -> str:
        return " ".join(text.split())