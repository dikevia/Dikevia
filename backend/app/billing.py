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
    # Current catalogue. Syndicate prices remain unset until explicitly decided.
    "AGENT_5_QUESTIONS": {
        "name": "Agent", "amount": 500, "currency": "eur", "interval": "month",
        "max_users": 1, "daily_question_limit": 5, "premium": False,
        "public": True, "purchasable": False, "tax_inclusive": True,
    },
    "SYNDICAT_5_ACCES": {
        "name": "Syndicat · 5 accès", "amount": None, "currency": "eur",
        "interval": "month", "max_users": 5, "daily_question_limit": None,
        "premium": True, "public": True, "purchasable": False,
    },
    "SYNDICAT_10_ACCES": {
        "name": "Syndicat · 10 accès", "amount": None, "currency": "eur",
        "interval": "month", "max_users": 10, "daily_question_limit": None,
        "premium": True, "public": True, "purchasable": False,
    },
    "SYNDICAT_15_ACCES": {
        "name": "Syndicat · 15 accès", "amount": None, "currency": "eur",
        "interval": "month", "max_users": 15, "daily_question_limit": None,
        "premium": True, "public": True, "purchasable": False,
    },
    # Historical codes remain readable for existing subscription records only.
    # They are not published, cannot be purchased, and do not grant new premium tools.
    "ESSENTIEL": {"name": "Offre historique Essentiel", "amount": 1490, "currency": "eur", "interval": "month", "max_users": 1, "public": False, "purchasable": False},
    "PRO": {"name": "Offre historique Pro", "amount": 2900, "currency": "eur", "interval": "month", "max_users": 1, "public": False, "purchasable": False},
    "EQUIPE_INSTANCES": {"name": "Offre historique Équipe & Instances", "amount": 11900, "currency": "eur", "interval": "month", "max_users": 5, "public": False, "purchasable": False},
    "COLLECTIVITE_SYNDICATS": {"name": "Offre historique Collectivité & Syndicats", "amount": 29900, "currency": "eur", "interval": "month", "max_users": 15, "public": False, "purchasable": False},
    "INDIVIDUAL_1": {"name": "Ancienne offre Individuel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 1, "public": False, "purchasable": False},
    "SYNDICAT_10": {"name": "Ancienne offre Syndicat 10", "amount": 8000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "purchasable": False},
    "SYNDICAT_50": {"name": "Ancienne offre Syndicat 50", "amount": 30000, "currency": "eur", "interval": "month", "max_users": 50, "public": False, "purchasable": False},
    "LEGACY_ESSENTIAL_3": {"name": "Ancienne offre Essentiel", "amount": 1500, "currency": "eur", "interval": "month", "max_users": 3, "public": False, "purchasable": False},
    "LEGACY_SYNDICAT_10": {"name": "Ancienne offre Syndicat", "amount": 5000, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "purchasable": False},
    "FOUNDING_FREE": {"name": "Accès fondateur", "amount": 0, "currency": "eur", "interval": "month", "max_users": 10, "public": False, "purchasable": False},
}

SYNDICATE_PLAN_CODES = frozenset({
    "SYNDICAT_5_ACCES", "SYNDICAT_10_ACCES", "SYNDICAT_15_ACCES",
})


def public_plans() -> list[dict[str, Any]]:
    """Return only the current two-category catalogue; unset syndicate prices stay unset."""
    plans = []
    for code, plan in PLANS.items():
        if not plan.get("public", False):
            continue
        amount = plan.get("amount")
        plans.append({
            "code": code,
            "name": plan["name"],
            "amount_cents": amount,
            "currency": plan["currency"],
            "interval": plan["interval"],
            "max_users": plan["max_users"],
            "daily_question_limit": plan.get("daily_question_limit"),
            "premium": bool(plan.get("premium", False)),
            "purchasable": bool(plan.get("purchasable", False)),
            "tax_behavior": "inclusive" if plan.get("tax_inclusive") else "unspecified",
            "price": f"{amount / 100:.2f} € TTC / mois" if amount is not None else None,
            "description": (
                "Chatbot juridique uniquement · 5 questions par jour"
                if code == "AGENT_5_QUESTIONS"
                else f"{plan['max_users']} accès · toutes les fonctionnalités · utilisation sans quota quotidien"
            ),
        })
    return plans


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
