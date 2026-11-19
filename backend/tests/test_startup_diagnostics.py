from app.config import Settings


def test_external_startup_diagnostics_are_disabled_by_default():
    assert Settings(_env_file=None).enable_external_startup_diagnostics is False


def test_external_startup_diagnostics_can_be_explicitly_enabled():
    assert Settings(_env_file=None, enable_external_startup_diagnostics=True).enable_external_startup_diagnostics is True
