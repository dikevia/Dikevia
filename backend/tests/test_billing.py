import hashlib
import hmac
import json

import pytest
from fastapi import HTTPException
from app.config import settings
from app.main import billing_checkout
from app.billing import PLANS, public_plans, verify_stripe_signature, extract_subscription_state


def test_current_catalogue_contains_only_agent_and_three_union_seat_tiers():
    plans = {plan["code"]: plan for plan in public_plans()}
    assert set(plans) == {
        "AGENT_5_QUESTIONS",
        "SYNDICAT_5_ACCES",
        "SYNDICAT_10_ACCES",
        "SYNDICAT_15_ACCES",
    }
    agent = plans["AGENT_5_QUESTIONS"]
    assert agent["amount_cents"] == 500
    assert agent["max_users"] == 1
    assert agent["daily_question_limit"] == 5
    assert agent["premium"] is False
    for code, seats in (
        ("SYNDICAT_5_ACCES", 5),
        ("SYNDICAT_10_ACCES", 10),
        ("SYNDICAT_15_ACCES", 15),
    ):
        plan = plans[code]
        assert plan["amount_cents"] is None
        assert plan["max_users"] == seats
        assert plan["daily_question_limit"] is None
        assert plan["premium"] is True
        assert plan["purchasable"] is False
    assert all(plan["purchasable"] is False for plan in plans.values())
    assert PLANS["ESSENTIEL"]["public"] is False
    assert PLANS["PRO"]["public"] is False
    assert PLANS["EQUIPE_INSTANCES"]["public"] is False
    assert PLANS["COLLECTIVITE_SYNDICATS"]["public"] is False
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
