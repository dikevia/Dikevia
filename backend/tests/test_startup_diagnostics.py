from app.config import Settings


def test_external_startup_diagnostics_are_disabled_by_default():
    assert Settings().enable_external_startup_diagnostics is False


def test_external_startup_diagnostics_can_be_explicitly_enabled():
    assert Settings(enable_external_startup_diagnostics=True).enable_external_startup_diagnostics is True
