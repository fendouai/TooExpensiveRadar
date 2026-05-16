import json
import re
from typing import Optional


EXTRACTION_PROMPT = """You are a SaaS alternative researcher. Given a user complaint about a software being too expensive or bloated, extract any named alternative software that the user mentions.

Return a JSON array of alternative SaaS names. Each entry should be the name of a specific SaaS product (not a generic category like "AI" or "automation tool").

Complaint: "{content}"

Rules:
- Only include software that is explicitly mentioned as an alternative or replacement
- Use proper capitalization of the SaaS name
- Include only real, named SaaS products
- If no alternatives are mentioned, return an empty array []

Example output: ["n8n", "Make", "Pipedrive"]

Return only valid JSON, no markdown formatting, no explanation."""

INFERENCE_PROMPT = """Given search results about "{saas_name}", determine if this SaaS has an affiliate program and identify its pricing model.

Search results:
{search_results}

Return a JSON object with these fields:
- affiliate_support: "confirmed" if affiliate program clearly exists, "likely" if partners/referral programs exist, "undetermined" if unclear
- affiliate_url: the URL to join the affiliate program if found, otherwise ""
- pricing_tier: "free", "freemium", "tiered", "per_user", "transaction", "enterprise", or "unknown"
- price_summary: a brief 1-sentence summary of pricing from the search results

Return only valid JSON, no markdown, no explanation."""

INFER_FROM_CONTEXT_PROMPT = """A user mentioned "{alt_name}" as an alternative to "{original}" in this context:
"{context}"

Based on this mention only (no external data), is "{alt_name}" likely to:
1. Have an affiliate program? (likely yes/no/unsure)
2. Be cheaper than "{original}"? (yes/no/unsure)
3. What category does it fall in? (automation, crm, project_management, etc.)

Return JSON:
{{"affiliate_likelihood": "likely_yes|likely_no|unsure", "cheaper": "yes|no|unsure", "category": "..."}}

Return only valid JSON."""


def extract_alternatives_from_text(content: str) -> list[str]:
    content_lower = content.lower()

    known_alternatives = {
        "n8n": "n8n",
        "make": "Make",
        "integrately": "Integrately",
        "pabbly": "Pabbly",
        "workato": "Workato",
        "ifttt": "IFTTT",
        "pipedrive": "Pipedrive",
        "activecampaign": "ActiveCampaign",
        "hubspot": "HubSpot",
        "mailchimp": "Mailchimp",
        "klaviyo": "Klaviyo",
        "convertkit": "ConvertKit",
        "sendgrid": "SendGrid",
        "trello": "Trello",
        "asana": "Asana",
        "clickup": "ClickUp",
        "monday": "Monday.com",
        "notion": "Notion",
        "coda": "Coda",
        "slack": "Slack",
        "discord": "Discord",
        "zendesk": "Zendesk",
        "intercom": "Intercom",
        "freshdesk": "Freshdesk",
        "helpscout": "HelpScout",
        "linear": "Linear",
        "github": "GitHub",
        "gitlab": "GitLab",
        "bitbucket": "Bitbucket",
        "airtable": "Airtable",
        "baserow": "Baserow",
        "jira": "Jira",
        "shortcut": "Shortcut",
        "basecamp": "Basecamp",
        "wrike": "Wrike",
        "proofhub": "ProofHub",
        "zoho": "Zoho",
        "freshsales": "Freshsales",
        "nutshell": "Nutshell",
        "close": "Close",
        "pandadoc": "PandaDoc",
        "docusign": "DocuSign",
        "hellosign": "HelloSign",
        "signrequest": "SignRequest",
        "confluence": "Confluence",
        "gitbook": "GitBook",
        "mintlify": "Mintlify",
        "stripe": "Stripe",
        "shopify": "Shopify",
        "woocommerce": "WooCommerce",
        "salesforce": "Salesforce",
        "servicenow": "ServiceNow",
        "quickbase": "QuickBase",
        "smartsheet": "Smartsheet",
        "dropbox": "Dropbox",
        "box": "Box",
        "temporal": "Temporal",
        "prefect": "Prefect",
        "dagster": "Dagster",
        "airflow": "Airflow",
        "buffer": "Buffer",
        "hootsuite": "Hootsuite",
        "later": "Later",
        "metricool": "Metricool",
        "canva": "Canva",
        "figma": "Figma",
        "sketch": "Sketch",
        "invision": "InVision",
        "zeplin": "Zeplin",
        "abstract": "Abstract",
        "webflow": "Webflow",
        "squarespace": "Squarespace",
        "wix": "Wix",
        "wordpress": "WordPress",
        "framer": "Framer",
        "appsheet": "AppSheet",
        "powerapps": "PowerApps",
        "retool": "Retool",
        "internalio": "Internal",
        "burner": "Burner",
        "textmagic": "TextMagic",
        "messagebird": "MessageBird",
        "twilio": "Twilio",
        "plivo": "Plivo",
        "nexmo": "Nexmo",
        "segment": "Segment",
        "mparticle": "mParticle",
        "snowflake": "Snowflake",
        "bigquery": "BigQuery",
        "redshift": "Redshift",
        "databricks": "Databricks",
    }

    found = []
    content_normalized = re.sub(r"[^\w\s]", " ", content_lower)
    for name_lower, name_proper in known_alternatives.items():
        if name_lower in content_normalized or name_lower in content_lower:
            found.append(name_proper)

    return list(dict.fromkeys(found))


async def infer_affiliate_from_context(
    alt_name: str,
    original: str,
    context: str,
    llm=None,
) -> dict:
    if llm:
        try:
            prompt = INFER_FROM_CONTEXT_PROMPT.format(
                alt_name=alt_name,
                original=original,
                context=context[:500],
            )
            result = await llm.complete(prompt)
            data = json.loads(result.content)
            return {
                "affiliate_likelihood": data.get("affiliate_likelihood", "unsure"),
                "cheaper": data.get("cheaper", "unsure"),
                "category": data.get("category", "unknown"),
                "source": "llm_inference",
            }
        except Exception:
            pass

    return {
        "affiliate_likelihood": "unsure",
        "cheaper": "unsure",
        "category": "unknown",
        "source": "llm_inference",
    }


def parse_llm_extraction(raw: str) -> list[str]:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if isinstance(x, str)]
    except json.JSONDecodeError:
        pass
    name_pattern = re.findall(r'"([A-Za-z][A-Za-z0-9 ._]{1,30})"', raw)
    if name_pattern:
        return name_pattern
    return []