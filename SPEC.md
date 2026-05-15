# TooExpensive.ai

## AI-Native Software Replacement Intelligence Platform

---

## 1. Product Overview

### 1.1 Product定位

TooExpensive.ai is an **AI-Native SaaS Replacement Intelligence Platform**.

**Core Mission**: Automatically discover software and workflows that users are:
- Currently using
- Already paying for
- Finding too expensive
- Actively seeking alternatives to

And automatically generate:
- AI-native replacement opportunities
- Workflow compression opportunities
- SMB simplification opportunities
- SaaS disruption opportunities

**This is NOT**:
- An AI startup idea generator
- A SaaS review website
- A trend analysis platform

**This IS**:
- Software Replacement Intelligence

### 1.2 Core Value Proposition

Help AI entrepreneurs, independent developers, Automation Agencies, SaaS Founders, and Venture Studios find the **most AI-native-replaceable software**.

---

## 2. Market Opportunity

### 2.1 The Shift

| Past | Present |
|------|---------|
| AI = content generation | AI = workflow compression |

### 2.2 Why Now

Traditional software organized workflows through:
- Tables and forms
- Configuration layers
- Admin panels
- Workflow rules
- Manual integrations

AI-native software can now:
- Use conversation
- Understand intent
- Maintain memory
- Automate end-to-end
- Orchestrate complex tasks

This dramatically compresses complexity.

### 2.3 The Real Signal

The strongest market signal is NOT "need AI" but:

```
"too expensive"
"overkill"
"alternative to X"
"pricing sucks"
"too complicated"
```

---

## 3. Target Users (ICP)

| Tier | User Type | Primary Needs |
|------|-----------|---------------|
| Tier 1 | Independent Developers | Find real needs, AI SaaS directions, low-competition workflows |
| Tier 2 | Automation Agencies | Find client automation needs, replacement opportunities |
| Tier 3 | AI SaaS Founders | Find vertical AI SaaS opportunities, workflow disruption angles |
| Tier 4 | Venture Studio / VC | AI-native trend intelligence |

---

## 4. Product Architecture

```
Data Collection (Scrapers)
    ↓
Raw Signal Storage (Layer 1)
    ↓
Complaint Detection (Layer 2)
    ↓
Workflow Extraction (Layer 3)
    ↓
AI-native Compression / LLM Analysis (Layer 4)
    ↓
Opportunity Scoring (Layer 5)
    ↓
Replacement Feed + Business Intelligence (Layer 6)
```

---

## 5. Core Modules

### 5.1 Module A — Complaint Intelligence Engine

**Objective**: Automatically discover users paying too much for poor workflows.

**Data Sources**:

| Source | Status | Focus |
|--------|--------|-------|
| Manual Input | ✅ Active | Text & CSV import |
| Reddit | 🔒 Phase 2 | OAuth app integration |
| G2 Reviews | 🔒 Phase 2 | 3-star pricing complaints |
| Capterra | 🔒 Phase 2 | Pricing & feature complaints |
| Hacker News | 🔒 Phase 2 | Developer workflows |
| Twitter/X | 🔒 Phase 2 | SaaS frustration signals |
| YouTube | 🔒 Phase 2 | SMB complaint comments |

### 5.2 Module B — Workflow Extraction Engine

**Dual Mode**:

1. **Rule-based** (V1 MVP): Pattern matching with WORKFLOW_MAP
2. **LLM-powered** (V2): Claude/GPT for deep workflow extraction

**Workflow Categories**:
- CRM workflow
- Proposal workflow
- Document signing workflow
- Automation workflow
- Project tracking workflow
- Support workflow
- Knowledge workflow
- Reporting workflow
- HR workflow
- Marketing workflow
- Internal Tool workflow

### 5.3 Module C — AI-native Compression Engine

**Dual Mode**:

1. **Rule-based** (V1 MVP): REPLACEMENT_TEMPLATES
2. **LLM-powered** (V2): Custom prompts for replacement suggestions

### 5.4 Module D — Opportunity Scoring Engine

**Scoring Dimensions**:

