from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TagMatch:
    tag: str
    score: float
    matched_titles: list[str]


class AIFilter:
    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score
        self._interest_hash = ""
        self._cached_tags = []

    def _compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    def _parse_interests_file(self, content: str) -> list[dict]:
        tags = []
        current_category = "general"
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                current_category = line[1:-1].strip().lower()
                continue

            if ":" in line:
                parts = line.split(":", 1)
                tag_name = parts[0].strip()
                keywords = [k.strip() for k in parts[1].split(",") if k.strip()]
            else:
                tag_name = line
                keywords = [line.lower()]

            tags.append({
                "name": tag_name,
                "category": current_category,
                "keywords": keywords,
                "patterns": [re.compile(r"\b" + re.escape(k) + r"\b", re.I) for k in keywords],
            })

        return tags

    def extract_tags(self, interests_content: str) -> list[dict]:
        self._interest_hash = self._compute_hash(interests_content)
        self._cached_tags = self._parse_interests_file(interests_content)
        return self._cached_tags

    def update_tags(self, old_tags: list[dict], new_interests: str) -> dict:
        new_hash = self._compute_hash(new_interests)
        if new_hash == self._interest_hash:
            return {"updated": False, "tags": old_tags}

        new_tags = self._parse_interests_file(new_interests)
        old_map = {t["name"]: t for t in old_tags}
        added = [t for t in new_tags if t["name"] not in old_map]
        removed = [t for t in old_tags if t["name"] not in {nt["name"] for nt in new_tags}]

        self._interest_hash = new_hash
        self._cached_tags = new_tags

        return {"updated": True, "tags": new_tags, "added": added, "removed": removed}

    def _match_title_to_tags(self, title: str, tags: list[dict]) -> list[TagMatch]:
        title_lower = title.lower()
        matches = []

        for tag in tags:
            score = 0.0
            matched_keywords = []

            for pattern in tag["patterns"]:
                if pattern.search(title):
                    score += 1.0
                    matched_keywords.append(pattern.pattern[2:-2])

            if matched_keywords:
                normalized_score = min(10.0, score * (1 + len(matched_keywords) * 0.2))
                matches.append(TagMatch(
                    tag=tag["name"],
                    score=normalized_score,
                    matched_titles=[title],
                ))

        return matches

    def classify_batch(self, titles: list[str], tags: Optional[list[dict]] = None) -> list[dict]:
        if tags is None:
            tags = self._cached_tags

        results = []
        for title in titles:
            matches = self._match_title_to_tags(title, tags)

            if matches:
                best_match = max(matches, key=lambda m: m.score)
                if best_match.score >= self.min_score:
                    results.append({
                        "title": title,
                        "matched_tags": [m.tag for m in matches],
                        "primary_tag": best_match.tag,
                        "confidence": best_match.score,
                    })
                    continue

            results.append({
                "title": title,
                "matched_tags": [],
                "primary_tag": "other",
                "confidence": 0.0,
            })

        return results

    def filter_by_tags(self, items: list[dict], required_tags: Optional[list[str]] = None, min_confidence: float = 0.0) -> list[dict]:
        if required_tags is None:
            return [i for i in items if i.get("confidence", 0) >= min_confidence]

        return [
            i for i in items
            if i.get("confidence", 0) >= min_confidence
            and any(tag in i.get("matched_tags", []) for tag in required_tags)
        ]

    def get_interest_hash(self) -> str:
        return self._interest_hash

    def get_cached_tags(self) -> list[dict]:
        return self._cached_tags


def create_ai_filter(config: dict) -> AIFilter:
    return AIFilter(min_score=config.get("min_score", 0.5))