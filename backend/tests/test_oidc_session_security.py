"""Security boundary tests for the opt-in OIDC BFF session flow."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth_sessions
from app.config import settings


def _request(origin=None):
    headers = []
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/v1/auth/oidc/logout",
        "raw_path": b"/api/v1/auth/oidc/logout",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    })


def test_oidc_bff_accepts_only_an_explicit_same_origin_request(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://app.example,https://staging.example")
    assert auth_sessions.require_same_origin(_request("https://app.example")) is None
    assert auth_sessions.require_same_origin(_request("https://staging.example/")) is None


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_oidc_bff_rejects_missing_or_untrusted_origin(monkeypatch, origin):
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    with pytest.raises(HTTPException) as error:
        auth_sessions.require_same_origin(_request(origin))
    assert error.value.status_code == 403


def test_oidc_redirect_uri_must_be_https_and_match_an_allowed_origin(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://app.example/")
    assert auth_sessions._redirect_uri() == "https://app.example/"

    monkeypatch.setattr(settings, "oidc_redirect_uri", "http://app.example/")
    with pytest.raises(HTTPException) as error:
        auth_sessions._redirect_uri()
    assert error.value.status_code == 503

    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://attacker.example/")
    with pytest.raises(HTTPException) as error:
        auth_sessions._redirect_uri()
    assert error.value.status_code == 503


def test_oidc_redirect_uri_rejects_non_root_callback_paths(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://app.example/callback")
    with pytest.raises(HTTPException) as error:
        auth_sessions._redirect_uri()
    assert error.value.status_code == 503
