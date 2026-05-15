from __future__ import annotations

import asyncio
import feedparser
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx


@dataclass
class RSSItem:
    id: str
    feed_id: str
    feed_name: str
    title: str
    url: str
    author: str
    published_at: Optional[datetime]
    content_snippet: str


@dataclass
class RSSData:
    date: datetime
    items: list[RSSItem]


class RSSFetcher:
    def __init__(
        self,
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
        request_interval: float = 1.0,
        max_retries: int = 3,
        user_agent: str = "TrendRadar/1.0",
    ):
        self.proxy_url = proxy_url
        self.timeout = timeout
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.user_agent = user_agent

    def _get_headers(self) -> dict:
        return {"User-Agent": self.user_agent}

    async def _fetch_with_retry(self, url: str) -> tuple[Optional[str], Optional[dict]]:
        headers = self._get_headers()
        proxies = self.proxy_url
        if proxies:
            proxies = {"http://": proxies, "https://": proxies}

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, proxy=proxies, follow_redirects=True) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    return response.text, response.headers
            except Exception as e:
                wait_time = (attempt + 1) * 2 + (attempt ** 2)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    return None, None
        return None, None

    def _parse_feed(self, feed_text: str, feed_url: str, feed_name: str, max_age_days: Optional[int] = None) -> list[RSSItem]:
        parsed = feedparser.parse(feed_text)
        items = []

        for entry in parsed.entries:
            if max_age_days:
                published = self._parse_date(entry.get("published") or entry.get("updated") or "")
                if published:
                    age = (datetime.now(timezone.utc) - published).days
                    if age > max_age_days:
                        continue

            item_id = entry.get("id") or entry.get("link") or str(hash(entry.get("title", "")))
            title = entry.get("title", "")
            link = entry.get("link", "")
            author = entry.get("author", entry.get("author_detail", {}).get("name", ""))
            published = self._parse_date(entry.get("published") or entry.get("updated") or "")
            content_snippet = self._extract_content(entry)

            if title and link:
                items.append(RSSItem(
                    id=item_id,
                    feed_id=self._feed_id_from_url(feed_url),
                    feed_name=feed_name,
                    title=title,
                    url=link,
                    author=author,
                    published_at=published,
                    content_snippet=content_snippet,
                ))

        return items

    def _feed_id_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}_{parsed.netloc}".replace(".", "_")

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            try:
                import isodate
                return isodate.parse_datetime(date_str)
            except Exception:
                return None

    def _extract_content(self, entry) -> str:
        for attr in ("summary", "description"):
            val = entry.get(attr)
            if val:
                import re
                text = re.sub(r'<[^>]+>', '', val).strip()
                if text and text != "Comments":
                    return text[:500]
        if hasattr(entry, "content"):
            for c in entry.content:
                if c.value:
                    import re
                    text = re.sub(r'<[^>]+>', '', c.value).strip()
                    if text:
                        return text[:500]
        title = entry.get("title", "")
        return title[:500]

    async def fetch_feed(self, feed_url: str, feed_name: str = "", max_age_days: Optional[int] = None) -> list[RSSItem]:
        feed_text, _ = await self._fetch_with_retry(feed_url)
        if not feed_text:
            return []
        return self._parse_feed(feed_text, feed_url, feed_name or feed_url, max_age_days)

    async def fetch_all(self, feeds: list[dict], request_interval: Optional[float] = None) -> RSSData:
        interval = request_interval or self.request_interval
        all_items = []
        seen_ids = set()

        for feed_config in feeds:
            url = feed_config.get("url")
            name = feed_config.get("name", url)
            max_age = feed_config.get("max_age_days")

            if not url:
                continue

            items = await self.fetch_feed(url, name, max_age)
            for item in items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    all_items.append(item)

            await asyncio.sleep(interval)

        return RSSData(date=datetime.now(timezone.utc), items=all_items)


def parse_multi_account_config(config_value: str, separator: str = ";") -> list[str]:
    if not config_value:
        return []
    return [s.strip() for s in config_value.split(separator) if s.strip()]


def validate_paired_configs(configs: list[str], channel_name: str) -> tuple[bool, int]:
    return len(configs) > 0, len(configs)


def limit_accounts(accounts: list[str], max_count: int, channel_name: str) -> list[str]:
    if len(accounts) > max_count:
        return accounts[:max_count]
    return accounts


def calculate_jitter(base_interval: float, jitter_factor: float = 0.3) -> float:
    import random
    return base_interval * (1 + random.uniform(-jitter_factor, jitter_factor))