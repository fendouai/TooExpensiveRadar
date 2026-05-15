from __future__ import annotations

from app.models import LLMProvider

SYSTEM_PROMPT_DETECTION = """You are a SaaS Complaint Detector. Your task is to analyze user complaints about software and determine if they indicate pricing pain or workflow bloat.

Analyze the provided text and respond with a JSON object containing:
{
  "is_pricing_complaint": true/false,
  "is_bloat_complaint": true/false,
  "is_smb_complaint": true/false,
  "emotion_score": 0-10,
  "software_name": "detected software name or 'Unknown'",
  "complaint_type": "pricing|bloat|both|other",
  "key_phrases": ["list of detected key phrases"],
  "sentiment_polarity": -1 to 1
}

Be strict in your classification. Only mark as pricing complaint if the text explicitly mentions cost, price, expensive, cheap, affordability, or value for money issues."""

SYSTEM_PROMPT_WORKFLOW = """You are a Workflow Extraction Engine. Your task is to analyze user complaints about software and extract the actual workflow being described.

Analyze the provided text and respond with a JSON object containing:
{
  "workflow_name": "name of the workflow type",
  "workflow_steps": ["step1", "step2", ...],
  "manual_handoffs": ["where manual coordination happens"],
  "software_dependencies": ["specific features/tools used"],
  "workflow_complexity": 1-10,
  "actual_need": ["what the user actually needs"],
  "unused_features": ["features mentioned as unnecessary"],
  "frequency_hint": "how often this workflow runs"
}

The complaint text mentions a software being too expensive or bloated. Extract ONLY the workflow the user actually needs."""

SYSTEM_PROMPT_REPLACEMENT = """You are an AI-Native Replacement Architect. Your task is to suggest how AI can compress or replace an existing software workflow.

Based on the complaint and extracted workflow, respond with a JSON object:
{
  "ai_native_replacement": "detailed description of the AI solution",
  "possible_price": "$XX/month",
  "existing_price": "$XX/month or 'unknown'",
  "replacement_potential": 0-10,
  "ai_native_score": 0-10,
  "market_gap": "description of the market gap",
  "competition_level": "low|medium|high",
  "key_differentiator": "what makes this AI solution better",
  "target_segment": "SMB|Enterprise|Startup|Agency"
}

Focus on how AI can reduce: admin overhead, configuration complexity, workflow friction, and software dependencies."""

SYSTEM_PROMPT_SCORING = """You are an Opportunity Scoring Engine. Score AI-native SaaS replacement opportunities based on market signals.

Score the following aspects (0-10 each):
- pricing_pain_score: How expensive do users find the current solution?
- feature_bloat_score: How bloated/overkill is the current solution?
- smb_overkill_score: Is the solution designed for enterprises but used by SMBs?
- ai_compression_score: How much can AI compress this workflow?
- workflow_simplicity_score: How simple and frequent is the workflow?
- replacement_feasibility_score: How easy is it to build an AI replacement?

Respond with JSON:
{
  "pricing_pain_score": 0-10,
  "feature_bloat_score": 0-10,
  "smb_overkill_score": 0-10,
  "ai_compression_score": 0-10,
  "workflow_simplicity_score": 0-10,
  "replacement_feasibility_score": 0-10,
  "disruption_score": "weighted average 0-10"
}

Use weights: pricing_pain=0.30, ai_compression=0.22, feature_bloat=0.18, smb_overkill=0.16, feasibility=0.14"""


USER_PROMPT_DETECTION = """Analyze this complaint:
{complaint_text}

Return ONLY valid JSON."""

USER_PROMPT_WORKFLOW = """Extract workflow from this complaint:
{complaint_text}

Return ONLY valid JSON."""

USER_PROMPT_REPLACEMENT = """Suggest AI replacement for:
Software: {software}
Workflow: {workflow}
Complaint: {complaint}

Return ONLY valid JSON."""

USER_PROMPT_SCORING = """Score this replacement opportunity:
Software: {software}
Workflow: {workflow}
Complaint: {complaint}

Return ONLY valid JSON."""


def build_detection_prompt(complaint_text: str) -> str:
    return f"""Analyze this complaint:
{complaint_text}

Return ONLY valid JSON."""


def build_workflow_prompt(complaint_text: str) -> str:
    return f"""Extract workflow from this complaint:
{complaint_text}

Return ONLY valid JSON."""


def build_replacement_prompt(software: str, workflow: str, complaint: str) -> str:
    return f"""Suggest AI replacement for:
Software: {software}
Workflow: {workflow}
Complaint: {complaint}

Return ONLY valid JSON."""


def build_scoring_prompt(software: str, workflow: str, complaint: str) -> str:
    return f"""Score this replacement opportunity:
Software: {software}
Workflow: {workflow}
Complaint: {complaint}

Return ONLY valid JSON."""