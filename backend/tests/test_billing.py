import hashlib
import hmac
import json
from app.billing import PLANS, public_plans, verify_stripe_signature, extract_subscription_state


def test_offers_have_expected_server_side_prices_and_limits():
    assert PLANS["INDIVIDUAL_1"]["amount"] == 1500
    assert PLANS["INDIVIDUAL_1"]["max_users"] == 1
    assert PLANS["SYNDICAT_10"]["amount"] == 8000
    assert PLANS["SYNDICAT_10"]["max_users"] == 10
    assert PLANS["SYNDICAT_50"]["amount"] == 30000
    assert PLANS["SYNDICAT_50"]["max_users"] == 50
    assert all(p["amount_cents"] in (1500,8000,30000) for p in public_plans())
    assert len(public_plans()) == 3
    assert "LEGACY_SYNDICAT_10" not in {p["code"] for p in public_plans()}


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


def test_public_prices_are_ttc_inclusive_and_server_side():
    plans = {p["code"]: p for p in public_plans()}
    assert plans["INDIVIDUAL_1"]["amount_cents"] == 1500
    assert plans["SYNDICAT_10"]["amount_cents"] == 8000
    assert plans["SYNDICAT_50"]["amount_cents"] == 30000
    assert set(plans) == {"INDIVIDUAL_1", "SYNDICAT_10", "SYNDICAT_50"}
    assert all(PLANS[code]["tax_inclusive"] for code in plans)
