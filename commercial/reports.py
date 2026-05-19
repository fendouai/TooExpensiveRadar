from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import AlternativeCandidate, Complaint, Opportunity, RawSignal


def build_report_preview(session: Session, limit: int = 12) -> dict[str, Any]:
    opportunities = list(
        session.exec(
            select(Opportunity)
            .where(Opportunity.disruption_score > 0)
            .order_by(Opportunity.disruption_score.desc(), Opportunity.created_at.desc())
            .limit(limit)
        ).all()
    )

    complaint_ids = [o.complaint_id for o in opportunities if o.complaint_id]
    raw_by_complaint: dict[int, RawSignal] = {}
    alternatives_by_complaint: dict[int, list[AlternativeCandidate]] = {}

    if complaint_ids:
        complaints = session.exec(select(Complaint).where(Complaint.id.in_(complaint_ids))).all()
        raw_ids = [c.raw_signal_id for c in complaints if c.raw_signal_id]
        if raw_ids:
            raw_signals = session.exec(select(RawSignal).where(RawSignal.id.in_(raw_ids))).all()
            raw_by_id = {r.id: r for r in raw_signals}
            raw_by_complaint = {
                c.id: raw_by_id[c.raw_signal_id]
                for c in complaints
                if c.id and c.raw_signal_id in raw_by_id
            }

        alternatives = session.exec(
            select(AlternativeCandidate).where(AlternativeCandidate.complaint_id.in_(complaint_ids))
        ).all()
        for alt in alternatives:
            if alt.complaint_id:
                alternatives_by_complaint.setdefault(alt.complaint_id, []).append(alt)

    category_counts = Counter(o.category for o in opportunities if o.category)
    software_counts = Counter(o.software for o in opportunities if o.software)
    affiliate_count = 0
    rows = []

    for opp in opportunities:
        alternatives = alternatives_by_complaint.get(opp.complaint_id or 0, [])
        confirmed = [a for a in alternatives if a.affiliate_support == "confirmed"]
        affiliate_count += 1 if confirmed else 0
        raw = raw_by_complaint.get(opp.complaint_id or 0)
        best_alt = confirmed[0] if confirmed else alternatives[0] if alternatives else None
        rows.append(
            {
                "software": opp.software,
                "category": opp.category,
                "score": round(opp.disruption_score, 1),
                "pain": opp.complaint_summary or opp.evidence,
                "replacement": opp.ai_native_replacement,
                "workflow": opp.actual_workflow,
                "evidence": opp.evidence,
                "source_url": raw.source_url if raw else "",
                "platform": raw.platform if raw else "",
                "alternative": best_alt.alternative_name if best_alt else "",
                "affiliate_url": best_alt.affiliate_url if best_alt else "",
                "price_advantage": best_alt.price_advantage if best_alt else "",
            }
        )

    top_category = category_counts.most_common(1)[0][0] if category_counts else "SaaS replacement"
    top_software = software_counts.most_common(1)[0][0] if software_counts else "legacy SaaS"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "positioning": {
            "model": "Paid recurring intelligence reports",
            "best_offer": "Sell a monthly Too Expensive Radar Report to founders, indie hackers, agencies, and affiliate operators.",
            "why": "The open-source product already finds pricing-pain signals. The sellable value is curation: ranked opportunities, proof links, replacement angles, and monetization paths.",
            "pricing": "$49 for a single report, $149/month for a recurring brief, then custom research for teams.",
        },
        "summary": {
            "opportunities": len(opportunities),
            "affiliate_ready": affiliate_count,
            "top_category": top_category,
            "top_software": top_software,
        },
        "products": [
            "Top 20 overpriced SaaS replacement opportunities",
            "Evidence links and complaint snippets",
            "AI-native replacement wedge for each opportunity",
            "Cheaper alternative and affiliate path when available",
        ],
        "opportunities": rows,
    }
