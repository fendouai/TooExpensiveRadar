from __future__ import annotations

import re
from typing import Optional
import httpx

from app.scrapers.base import BaseScraper, ScrapedItem

SUBREDDITS = [
    "SaaS", "startups", "smallbusiness", "SYSADMIN", "agency",
    "Entrepreneur", "webdev", "ecommerce", "marketing",
]


class RedditScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.client_id = config.get("client_id", "") if config else ""
        self.client_secret = config.get("client_secret", "") if config else ""
        self.user_agent = config.get("user_agent", "TooExpensiveRadar/1.0") if config else "TooExpensiveRadar/1.0"
        self.access_token: Optional[str] = None

    PRICING_SIGNALS = [
        "too expensive", "overpriced", "pricing sucks", "expensive",
        "not worth", "pricey", "cheaper alternative", "cost", "subscription",
        "overkill", "pricing", "afford",
    ]

    def _extract_signal(self, text: str) -> bool:
        lower = text.lower()
        return any(signal in lower for signal in self.PRICING_SIGNALS)

    async def test_connection(self) -> bool:
        if not self.client_id or not self.client_secret:
            return False
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"User-Agent": self.user_agent},
                )
                return res.status_code == 200
        except Exception:
            return False

    async def _get_access_token(self) -> Optional[str]:
        if self.access_token:
            return self.access_token
        if not self.client_id or not self.client_secret:
            return None
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"User-Agent": self.user_agent},
                )
                if res.status_code == 200:
                    self.access_token = res.json().get("access_token")
                    return self.access_token
        except Exception:
            pass
        return None

    async def scrape(self, subreddits: list[str] | None = None, limit: int = 50, **kwargs) -> list[ScrapedItem]:
        token = await self._get_access_token()
        if not token:
            return []

        headers = {"Authorization": f"Bearer {token}", "User-Agent": self.user_agent}
        items = []
        target_subreddits = subreddits or SUBREDDITS

        async with httpx.AsyncClient(timeout=30.0) as client:
            for subreddit in target_subreddits:
                try:
                    res = await client.get(
                        f"https://oauth.reddit.com/r/{subreddit}/hot",
                        headers=headers,
                        params={"limit": limit, "raw_json": 1},
                    )
                    if res.status_code != 200:
                        continue

                    data = res.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        post_data = post.get("data", {})
                        title = post_data.get("title", "")
                        selftext = post_data.get("selftext", "")
                        combined = f"{title} {selftext}"
                        if self._extract_signal(combined):
                            items.append(ScrapedItem(
                                platform="reddit",
                                source_url=f"https://reddit.com{post_data.get('permalink', '')}",
                                author=post_data.get("author", ""),
                                author_metadata={"subreddit": subreddit, "score": post_data.get("score", 0)},
                                content=self.normalize_content(f"{title}. {selftext}"),
                                raw_content=self.normalize_content(combined),
                                metadata={"type": "post", "subreddit": subreddit},
                            ))
                except Exception:
                    continue

                try:
                    res = await client.get(
                        f"https://oauth.reddit.com/r/{subreddit}/new",
                        headers=headers,
                        params={"limit": limit, "raw_json": 1},
                    )
                    if res.status_code == 200:
                        data = res.json()
                        posts = data.get("data", {}).get("children", [])
                        for post in posts:
                            post_data = post.get("data", {})
                            title = post_data.get("title", "")
                            selftext = post_data.get("selftext", "")
                            combined = f"{title} {selftext}"
                            if self._extract_signal(combined):
                                items.append(ScrapedItem(
                                    platform="reddit",
                                    source_url=f"https://reddit.com{post_data.get('permalink', '')}",
                                    author=post_data.get("author", ""),
                                    author_metadata={"subreddit": subreddit, "score": post_data.get("score", 0)},
                                    content=self.normalize_content(f"{title}. {selftext}"),
                                    raw_content=self.normalize_content(combined),
                                    metadata={"type": "post", "subreddit": subreddit},
                                ))
                except Exception:
                    continue

        return items


class G2Scraper(BaseScraper):
    async def scrape(self, product: str | None = None, limit: int = 50, **kwargs) -> list[ScrapedItem]:
        return []

    async def test_connection(self) -> bool:
        return False


class CapterraScraper(BaseScraper):
    async def scrape(self, product: str | None = None, limit: int = 50, **kwargs) -> list[ScrapedItem]:
        return []

    async def test_connection(self) -> bool:
        return False


class HackerNewsScraper(BaseScraper):
    async def scrape(self, limit: int = 50, keywords: list[str] | None = None, **kwargs) -> list[ScrapedItem]:
        items = []
        keywords = keywords or ["expensive", "overkill", "pricing", "alternative"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(
                    "https://hacker-news.firebaseio.com/v0/topstories.json",
                    timeout=30.0,
                )
                if res.status_code != 200:
                    return []
                ids = res.json()[:100]
                count = 0
                for item_id in ids:
                    if count >= limit:
                        break
                    try:
                        res = await client.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                            timeout=10.0,
                        )
                        if res.status_code == 200:
                            item = res.json()
                            text = (item.get("text") or item.get("title") or "")
                            lower = text.lower()
                            if any(kw.lower() in lower for kw in keywords):
                                items.append(ScrapedItem(
                                    platform="hackernews",
                                    source_url=f"https://news.ycombinator.com/item?id={item_id}",
                                    author=item.get("by", ""),
                                    author_metadata={},
                                    content=self.normalize_content(text),
                                    raw_content=text,
                                    metadata={"type": item.get("type", "story")},
                                ))
                                count += 1
                    except Exception:
                        continue
        except Exception:
            pass
        return items

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
                return res.status_code == 200
        except Exception:
            return False


class TwitterScraper(BaseScraper):
    async def scrape(self, query: str = "expensive software alternative", limit: int = 50, **kwargs) -> list[ScrapedItem]:
        return []

    async def test_connection(self) -> bool:
        return False


class YouTubeScraper(BaseScraper):
    async def scrape(self, video_id: str | None = None, limit: int = 50, **kwargs) -> list[ScrapedItem]:
        return []

    async def test_connection(self) -> bool:
        return False


SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "reddit": RedditScraper,
    "g2": G2Scraper,
    "capterra": CapterraScraper,
    "hackernews": HackerNewsScraper,
    "twitter": TwitterScraper,
    "youtube": YouTubeScraper,
}


def get_scraper(source: str, config: dict | None = None) -> BaseScraper:
    scraper_cls = SCRAPER_REGISTRY.get(source.lower(), RedditScraper)
    return scraper_cls(config)