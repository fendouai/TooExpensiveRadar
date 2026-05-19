from __future__ import annotations

import csv
import httpx
import json
from contextlib import asynccontextmanager, contextmanager
from io import StringIO
from pathlib import Path
from typing import List

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.analyzer import analyze_text
from app.database import engine, get_session, init_db, settings
from commercial.payments import CheckoutRequest, create_checkout_session, public_products
from commercial.reports import build_report_preview
from commercial.pdf_generator import get_pdf_bytes
from commercial.publishers import GumroadPublisher, LemonsqueezyPublisher
from pydantic import BaseModel
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
COMMERCIAL_DIR = BASE_DIR.parent / "commercial"

DEFAULT_RSS_FEEDS = [
    # === TECH NEWS (12 feeds) ===
    {"url": "https://news.ycombinator.com/rss", "name": "Hacker News", "max_age_days": 3},
    {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "max_age_days": 2},
    {"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge", "max_age_days": 2},
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "name": "Ars Technica", "max_age_days": 3},
    {"url": "https://www.wired.com/feed/rss", "name": "Wired", "max_age_days": 3},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "name": "BBC Tech", "max_age_days": 3},
    {"url": "https://www.engadget.com/rss.xml", "name": "Engadget", "max_age_days": 3},
    {"url": "https://www.businessinsider.com/rss", "name": "Business Insider Tech", "max_age_days": 2},
    {"url": "https://feeds.feedburner.com/TechCrunch", "name": "TechCrunch FeedBurner", "max_age_days": 3},
    {"url": "https://www.siliconvalley.com/rss", "name": "Silicon Valley", "max_age_days": 3},
    {"url": "https://www.theinformation.com/feed", "name": "The Information", "max_age_days": 2},

    # === AI & ML (10 feeds) ===
    {"url": "https://blogs.nvidia.com/feed/", "name": "NVIDIA Blog", "max_age_days": 5},
    {"url": "https://aws.amazon.com/blogs/machine-learning/feed/", "name": "AWS ML Blog", "max_age_days": 5},
    {"url": "https://blogs.microsoft.com/ai/feed/", "name": "Microsoft AI Blog", "max_age_days": 3},
    {"url": "https://blog.google/technology/ai/feed/", "name": "Google AI Blog", "max_age_days": 3},
    {"url": "https://deepmind.google/blog/rss.xml", "name": "Google DeepMind", "max_age_days": 5},
    {"url": "https://ai.google/research/rss", "name": "Google Research AI", "max_age_days": 5},
    {"url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog", "max_age_days": 3},
    {"url": "https://anthropic.com/blog/rss.xml", "name": "Anthropic Blog", "max_age_days": 3},
    {"url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat AI", "max_age_days": 2},
    {"url": "https://www.artificialintelligence-news.com/feed/", "name": "AI News", "max_age_days": 2},

    # === DEV & OSS COMMUNITY (15 feeds) ===
    {"url": "https://lobste.rs/rss", "name": "Lobsters", "max_age_days": 3},
    {"url": "https://github.com/blog.atom", "name": "GitHub Blog", "max_age_days": 5},
    {"url": "https://about.gitlab.com/feed/", "name": "GitLab Blog", "max_age_days": 5},
    {"url": "https://blog.cloudflare.com/feed/", "name": "Cloudflare Blog", "max_age_days": 5},
    {"url": "https://www.infoq.com/feed/", "name": "InfoQ", "max_age_days": 3},
    {"url": "https://dev.to/feed", "name": "DEV.to", "max_age_days": 2},
    {"url": "https://hashnode.com/feed", "name": "Hashnode", "max_age_days": 3},
    {"url": "https://www.indiehackers.com/feed", "name": "Indie Hackers", "max_age_days": 3},
    {"url": "https://www.producthunt.com/feed", "name": "Product Hunt", "max_age_days": 2},
    {"url": "https://devops.com/feed/", "name": "DevOps.com", "max_age_days": 5},
    {"url": "https://stackoverflow.com/feeds", "name": "Stack Overflow", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/programming/.rss", "name": "r/programming", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/typescript/.rss", "name": "r/typescript", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/javascript/.rss", "name": "r/javascript", "max_age_days": 3},

    # === REDDIT: SaaS & BUSINESS COMPLAINTS (20 feeds) ===
    {"url": "https://www.reddit.com/r/SaaS/.rss", "name": "r/SaaS", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/startups/.rss", "name": "r/startups", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/entrepreneur/.rss", "name": "r/entrepreneur", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/smallbusiness/.rss", "name": "r/smallbusiness", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/indiehackers/.rss", "name": "r/indiehackers", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/founder/.rss", "name": "r/founder", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/SideProject/.rss", "name": "r/SideProject", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/growthhacking/.rss", "name": "r/growthhacking", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/marketing/.rss", "name": "r/marketing", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/SEO/.rss", "name": "r/SEO", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/crm/.rss", "name": "r/crm", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/projectmanagement/.rss", "name": "r/projectmanagement", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/productivity/.rss", "name": "r/productivity", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/webdev/.rss", "name": "r/webdev", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/webdesigner/.rss", "name": "r/webdesigner", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/Frontend/.rss", "name": "r/Frontend", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/EntrepreneurRideAlong/.rss", "name": "r/EntrepreneurRideAlong", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/legaladvice/.rss", "name": "r/legaladvice", "max_age_days": 7},
    {"url": "https://www.reddit.com/r/sales/.rss", "name": "r/sales", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/ecommerce/.rss", "name": "r/ecommerce", "max_age_days": 5},

    # === REDDIT: SPECIFIC TOOL COMPLAINTS (15 feeds) ===
    {"url": "https://www.reddit.com/r/SaaShosting/.rss", "name": "r/SaaShosting", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/salesforce/.rss", "name": "r/salesforce", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/jira/.rss", "name": "r/jira", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/zapier/.rss", "name": "r/zapier", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/notion/.rss", "name": "r/notion", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/Asana/.rss", "name": "r/Asana", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/trello/.rss", "name": "r/trello", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/Pipedrive/.rss", "name": "r/Pipedrive", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/zendesk/.rss", "name": "r/zendesk", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/hubspot/.rss", "name": "r/hubspot", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/slack/.rss", "name": "r/slack", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/zoom/.rss", "name": "r/zoom", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/gsuite/.rss", "name": "r/gsuite", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/office365/.rss", "name": "r/office365", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/aws/.rss", "name": "r/aws", "max_age_days": 5},

    # === REDDIT: AI & TECH DISCUSSIONS (12 feeds) ===
    {"url": "https://www.reddit.com/r/artificial/.rss", "name": "r/artificial", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/MachineLearning/.rss", "name": "r/MachineLearning", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/deeplearning/.rss", "name": "r/deeplearning", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/ChatGPT/.rss", "name": "r/ChatGPT", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/LocalLLaMA/.rss", "name": "r/LocalLLaMA", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/LLMs/.rss", "name": "r/LLMs", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/LocalAI/.rss", "name": "r/LocalAI", "max_age_days": 3},
    {"url": "https://www.reddit.com/r/cscareerquestions/.rss", "name": "r/cscareerquestions", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/sysadmin/.rss", "name": "r/sysadmin", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/devops/.rss", "name": "r/devops", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/cloud/.rss", "name": "r/cloud", "max_age_days": 5},
    {"url": "https://www.reddit.com/r/docker/.rss", "name": "r/docker", "max_age_days": 5},

    # === SECURITY (5 feeds) ===
    {"url": "https://feeds.feedburner.com/TheHackersNews", "name": "The Hacker News", "max_age_days": 2},
    {"url": "https://www.darkreading.com/rss.xml", "name": "Dark Reading", "max_age_days": 3},
    {"url": "https://www.theregister.com/security/headlines.atom", "name": "The Register Security", "max_age_days": 3},
    {"url": "https://www.schneier.com/blog/atom.xml", "name": "Schneier on Security", "max_age_days": 5},
    {"url": "https://krebsonsecurity.com/feed/", "name": "Krebs on Security", "max_age_days": 3},

    # === STARTUP & BUSINESS NEWS (8 feeds) ===
    {"url": "https://www.techinasia.com/feed", "name": "Tech in Asia", "max_age_days": 3},
    {"url": "https://siliconangle.com/feed/", "name": "SiliconANGLE", "max_age_days": 3},
    {"url": "https://www.ft.com/?format=rss", "name": "Financial Times Tech", "max_age_days": 3},
    {"url": "https://www.wired.co.uk/rss", "name": "Wired UK", "max_age_days": 3},
    {"url": "https://mixergy.com/feed/", "name": "Mixergy Podcast", "max_age_days": 7},
    {"url": "https://feeds.feedburner.com/SouthChinaMorningPost", "name": "SCMP", "max_age_days": 5},
    {"url": "https://www.alleywatch.com/feed/", "name": "AlleyWatch", "max_age_days": 3},

    # === YOUTUBE & VIDEO COMMENTS (via yt rss - video complaints) (5 feeds) ===
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA", "name": "YouTube: TechQuickie", "max_age_days": 7},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYP01IT9PkYGK6lX4f9HA", "name": "YouTube: LowEndBox", "max_age_days": 7},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCpMsRL6LiB7lvC0oMy2kZ8g", "name": "YouTube: AustinEvans", "max_age_days": 7},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCCogitoYIwYwBjY9jTMlg9w", "name": "YouTube: MKBHD", "max_age_days": 7},
    {"url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCsUcy4mV4sAqw3qV4_KkgLw", "name": "YouTube: ReviewTech", "max_age_days": 7},

    # === NEWSLETTER & BLOG AGGREGATORS (5 feeds) ===
    {"url": "https://www.lennysnewsletter.com/feed", "name": "Lenny's Newsletter", "max_age_days": 5},
    {"url": "https://stratechery.com/feed/", "name": "Stratechery", "max_age_days": 5},
    {"url": "https://mailchi.mp/feed", "name": "Mailchimp Newsletter", "max_age_days": 5},
    {"url": "https://buttondown.email/feed", "name": "Buttondown RSS", "max_age_days": 5},
    {"url": "https://convertkit.com/feed", "name": "ConvertKit", "max_age_days": 5},

    # === CRYPTO & WEB3 (3 feeds) ===
    {"url": "https://coindesk.com/feed", "name": "CoinDesk", "max_age_days": 2},
    {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph", "max_age_days": 2},
    {"url": "https://decrypt.co/feed", "name": "Decrypt", "max_age_days": 2},

    # === SPANISH & CHINESE TECH (3 feeds) - for non-English SaaS complaints ===
    {"url": "https://wwwhatsnew.com/feed", "name": "WWWhatsnew (ES)", "max_age_days": 5},
    {"url": "https://www.genbeta.com/feed", "name": "Genbeta (ES)", "max_age_days": 5},
    {"url": "https://36kr.com/feed", "name": "36kr (CN)", "max_age_days": 3},
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


@app.get("/commercial", response_class=HTMLResponse)
def commercial_index() -> str:
    return (COMMERCIAL_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/commercial/report")
def commercial_report(session: Session = Depends(get_session)) -> dict:
    return build_report_preview(session)


@app.get("/api/commercial/products")
def commercial_products() -> dict:
    return {"products": public_products()}


@app.get("/api/commercial/report/pdf")
def commercial_report_pdf(session: Session = Depends(get_session)) -> Response:
    try:
        pdf_bytes = get_pdf_bytes(session)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc) + " Install with: pip install weasyprint",
        )
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; filename="
                "too-expensive-radar-report.pdf"
            )
        },
    )


