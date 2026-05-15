from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from app.models import LLMProvider, SoftwareCategory


SOFTWARE_CATALOG = {
    "hubspot": ("HubSpot", SoftwareCategory.CRM),
    "salesforce": ("Salesforce", SoftwareCategory.CRM),
    "jira": ("Jira", SoftwareCategory.PROJECT_MANAGEMENT),
    "zapier": ("Zapier", SoftwareCategory.AUTOMATION),
    "make": ("Make", SoftwareCategory.AUTOMATION),
    "pandadoc": ("PandaDoc", SoftwareCategory.PROPOSAL),
    "docusign": ("DocuSign", SoftwareCategory.E_SIGNATURE),
    "zendesk": ("Zendesk", SoftwareCategory.CUSTOMER_SUPPORT),
    "intercom": ("Intercom", SoftwareCategory.CUSTOMER_SUPPORT),
    "airtable": ("Airtable", SoftwareCategory.INTERNAL_TOOLS),
    "notion": ("Notion", SoftwareCategory.KNOWLEDGE_MANAGEMENT),
    "monday": ("Monday.com", SoftwareCategory.PROJECT_MANAGEMENT),
    "asana": ("Asana", SoftwareCategory.PROJECT_MANAGEMENT),
    "clickup": ("ClickUp", SoftwareCategory.PROJECT_MANAGEMENT),
    "workday": ("Workday", SoftwareCategory.HR),
    "rippling": ("Rippling", SoftwareCategory.HR),
    "servicenow": ("ServiceNow", SoftwareCategory.INTERNAL_TOOLS),
    "smartsheet": ("Smartsheet", SoftwareCategory.PROJECT_MANAGEMENT),
    "confluence": ("Confluence", SoftwareCategory.KNOWLEDGE_MANAGEMENT),
    "slack": ("Slack", SoftwareCategory.AUTOMATION),
    "linear": ("Linear", SoftwareCategory.PROJECT_MANAGEMENT),
    "github": ("GitHub", SoftwareCategory.PROJECT_MANAGEMENT),
    "gitlab": ("GitLab", SoftwareCategory.PROJECT_MANAGEMENT),
    "bitbucket": ("Bitbucket", SoftwareCategory.PROJECT_MANAGEMENT),
    "trello": ("Trello", SoftwareCategory.PROJECT_MANAGEMENT),
    "basecamp": ("Basecamp", SoftwareCategory.PROJECT_MANAGEMENT),
    "wrike": ("Wrike", SoftwareCategory.PROJECT_MANAGEMENT),
    "proofhub": ("ProofHub", SoftwareCategory.PROJECT_MANAGEMENT),
    "hubspot": ("HubSpot", SoftwareCategory.CRM),
    "pipedrive": ("Pipedrive", SoftwareCategory.CRM),
    "hubspot": ("HubSpot", SoftwareCategory.CRM),
    "activecampaign": ("ActiveCampaign", SoftwareCategory.CRM),
    "mailchimp": ("Mailchimp", SoftwareCategory.CRM),
    "marketo": ("Marketo", SoftwareCategory.CRM),
    "pardot": ("Pardot", SoftwareCategory.CRM),
    "eloqua": ("Eloqua", SoftwareCategory.CRM),
    "sendgrid": ("SendGrid", SoftwareCategory.AUTOMATION),
    "mailgun": ("Mailgun", SoftwareCategory.AUTOMATION),
    "twilio": ("Twilio", SoftwareCategory.AUTOMATION),
    "statuspage": ("StatusPage", SoftwareCategory.INTERNAL_TOOLS),
    "pagerduty": ("PagerDuty", SoftwareCategory.AUTOMATION),
    "datadog": ("Datadog", SoftwareCategory.INTERNAL_TOOLS),
    "newrelic": ("NewRelic", SoftwareCategory.INTERNAL_TOOLS),
    "sentry": ("Sentry", SoftwareCategory.INTERNAL_TOOLS),
    "mixpanel": ("Mixpanel", SoftwareCategory.INTERNAL_TOOLS),
    "amplitude": ("Amplitude", SoftwareCategory.INTERNAL_TOOLS),
    "segment": ("Segment", SoftwareCategory.AUTOMATION),
    "mparticle": ("mParticle", SoftwareCategory.AUTOMATION),
    "braze": ("Braze", SoftwareCategory.CRM),
    "iterable": ("Iterable", SoftwareCategory.CRM),
    "klaviyo": ("Klaviyo", SoftwareCategory.CRM),
}

