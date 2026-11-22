import hashlib
import hmac
import json

import pytest
from fastapi import HTTPException
from app.config import settings
from app.main import billing_checkout
from app.billing import PLANS, public_plans, verify_stripe_signature, extract_subscription_state


def test_official_offers_have_exact_ttc_prices_seats_and_monthly_credits():
    expected = {
        "ESSENTIEL": (1490, 14900, 1, 125),
        "PRO": (2900, 29000, 1, 248),
        "EQUIPE_INSTANCES": (11900, 119000, 5, 1000),
        "COLLECTIVITE_SYNDICATS": (29900, 299000, 15, 2450),
    }
    plans = {plan["code"]: plan for plan in public_plans()}
    assert set(plans) == set(expected)
    for code, (monthly, annual, seats, credits) in expected.items():
        assert PLANS[code]["amount"] == monthly
        assert PLANS[code]["annual_amount"] == annual
        assert PLANS[code]["max_users"] == seats
        assert PLANS[code]["monthly_credits"] == credits
        assert PLANS[code]["tax_inclusive"] is True
        assert plans[code]["amount_cents"] == monthly
        assert plans[code]["annual_amount_cents"] == annual
        assert plans[code]["monthly_credits"] == credits
        assert "TTC" in plans[code]["price"]
    assert len(public_plans()) == 4
    assert "INDIVIDUAL_1" not in plans
    assert PLANS["INDIVIDUAL_1"]["public"] is False


def test_stripe_signature_valid_and_tampered_payload_rejected():
    secret = "whsec_test"
    payload = b'{"id":"evt_123"}'
    timestamp = 1700000000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={digest}"
    assert verify_stripe_signature(payload, header, secret, now=timestamp)
    assert not verify_stripe_signature(payload + b" ", header, secret, now=timestamp)
    assert not verify_stripe_signature(payload, header, secret, now=timestamp + 900)


def test_checkout_event_maps_org_and_plan():
    event = {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": "org-1", "customer": "cus_1", "subscription": "sub_1",
        "metadata": {"plan_code": "ESSENTIAL_3"}}}}
    state = extract_subscription_state(event)
    assert state["organization_id"] == "org-1"
    assert state["status"] == "ACTIVE"
    assert state["plan_code"] == "ESSENTIAL_3"


def test_unrecognized_event_is_ignored():
    assert extract_subscription_state({"type": "customer.created", "data": {"object": {}}}) is None

@pytest.mark.asyncio
async def test_checkout_is_blocked_until_monthly_credit_enforcement_is_live(monkeypatch):
    monkeypatch.setattr(settings, "private_instance_mode", False)
    with pytest.raises(HTTPException) as exc:
        await billing_checkout({"plan_code": "ESSENTIEL"})
    assert exc.value.status_code == 503
    assert "compteur de crédits mensuels" in exc.value.detail
