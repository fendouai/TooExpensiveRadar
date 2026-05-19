from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Session, select

from app.models import AlternativeCandidate, Complaint, Opportunity, RawSignal


ISSUE_COUNTER_FILE = Path(__file__).parent / ".issue_counter"


def _get_next_issue_number() -> int:
    try:
        n = int(ISSUE_COUNTER_FILE.read_text().strip())
    except Exception:
        n = 0
    n += 1
    ISSUE_COUNTER_FILE.write_text(str(n))
    return n


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).strftime("%B %d, %Y")
    return dt.strftime("%B %d, %Y")


# ─────────────────────────────────────────────
# DATA GATHERING
# ─────────────────────────────────────────────

def gather_report_data(session: Session, limit: int = 20) -> dict[str, Any]:
    opportunities = list(
        session.exec(
            select(Opportunity)
            .where(Opportunity.disruption_score > 0)
            .order_by(Opportunity.disruption_score.desc())
            .limit(limit)
        ).all()
    )

    complaint_ids = [o.complaint_id for o in opportunities if o.complaint_id]
    raw_by_complaint: dict[int, RawSignal] = {}
    alts_by_complaint: dict[int, list[AlternativeCandidate]] = {}

    if complaint_ids:
        complaints = session.exec(
            select(Complaint).where(Complaint.id.in_(complaint_ids))
        ).all()
        raw_ids = [c.raw_signal_id for c in complaints if c.raw_signal_id]
        if raw_ids:
            raw_signals = session.exec(
                select(RawSignal).where(RawSignal.id.in_(raw_ids))
            ).all()
            raw_by_id = {r.id: r for r in raw_signals}
            raw_by_complaint = {
                c.id: raw_by_id[c.raw_signal_id]
                for c in complaints
                if c.id and c.raw_signal_id in raw_by_id
            }

        alternatives = session.exec(
            select(AlternativeCandidate).where(
                AlternativeCandidate.complaint_id.in_(complaint_ids)
            )
        ).all()
        for alt in alternatives:
            if alt.complaint_id:
                alts_by_complaint.setdefault(alt.complaint_id, []).append(alt)

    total_signals = session.exec(select(RawSignal)).all()
    total_signals_count = len(list(total_signals))

    # Build top opportunities
    top_opps = []
    affiliate_ready_count = 0

    for opp in opportunities[:10]:
        alts = alts_by_complaint.get(opp.complaint_id or 0, [])
        confirmed = [a for a in alts if a.affiliate_support == "confirmed"]
        affiliate_ready_count += 1 if confirmed else 0
        best_alt = confirmed[0] if confirmed else (alts[0] if alts else None)
        raw = raw_by_complaint.get(opp.complaint_id or 0)

        # Parse pain bars from opportunity fields
        pain_bars = _extract_pain_bars(opp)

        top_opps.append({
            "software": opp.software or "Unknown",
            "category": opp.category or "SaaS",
            "score": round(opp.disruption_score, 1),
            "evidence": (opp.evidence or opp.complaint_summary or "")[:200],
            "alternative": best_alt.alternative_name if best_alt else (opp.ai_native_replacement or ""),
            "price_advantage": best_alt.price_advantage if best_alt else "",
            "affiliate_url": best_alt.affiliate_url if best_alt else "",
            "replacement_wedge": opp.actual_workflow or opp.ai_native_replacement or "",
            "pain_bars": pain_bars,
        })

    # Build all opportunities table
    all_opps_table = []
    for opp in opportunities:
        alts = alts_by_complaint.get(opp.complaint_id or 0, [])
        confirmed = [a for a in alts if a.affiliate_support == "confirmed"]
        best_alt = confirmed[0] if confirmed else (alts[0] if alts else None)
        all_opps_table.append({
            "score": round(opp.disruption_score, 1),
            "software": opp.software or "Unknown",
            "category": opp.category or "SaaS",
            "pain_summary": (opp.complaint_summary or opp.evidence or "")[:120],
            "alternative": best_alt.alternative_name if best_alt else (opp.ai_native_replacement or "—"),
            "price_advantage": best_alt.price_advantage if best_alt else "—",
        })

    # Switcher data (Zapier example)
    switcher_data = _build_switcher_data(session)

    issue_number = _get_next_issue_number()
    publish_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    top_score = opportunities[0].disruption_score if opportunities else 0

    # Executive summary
    if top_opps:
        top = top_opps[0]
        summary_hook = (
            f"{top['software']} is the #1 opportunity this issue — "
            f"scoring {top['score']}/10 with {top['alternative']} as the recommended replacement."
        )
    else:
        summary_hook = "No opportunities found in this period."

    summary_body = (
        f"This issue analyzed {total_signals_count:,} raw signals from 110 RSS sources "
        f"across Hacker News, Reddit, DEV.to, Lobsters, and more. "
        f"{len(opportunities)} opportunities passed the pricing-pain filter. "
        f"{affiliate_ready_count} have confirmed affiliate programs ready to monetize."
    )

    key_takeaway = (
        f"The highest-confidence opportunity is {top['software']} → {top['alternative']} "
        f"({top['price_advantage']}). "
        f"Affiliate links are available at the recommended alternative's program page. "
        f"Full rankings, evidence links, and switcher analysis below."
    )

    return {
        "issue_number": f"#{issue_number:03d}",
        "publish_date": publish_date,
        "title": "Too Expensive Radar",
        "badge": "SaaS Opportunity Intelligence",
        "subtitle": (
            "Weekly analysis of pricing pain signals, affiliate-ready replacements, "
            "and disruption opportunities across the SaaS ecosystem."
        ),
        "total_signals": total_signals_count,
        "opportunities_count": len(opportunities),
        "affiliate_ready": affiliate_ready_count,
        "top_score": top_score,
        "summary_hook": summary_hook,
        "summary_body": summary_body,
        "key_takeaway": key_takeaway,
        "top_opportunities": top_opps,
        "all_opportunities": all_opps_table,
        "switcher_data": switcher_data,
        "funnel_stats": [
            {"layer": "L1 · Raw Signals", "description": "All RSS signals scraped this period", "count": total_signals_count},
            {"layer": "L2 · Pricing Pain", "description": "Flagged as too expensive / overkill / bloated", "count": len(opportunities)},
            {"layer": "L3 · Affiliate Ready", "description": "Confirmed cheaper alt + active affiliate program", "count": affiliate_ready_count},
        ],
    }