| Score | Weight | Description |
|-------|--------|-------------|
| Pricing Pain Score | 30% | How expensive users find this software |
| AI Compression Score | 22% | How much AI can compress the workflow |
| Feature Bloat Score | 18% | How many unused features exist |
| SMB Overkill Score | 16% | Whether SMBs are tortured by enterprise software |
| Replacement Feasibility Score | 14% | How easy the AI-native replacement is to implement |
| Workflow Simplicity Score | - | How simple and frequent the workflow is |

### 5.5 Module E — Replacement Opportunity Feed

Final output with full scoring breakdown.

---

## 6. Data Architecture

### 6.1 Layer 1 — Raw Source

```python
RawSignal:
  id, source, platform, source_url, author, author_metadata
  content, raw_content, collected_at, created_at
```

### 6.2 Layer 2 — Complaint

```python
Complaint:
  id, raw_signal_id, complaint_type, pricing_signal
  bloat_signal, smb_signal, emotion_score, software_name
  workflow_keywords, detected_keywords, sentiment_polarity
```

### 6.3 Layer 3 — Workflow Graph

```python
WorkflowGraph:
  id, complaint_id, workflow_name, workflow_steps
  manual_handoffs, software_dependencies, workflow_complexity
```

### 6.4 Layer 4 — Opportunity

```python
Opportunity:
  id, complaint_id, workflow_graph_id, software, category
  complaint_summary, actual_workflow, ai_native_replacement
  existing_price, possible_price, pricing_pain_score
  feature_bloat_score, smb_overkill_score, ai_compression_score
  workflow_simplicity_score, replacement_feasibility_score
  disruption_score, evidence
```

### 6.5 Layer 5 — Business Intelligence

```python
BusinessLayer:
  id, opportunity_id, possible_saas_name, pricing_gap
  estimated_arpu, go_to_market, target_segment, key_differentiator
```

### 6.6 Configuration Tables

```python
DataSourceConfig: id, source, enabled, config, last_collected_at, total_collected, success_count, error_count
LLMConfig: id, provider, api_key, model, enabled, is_default, config
AsyncTask: id, task_id, task_type, status, progress, input_data, output_data, error_message
```

---

## 7. Technical Architecture

### 7.1 Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | FastAPI + Python 3.10+ | Mature scraping/AI/NLP ecosystem |
| Database | SQLite (default) / PostgreSQL | Development: SQLite; Production: PostgreSQL |
| LLM | Claude (Anthropic) / GPT (OpenAI) | Workflow extraction, opportunity inference |
| Async Tasks | Celery + Redis | Background scraping, batch analysis |
| Frontend | Vanilla HTML/CSS/JS | Lightweight dashboard |

### 7.2 Key Dependencies

```
fastapi, uvicorn, sqlmodel, pydantic, pydantic-settings
httpx, anthropic, openai, celery, redis, python-dotenv
```

---

## 8. API Endpoints

### 8.1 Core Endpoints

| Method | Endpoint | Description |
|-------|---------|-------------|
| POST | `/api/ingest/text` | Ingest single text comment |
| POST | `/api/ingest/csv` | Batch CSV import |
| GET | `/api/opportunities` | List opportunities (filterable) |
| GET | `/api/opportunities/{id}` | Get opportunity detail |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/seed` | Load seed data |

### 8.2 Data Source Management

| Method | Endpoint | Description |
|-------|---------|-------------|
| GET | `/api/datasources` | List all data source configs |
| PUT | `/api/datasources/{source}` | Update source config |
| POST | `/api/datasources/{source}/collect` | Trigger collection task |

### 8.3 LLM Configuration

| Method | Endpoint | Description |
|-------|---------|-------------|
| GET | `/api/llm/configs` | List LLM configurations |
| PUT | `/api/llm/configs/{provider}` | Update LLM config (Claude/OpenAI) |

### 8.4 Task Management

| Method | Endpoint | Description |
|-------|---------|-------------|
| GET | `/api/tasks` | List background tasks |
| GET | `/api/tasks/{task_id}` | Get task status |

---

## 9. Scoring System

### 9.1 Rule-based Scoring (V1)

```python
pricing_pain = min(10.0, 2.5 + pricing_hits * 1.7 + alternative_hit * 1.5)
feature_bloat = min(10.0, 1.5 + bloat_hits * 2.0)
smb_overkill = min(10.0, 1.0 + smb_hits * 2.0 + bloat_hits * 1.2)
ai_compression = min(10.0, 4.0 + workflow_known * 2.2 + bloat_hits * 0.8 + pricing_hits * 0.4)
feasibility = min(10.0, 5.0 + workflow_known * 1.8 + software_known + alternative_hit)

