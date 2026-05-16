from __future__ import annotations

import csv
import json
from contextlib import asynccontextmanager, contextmanager
from io import StringIO
from pathlib import Path
from typing import List

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.analyzer import analyze_text
from app.database import engine, get_session, init_db, settings
from app.llm import get_llm
from app.models import (
    AlternativeCandidate,
    AlternativeCandidateRead,
    AsyncTask,
    AsyncTaskRead,
    Complaint,
    DataSource,
    DataSourceConfig,
    DataSourceConfigRead,
    LLMConfig,
    LLMConfigRead,
    LLMProvider,
    Opportunity,
    OpportunityRead,
    RawSignal,
    StatsResponse,
    TaskStatus,
    TextIngestRequest,
    WorkflowGraph,
)
from app.scrapers import get_scraper
from app.scrapers.rss_fetcher import RSSFetcher, parse_multi_account_config, limit_accounts

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_RSS_FEEDS = [
    # Tech News
    {"url": "https://news.ycombinator.com/rss", "name": "Hacker News", "max_age_days": 7},
    {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "max_age_days": 3},
    {"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge", "max_age_days": 3},
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "name": "Ars Technica", "max_age_days": 3},
    {"url": "https://www.wired.com/feed/rss", "name": "Wired", "max_age_days": 3},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "name": "BBC Tech", "max_age_days": 3},
    {"url": "https://www.engadget.com/rss.xml", "name": "Engadget", "max_age_days": 3},
    {"url": "https://feeds.feedburner.com/TechCrunch", "name": "TechCrunch FeedBurner", "max_age_days": 3},

    # AI & ML
    {"url": "https://blogs.nvidia.com/feed/", "name": "NVIDIA Blog", "max_age_days": 7},
    {"url": "https://blogs.vmware.com/feeds/regression", "name": "VMware AI Blog", "max_age_days": 7},
    {"url": "https://aws.amazon.com/blogs/machine-learning/feed/", "name": "AWS ML Blog", "max_age_days": 7},
    {"url": "https://blogs.microsoft.com/ai/feed/", "name": "Microsoft AI Blog", "max_age_days": 5},
    {"url": "https://blog.google/technology/ai/feed/", "name": "Google AI Blog", "max_age_days": 5},
    {"url": "https://deepmind.google/blog/rss.xml", "name": "Google DeepMind", "max_age_days": 7},
    {"url": "https://ai.google/research/rss", "name": "Google Research AI", "max_age_days": 7},
    {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog", "max_age_days": 5},
    {"url": "https://anthropic.com/blog/rss.xml", "name": "Anthropic Blog", "max_age_days": 5},

    # Startups & Funding
    {"url": "https://www.producthunt.com/feed", "name": "Product Hunt", "max_age_days": 3},
    {"url": "https://feeds.feedburner.com/SouthChinaMorningPost", "name": "SCMP", "max_age_days": 7},
    {"url": "https://www.ft.com/?format=rss", "name": "Financial Times Tech", "max_age_days": 3},
    {"url": "https://www.theinformation.com/feed", "name": "The Information", "max_age_days": 3},
    {"url": "https://www.wired.co.uk/rss", "name": "Wired UK", "max_age_days": 3},
    {"url": "https://siliconangle.com/feed/", "name": "SiliconANGLE", "max_age_days": 3},
    {"url": "https://www.techinasia.com/feed", "name": "Tech in Asia", "max_age_days": 3},

    # Dev & OSS
    {"url": "https://github.com/blog.atom", "name": "GitHub Blog", "max_age_days": 7},
    {"url": "https://blog.cloudflare.com/feed/", "name": "Cloudflare Blog", "max_age_days": 5},
    {"url": "https://about.gitlab.com/feed/", "name": "GitLab Blog", "max_age_days": 7},
    {"url": "https://stackify.com/feed/", "name": "Stackify", "max_age_days": 7},
    {"url": "https://devops.com/feed/", "name": "DevOps.com", "max_age_days": 7},
    {"url": "https://www.infoq.com/feed/", "name": "InfoQ", "max_age_days": 5},

    # AI News Sites
    {"url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat AI", "max_age_days": 3},
    {"url": "https://www.artificialintelligence-news.com/feed/", "name": "AI News", "max_age_days": 3},
    {"url": "https://www.aitimejournal.com/feed", "name": "AI Time Journal", "max_age_days": 5},
    {"url": "https://blog.cloudsight.ai/feed/", "name": "CloudSight AI", "max_age_days": 7},
    {"url": "https://blogs.nvidia.com/feed/", "name": "NVIDIA AI Blog", "max_age_days": 5},

    # Crypto & Web3
    {"url": "https://coindesk.com/feed", "name": "CoinDesk", "max_age_days": 3},
    {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph", "max_age_days": 3},

    # Security
    {"url": "https://feeds.feedburner.com/TheHackersNews", "name": "The Hacker News", "max_age_days": 3},
    {"url": "https://www.darkreading.com/rss.xml", "name": "Dark Reading", "max_age_days": 5},
    {"url": "https://www.theregister.com/security/headlines.atom", "name": "The Register Security", "max_age_days": 5},

    # Community - Reddit (SaaS/Pricing complaints)
    {"url": "https://www.reddit.com/r/SaaS/hot.rss", "name": "r/SaaS", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/startups/hot.rss", "name": "r/startups", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/entrepreneur/hot.rss", "name": "r/entrepreneur", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/smallbusiness/hot.rss", "name": "r/smallbusiness", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/webdev/hot.rss", "name": "r/webdev", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/webdesigner/hot.rss", "name": "r/webdesigner", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/Frontend/hot.rss", "name": "r/Frontend", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/SideProject/hot.rss", "name": "r/SideProject", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/indiehackers/hot.rss", "name": "r/indiehackers", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/growthhacking/hot.rss", "name": "r/growthhacking", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/marketing/hot.rss", "name": "r/marketing", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/SEO/hot.rss", "name": "r/SEO", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/crm/hot.rss", "name": "r/crm", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/projectmanagement/hot.rss", "name": "r/projectmanagement", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/productivity/hot.rss", "name": "r/productivity", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/EntrepreneurRideAlong/hot.rss", "name": "r/EntrepreneurRideAlong", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/founder/hot.rss", "name": "r/founder", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/legaladvice/hot.rss", "name": "r/legaladvice", "max_age_days": 14},

    # Community - Reddit (Tech/AI discussions)
    {"url": "https://www.reddit.com/r/artificial/hot.rss", "name": "r/artificial", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/MachineLearning/hot.rss", "name": "r/MachineLearning", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/deeplearning/hot.rss", "name": "r/deeplearning", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/ChatGPT/hot.rss", "name": "r/ChatGPT", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/LocalLLaMA/hot.rss", "name": "r/LocalLLaMA", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/LLMs/hot.rss", "name": "r/LLMs", "max_age_days": 5},
    {"url": "https://www.reddit.com/r//programming/hot.rss", "name": "r/programming", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/cscareerquestions/hot.rss", "name": "r/cscareerquestions", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/sysadmin/hot.rss", "name": "r/sysadmin", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/devops/hot.rss", "name": "r/devops", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/aws/hot.rss", "name": "r/aws", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/cloud/hot.rss", "name": "r/cloud", "max_age_days": 7},

    # Community - Reddit (Business/Tools complaints)
    {"url": "https://www.reddit.com/r/SaaShosting/hot.rss", "name": "r/SaaShosting", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/salesforce/hot.rss", "name": "r/salesforce", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/jira/hot.rss", "name": "r/jira", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/zapier/hot.rss", "name": "r/zapier", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/notion/hot.rss", "name": "r/notion", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/Asana/hot.rss", "name": "r/Asana", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/trello/hot.rss", "name": "r/trello", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/Pipedrive/hot.rss", "name": "r/Pipedrive", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/zendesk/hot.rss", "name": "r/zendesk", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/hubspot/hot.rss", "name": "r/hubspot", "max_age_days": 7},

    # Community - Other forums
    {"url": "https://www.producthunt.com/feed", "name": "Product Hunt", "max_age_days": 3},
    {"url": "https://news.ycombinator.com/rss", "name": "Hacker News", "max_age_days": 7},
    {"url": "https://www.indiehackers.com/feed", "name": "Indie Hackers", "max_age_days": 5},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        from app.models import DataSourceConfig, DataSource
        config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.RSS.value)).first()
        if not config:
            config = DataSourceConfig(source=DataSource.RSS.value, enabled=True, config=json.dumps({"feeds": DEFAULT_RSS_FEEDS}))
            session.add(config)
            session.commit()
    yield


app = FastAPI(title="Too Expensive Radar", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/ingest/text", response_model=OpportunityRead)
def ingest_text(req: TextIngestRequest, session: Session = Depends(get_session)) -> Opportunity:
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    return _persist_analysis(session, req)


@app.post("/api/ingest/csv")
async def ingest_csv(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict:
    content = (await file.read()).decode("utf-8-sig")
    rows = csv.DictReader(StringIO(content))
    created = []
    for row in rows:
        text = (row.get("content") or "").strip()
        if not text:
            continue
        req = TextIngestRequest(
            content=text,
            platform=row.get("platform") or "csv",
            source_url=row.get("source_url") or "",
            author=row.get("author") or "",
        )
        created.append(_persist_analysis(session, req).id)
    return {"created": len(created), "ids": created}


@app.post("/api/ingest/url")
async def ingest_url(url: str, session: Session = Depends(get_session)) -> dict:
    from app.database import get_llm_config_for_provider
    import httpx
    import json

    minimax_config = get_llm_config_for_provider("minimax")
    if not minimax_config or not minimax_config.get("api_key"):
        raise HTTPException(status_code=400, detail="LLM not configured")

    llm = get_llm("openai", minimax_config["api_key"], minimax_config.get("model", "MiniMax-Text-01"), minimax_config.get("base_url", ""))

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url)
            text = res.text[:5000]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    prompt = f"""Extract any software pricing complaints, "too expensive" mentions, or requests for alternatives from this content. Return a JSON array of objects with fields: content (the complaint text), software (the software mentioned), platform (source platform).

Content:
{text}

Return ONLY valid JSON array."""

    try:
        response = await llm.complete(prompt)
        data = json.loads(response.content)
        if not isinstance(data, list):
            data = [data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {e}")

    created = []
    for item in data:
        content = item.get("content", "")
        if content:
            req = TextIngestRequest(
                content=content,
                platform=item.get("platform", "url"),
                source_url=url,
                author="",
            )
            created.append(_persist_analysis(session, req).id)

    return {"created": len(created), "ids": created}


@app.get("/api/opportunities", response_model=List[OpportunityRead])
def list_opportunities(
    min_score: float = 0,
    software: str | None = None,
    category: str | None = None,
    session: Session = Depends(get_session),
) -> List[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.disruption_score >= min_score)
    if software:
        stmt = stmt.where(Opportunity.software == software)
    if category:
        stmt = stmt.where(Opportunity.category == category)
    stmt = stmt.order_by(Opportunity.disruption_score.desc(), Opportunity.created_at.desc())
    return list(session.exec(stmt).all())


@app.get("/api/opportunities/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: int, session: Session = Depends(get_session)) -> Opportunity:
    opp = session.get(Opportunity, opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return opp


@app.get("/api/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    opps = list(session.exec(select(Opportunity)).all())
    complaints = list(session.exec(select(Complaint)).all())
    ds_configs = list(session.exec(select(DataSourceConfig)).all())
    llm_configs = list(session.exec(select(LLMConfig).where(LLMConfig.enabled == True)).all())

    if not opps:
        return StatsResponse(
            total=0, avg_score=0, top_software=[], top_categories=[],
            total_complaints=len(complaints), total_datasources=len(ds_configs), llm_enabled=len(llm_configs) > 0
        )

    avg_score = round(sum(o.disruption_score for o in opps) / len(opps), 2)
    software_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for o in opps:
        software_counts[o.software] = software_counts.get(o.software, 0) + 1
        category_counts[o.category] = category_counts.get(o.category, 0) + 1

    return StatsResponse(
        total=len(opps),
        avg_score=avg_score,
        top_software=sorted(software_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        top_categories=sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        total_complaints=len(complaints),
        total_datasources=len([d for d in ds_configs if d.enabled]),
        llm_enabled=len(llm_configs) > 0,
    )


SEED_COMMENTS = [
    "HubSpot is too expensive for a small business. We only need basic CRM automation, lead tracking and follow-up reminders. Any cheaper alternative?",
    "PandaDoc feels overpriced and overkill for simple proposals, SOWs and e-signature. I just need proposal to PDF to signature.",
    "Zapier pricing sucks when multi-step automations run a lot of tasks. We need a cheaper alternative for basic workflow automation.",
    "Jira is too complicated for our small team. We just need issue tracking and status updates without admin setup nightmare.",
    "Salesforce is powerful but overkill and expensive for our startup. We mostly use lead notes, pipeline stages and email follow-ups.",
    "DocuSign is expensive for the amount of simple signature workflows we run. Looking for an alternative to DocuSign for SMB docs.",
    "Zendesk is getting pricey. We only need support tickets, AI draft replies and routing, not enterprise helpdesk complexity.",
    "Airtable becomes expensive and hard to configure once our internal workflow grows. We need simple approval and reporting automation.",
    "HubSpot's marketing automation is bloated for our startup. We only need email sequences and landing pages, not full Marketing Hub.",
    "Pipedrive is overpriced for basic CRM. Our sales team just needs deal tracking and follow-up reminders, nothing fancy.",
    "Asana is overkill for our 5-person startup. We just need task lists and due dates without the complexity.",
    "Intercom is too expensive for small business support. We only need chat and simple canned responses.",
    "Monday.com gets pricey as teams grow. We need only project boards and timelines for a small team.",
    "ClickUp has too many features we never use. All we need is tasks and subtasks for our agency.",
    "Confluence is over-engineered for our internal wiki needs. We just need simple docs and notes.",
]


@app.post("/api/seed")
def seed(session: Session = Depends(get_session)) -> dict:
    created = []
    for text in SEED_COMMENTS:
        created.append(_persist_analysis(session, TextIngestRequest(content=text, platform="seed")).id)
    return {"created": len(created), "ids": created}


@app.get("/api/datasources", response_model=List[DataSourceConfigRead])
def list_datasources(session: Session = Depends(get_session)) -> List[DataSourceConfig]:
    configs = list(session.exec(select(DataSourceConfig)).all())
    if not configs:
        for source in [s.value for s in DataSource if s != DataSource.MANUAL]:
            config = DataSourceConfig(source=source, enabled=False)
            session.add(config)
        session.commit()
        configs = list(session.exec(select(DataSourceConfig)).all())
    return configs


@app.put("/api/datasources/{source}")
def update_datasource(source: str, enabled: bool, config: str, session: Session = Depends(get_session)) -> dict:
    ds_config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == source)).first()
    if not ds_config:
        ds_config = DataSourceConfig(source=source, enabled=enabled, config=config)
    else:
        ds_config.enabled = enabled
        ds_config.config = config
    session.add(ds_config)
    session.commit()
    session.refresh(ds_config)
    return {"source": ds_config.source, "enabled": ds_config.enabled}


@app.post("/api/datasources/{source}/collect")
def collect_datasource(source: str, background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    ds_config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == source)).first()
    if not ds_config:
        raise HTTPException(status_code=404, detail="datasource not found")
    if not ds_config.enabled:
        raise HTTPException(status_code=400, detail="datasource not enabled")

    task = AsyncTask(task_type=f"collect_{source}", status=TaskStatus.PENDING)
    session.add(task)
    session.commit()
    session.refresh(task)

    background_tasks.add_task(_run_collect_async, task.task_id, source, ds_config.config)

    return {"task_id": task.task_id, "status": task.status}


async def _run_collect_async(task_id: str, source: str, config: str):
    import asyncio
    from app.scrapers import get_scraper
    from app.models import RawSignal, DataSourceConfig
    from datetime import datetime, timezone

    try:
        scraper = get_scraper(source, json.loads(config) if config else {})
        items = await scraper.scrape()

        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.output_data = json.dumps({"collected": len(items)})
                session.add(task)

            ds_config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == source)).first()
            if ds_config:
                ds_config.last_collected_at = datetime.now(timezone.utc)
                ds_config.total_collected += len(items)
                ds_config.success_count += 1
                session.add(ds_config)

            session.commit()

            for item in items:
                raw = RawSignal(
                    platform=item.platform,
                    source_url=item.source_url,
                    author=item.author,
                    author_metadata=json.dumps(item.author_metadata),
                    content=item.content,
                    raw_content=item.raw_content,
                )
                session.add(raw)
            session.commit()

    except Exception as e:
        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                session.add(task)

            ds_config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == source)).first()
            if ds_config:
                ds_config.error_count += 1
                session.add(ds_config)
            session.commit()


@app.get("/api/llm/configs", response_model=List[LLMConfigRead])
def list_llm_configs(session: Session = Depends(get_session)) -> List[LLMConfig]:
    configs = list(session.exec(select(LLMConfig)).all())
    if not configs:
        for provider in [LLMProvider.CLAUDE.value, LLMProvider.OPENAI.value]:
            config = LLMConfig(provider=provider, enabled=False)
            session.add(config)
        session.commit()
        configs = list(session.exec(select(LLMConfig)).all())
    return configs


@app.post("/api/rss/feeds")
def add_rss_feed(feed_url: str, feed_name: str = "", max_age_days: int = 30, session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource
    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.RSS.value)).first()
    if not config:
        config = DataSourceConfig(source=DataSource.RSS.value, enabled=True, config="{}")
        session.add(config)

    import json
    feeds = json.loads(config.config or "{}").get("feeds", [])
    feeds.append({"url": feed_url, "name": feed_name, "max_age_days": max_age_days})
    config.config = json.dumps({"feeds": feeds})
    session.commit()
    return {"added": feed_url, "total_feeds": len(feeds)}


@app.get("/api/rss/feeds")
def list_rss_feeds(session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource
    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.RSS.value)).first()
    if not config:
        return {"feeds": []}
    import json
    feeds = json.loads(config.config or "{}").get("feeds", [])
    return {"feeds": feeds}


@app.delete("/api/rss/feeds/{feed_url}")
def delete_rss_feed(feed_url: str, session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource
    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.RSS.value)).first()
    if config:
        import json
        feeds = json.loads(config.config or "{}").get("feeds", [])
        feeds = [f for f in feeds if f.get("url") != feed_url]
        config.config = json.dumps({"feeds": feeds})
        session.commit()
    return {"removed": feed_url}


