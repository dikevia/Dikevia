"""Server-side subscription catalogue for Dikévia.

All prices are TTC integer cents. Legacy plans remain readable for existing
subscriptions; new catalogue entries are not a credit wallet implementation.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from typing import Any

PLANS: dict[str, dict[str, Any]] = {
    # New public catalogue. Credit allowances are descriptive until a
    # transactional server-side credit ledger is implemented.
    "ESSENTIEL": {"name": "Essentiel", "amount": 1490, "annual_amount": 14900, "currency": "eur", "interval": "month", "max_users": 1, "monthly_credits": 125, "public": True, "tax_inclusive": True},
    "PRO": {"name": "Pro", "amount": 2900, "annual_amount": 29000, "currency": "eur", "interval": "month", "max_users": 1, "monthly_credits": 248, "public": True, "tax_inclusive": True},
    "EQUIPE_INSTANCES": {"name": "Équipe & Instances", "amount": 11900, "annual_amount": 119000, "currency": "eur", "interval": "month", "max_users": 5, "monthly_credits": 1000, "public": True, "tax_inclusive": True},
    "COLLECTIVITE_SYNDICATS": {"name": "Collectivité & Syndicats", "amount": 29900, "annual_amount": 299000, "currency": "eur", "interval": "month", "max_users": 15, "monthly_credits": 2450, "public": True, "tax_inclusive": True},
    # Existing subscribers are grandfathered. Never delete or silently remap.
    "INDIVIDUAL_1": {"name": "Ancienne offre Individuel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 1, "public": False, "tax_inclusive": True},
    "SYNDICAT_10": {"name": "Ancienne offre Syndicat 10", "amount": 8000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
    "SYNDICAT_50": {"name": "Ancienne offre Syndicat 50", "amount": 30000, "currency": "eur", "interval": "month", "max_users": 50, "public": False, "tax_inclusive": True},
    "LEGACY_ESSENTIAL_3": {"name": "Ancienne offre Essentiel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 3, "public": False, "tax_inclusive": True},
    "LEGACY_SYNDICAT_10": {"name": "Ancienne offre Syndicat", "amount": 5000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
    "FOUNDING_FREE": {"name": "Accès offert organisation", "amount": 0, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "tax_inclusive": True},
}

CREDIT_PACKS: dict[str, dict[str, Any]] = {
    "CREDITS_200": {"name": "Recharge 200 crédits", "amount": 2900, "credits": 200, "currency": "eur", "public": True, "tax_inclusive": True},
    "CREDITS_600": {"name": "Recharge 600 crédits", "amount": 7900, "credits": 600, "currency": "eur", "public": True, "tax_inclusive": True},
}



def resolve_plan_price(plan_code: str, billing_interval: str = "month") -> tuple[int, str]:
    """Return the server-authoritative amount and Stripe recurring interval."""
    plan = PLANS.get(plan_code)
    if not plan or not plan.get("public", False):
        raise ValueError("Offre inconnue.")
    if billing_interval == "month":
        return int(plan["amount"]), "month"
    if billing_interval == "year" and plan.get("annual_amount") is not None:
        return int(plan["annual_amount"]), "year"
    raise ValueError("Périodicité de facturation invalide pour cette offre.")


def public_plans() -> list[dict[str, Any]]:
    return [
        {"code": code, "name": p["name"], "amount_cents": p["amount"],
         "annual_amount_cents": p.get("annual_amount"),
         "annual_billing_months": 10 if p.get("annual_amount") else None,
         "monthly_credits": p.get("monthly_credits"),
         "currency": p["currency"], "interval": p["interval"], "max_users": p["max_users"],
         "tax_behavior": "inclusive" if p.get("tax_inclusive") else "unspecified",
         "price": f"{p['amount'] / 100:.2f} € TTC" if p["amount"] else "Sur attribution",
         "description": f"Jusqu'à {p['max_users']} utilisateurs"}
        for code, p in PLANS.items() if p.get("public", False)
    ]


def public_credit_packs() -> list[dict[str, Any]]:
    return [{"code": code, "name": p["name"], "amount_cents": p["amount"],
             "credits": p["credits"], "currency": p["currency"],
             "tax_behavior": "inclusive" if p.get("tax_inclusive") else "unspecified"}
            for code, p in CREDIT_PACKS.items() if p.get("public", False)]


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
