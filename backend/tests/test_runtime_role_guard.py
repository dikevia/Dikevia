import pytest


class RuntimeRoleConnection:
    def __init__(self, role):
        self.role = role
        self.checked = False

    async def fetchrow(self, query):
        assert "rolsuper" in query and "rolbypassrls" in query
        self.checked = True
        return self.role


class RuntimeRolePool:
    def __init__(self, role):
        self.connection = RuntimeRoleConnection(role)

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_runtime_role_guard_checks_every_configured_pool(monkeypatch):
    from app import db

    api = RuntimeRolePool({"rolsuper": False, "rolbypassrls": False})
    ingest = RuntimeRolePool({"rolsuper": False, "rolbypassrls": False})
    platform = RuntimeRolePool({"rolsuper": False, "rolbypassrls": False})
    monkeypatch.setattr(db, "_pool", api)
    monkeypatch.setattr(db, "_ingest_pool", ingest)
    monkeypatch.setattr(db, "_platform_admin_pool", platform)

    await db.assert_runtime_role_is_safe()

    assert api.connection.checked
    assert ingest.connection.checked
    assert platform.connection.checked


@pytest.mark.parametrize(
    ("unsafe_pool", "expected_label"),
    [
        ("_pool", "API"),
        ("_ingest_pool", "ingestion du corpus"),
        ("_platform_admin_pool", "administration de plateforme"),
    ],
)
@pytest.mark.parametrize("privilege", ["rolsuper", "rolbypassrls"])
@pytest.mark.asyncio
async def test_runtime_role_guard_rejects_privileged_role_in_every_pool(
    monkeypatch, unsafe_pool, expected_label, privilege
):
    from app import db

    safe = RuntimeRolePool({"rolsuper": False, "rolbypassrls": False})
    unsafe_role = {"rolsuper": False, "rolbypassrls": False}
    unsafe_role[privilege] = True
    unsafe = RuntimeRolePool(unsafe_role)
    monkeypatch.setattr(db, "_pool", safe)
    monkeypatch.setattr(db, "_ingest_pool", safe)
    monkeypatch.setattr(db, "_platform_admin_pool", safe)
    monkeypatch.setattr(db, unsafe_pool, unsafe)

    with pytest.raises(RuntimeError, match=expected_label):
        await db.assert_runtime_role_is_safe()


@pytest.mark.asyncio
async def test_runtime_role_guard_skips_unconfigured_optional_pools(monkeypatch):
    from app import db

    api = RuntimeRolePool({"rolsuper": False, "rolbypassrls": False})
    monkeypatch.setattr(db, "_pool", api)
    monkeypatch.setattr(db, "_ingest_pool", None)
    monkeypatch.setattr(db, "_platform_admin_pool", None)

    await db.assert_runtime_role_is_safe()

    assert api.connection.checked