PRICING_TERMS = [
    "too expensive", "overpriced", "pricing sucks", "expensive", "costs too much",
    "not worth", "pricey", "cheaper alternative", "cheap alternative", "alternative to",
    "cost", "pricing", "afford", "unaffordable", "paying", "subscription", "pricey",
]

BLOAT_TERMS = [
    "bloated", "overkill", "too complicated", "too complex", "too many features",
    "hard to configure", "setup nightmare", "implementation", "admin", "too many clicks",
    "overengineered", "enterprise", "heavy", "complex",
]

SMB_TERMS = ["small business", "smb", "startup", "solo", "freelancer", "small team", "agency", "bootstrapped"]

WORKFLOW_MAP = {
    "CRM workflow": ["crm", "lead", "pipeline", "sales", "contact", "deal", "follow up", "email follow", "lead capture"],
    "Proposal workflow": ["proposal", "quote", "sow", "statement of work", "contract", "pricing page", "estimate"],
    "Document signing workflow": ["signature", "sign", "esign", "e-sign", "document", "pdf"],
    "Automation workflow": ["automation", "zap", "workflow", "integration", "webhook", "task", "trigger"],
    "Project tracking workflow": ["ticket", "project", "task", "sprint", "kanban", "issue", "milestone"],
    "Support workflow": ["support", "ticket", "chat", "helpdesk", "customer service", "reply", "agent"],
    "Knowledge workflow": ["docs", "wiki", "knowledge", "notes", "documentation", "doc", "article"],
    "Reporting workflow": ["report", "dashboard", "export", "analytics", "weekly report", "metrics"],
    "HR workflow": ["hr", "onboarding", "payroll", "employee", "benefits", "recruiting", "hiring"],
    "Marketing workflow": ["email", "campaign", "newsletter", "marketing", "automation", "drip"],
    "Internal Tool workflow": ["database", "spreadsheet", "table", "form", "approval", "internal"],
}

REPLACEMENT_TEMPLATES = {
    "CRM workflow": "AI-native lightweight CRM: auto-capture leads, summarize interactions, create follow-up reminders, update records via conversation.",
    "Proposal workflow": "AI proposal generator: intake client details, generate proposal/SOW, export PDF, send for signature, track status.",
    "Document signing workflow": "Simple document workflow: generate doc, collect signature, archive PDF, notify stakeholders without enterprise setup.",
    "Automation workflow": "AI workflow compressor: describe automation in natural language, auto-map integrations, monitor failures, reduce task-based pricing.",
    "Project tracking workflow": "AI project tracker: convert chat/docs into tasks, summarize status, detect blockers, reduce manual project admin.",
    "Support workflow": "AI support desk: summarize tickets, draft replies, route issues, expose only lightweight team workflows.",
    "Knowledge workflow": "AI knowledge hub: auto-organize docs, answer questions, detect stale pages, reduce manual wiki maintenance.",
    "Reporting workflow": "AI reporting assistant: pull data, generate narrative summaries, export PDF/slides, send scheduled reports.",
    "HR workflow": "AI HR workflow pack: onboarding checklist, document collection, status reminders, employee Q&A.",
    "Marketing workflow": "AI marketing copilot: manage email campaigns, automate drip sequences, generate content, analyze performance.",
    "Internal Tool workflow": "AI internal tool: natural language database queries, smart forms, automated approvals, minimal configuration.",
    "Unknown": "AI-native focused workflow: keep only the core user job, remove enterprise config, automate manual handoffs.",
}


@dataclass
class AnalysisResult:
    software: str
    category: str
    complaint_summary: str
    pricing_signal: bool
    bloat_signal: bool
    smb_signal: bool
    emotion_score: float
    sentiment_polarity: float
    workflow_name: str
    workflow_steps: list
    manual_handoffs: list
    software_dependencies: list
    workflow_complexity: float
    actual_workflow: str
    ai_native_replacement: str
    existing_price: str
    possible_price: str
    pricing_pain_score: float
    feature_bloat_score: float
    smb_overkill_score: float
    ai_compression_score: float
    workflow_simplicity_score: float
    replacement_feasibility_score: float
    disruption_score: float
    evidence: str
    _raw_llm: dict = field(default_factory=dict)


