"""Small, auditable Stripe Billing adapter for CFDT JURIS.

Prices are server-side constants; the browser never supplies an amount.
The webhook signature is verified before any database mutation.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from typing import Any

PLANS: dict[str, dict[str, Any]] = {
    # Official Dikévia catalogue. Prices are TTC; credits are monthly.
    "ESSENTIEL": {"name": "Essentiel", "amount": 1490, "annual_amount": 14900, "currency": "eur", "interval": "month", "annual_interval": "year", "max_users": 1, "monthly_credits": 125, "public": True, "tax_inclusive": True},
    "PRO": {"name": "Pro", "amount": 2900, "annual_amount": 29000, "currency": "eur", "interval": "month", "annual_interval": "year", "max_users": 1, "monthly_credits": 248, "public": True, "tax_inclusive": True},
    "EQUIPE_INSTANCES": {"name": "Équipe & Instances", "amount": 11900, "annual_amount": 119000, "currency": "eur", "interval": "month", "annual_interval": "year", "max_users": 5, "monthly_credits": 1000, "public": True, "tax_inclusive": True},
    "COLLECTIVITE_SYNDICATS": {"name": "Collectivité & Syndicats", "amount": 29900, "annual_amount": 299000, "currency": "eur", "interval": "month", "annual_interval": "year", "max_users": 15, "monthly_credits": 2450, "public": True, "tax_inclusive": True},
    # Existing subscriptions are preserved, but these obsolete offers are no longer sold.
    "INDIVIDUAL_1": {"name": "Ancienne offre Individuel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 1, "public": False, "tax_inclusive": True},
    "SYNDICAT_10": {"name": "Ancienne offre Syndicat 10", "amount": 8000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
    "SYNDICAT_50": {"name": "Ancienne offre Syndicat 50", "amount": 30000, "currency": "eur", "interval": "month", "max_users": 50, "public": False, "tax_inclusive": True},
    "LEGACY_ESSENTIAL_3": {"name": "Ancienne offre Essentiel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 3, "public": False, "tax_inclusive": True},
    "LEGACY_SYNDICAT_10": {"name": "Ancienne offre Syndicat", "amount": 5000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
    "FOUNDING_FREE": {"name": "Accès offert organisation", "amount": 0, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
}


def public_plans() -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "name": plan["name"],
            "amount_cents": plan["amount"],
            "annual_amount_cents": plan["annual_amount"],
            "currency": plan["currency"],
            "interval": plan["interval"],
            "annual_interval": plan["annual_interval"],
            "max_users": plan["max_users"],
            "monthly_credits": plan["monthly_credits"],
            "tax_behavior": "inclusive",
            "price": f"{plan['amount'] / 100:.2f} € TTC / mois",
            "annual_price": f"{plan['annual_amount'] / 100:.2f} € TTC / an",
            "description": f"{plan['max_users']} accès · {plan['monthly_credits']} crédits par mois",
        }
        for code, plan in PLANS.items()
        if plan.get("public", False)
    ]


def verify_stripe_signature(payload: bytes, header: str | None, secret: str,
                            tolerance_seconds: int = 300, now: int | None = None) -> bool:
    if not header or not secret:
        return False
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, sep, value = item.partition("=")
        if sep:
            parts.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(parts["t"][0])
        signatures = parts["v1"]
    except (KeyError, IndexError, ValueError):
        return False
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        return False
    signed = str(timestamp).encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def extract_subscription_state(event: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize only supported Stripe event shapes; ignore unrelated events."""
    event_type = event.get("type")
    obj = ((event.get("data") or {}).get("object") or {})
    metadata = obj.get("metadata") or {}
    org_id = metadata.get("organization_id")
    if event_type == "checkout.session.completed":
        org_id = org_id or obj.get("client_reference_id")
        if not org_id:
            return None
        return {"organization_id": org_id, "provider_customer_id": obj.get("customer"),
                "provider_subscription_id": obj.get("subscription"), "plan_code": metadata.get("plan_code"),
                "status": "ACTIVE"}
    if event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        if not org_id:
            return None
        status = "CANCELED" if event_type.endswith("deleted") else {
            "active": "ACTIVE", "trialing": "TRIAL", "past_due": "PAST_DUE",
            "unpaid": "SUSPENDED", "canceled": "CANCELED", "incomplete": "PAST_DUE",
            "incomplete_expired": "CANCELED", "paused": "SUSPENDED",
        }.get(obj.get("status"), "PAST_DUE")
        return {"organization_id": org_id, "provider_customer_id": obj.get("customer"),
                "provider_subscription_id": obj.get("id"), "plan_code": metadata.get("plan_code"),
                "status": status, "current_period_end": obj.get("current_period_end"),
                "cancel_at_period_end": bool(obj.get("cancel_at_period_end"))}
    if event_type in {"invoice.payment_failed", "invoice.paid"}:
        subscription_id = obj.get("subscription") or ((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        invoice_metadata = obj.get("metadata") or ((obj.get("parent") or {}).get("subscription_details") or {}).get("metadata") or {}
        org_id = invoice_metadata.get("organization_id")
        if not subscription_id or not org_id:
            return None
        return {"organization_id": org_id, "provider_subscription_id": subscription_id,
                "status": "PAST_DUE" if event_type.endswith("failed") else "ACTIVE"}
    return None


def stripe_form_encode(fields: dict[str, str]) -> dict[str, str]:
    """Kept as a tiny helper so tests can assert trusted server-generated fields."""
    return {k: str(v) for k, v in fields.items()}
