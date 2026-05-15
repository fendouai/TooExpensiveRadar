# Too Expensive Radar

**AI-Native SaaS Replacement Intelligence — Find the next billion-dollar opportunity in "too expensive" complaints.**

[![CI](https://github.com/YOUR_USERNAME/TooExpensiveRadar/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/TooExpensiveRadar/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## What is this?

Every day, millions of users complain online that their software is **too expensive**, **overkill**, or **bloated**. They want alternatives. Too Expensive Radar listens to these signals and transforms them into **actionable AI-native SaaS replacement opportunities**.

### The Core Insight

> **The biggest alpha in AI startups isn't "what AI can do" — it's identifying which expensive SaaS are legacy artifacts of complex workflows.**

Users constantly signal what they need:
- "HubSpot is too expensive for basic CRM"
- "Jira is overkill for our 5-person team"
- "Zapier pricing sucks for multi-step automations"

**Too Expensive Radar** captures these signals and scores them for opportunity potential.

---

## Features

- **54 Data Sources** — Hacker News, Reddit communities, TechCrunch, AI blogs, startup forums, and more (via RSS)
- **Dual Analysis Engine** — Rule-based (no API key needed) or LLM-powered (Claude/MiniMax/GPT)
- **6-Dimension Scoring** — Pricing Pain, Feature Bloat, SMB Overkill, AI Compression, Feasibility, Workflow Simplicity
- **Opportunity Feed** — Ranked disruption scores with evidence links
- **Background Collection** — Celery + Redis task queue for continuous monitoring
- **Multi-Channel Alerts** — Telegram, Email, DingTalk, Feishu, WeCom, ntfy, Bark, Webhooks
- **Flexible Scheduling** — Always on, morning/evening, office hours, or night owl presets

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/TooExpensiveRadar.git
cd TooExpensiveRadar

# Start everything with one command
docker-compose up
```

Open [http://localhost:8000](http://localhost:8000)

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/TooExpensiveRadar.git
cd TooExpensiveRadar

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[test]"

# Start Redis (required for background tasks)
# macOS: brew install redis && redis-server
# Ubuntu: sudo apt install redis-server

# Start the app
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000)

### Configuration

Copy `config.yaml.example` to `config.yaml` and add your API keys:

```yaml
llm:
  minimax:
    api_key: "your-minimax-api-key"
    base_url: "https://api.minimax.chat/v1"
    model: "MiniMax-M2.7"
```

---

## How It Works

```
Data Collection (RSS feeds from 54 sources)
         ↓
Raw Signal Storage (Layer 1)
         ↓
Complaint Detection (pricing/bloat/SMB signals)
         ↓
Workflow Extraction (CRM, proposal, automation, etc.)
         ↓
LLM Analysis (optional — Claude/MiniMax)
         ↓
Opportunity Scoring (6 dimensions)
         ↓
Ranked Opportunity Feed + Alerts
```

---

## Project Structure

```
TooExpensiveRadar/
├── app/
│   ├── main.py              # FastAPI app + endpoints
│   ├── analyzer.py         # Rule-based + LLM analysis
│   ├── models.py           # SQLModel database schema
│   ├── database.py         # Database connections
│   ├── scheduler.py        # Timeline scheduling
│   ├── llm/                # LLM clients (Claude, OpenAI, MiniMax)
│   ├── scrapers/           # Data source collectors
│   │   └── rss_fetcher.py # RSS/Atom/JSON feed parser
│   ├── notification/        # Multi-channel alerts
│   │   └── senders.py     # Telegram, Email, DingTalk, etc.
│   └── tasks/              # Celery background tasks
├── tests/                  # pytest tests
├── .github/workflows/      # GitHub Actions CI/CD
├── docker-compose.yml      # Docker setup
└── pyproject.toml         # Project metadata
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Dashboard statistics |
| `GET` | `/api/opportunities` | List opportunities (filterable by score/software/category) |
| `POST` | `/api/ingest/text` | Ingest a single complaint |
| `POST` | `/api/ingest/csv` | Batch CSV import |
| `POST` | `/api/ingest/url` | Extract from URL via LLM |
| `GET` | `/api/datasources` | List configured data sources |
| `POST` | `/api/rss/collect` | Trigger RSS collection |
| `GET/POST` | `/api/rss/feeds` | Manage RSS feeds |
| `GET/PUT` | `/api/llm/configs/{provider}` | Configure LLM providers |
| `POST` | `/api/notifications/send` | Send test notification |
| `GET` | `/api/scheduler/status` | Scheduler status |
| `GET` | `/api/tasks` | Background task status |

Full API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Scoring System

| Score | Weight | What It Measures |
|-------|--------|------------------|
| **Pricing Pain** | 30% | How much users complain about cost |
| **AI Compression** | 22% | How much AI can simplify the workflow |
| **Feature Bloat** | 18% | How many unused features exist |
| **SMB Overkill** | 16% | Whether SMBs are tortured by enterprise software |
| **Feasibility** | 14% | How easy the replacement is to build |

---

## Data Sources (54 Feeds)

### Tech News
Hacker News, TechCrunch, The Verge, Ars Technica, Wired, BBC Tech, Engadget

### AI & ML
NVIDIA Blog, AWS ML Blog, Microsoft AI Blog, Google AI Blog, Google DeepMind, OpenAI Blog, Anthropic Blog

### Community (Reddit)
r/SaaS, r/startups, r/entrepreneur, r/smallbusiness, r/webdev, r/indiehackers, r/artificial, r/MachineLearning, r/ChatGPT, r/programming, r/devops, and 20+ more

### More
Product Hunt, Indie Hackers, VentureBeat AI, CoinDesk, The Hacker News, and more.

---

## Contributing

Contributions are welcome! Please read our guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Roadmap

- [ ] PostgreSQL + pgvector for semantic clustering
- [ ] Automated weekly newsletter generation
- [ ] Price gap analysis (existing vs. possible pricing)
- [ ] Multi-tenant support
- [ ] API rate limiting and authentication
- [ ] Deployment to major cloud platforms