disruption = (
    pricing_pain * 0.30 +
    feature_bloat * 0.18 +
    smb_overkill * 0.16 +
    ai_compression * 0.22 +
    feasibility * 0.14
)
```

### 9.2 LLM-powered Scoring (V2)

Uses structured prompts for detection, workflow extraction, replacement suggestion, and scoring via Claude/GPT.

---

## 10. Software Catalog

### 10.1 Tier 1 Targets

| Category | Target Software |
|----------|----------------|
| CRM | HubSpot, Salesforce, Pipedrive, ActiveCampaign, Mailchimp |
| Proposal | PandaDoc, DocuSign |
| Automation | Zapier, Make, Slack |
| Project Management | Jira, Monday, Asana, ClickUp, Linear, GitHub, Trello |

### 10.2 Tier 2 Targets

| Category | Target Software |
|----------|----------------|
| Knowledge Management | Confluence, Notion |
| Customer Support | Zendesk, Intercom |
| Internal Tools | Airtable, Smartsheet, ServiceNow |
| HR | Workday, Rippling |

---

## 11. Roadmap

### Phase 1 (V1 MVP) — ✅ Completed
- [x] Rule-based analyzer
- [x] SQLite database
- [x] Manual text/CSV import
- [x] Dashboard UI
- [x] Basic API endpoints

### Phase 2 (V2) — ✅ Completed
- [x] PostgreSQL support
- [x] LLM integration (Claude/OpenAI)
- [x] Data source configuration UI
- [x] LLM configuration UI
- [x] Background task tracking
- [x] Reddit scraper (OAuth)
- [x] HackerNews scraper

### Phase 3 (V3) — Planned
- [ ] Reddit API / SerpAPI integration
- [ ] G2/Capterra scrapers
- [ ] pgvector semantic clustering
- [ ] Automated newsletter generation
- [ ] Email alerting
- [ ] API for external clients

---

## 12. Pricing Tiers

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Daily Top 5, manual import |
| Pro | $29-$99/mo | Full database, workflow graphs, LLM analysis |
| Team | $299/mo | Alerts, API access, CSV export |
| Enterprise | $2k-$10k/mo | Custom intelligence, dedicated support |

---

## 13. Go-To-Market

### 13.1 Content Strategy

**NOT**: AI news

**IS**: "Which SaaS is most vulnerable to AI replacement"

### 13.2 Content Templates

| Platform | Template |
|----------|----------|
| Twitter/X | "People pay $1200/mo for this workflow?" |
| 小红书 | "这个 SaaS 太贵了，其实 AI 两周就能重做" |
| YouTube | "Overpriced SaaS teardown" |

---

## 14. Strategic Positioning

### 14.1 Core Insight

| Era | Competition Model |
|-----|-------------------|
| Past | Software competition |
| Present | Workflow compression competition |

### 14.2 AI-Native Software Core Competency

NOT more features, but:

```
less admin
less configuration
less workflow friction
less software complexity
```

### 14.3 Final Strategic Statement

The biggest alpha in AI startups is NOT "what AI can do", but:

**"Which expensive SaaS are essentially just legacy artifacts of complex workflows?"**

---

## 15. Running the Project

### 15.1 Quick Start

```bash
cd TooExpensiveRadar
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

### 15.2 Environment Variables

```bash
DATABASE_URL=sqlite:///./too_expensive.db  # or postgres://...
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...  # Optional for LLM mode
OPENAI_API_KEY=sk-...  # Optional for LLM mode
```

### 15.3 API Documentation

Visit: http://127.0.0.1:8000/docs

---

## 16. Out of Scope

- AI startup idea generation
- SaaS review/rating system
- Trend prediction/forecasting
- Direct competitor comparisons
- Tool-specific tutorials