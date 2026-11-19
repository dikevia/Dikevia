import hashlib
import hmac
from app.billing import (
    PLANS, CREDIT_PACKS, public_plans, public_credit_packs,
    verify_stripe_signature, extract_subscription_state,
)


def test_four_public_offers_have_expected_prices_seats_and_credit_allowances():
    expected = {
        "ESSENTIEL": (1490, 14900, 1, 125),
        "PRO": (2900, 29000, 1, 248),
        "EQUIPE_INSTANCES": (11900, 119000, 5, 1000),
        "COLLECTIVITE_SYNDICATS": (29900, 299000, 15, 2450),
    }
    public = {p["code"]: p for p in public_plans()}
    assert set(public) == set(expected)
    for code, (monthly, annual, seats, credits) in expected.items():
        assert PLANS[code]["amount"] == monthly
        assert public[code]["annual_amount_cents"] == annual
        assert public[code]["max_users"] == seats
        assert public[code]["monthly_credits"] == credits
        assert PLANS[code]["tax_inclusive"] is True


def test_legacy_plans_remain_available_for_existing_subscriptions_but_not_public():
    assert PLANS["LEGACY_ESSENTIAL_3"]["max_users"] == 3
    assert PLANS["LEGACY_SYNDICAT_10"]["max_users"] == 10
    assert "LEGACY_ESSENTIAL_3" not in {p["code"] for p in public_plans()}
    assert "INDIVIDUAL_1" not in {p["code"] for p in public_plans()}


def test_recharge_packs_have_server_side_prices_and_credit_amounts():
    packs = {p["code"]: p for p in public_credit_packs()}
    assert packs["CREDITS_200"]["amount_cents"] == 2900
    assert packs["CREDITS_200"]["credits"] == 200
    assert packs["CREDITS_600"]["amount_cents"] == 7900
    assert packs["CREDITS_600"]["credits"] == 600


def test_stripe_signature_valid_and_tampered_payload_rejected():
    secret = "whsec_test"
    payload = b'{"id":"evt_123"}'
    timestamp = 1700000000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={digest}"
    assert verify_stripe_signature(payload, header, secret, now=timestamp)
    assert not verify_stripe_signature(payload + b" ", header, secret, now=timestamp)
    assert not verify_stripe_signature(payload, header, secret, now=timestamp + 900)


def test_checkout_event_maps_org_and_new_plan():
    event = {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": "org-1", "customer": "cus_1", "subscription": "sub_1",
        "metadata": {"plan_code": "ESSENTIEL"}}}}
    state = extract_subscription_state(event)
    assert state["organization_id"] == "org-1"
    assert state["status"] == "ACTIVE"
    assert state["plan_code"] == "ESSENTIEL"


def test_unrecognized_event_is_ignored():
    assert extract_subscription_state({"type": "customer.created", "data": {"object": {}}}) is None