def _count_terms(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if t in text)


def detect_software(text: str) -> tuple[str, str]:
    lower = text.lower()
    for key, (name, category) in SOFTWARE_CATALOG.items():
        if key in lower:
            return name, category.value
    m = re.search(r"alternative to\s+([A-Za-z0-9 ._-]{2,30})", text, re.I)
    if m:
        return m.group(1).strip().rstrip("?.!"), SoftwareCategory.UNKNOWN.value
    return "Unknown", SoftwareCategory.UNKNOWN.value


def detect_workflow(text: str) -> tuple[str, list]:
    lower = text.lower()
    best = ("Unknown", 0)
    for workflow, terms in WORKFLOW_MAP.items():
        score = _count_terms(lower, terms)
        if score > best[1]:
            best = (workflow, score)
    return best[0], []


def analyze_text_rule_based(content: str) -> AnalysisResult:
    lower = content.lower()
    software, category = detect_software(content)
    workflow_name, workflow_terms = detect_workflow(content)

    pricing_hits = _count_terms(lower, PRICING_TERMS)
    bloat_hits = _count_terms(lower, BLOAT_TERMS)
    smb_hits = _count_terms(lower, SMB_TERMS)
    alternative_hit = 1 if "alternative to" in lower or "cheaper alternative" in lower else 0

    pricing_pain = min(10.0, 2.5 + pricing_hits * 1.7 + alternative_hit * 1.5)
    feature_bloat = min(10.0, 1.5 + bloat_hits * 2.0)
    smb_overkill = min(10.0, 1.0 + smb_hits * 2.0 + bloat_hits * 1.2)

    workflow_known = 1 if workflow_name != "Unknown" else 0
    ai_compression = min(10.0, 4.0 + workflow_known * 2.2 + bloat_hits * 0.8 + pricing_hits * 0.4)
    feasibility = min(10.0, 5.0 + workflow_known * 1.8 + (1 if software != "Unknown" else 0) + alternative_hit)
    workflow_simplicity = min(10.0, 5.0 + (1 if workflow_known else 0) * 2 - bloat_hits * 0.5)

    disruption = round(
        pricing_pain * 0.30
        + feature_bloat * 0.18
        + smb_overkill * 0.16
        + ai_compression * 0.22
        + feasibility * 0.14,
        2,
    )

    complaint_summary = summarize_complaint_rule_based(content, software, pricing_pain > 5, feature_bloat > 3)
    evidence = extract_evidence(content)
    replacement = REPLACEMENT_TEMPLATES.get(workflow_name, REPLACEMENT_TEMPLATES["Unknown"])

    return AnalysisResult(
        software=software,
        category=category,
        complaint_summary=complaint_summary,
        pricing_signal=pricing_pain > 4,
        bloat_signal=feature_bloat > 3,
        smb_signal=smb_overkill > 3,
        emotion_score=round(min(10.0, (pricing_pain + feature_bloat) / 2), 2),
        sentiment_polarity=round(-0.3 - (pricing_pain / 20), 2),
        workflow_name=workflow_name,
        workflow_steps=workflow_terms,
        manual_handoffs=[],
        software_dependencies=[software] if software != "Unknown" else [],
        workflow_complexity=round(feature_bloat / 2 + 1, 2),
        actual_workflow=workflow_name,
        ai_native_replacement=replacement,
        existing_price="",
        possible_price="",
        pricing_pain_score=round(pricing_pain, 2),
        feature_bloat_score=round(feature_bloat, 2),
        smb_overkill_score=round(smb_overkill, 2),
        ai_compression_score=round(ai_compression, 2),
        workflow_simplicity_score=round(workflow_simplicity, 2),
        replacement_feasibility_score=round(feasibility, 2),
        disruption_score=disruption,
        evidence=evidence,
    )


