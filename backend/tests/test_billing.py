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



def test_resolve_plan_price_supports_monthly_and_annual_server_prices():
    from app.billing import resolve_plan_price

    assert resolve_plan_price("ESSENTIEL", "month") == (1490, "month")
    assert resolve_plan_price("ESSENTIEL", "year") == (14900, "year")
    assert resolve_plan_price("COLLECTIVITE_SYNDICATS", "year") == (299000, "year")


def test_resolve_plan_price_rejects_unknown_private_and_invalid_intervals():
    from app.billing import resolve_plan_price
    import pytest

    with pytest.raises(ValueError):
        resolve_plan_price("FOUNDING_FREE", "month")
    with pytest.raises(ValueError):
        resolve_plan_price("UNKNOWN", "year")
    with pytest.raises(ValueError):
        resolve_plan_price("PRO", "weekly")


def test_founder_access_remains_zero_cost_private_and_outside_checkout():
    founder = PLANS["FOUNDING_FREE"]
    assert founder["amount"] == 0
    assert founder["public"] is False
    assert founder["max_users"] == 10
    assert "annual_amount" not in founder
    assert "FOUNDING_FREE" not in {plan["code"] for plan in public_plans()}




def test_stripe_billing_is_disabled_by_default_even_when_secrets_exist():
    from app.config import Settings

    assert Settings(_env_file=None).stripe_billing_enabled is False
    configured = Settings(_env_file=None, stripe_secret_key="sk_test_example",
                          stripe_webhook_secret="whsec_example")
    assert configured.stripe_billing_enabled is False



def test_stripe_checkout_and_portal_routes_are_blocked_before_network_calls(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from app.main import app, settings

    monkeypatch.setattr(settings, "private_instance_mode", False)
    monkeypatch.setattr(settings, "stripe_billing_enabled", False)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_present")
    ctx = SimpleNamespace(organization_id="00000000-0000-0000-0000-000000000001",
                          user_id="00000000-0000-0000-0000-000000000002")

    checkout = next(route.endpoint for route in app.routes
                    if getattr(route, "path", None) == "/api/v1/billing/checkout")
    portal = next(route.endpoint for route in app.routes
                  if getattr(route, "path", None) == "/api/v1/billing/portal")

    with pytest.raises(HTTPException) as checkout_error:
        asyncio.run(checkout({"plan_code": "ESSENTIEL"}, ctx))
    with pytest.raises(HTTPException) as portal_error:
        asyncio.run(portal(ctx))

    assert checkout_error.value.status_code == 404
    assert portal_error.value.status_code == 404


def test_stripe_webhook_route_is_blocked_before_body_or_database_access(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from app.main import app, settings

    class RequestMustNotBeRead:
        headers = {}
        async def body(self):
            raise AssertionError("Le webhook désactivé ne doit même pas lire le corps.")

    monkeypatch.setattr(settings, "private_instance_mode", False)
    monkeypatch.setattr(settings, "stripe_billing_enabled", False)
    webhook = next(route.endpoint for route in app.routes
                   if getattr(route, "path", None) == "/api/v1/billing/stripe/webhook")

    with pytest.raises(HTTPException) as error:
        asyncio.run(webhook(RequestMustNotBeRead()))

    assert error.value.status_code == 404



def test_stripe_billing_opt_in_requires_both_secrets():
    import pytest
    from app.config import Settings, validate_runtime_configuration

    config = Settings(_env_file=None, stripe_billing_enabled=True)
    with pytest.raises(RuntimeError, match="STRIPE_BILLING_ENABLED"):
        validate_runtime_configuration(config)