@app.post("/api/rss/collect")
async def collect_rss(background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource, AsyncTask, TaskStatus
    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.RSS.value)).first()
    if not config:
        raise HTTPException(status_code=404, detail="RSS not configured")

    import json
    import uuid
    feeds = json.loads(config.config or "{}").get("feeds", [])
    if not feeds:
        raise HTTPException(status_code=400, detail="No feeds configured")

    task_id = str(uuid.uuid4())
    task = AsyncTask(task_id=task_id, task_type="collect_rss", status=TaskStatus.PENDING)
    session.add(task)
    session.commit()
    session.refresh(task)

    background_tasks.add_task(_run_rss_collect_async, task.task_id, feeds)

    return {"task_id": task.task_id, "status": task.status}


async def _run_rss_collect_async(task_id: str, feeds: list):
    import asyncio
    import logging
    from app.models import RawSignal, AsyncTask, TaskStatus, Complaint, WorkflowGraph, Opportunity, LLMConfig
    from app.analyzer import analyze_text
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    try:
        fetcher = RSSFetcher(timeout=30.0, max_retries=3)
        rss_data = await fetcher.fetch_all(feeds, request_interval=1.0)
        logger.info(f"RSS collected {len(rss_data.items)} items")

        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.RUNNING
                task.progress = 10
                session.add(task)
                session.commit()

            raw_data = []
            for item in rss_data.items:
                raw = RawSignal(
                    platform=f"rss:{item.feed_name}",
                    source_url=item.url,
                    author=item.author,
                    content=item.content_snippet or item.title,
                )
                session.add(raw)
                session.flush()
                raw_data.append({"id": raw.id, "content": raw.content, "platform": raw.platform})
            session.commit()

        logger.info(f"Saved {len(raw_data)} raw signals, starting analysis")

        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.progress = 40
                session.add(task)
                session.commit()

            llm_config = session.exec(select(LLMConfig).where(LLMConfig.enabled == True)).first()
            llm = None
            if llm_config and llm_config.api_key:
                from app.llm import get_llm
                llm = get_llm(llm_config.provider, llm_config.api_key, llm_config.model, llm_config.base_url)
                logger.info(f"LLM configured: {llm_config.provider}/{llm_config.model}")

        opp_count = 0
        total = len(raw_data)
        logger.info(f"Starting analysis loop for {total} items")

        for i, raw in enumerate(raw_data):
            try:
                content = raw["content"] or ""
                if len(content) < 20:
                    continue

                result = await analyze_text(content, llm)
                logger.info(f"[{i+1}/{total}] {raw['platform']}: {content[:40]}... -> {result.software} ({result.disruption_score})")

                with Session(engine) as session:
                    complaint = Complaint(
                        raw_signal_id=raw["id"],
                        complaint_type="rss",
                        pricing_signal=result.pricing_signal,
                        bloat_signal=result.bloat_signal,
                        smb_signal=result.smb_signal,
                        emotion_score=result.emotion_score,
                        software_name=result.software,
                        workflow_keywords=",".join(result.workflow_steps),
                        detected_keywords=",".join([p for p in [result.pricing_signal and "pricing", result.bloat_signal and "bloat", result.smb_signal and "smb"] if p]),
                        sentiment_polarity=result.sentiment_polarity,
                    )
                    session.add(complaint)
                    session.flush()

                    workflow = WorkflowGraph(
                        complaint_id=complaint.id,
                        workflow_name=result.workflow_name,
                        workflow_steps=",".join(result.workflow_steps),
                        manual_handoffs=",".join(result.manual_handoffs),
                        software_dependencies=",".join(result.software_dependencies),
                        workflow_complexity=result.workflow_complexity,
                    )
                    session.add(workflow)
                    session.flush()

                    opp = Opportunity(
                        complaint_id=complaint.id,
                        workflow_graph_id=workflow.id,
                        software=result.software,
                        category=result.category,
                        complaint_summary=result.complaint_summary,
                        actual_workflow=result.actual_workflow,
                        ai_native_replacement=result.ai_native_replacement,
                        existing_price=result.existing_price,
                        possible_price=result.possible_price,
                        pricing_pain_score=result.pricing_pain_score,
                        feature_bloat_score=result.feature_bloat_score,
                        smb_overkill_score=result.smb_overkill_score,
                        ai_compression_score=result.ai_compression_score,
                        workflow_simplicity_score=result.workflow_simplicity_score,
                        replacement_feasibility_score=result.replacement_feasibility_score,
                        disruption_score=result.disruption_score,
                        evidence=result.evidence,
                    )
                    session.add(opp)
                    session.commit()
                    opp_count += 1

                    if (i + 1) % 20 == 0:
                        task_obj = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
                        if task_obj:
                            task_obj.progress = 40 + int(50 * (i + 1) / total)
                            session.add(task_obj)
                            session.commit()
                        logger.info(f"Progress: {40 + int(50 * (i + 1) / total)}% ({i+1}/{total})")

            except Exception as e:
                logger.error(f"Error processing item {i}: {type(e).__name__}: {e}")

        logger.info(f"Analysis complete: {opp_count} opportunities created")

        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.output_data = json.dumps({"collected": total, "analyzed": opp_count})
                session.add(task)
                session.commit()

    except Exception as e:
        import traceback
        traceback.print_exc()
        with Session(engine) as session:
            task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)[:500]
                session.add(task)
            session.commit()