class PublishRequest(BaseModel):
    platform: str = "gumroad"
    price_usd: int = 49


@app.post("/api/commercial/publish")
def commercial_publish(req: PublishRequest, session: Session = Depends(get_session)) -> dict:
    try:
        pdf_bytes = get_pdf_bytes(session)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    from commercial.pdf_generator import gather_report_data
    data = gather_report_data(session)
    issue = data.get("issue_number", "001")
    title = data.get("title", "Too Expensive Radar")
    summary = data.get("summary_hook", "")

    name = f"{title} {issue}"
    description = f"{summary}\n\n{summary}\n\nThis report is generated automatically from pricing pain signals across the SaaS ecosystem."

    if req.platform == "gumroad":
        try:
            pub = GumroadPublisher()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        result = pub.create_product(
            name=name,
            price=req.price_usd,
            description=description,
            published=True,
        )
        return {"platform": "gumroad", "result": result}

    elif req.platform == "lemonsqueezy":
        try:
            pub = LemonsqueezyPublisher()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        result = pub.create_product(
            name=name,
            price=req.price_usd * 100,
            description=description,
        )
        checkout_url = pub.get_checkout_url(result["variant"]["id"])
        return {"platform": "lemonsqueezy", "result": result, "checkout_url": checkout_url}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {req.platform}")


