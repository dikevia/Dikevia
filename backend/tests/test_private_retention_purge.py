import pytest

from scripts.purge_private_conversations import (
    parse_args,
    parse_cutoff,
    validate_confirmation,
)


def test_retention_cutoff_requires_explicit_timezone():
    cutoff = parse_cutoff("2026-01-01T00:00:00Z")
    assert cutoff.isoformat() == "2026-01-01T00:00:00+00:00"


def test_retention_cutoff_rejects_timezone_naive_value():
    with pytest.raises(Exception, match="fuseau horaire"):
        parse_cutoff("2026-01-01T00:00:00")


def test_retention_cutoff_rejects_invalid_iso_value():
    with pytest.raises(Exception, match="ISO-8601"):
        parse_cutoff("pas-une-date")


def test_purge_requires_two_explicit_confirmation_flags():
    with pytest.raises(ValueError, match="--confirm-delete"):
        validate_confirmation(True, False)
    with pytest.raises(ValueError, match="--execute"):
        validate_confirmation(False, True)
    validate_confirmation(False, False)
    validate_confirmation(True, True)


def test_cli_requires_explicit_cutoff():
    with pytest.raises(SystemExit) as error:
        parse_args([])
    assert error.value.code == 2