def _extract_pain_bars(opp: Opportunity) -> list[dict]:
    bars = []
    evidence = (opp.evidence or "").lower()

    pricing_signals = [
        "price", "pricing", "expensive", "cost", "subscription",
        "billing", "overpriced", "too expensive", "charged"
    ]
    bloat_signals = [
        "feature", "bloat", "bloated", "overkill", "complex",
        "complicated", "clunky", "slow"
    ]
    workflow_signals = [
        "workflow", "automation", "automate", "multi-step", "task",
        "integration", "connect"
    ]

    def count_signals(sig_list: list[str]) -> int:
        return sum(1 for s in sig_list if s in evidence)

    p_count = count_signals(pricing_signals)
    b_count = count_signals(bloat_signals)
    w_count = count_signals(workflow_signals)
    total = p_count + b_count + w_count

    if p_count:
        bars.append({"label": "Pricing Pain", "value": int(p_count / max(total, 1) * 100)})
    if b_count:
        bars.append({"label": "Feature Bloat", "value": int(b_count / max(total, 1) * 100)})
    if w_count:
        bars.append({"label": "Workflow Friction", "value": int(w_count / max(total, 1) * 100)})

    return bars[:3]


def _build_switcher_data(session: Session) -> dict[str, Any] | None:
    zapier_opp = session.exec(
        select(Opportunity)
        .where(Opportunity.software.ilike("%zapier%"))
        .order_by(Opportunity.disruption_score.desc())
    ).first()

    if not zapier_opp:
        return None

    complaint_ids = [zapier_opp.complaint_id] if zapier_opp.complaint_id else []
    if not complaint_ids:
        return None

    alts = session.exec(
        select(AlternativeCandidate)
        .where(AlternativeCandidate.complaint_id.in_(complaint_ids))
    ).all()

    # Use hardcoded switcher data for now (same as content/pabbly-vs-zapier/data.json)
    switchers = [
        {"name": "Pabbly", "pct": 28, "price_tier": "70% cheaper"},
        {"name": "n8n", "pct": 24, "price_tier": "Free + self-hosted"},
        {"name": "Make", "pct": 19, "price_tier": "30% cheaper"},
        {"name": "Integrately", "pct": 15, "price_tier": "50% cheaper"},
        {"name": "IFTTT", "pct": 9, "price_tier": "Free tier available"},
        {"name": "Workato", "pct": 5, "price_tier": "Enterprise pricing"},
    ]

    pricing_comparison = [
        {"platform": "Zapier", "monthly_min": "0", "task_cost": "0.0019", "ten_k_cost": "19.50", "highlight": True},
        {"platform": "Pabbly", "monthly_min": "0", "task_cost": "0", "ten_k_cost": "0", "highlight": False},
        {"platform": "n8n", "monthly_min": "0", "task_cost": "0", "ten_k_cost": "0", "highlight": False},
        {"platform": "Make", "monthly_min": "0", "task_cost": "0.0015", "ten_k_cost": "15.00", "highlight": False},
    ]

    return {
        "competitor": "Zapier",
        "competitor_score": round(zapier_opp.disruption_score, 1),
        "switchers": switchers,
        "pricing_comparison": pricing_comparison,
    }


# ─────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────

def generate_pdf(session: Session, output_path: Path | None = None) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError(
            "WeasyPrint is not installed. Install it with:\n"
            "  pip install weasyprint\n"
            "On macOS also run:\n"
            "  brew install pango gdk-pixbuf libffi"
        )

    data = gather_report_data(session)

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    html_content = env.get_template("report.html").render(**data)

    pdf_io = io.BytesIO()
    HTML(string=html_content, base_url=str(template_dir)).write_pdf(pdf_io)
    pdf_bytes = pdf_io.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

    return pdf_bytes


def get_pdf_bytes(session: Session) -> bytes:
    return generate_pdf(session)
