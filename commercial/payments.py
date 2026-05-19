from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: str = "single_report"
    email: str | None = None


REPORT_PRODUCTS = {
    "single_report": {
        "name": "Too Expensive Radar Report",
        "env": "DODO_REPORT_PRODUCT_ID",
        "price": "$49",
        "cadence": "one-time",
    },
    "monthly": {
        "name": "Monthly Radar Brief",
        "env": "DODO_MONTHLY_PRODUCT_ID",
        "price": "$149/mo",
        "cadence": "monthly",
    },
}


def payment_configured(plan: str = "single_report") -> bool:
    product = REPORT_PRODUCTS.get(plan, REPORT_PRODUCTS["single_report"])
    return bool(os.getenv("DODO_PAYMENTS_API_KEY") and os.getenv(product["env"]))


def public_products() -> list[dict[str, str]]:
    return [
        {
            "id": key,
            "name": product["name"],
            "price": product["price"],
            "cadence": product["cadence"],
            "configured": str(payment_configured(key)).lower(),
        }
        for key, product in REPORT_PRODUCTS.items()
    ]


async def create_checkout_session(req: CheckoutRequest) -> dict[str, Any]:
    product = REPORT_PRODUCTS.get(req.plan)
    if not product:
        raise ValueError("Unknown report plan")

    api_key = os.getenv("DODO_PAYMENTS_API_KEY", "")
    product_id = os.getenv(product["env"], "")
    if not api_key or not product_id:
        missing = [
            name
            for name, value in {
                "DODO_PAYMENTS_API_KEY": api_key,
                product["env"]: product_id,
            }.items()
            if not value
        ]
        return {
            "configured": False,
            "missing": missing,
            "message": "Dodo Payments is not configured yet.",
        }

    environment = os.getenv("DODO_PAYMENTS_ENV", "test").lower()
    default_base = "https://live.dodopayments.com" if environment == "live" else "https://test.dodopayments.com"
    base_url = os.getenv("DODO_PAYMENTS_BASE_URL", default_base).rstrip("/")
    site_url = os.getenv("COMMERCIAL_SITE_URL", "http://localhost:8000").rstrip("/")

    payload: dict[str, Any] = {
        "product_cart": [{"product_id": product_id, "quantity": 1}],
        "return_url": os.getenv("DODO_RETURN_URL", f"{site_url}/commercial?checkout=success"),
        "cancel_url": os.getenv("DODO_CANCEL_URL", f"{site_url}/commercial?checkout=cancelled"),
        "metadata": {
            "product": product["name"],
            "plan": req.plan,
            "source": "too_expensive_radar_commercial",
        },
        "allowed_payment_method_types": ["credit", "debit"],
    }
    if req.email:
        payload["metadata"]["email"] = req.email

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{base_url}/checkouts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    return {
        "configured": True,
        "session_id": data.get("session_id"),
        "checkout_url": data.get("checkout_url"),
    }