@app.get("/api/notifications/channels")
def list_notification_channels() -> dict:
    return {
        "channels": [
            {"id": "telegram", "name": "Telegram", "fields": ["bot_token", "chat_id"]},
            {"id": "email", "name": "Email", "fields": ["smtp_host", "smtp_port", "username", "password"]},
            {"id": "dingtalk", "name": "DingTalk", "fields": ["webhook_url"]},
            {"id": "feishu", "name": "Feishu", "fields": ["webhook_url"]},
            {"id": "wecom", "name": "WeCom", "fields": ["webhook_url"]},
            {"id": "ntfy", "name": "ntfy", "fields": ["topic", "server_url", "auth_token"]},
            {"id": "bark", "name": "Bark", "fields": ["push_token", "server_url"]},
            {"id": "webhook", "name": "Generic Webhook", "fields": ["webhook_url", "headers"]},
        ]
    }


@app.post("/api/notifications/send")
def send_notification(
    channel: str,
    content: str,
    title: str = "Too Expensive Alert",
    config: str = "",
    session: Session = Depends(get_session),
) -> dict:
    from app.notification.senders import create_notification_sender, markdown_to_telegram, markdown_to_dingtalk

    import json
    channel_config = json.loads(config) if config else {}

    sender = create_notification_sender(channel, channel_config)
    if not sender:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

    formatted_content = content
    if channel == "telegram":
        formatted_content = markdown_to_telegram(content)
    elif channel in ["dingtalk", "wecom"]:
        formatted_content = markdown_to_dingtalk(content)

    try:
        if channel == "email":
            result = sender.send(to_email=channel_config.get("to_email", ""), subject=title, html_content=f"<pre>{formatted_content}</pre>")
        else:
            result = sender.send(formatted_content)

        return {"success": result.success, "channel": channel, "message": result.message}
    except Exception as e:
        return {"success": False, "channel": channel, "message": str(e)}