@app.post("/api/commercial/checkout")
async def commercial_checkout(req: CheckoutRequest) -> dict:
    try:
        result = await create_checkout_session(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response else str(exc)
        raise HTTPException(status_code=502, detail=f"Dodo checkout failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Dodo checkout failed: {exc}") from exc

    if not result.get("configured"):
        raise HTTPException(status_code=503, detail=result)
    return result


@app.post("/api/ingest/text", response_model=OpportunityRead)
async def ingest_text(req: TextIngestRequest, session: Session = Depends(get_session)) -> Opportunity:
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    return await _persist_analysis(session, req)


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
        created.append((await _persist_analysis(session, req)).id)
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
            created.append((await _persist_analysis(session, req)).id)

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
    import asyncio
    created = []
    for text in SEED_COMMENTS:
        result = asyncio.run(_persist_analysis(session, TextIngestRequest(content=text, platform="seed")))
        created.append(result.id)
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


@app.post("/api/rss/fetch-all")
async def fetch_all_rss(background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    from app.models import AsyncTask, TaskStatus
    import uuid

    task_id = str(uuid.uuid4())
    task = AsyncTask(task_id=task_id, task_type="rss_fetch_all", status=TaskStatus.PENDING)
    session.add(task)
    session.commit()
    session.refresh(task)

    background_tasks.add_task(_run_rss_collect_async, task.task_id, DEFAULT_RSS_FEEDS)

    return {"task_id": task.task_id, "status": task.status, "feeds_count": len(DEFAULT_RSS_FEEDS)}


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
                    session.refresh(opp)

                    await _discover_alternatives_for_opportunity(session, opp, content)
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


@app.get("/api/funnel/status")
def funnel_status(session: Session = Depends(get_session)) -> dict:
    from app.models import Opportunity, AlternativeCandidate, RawSignal, Complaint

    total_opps = session.exec(
        select(Opportunity).where(Opportunity.disruption_score > 0)
    ).all()

    opp_ids_level1 = [o.id for o in total_opps]
    level1_count = len(opp_ids_level1)

    if opp_ids_level1:
        complaint_ids = [o.complaint_id for o in total_opps if o.complaint_id]
        complaint_to_opp = {o.complaint_id: o.id for o in total_opps if o.complaint_id}
        if complaint_ids:
            alts_with_boost = session.exec(
                select(AlternativeCandidate)
                .where(AlternativeCandidate.complaint_id.in_(complaint_ids))
                .where(AlternativeCandidate.disruption_score_boost > 0)
            ).all()
            opp_ids_level2 = set(complaint_to_opp.get(a.complaint_id) for a in alts_with_boost if a.complaint_id in complaint_to_opp)
            level2_count = len(opp_ids_level2)

            alts_confirmed = [a for a in alts_with_boost if a.affiliate_support == "confirmed"]
            opp_ids_level3 = set(complaint_to_opp.get(a.complaint_id) for a in alts_confirmed if a.complaint_id in complaint_to_opp)
            level3_count = len(opp_ids_level3)
        else:
            level2_count = 0
            level3_count = 0
    else:
        level2_count = 0
        level3_count = 0

    return {
        "level1_count": level1_count,
        "level2_count": level2_count,
        "level3_count": level3_count,
        "total_opportunities": level1_count,
    }


@app.get("/api/funnel/data")
def funnel_data(session: Session = Depends(get_session)) -> dict:
    from app.models import Opportunity, AlternativeCandidate, RawSignal, Complaint

    all_opps = session.exec(
        select(Opportunity).where(Opportunity.disruption_score > 0)
    ).all()

    raw_map = {}
    for opp in all_opps:
        complaint = session.exec(select(Complaint).where(Complaint.id == opp.complaint_id)).first()
        if complaint:
            raw = session.exec(select(RawSignal).where(RawSignal.id == complaint.raw_signal_id)).first()
            if raw:
                raw_map[opp.id] = raw

    opp_ids_all = [o.id for o in all_opps]
    complaint_ids = [o.complaint_id for o in all_opps if o.complaint_id]
    alts_map: dict[int, list] = {}
    if complaint_ids:
        complaint_to_opp = {o.complaint_id: o.id for o in all_opps if o.complaint_id}
        alts = session.exec(
            select(AlternativeCandidate)
            .where(AlternativeCandidate.complaint_id.in_(complaint_ids))
        ).all()
        for alt in alts:
            opp_id = complaint_to_opp.get(alt.complaint_id)
            if opp_id:
                if opp_id not in alts_map:
                    alts_map[opp_id] = []
                alts_map[opp_id].append({
                    "alternative_name": alt.alternative_name,
                    "pricing_tier": alt.pricing_tier,
                    "affiliate_support": alt.affiliate_support,
                    "affiliate_url": alt.affiliate_url,
                    "price_advantage": alt.price_advantage,
                    "disruption_score_boost": alt.disruption_score_boost,
                })

    def build_opp(o):
        raw = raw_map.get(o.id)
        alts = alts_map.get(o.id, [])
        return {
            "id": o.id,
            "software": o.software,
            "category": o.category,
            "complaint_summary": o.complaint_summary,
            "disruption_score": o.disruption_score,
            "evidence": o.evidence,
            "created_at": o.created_at.isoformat() if o.created_at else "",
            "platform": raw.platform if raw else "",
            "content": raw.content if raw else "",
            "source_url": raw.source_url if raw else "",
            "alternatives": alts,
        }

    all_opps_data = [build_opp(o) for o in all_opps]

    level1 = all_opps_data

    level2 = [o for o in all_opps_data if any(a["disruption_score_boost"] > 0 for a in o["alternatives"])]

    level3 = [o for o in all_opps_data if any(a["affiliate_support"] == "confirmed" for a in o["alternatives"])]

    return {
        "level1": level1,
        "level2": level2,
        "level3": level3,
    }


@app.get("/api/raw-signals")
def list_raw_signals(limit: int = 50, session: Session = Depends(get_session)) -> list:
    from app.models import RawSignal
    opps = session.exec(
        select(Opportunity).where(Opportunity.disruption_score > 0)
    ).all()
    opp_ids = [o.id for o in opps]
    complaint_map = {}
    if opp_ids:
        complaints = session.exec(
            select(Complaint).where(Complaint.id.in_([o.complaint_id for o in opps if o.complaint_id]))
        ).all()
        complaint_map = {c.id: c for c in complaints}

    signals = []
    for opp in opps:
        cid = opp.complaint_id
        if cid in complaint_map:
            comp = complaint_map[cid]
            raw = session.exec(select(RawSignal).where(RawSignal.id == comp.raw_signal_id)).first()
            if raw:
                signals.append({
                    "id": raw.id,
                    "content": raw.content,
                    "platform": raw.platform,
                    "source_url": raw.source_url,
                    "author": raw.author,
                    "created_at": raw.created_at.isoformat() if raw.created_at else "",
                })
    return signals[:limit]


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


async def _persist_analysis(session: Session, req: TextIngestRequest) -> Opportunity:
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

    result = await analyze_text(req.content, llm)

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
    best_boost = 0.0
    for c in candidates:
        if c.disruption_score_boost > best_boost:
            best_boost = c.disruption_score_boost
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

    if best_boost > 0:
        opp.disruption_score += best_boost
        session.add(opp)

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
