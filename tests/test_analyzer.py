from app.analyzer import analyze_text_rule_based, detect_software, detect_workflow, REPLACEMENT_TEMPLATES
from app.models import SoftwareCategory


def test_detect_software_hubspot():
    assert detect_software("HubSpot is too expensive")[0] == "HubSpot"


def test_detect_workflow_crm():
    assert detect_workflow("basic CRM lead tracking and follow up")[0] == "CRM workflow"


def test_analyze_text_high_score():
    r = analyze_text_rule_based("HubSpot is too expensive for small business basic CRM automation. Need cheaper alternative.")
    assert r.software == "HubSpot"
    assert r.pricing_pain_score >= 7
    assert r.disruption_score >= 4
    assert "CRM" in r.actual_workflow or r.actual_workflow == "Unknown"


def test_analyze_overkill_proposal():
    r = analyze_text_rule_based("PandaDoc is overpriced and overkill for simple proposal and SOW generation.")
    assert r.software == "PandaDoc"
    assert r.feature_bloat_score >= 3
    assert r.actual_workflow == "Proposal workflow"


def test_analyze_zapier():
    r = analyze_text_rule_based("Zapier pricing sucks for multi-step automation workflows. Need cheaper alternative.")
    assert r.software == "Zapier"
    assert r.pricing_signal == True
    assert r.actual_workflow == "Automation workflow"
    assert r.disruption_score > 5


def test_detect_workflow_unknown():
    r = analyze_text_rule_based("Some random software that does something unknown.")
    assert r.workflow_name == "Unknown"


def test_replacement_templates_exist():
    assert "CRM workflow" in REPLACEMENT_TEMPLATES
    assert "Proposal workflow" in REPLACEMENT_TEMPLATES
    assert "Automation workflow" in REPLACEMENT_TEMPLATES


def test_analyze_sentiment():
    r = analyze_text_rule_based("This software is absolutely terrible, way too expensive, completely overpriced!")
    assert r.pricing_signal == True
    assert r.emotion_score > 4
    assert r.sentiment_polarity < 0