@app.get("/api/scheduler/status")
def scheduler_status() -> dict:
    from app.scheduler import Scheduler
    scheduler = Scheduler()
    return {
        "active": scheduler.is_active(),
        "period": scheduler.get_active_period_name(),
        "should_crawl": scheduler.should_crawl(),
        "should_analyze": scheduler.should_analyze(),
        "should_push": scheduler.should_push(),
        "next_runs": [t.isoformat() for t in scheduler.get_next_run_times(count=3)],
    }


@app.post("/api/scheduler/config")
def configure_scheduler(
    preset: str = "always_on",
    crawl: bool = True,
    analyze: bool = True,
    push: bool = True,
) -> dict:
    from app.scheduler import Scheduler
    scheduler = Scheduler({"preset": preset, "crawl": crawl, "analyze": analyze, "push": push})
    return {
        "preset": preset,
        "active": scheduler.is_active(),
        "period": scheduler.get_active_period_name(),
        "actions": {"crawl": crawl, "analyze": analyze, "push": push},
    }


@app.get("/api/ai/filter/interests")
def get_ai_filter_interests(session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource
    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.AI_FILTER.value)).first()
    if not config:
        return {"interests": "", "hash": ""}
    import json
    data = json.loads(config.config or "{}")
    return {"interests": data.get("interests", ""), "hash": data.get("hash", "")}


