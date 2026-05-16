import asyncio
import json
from dataclasses import dataclass
from typing import Optional

from app.alternatives.db import lookup_alternative, get_known_alternatives_for, lookup_alternative_by_category
from app.alternatives.llm import extract_alternatives_from_text, infer_affiliate_from_context, parse_llm_extraction
from app.alternatives.search import search_multi


@dataclass
class AlternativeCandidate:
    original_software: str
    alternative_name: str
    pricing_tier: str = "unknown"
    affiliate_support: str = "undetermined"
    affiliate_url: str = ""
    price_advantage: str = ""
    verification_source: str = ""
    verification_details: str = ""
    disruption_score_boost: float = 0.0


class AlternativeDiscoveryEngine:
    def __init__(self, llm=None):
        self.llm = llm

    async def discover(
        self,
        complaint_text: str,
        original_software: str,
        force_search: bool = False,
    ) -> list[AlternativeCandidate]:
        candidates: list[AlternativeCandidate] = []
        alt_names: set[str] = set()
        original_key = original_software.lower().strip()

        step1 = await self._step1_extract(complaint_text)
        for name in step1:
            if name.lower().strip() != original_key:
                alt_names.add(name)

        if len(alt_names) < 3:
            step1b = extract_alternatives_from_text(complaint_text)
            for name in step1b:
                if name.lower().strip() != original_key:
                    alt_names.add(name)

        if not alt_names:
            known_alts = get_known_alternatives_for(original_software)
            for name in known_alts:
                if name.lower().strip() != original_key:
                    alt_names.add(name)

        if not alt_names:
            orig_entry = lookup_alternative(original_key)
            if orig_entry:
                cat = orig_entry.get("category", "")
                same_cat = lookup_alternative_by_category(cat)
                for e in same_cat:
                    if e["name"].lower().strip() != original_key:
                        alt_names.add(e["name"])

        for name in alt_names:
            candidate = await self._verify_candidate(name, original_software, complaint_text, force_search)
            if candidate:
                candidates.append(candidate)

        candidates.sort(
            key=lambda c: (
                0 if c.affiliate_support == "confirmed" else 1 if c.affiliate_support == "likely" else 2,
                -c.disruption_score_boost,
            )
        )

        return candidates

    async def _step1_extract(self, text: str) -> list[str]:
        if not self.llm:
            return []

        try:
            from app.alternatives.llm import EXTRACTION_PROMPT
            prompt = EXTRACTION_PROMPT.format(content=text)
            result = await self.llm.complete(prompt)
            return parse_llm_extraction(result.content)
        except Exception:
            return []

    async def _verify_candidate(self, alt_name: str, original_software: str, context: str, force_search: bool) -> Optional[AlternativeCandidate]:
        db_entry = lookup_alternative(alt_name)

        if not db_entry:
            search_result = await search_multi(alt_name)
            if search_result.get("found"):
                affiliate = search_result.get("affiliate_support", "undetermined")
                boost = 1.0 if affiliate == "confirmed" else 0.5 if affiliate == "likely" else 0.0
                return AlternativeCandidate(
                    original_software=original_software,
                    alternative_name=alt_name,
                    pricing_tier=search_result.get("pricing_tier", "unknown"),
                    affiliate_support=affiliate,
                    affiliate_url=search_result.get("source_urls", [""])[0] if search_result.get("source_urls") else "",
                    price_advantage="",
                    verification_source="web_search",
                    verification_details=json.dumps({
                        "query": search_result.get("query", ""),
                        "snippets": search_result.get("snippets", [])[:2],
                    }),
                    disruption_score_boost=boost,
                )

        if db_entry:
            affiliate = "confirmed" if db_entry.get("affiliate_support", False) else "undetermined"
            boost = 1.0 if affiliate == "confirmed" else 0.5 if affiliate == "likely" else 0.0
            return AlternativeCandidate(
                original_software=original_software,
                alternative_name=db_entry["name"],
                pricing_tier=db_entry.get("pricing_tier", "unknown"),
                affiliate_support=affiliate,
                affiliate_url=db_entry.get("affiliate_url", ""),
                price_advantage=db_entry.get("price_advantage", ""),
                verification_source="prebuilt_db",
                verification_details=json.dumps({"db_match": True}),
                disruption_score_boost=boost,
            )

        if self.llm:
            llm_result = await infer_affiliate_from_context(alt_name, original_software, context, self.llm)
            affiliate = "likely" if llm_result.get("affiliate_likelihood") in ("likely_yes",) else "undetermined"
            boost = 0.5 if affiliate == "likely" else 0.0
            return AlternativeCandidate(
                original_software=original_software,
                alternative_name=alt_name,
                pricing_tier="unknown",
                affiliate_support=affiliate,
                affiliate_url="",
                price_advantage="",
                verification_source="llm_inference",
                verification_details=json.dumps(llm_result),
                disruption_score_boost=boost,
            )

        return None

    def get_affiliate_affirmed_count(self, candidates: list[AlternativeCandidate]) -> int:
        return sum(1 for c in candidates if c.affiliate_support in ("confirmed", "likely"))