#!/usr/bin/env python3
"""E2E test: Run complaints through the alternative discovery pipeline."""

import asyncio
import json
import sys
from app.alternatives.engine import AlternativeDiscoveryEngine
from app.alternatives.db import lookup_alternative, get_db_stats
from app.alternatives.search import search_multi


TEST_COMPLAINTS = [
    ("Zapier is too expensive for multi-step automation. Looking for alternatives.", "Zapier"),
    ("Jira is overkill for our 5-person startup team.", "Jira"),
    ("HubSpot CRM pricing is insane for a small business.", "HubSpot"),
    ("Salesforce is way too expensive, we need something simpler.", "Salesforce"),
    ("Airtable limits are frustrating, looking for a more affordable option.", "Airtable"),
    ("Monday.com gets too expensive as we add more team members.", "Monday.com"),
    ("Notion is not cheap for teams, considering alternatives.", "Notion"),
    ("Zendesk pricing is too high for our support team of 3.", "Zendesk"),
    ("Asana free tier is too limited for our workflow.", "Asana"),
    ("Clickup is getting expensive, need something cheaper.", "ClickUp"),
    ("Pipedrive pricing doesn't make sense for early stage startups.", "Pipedrive"),
    ("Intercom is overpriced for small product teams.", "Intercom"),
    ("Linear pricing is high for growing dev teams.", "Linear"),
    ("We switched from Zapier to n8n and saved a lot.", "Zapier"),
    ("Dropbox storage costs are getting out of hand.", "Dropbox"),
    ("Confluence is expensive for a small engineering team.", "Confluence"),
    ("Airbnb's pricing for property management is too high.", "Airbnb"),
    ("Shopify fees are eating into our margins.", "Shopify"),
    ("Canva pricing went up, looking for alternatives.", "Canva"),
    ("Figma is too expensive for side projects.", "Figma"),
]


async def test_single(complaint: str, software: str, engine: AlternativeDiscoveryEngine, idx: int):
    candidates = await engine.discover(complaint, software, force_search=False)
    affiliate_count = engine.get_affiliate_affirmed_count(candidates)
    qualifies = affiliate_count > 0

    print(f"\n{'='*60}")
    print(f"[{idx}] COMPLAINT: {complaint[:60]}...")
    print(f"    ORIGINAL: {software}")
    print(f"    CANDIDATES FOUND: {len(candidates)}")
    print(f"    AFFILIATE QUALIFYING: {affiliate_count}")
    print(f"    QUALIFIES: {'YES ✓' if qualifies else 'NO ✗'}")

    for c in candidates[:5]:
        print(f"    - {c.alternative_name:20s} | tier={c.pricing_tier:15s} | affiliate={c.affiliate_support:12s} | src={c.verification_source}")

    return qualifies, candidates


async def main():
    print("="*60)
    print("E2E: Alternative Discovery Pipeline")
    print("="*60)

    db_stats = get_db_stats()
    print(f"\nPre-built DB: {db_stats['total_saas']} SaaS, {db_stats['with_affiliate']} with affiliate support")
    print(f"By category: {json.dumps(db_stats['by_category'], indent=2)}")

    engine = AlternativeDiscoveryEngine(llm=None)

    qualifying_cases = []
    all_results = []

    for idx, (complaint, software) in enumerate(TEST_COMPLAINTS, 1):
        try:
            qualifies, candidates = await test_single(complaint, software, engine, idx)
            if qualifies:
                qualifying_cases.append((complaint, software, candidates))
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(qualifying_cases)} / {len(TEST_COMPLAINTS)} cases have affiliate alternatives")
    print(f"Target: 3 qualifying cases")
    print(f"Status: {'PASS ✓' if len(qualifying_cases) >= 3 else 'FAIL ✗'}")

    if qualifying_cases:
        print(f"\nQualifying cases:")
        for complaint, software, candidates in qualifying_cases:
            print(f"  - [{software}] → {[c.alternative_name for c in candidates if c.affiliate_support in ('confirmed', 'likely')]}")

    return len(qualifying_cases) >= 3, qualifying_cases


if __name__ == "__main__":
    success, cases = asyncio.run(main())
    sys.exit(0 if success else 1)