@app.put("/api/ai/filter/interests")
def update_ai_filter_interests(interests: str, session: Session = Depends(get_session)) -> dict:
    from app.models import DataSourceConfig, DataSource
    from app.ai.filter import AIFilter
    import hashlib

    config = session.exec(select(DataSourceConfig).where(DataSourceConfig.source == DataSource.AI_FILTER.value)).first()
    if not config:
        config = DataSourceConfig(source=DataSource.AI_FILTER.value, enabled=True, config="{}")
        session.add(config)

    ai_filter = AIFilter()
    ai_filter.extract_tags(interests)

    import json
    config.config = json.dumps({"interests": interests, "hash": ai_filter.get_interest_hash()})
    session.commit()

    return {"updated": True, "hash": ai_filter.get_interest_hash(), "tags_count": len(ai_filter.get_cached_tags())}


@app.post("/api/batch/analyze")
async def batch_analyze(
    items: List[dict],
    use_llm: bool = False,
    llm_provider: str = "openai",
    session: Session = Depends(get_session),
) -> dict:
    from app.ai.batch import BatchProcessor, default_json_parser

    llm_config = session.exec(select(LLMConfig).where(LLMConfig.provider == llm_provider, LLMConfig.enabled == True)).first()
    if use_llm and not llm_config:
        raise HTTPException(status_code=400, detail=f"LLM provider {llm_provider} not enabled")

    llm = None
    if use_llm and llm_config:
        llm = get_llm(llm_config.provider, llm_config.api_key, llm_config.model, llm_config.base_url)

    processor = BatchProcessor(max_concurrent=5, batch_size=20)

    def prompt_func(item):
        return f"Analyze this complaint and return JSON with software_name, category, and disruption_score:\n\n{item.get('content', '')}"

    def parser(content):
        try:
            import json
            return json.loads(content)
        except:
            return {"error": "parse_failed", "content": content[:100]}

    results = await processor.process_batch(items, llm, prompt_func, parser)

    return {
        "total": results.total,
        "successful": results.successful,
        "failed": results.failed,
        "errors": results.errors[:5],
    }


