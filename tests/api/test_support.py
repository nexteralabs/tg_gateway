"""Deploy checks served to the SRE agent."""
from unittest.mock import AsyncMock, patch


async def test_manifest_lists_healthz_and_database_checks(client):
    resp = await client.get("/support/manifest")
    assert resp.status_code == 200
    checks = resp.json()["deploy_checks"]
    assert [c["name"] for c in checks] == ["healthz", "database"]
    assert all(c["method"] == "GET" and c["url"].startswith("http://tg-gateway:8100/") for c in checks)


async def test_database_check_passes_when_the_query_answers(client):
    async def fake_get_conn():
        yield object()

    with (
        patch("tg_gateway.api.support.db.get_conn", new=fake_get_conn),
        patch("tg_gateway.api.support.db.fetchone", new=AsyncMock(return_value={"ok": 1})),
    ):
        resp = await client.get("/support/checks/database")
    assert resp.status_code == 200


async def test_database_check_fails_when_the_database_is_down(client):
    async def broken_get_conn():
        raise ConnectionError("refused")
        yield  # pragma: no cover

    with patch("tg_gateway.api.support.db.get_conn", new=broken_get_conn):
        resp = await client.get("/support/checks/database")
    assert resp.status_code == 503
    assert resp.json()["ok"] is False
