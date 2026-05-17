# Alternative Discovery Pipeline — Design Spec

**Date:** 2025-05-16
**Status:** Approved

---

## 1. Overview

This pipeline extends TooExpensiveRadar to discover **cheaper alternatives** with **affiliate program support** from user complaints. When a user says "X is too expensive", we extract alternatives mentioned in the same complaint, verify their pricing, and check affiliate program availability via a 3-tier system: pre-built DB → web search → LLM inference.

---

## 2. Architecture

```
User Complaint Text
        │
        ▼
┌───────────────────────────────────────────────┐
│ Step 1: LLM Alternative Extraction            │
│ Extract named SaaS alternatives from text      │
│ ("I switched to n8n because Zapier is pricey") │
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│ Step 2: Pre-built Affiliate DB Lookup         │
│ 60+ known SaaS with pricing + affiliate data  │
└───────────────────────────────────────────────┘
        │
         ▼ (if not in DB)
┌───────────────────────────────────────────────┐
│ Step 3: Web Search Verification               │
│ SerpAPI/BochaAI: "[Software] affiliate        │
│ program pricing"                              │
└───────────────────────────────────────────────┘
        │
         ▼ (if search inconclusive)
┌───────────────────────────────────────────────┐
│ Step 4: LLM Inference                         │
│ Infer affiliate likelihood from context       │
└───────────────────────────────────────────────┘
        │
        ▼
  AlternativeCandidate(record)
```

---

## 3. Data Models

### AlternativeCandidate

```python
class AlternativeCandidate(SQLModel, table=True):
    __tablename__ = "alternative_candidates"

    id: Optional[int] = Field(default=None, primary_key=True)
    complaint_id: Optional[int] = Field(default=None, foreign_key="complaints.id", index=True)
    original_software: str = Field(default="", index=True)
    alternative_name: str = Field(default="", index=True)
    pricing_tier: str = ""           # free, freemium, tiered, enterprise, unknown
    affiliate_support: str = ""     # confirmed, likely, unlikely, undetermined
    affiliate_url: str = ""
    price_advantage: str = ""       # "50% cheaper", "free tier available"
    verification_source: str = ""   # prebuilt_db, web_search, llm_inference
    verification_details: str = ""  # JSON: search query, LLM reasoning, etc.
    disruption_score_boost: float = 0  # extra points for having cheap affiliate alternatives
    created_at: datetime = Field(default_factory=_utcnow)
```

### AlternativeCandidateRead

```python
class AlternativeCandidateRead(SQLModel):
    id: int
    original_software: str
    alternative_name: str
    pricing_tier: str
    affiliate_support: str
    affiliate_url: str
    price_advantage: str
    verification_source: str
    verification_details: str
    disruption_score_boost: float
    created_at: datetime
```

---

## 4. Component Specifications

### 4.1 Pre-built Affiliate Database (`app/alternatives/db.py`)

**60+ SaaS entries** covering the SOFTWARE_CATALOG target categories.

Each entry contains:
```python
{
    "name": "n8n",
    "pricing_tier": "free_self_hosted",
    "affiliate_support": True,
    "affiliate_url": "https://n8n.io/affiliates",
    "price_compared_to_zapier": "80% cheaper",
    "category": "automation",
    "notes": "Self-hosted option available"
}
```

**Affiliate programs confirmed:** n8n, Make, Integrately, Pabbly, Workato, Zapier, IFTTT, Integrify, Bonanza, PrestaShop, etc.

### 4.2 Search Verification (`app/alternatives/search.py`)

Uses `config.yaml` search API keys (bochaai or tavily) to query:
- `"[Software] affiliate program"`
- `"[Software] pricing plans"`
- `"[Software] free tier"`

Extracts: price range, affiliate program existence, program URL.

### 4.3 LLM Extraction (`app/alternatives/llm.py`)

Two LLM operations:
1. **Extraction prompt**: Given complaint text, output JSON array of alternative SaaS names
2. **Inference prompt**: Given search results, output affiliate likelihood (confirmed/likely/undetermined)

### 4.4 Pipeline Engine (`app/alternatives/engine.py`)

Orchestrates the 4-step flow:
```python
async def discover_alternatives(complaint_text: str, original_software: str, llm=None) -> list[AlternativeCandidate]
```

---

## 5. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/alternatives/discover` | Discover alternatives from a complaint text |
| `POST` | `/api/alternatives/verify` | Verify a specific SaaS (force web search + LLM) |
| `GET` | `/api/alternatives/known` | List all SaaS in pre-built DB |
| `GET` | `/api/alternatives/db-stats` | DB coverage statistics |

---

## 6. Scoring Boost

When an `Opportunity` has alternatives with `affiliate_support != "undetermined"`:
- `confirmed` affiliate: +1.0 to disruption_score
- `likely` affiliate: +0.5 to disruption_score
- `undetermined`: no boost

---

## 7. File Structure

```
app/alternatives/
    __init__.py
    db.py        # Pre-built knowledge base + lookup
    search.py    # Web search via BochaAI/SerpAPI
    llm.py       # LLM extraction + inference prompts
    engine.py    # Pipeline orchestrator
```

---

## 8. Dependencies

- `config.yaml` search_apis (bochaai or tavily)
- Optional LLM (for richer extraction, falls back gracefully)

---

## 9. Error Handling

- Search API unavailable → skip to LLM inference only
- LLM unavailable → return pre-built DB results only
- No alternatives found → return empty list (not an error)

---

## 10. Acceptance Criteria

1. Given complaint "Zapier is too expensive for multi-step automation", returns n8n as a cheaper alternative with confirmed affiliate support
2. Given complaint "HubSpot CRM is overpriced", returns at least one confirmed-affiliate alternative
3. Pipeline gracefully handles: no API keys, no LLM, no search results
4. All pre-built DB lookups complete in <50ms
5. New SaaS not in DB can still be discovered via search + LLM