@app.put("/api/llm/configs/{provider}")
def update_llm_config(
    provider: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    enabled: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    config = session.exec(select(LLMConfig).where(LLMConfig.provider == provider)).first()
    if not config:
        config = LLMConfig(provider=provider, api_key=api_key, model=model, base_url=base_url, enabled=enabled)
    else:
        if api_key:
            config.api_key = api_key
        if model:
            config.model = model
        if base_url:
            config.base_url = base_url
        config.enabled = enabled
    session.add(config)
    session.commit()
    session.refresh(config)
    return {"provider": config.provider, "enabled": config.enabled, "model": config.model}


@app.get("/api/tasks/{task_id}", response_model=AsyncTaskRead)
def get_task(task_id: str, session: Session = Depends(get_session)) -> AsyncTask:
    task = session.exec(select(AsyncTask).where(AsyncTask.task_id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.get("/api/tasks", response_model=List[AsyncTaskRead])
def list_tasks(
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 20,
    session: Session = Depends(get_session),
) -> List[AsyncTask]:
    stmt = select(AsyncTask).order_by(AsyncTask.created_at.desc())
    if status:
        stmt = stmt.where(AsyncTask.status == status)
    if task_type:
        stmt = stmt.where(AsyncTask.task_type == task_type)
    stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())


def _persist_analysis(session: Session, req: TextIngestRequest) -> Opportunity:
    raw = RawSignal(
        platform=req.platform,
        source_url=req.source_url,
        author=req.author,
        content=req.content,
    )
    session.add(raw)
    session.commit()
    session.refresh(raw)

    llm = None
    llm_config = session.exec(select(LLMConfig).where(LLMConfig.enabled == True)).first()
    if llm_config and llm_config.api_key:
        llm = get_llm(llm_config.provider, llm_config.api_key, llm_config.model, llm_config.base_url)

    import asyncio
    result = asyncio.run(analyze_text(req.content, llm))

    complaint = Complaint(
        raw_signal_id=raw.id,
        complaint_type="pricing" if result.pricing_signal else "bloat",
        pricing_signal=result.pricing_signal,
        bloat_signal=result.bloat_signal,
        smb_signal=result.smb_signal,
        emotion_score=result.emotion_score,
        software_name=result.software,
        workflow_keywords=",".join(result.workflow_steps),
        detected_keywords=",".join([p for p in [result.pricing_signal and "pricing", result.bloat_signal and "bloat", result.smb_signal and "smb"] if p]),
        sentiment_polarity=result.sentiment_polarity,
    )
    session.add(complaint)
    session.commit()
    session.refresh(complaint)

    workflow = WorkflowGraph(
        complaint_id=complaint.id,
        workflow_name=result.workflow_name,
        workflow_steps=",".join(result.workflow_steps),
        manual_handoffs=",".join(result.manual_handoffs),
        software_dependencies=",".join(result.software_dependencies),
        workflow_complexity=result.workflow_complexity,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    opp = Opportunity(
        complaint_id=complaint.id,
        workflow_graph_id=workflow.id,
        software=result.software,
        category=result.category,
        complaint_summary=result.complaint_summary,
        actual_workflow=result.actual_workflow,
        ai_native_replacement=result.ai_native_replacement,
        existing_price=result.existing_price,
        possible_price=result.possible_price,
        pricing_pain_score=result.pricing_pain_score,
        feature_bloat_score=result.feature_bloat_score,
        smb_overkill_score=result.smb_overkill_score,
        ai_compression_score=result.ai_compression_score,
        workflow_simplicity_score=result.workflow_simplicity_score,
        replacement_feasibility_score=result.replacement_feasibility_score,
        disruption_score=result.disruption_score,
        evidence=result.evidence,
    )
    session.add(opp)
    session.commit()
    session.refresh(opp)

    await _discover_alternatives_for_opportunity(session, opp, req.content)

    return opp


async def _discover_alternatives_for_opportunity(
    session: Session, opp: Opportunity, content: str
) -> list[AlternativeCandidate]:
    from app.alternatives.engine import AlternativeDiscoveryEngine

    llm = None
    llm_config = session.exec(select(LLMConfig).where(LLMConfig.enabled == True)).first()
    if llm_config and llm_config.api_key:
        llm = get_llm(llm_config.provider, llm_config.api_key, llm_config.model, llm_config.base_url)

    engine = AlternativeDiscoveryEngine(llm=llm)
    candidates = await engine.discover(content, opp.software, force_search=False)

    stored = []
    for c in candidates:
        alt = AlternativeCandidate(
            complaint_id=opp.complaint_id,
            original_software=c.original_software,
            alternative_name=c.alternative_name,
            pricing_tier=c.pricing_tier,
            affiliate_support=c.affiliate_support,
            affiliate_url=c.affiliate_url,
            price_advantage=c.price_advantage,
            verification_source=c.verification_source,
            verification_details=c.verification_details,
            disruption_score_boost=c.disruption_score_boost,
        )
        session.add(alt)
        stored.append(alt)

    session.commit()
    return stored


@app.post("/api/alternatives/discover")
def discover_alternatives(
    text: str,
    software: str,
    force_search: bool = False,
    session: Session = Depends(get_session),
):
    import asyncio
    from app.alternatives.engine import AlternativeDiscoveryEngine

    llm = None
    llm_config = session.exec(select(LLMConfig).where(LLMConfig.enabled == True)).first()
    if llm_config and llm_config.api_key:
        llm = get_llm(llm_config.provider, llm_config.api_key, llm_config.model, llm_config.base_url)

    engine = AlternativeDiscoveryEngine(llm=llm)
    candidates = asyncio.run(engine.discover(text, software, force_search=force_search))

    return {
        "original_software": software,
        "original_complaint": text,
        "alternatives": [
            {
                "name": c.alternative_name,
                "pricing_tier": c.pricing_tier,
                "affiliate_support": c.affiliate_support,
                "affiliate_url": c.affiliate_url,
                "price_advantage": c.price_advantage,
                "verification_source": c.verification_source,
                "disruption_score_boost": c.disruption_score_boost,
            }
            for c in candidates
        ],
        "total_found": len(candidates),
        "affiliate_confirmed": sum(1 for c in candidates if c.affiliate_support == "confirmed"),
        "affiliate_likely": sum(1 for c in candidates if c.affiliate_support == "likely"),
    }


@app.get("/api/alternatives/known")
def list_known_alternatives(session: Session = Depends(get_session)):
    from app.alternatives.db import get_all_affiliate_saas

    return {
        "saas": get_all_affiliate_saas(),
        "total": len(get_all_affiliate_saas()),
    }


@app.get("/api/alternatives/db-stats")
def alternative_db_stats():
    from app.alternatives.db import get_db_stats

    return get_db_stats()


@app.post("/api/alternatives/verify/{saas_name}")
async def verify_saas_affiliate(saas_name: str, session: Session = Depends(get_session)):
    from app.alternatives.search import search_multi
    from app.alternatives.db import lookup_alternative

    db_entry = lookup_alternative(saas_name)
    if db_entry:
        return {
            "name": saas_name,
            "in_database": True,
            "affiliate_support": "confirmed" if db_entry.get("affiliate_support") else "undetermined",
            "pricing_tier": db_entry.get("pricing_tier", "unknown"),
            "affiliate_url": db_entry.get("affiliate_url", ""),
            "verification_source": "prebuilt_db",
        }

    result = await search_multi(saas_name)
    return {
        "name": saas_name,
        "in_database": False,
        "affiliate_support": result.get("affiliate_support", "undetermined"),
        "pricing_tier": result.get("pricing_tier", "unknown"),
        "source_urls": result.get("source_urls", []),
        "verification_source": "web_search",
        "snippets": result.get("snippets", [])[:2],
    }


@app.get("/api/opportunities/{opp_id}/alternatives")
def get_opportunity_alternatives(opp_id: int, session: Session = Depends(get_session)):
    alts = session.exec(
        select(AlternativeCandidate).where(AlternativeCandidate.complaint_id == opp_id)
    ).all()
    return list(alts)