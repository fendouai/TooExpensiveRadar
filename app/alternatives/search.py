import json
from typing import Optional

import httpx

from app.database import get_search_api_key


async def search_saas_affiliate(
    saas_name: str,
    provider: str = "bochaai",
    timeout: float = 15.0,
) -> dict:
    api_key = get_search_api_key(provider)
    if not api_key or api_key.startswith("your-"):
        return {
            "found": False,
            "error": "No search API key configured",
            "affiliate_support": "undetermined",
            "pricing_tier": "unknown",
            "source_url": "",
        }

    query = f"{saas_name} affiliate program"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "bochaai":
                response = await client.post(
                    "https://api.bocha.ai/v1/search",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "query": query,
                        "count": 5,
                        "extra": {"show_source": True},
                    },
                )
                result = response.json()
                organic = result.get("organic", [])
                snippets = []
                source_urls = []
                for item in organic:
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    snippets.append(snippet)
                    if link:
                        source_urls.append(link)

                return {
                    "found": len(organic) > 0,
                    "affiliate_support": _infer_affiliate_from_snippets(snippets),
                    "pricing_tier": _infer_pricing_from_snippets(snippets),
                    "source_urls": source_urls,
                    "snippets": snippets,
                    "query": query,
                    "error": None,
                }
            elif provider == "tavily":
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 5,
                    },
                )
                result = response.json()
                results = result.get("results", [])
                snippets = [r.get("content", "") for r in results]
                source_urls = [r.get("url", "") for r in results]

                return {
                    "found": len(results) > 0,
                    "affiliate_support": _infer_affiliate_from_snippets(snippets),
                    "pricing_tier": _infer_pricing_from_snippets(snippets),
                    "source_urls": source_urls,
                    "snippets": snippets,
                    "query": query,
                    "error": None,
                }
    except Exception as e:
        return {
            "found": False,
            "error": str(e),
            "affiliate_support": "undetermined",
            "pricing_tier": "unknown",
            "source_url": "",
        }


def _infer_affiliate_from_snippets(snippets: list[str]) -> str:
    combined = " ".join(snippets).lower()
    if "affiliate" in combined and ("program" in combined or "join" in combined or "sign up" in combined):
        return "confirmed"
    if "partner" in combined and ("program" in combined or "referral" in combined):
        return "likely"
    return "undetermined"


def _infer_pricing_from_snippets(snippets: list[str]) -> str:
    combined = " ".join(snippets).lower()
    if "free" in combined and "tier" in combined:
        return "freemium"
    if "starts at $0" in combined or "free plan" in combined or "free forever" in combined:
        return "freemium"
    if "enterprise" in combined or "contact us" in combined:
        return "enterprise"
    if "per user" in combined or "/user" in combined or "/month per user" in combined:
        return "per_user"
    if "transaction" in combined or "% +" in combined:
        return "transaction"
    if "flat" in combined or "$" in combined:
        return "tiered"
    return "unknown"


async def search_multi(
    saas_name: str,
    providers: list[str] = None,
) -> dict:
    if providers is None:
        providers = ["bochaai", "tavily"]

    for provider in providers:
        result = await search_saas_affiliate(saas_name, provider=provider)
        if result.get("found") and not result.get("error"):
            return result

    return {
        "found": False,
        "error": "All search providers failed",
        "affiliate_support": "undetermined",
        "pricing_tier": "unknown",
        "source_urls": [],
        "snippets": [],
        "query": "",
    }