def summarize_complaint_rule_based(content: str, software: str, is_pricing: bool, is_bloat: bool) -> str:
    lower = content.lower()
    if is_pricing and is_bloat:
        return f"Users perceive {software} as too expensive and bloated for the workflow they actually need."
    if is_pricing:
        return f"Users perceive {software} as too expensive for the workflow they actually need."
    if is_bloat:
        return f"Users perceive {software} as overkill and too heavy for a narrow workflow."
    if "alternative" in lower:
        return f"Users are actively looking for an alternative to {software}."
    return f"Potential pricing or workflow friction around {software}."


def extract_evidence(content: str) -> str:
    clean = " ".join(content.split())
    return clean[:300] + ("..." if len(clean) > 300 else "")


async def analyze_text_llm(content: str, llm) -> AnalysisResult:
    from app.llm.prompts import (
        build_detection_prompt,
        build_workflow_prompt,
        build_replacement_prompt,
        build_scoring_prompt,
    )

    try:
        detection = await llm.complete(build_detection_prompt(content))
        detection_data = json.loads(detection.content)
    except Exception:
        return analyze_text_rule_based(content)

    try:
        workflow = await llm.complete(build_workflow_prompt(content))
        workflow_data = json.loads(workflow.content)
    except Exception:
        workflow_data = {"workflow_name": "Unknown", "workflow_steps": [], "manual_handoffs": [], "software_dependencies": [], "workflow_complexity": 5}

    software = detection_data.get("software_name", "Unknown")
    category = SoftwareCategory.UNKNOWN.value
    for key, (name, cat) in SOFTWARE_CATALOG.items():
        if key in software.lower():
            category = cat.value
            break

    try:
        replacement = await llm.complete(build_replacement_prompt(
            software, workflow_data.get("workflow_name", "Unknown"), content
        ))
        replacement_data = json.loads(replacement.content)
    except Exception:
        replacement_data = {}

    try:
        scoring = await llm.complete(build_scoring_prompt(software, workflow_data.get("workflow_name", "Unknown"), content))
        scoring_data = json.loads(scoring.content)
    except Exception:
        scoring_data = {}

    workflow_name = workflow_data.get("workflow_name", "Unknown")
    replacement_text = replacement_data.get("ai_native_replacement", REPLACEMENT_TEMPLATES.get(workflow_name, REPLACEMENT_TEMPLATES["Unknown"]))

    return AnalysisResult(
        software=software,
        category=category,
        complaint_summary=summarize_complaint_rule_based(content, software, detection_data.get("is_pricing_complaint", False), detection_data.get("is_bloat_complaint", False)),
        pricing_signal=detection_data.get("is_pricing_complaint", False),
        bloat_signal=detection_data.get("is_bloat_complaint", False),
        smb_signal=detection_data.get("is_smb_complaint", False),
        emotion_score=detection_data.get("emotion_score", 5),
        sentiment_polarity=detection_data.get("sentiment_polarity", -0.5),
        workflow_name=workflow_name,
        workflow_steps=workflow_data.get("workflow_steps", []),
        manual_handoffs=workflow_data.get("manual_handoffs", []),
        software_dependencies=workflow_data.get("software_dependencies", []),
        workflow_complexity=workflow_data.get("workflow_complexity", 5),
        actual_workflow=workflow_name,
        ai_native_replacement=replacement_text,
        existing_price=replacement_data.get("existing_price", ""),
        possible_price=replacement_data.get("possible_price", ""),
        pricing_pain_score=scoring_data.get("pricing_pain_score", 5),
        feature_bloat_score=scoring_data.get("feature_bloat_score", 5),
        smb_overkill_score=scoring_data.get("smb_overkill_score", 5),
        ai_compression_score=scoring_data.get("ai_compression_score", 5),
        workflow_simplicity_score=scoring_data.get("workflow_simplicity_score", 5),
        replacement_feasibility_score=scoring_data.get("replacement_feasibility_score", 5),
        disruption_score=scoring_data.get("disruption_score", 5),
        evidence=extract_evidence(content),
        _raw_llm={"detection": detection_data, "workflow": workflow_data, "replacement": replacement_data, "scoring": scoring_data},
    )


async def analyze_text(content: str, llm=None) -> AnalysisResult:
    if llm:
        return await analyze_text_llm(content, llm)
    return analyze_text_rule_based(content)