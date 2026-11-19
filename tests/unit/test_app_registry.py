"""Self-registration in the App Registry."""
import json
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from tg_gateway import app_registry
from tg_gateway.core.config import Settings

REGISTRY = "http://registry.test"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_creates_the_app_when_not_registered():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "x1", "name": "other-app"}])
        return httpx.Response(201, json={"id": "new"})

    async with _client(handler) as client:
        assert await app_registry.register_self(REGISTRY, "1.2.3", client=client) is True

    assert [(c.method, c.url.path) for c in calls] == [("GET", "/apps"), ("POST", "/apps")]
    body = json.loads(calls[1].content)
    assert body == {**app_registry.APP_RECORD, "version": "1.2.3"}
    # internal URLs: the SRE probes the container name
    assert body["health_endpoint"] == "http://tg-gateway:8100/healthz"
    assert body["support_manifest_endpoint"] == "http://tg-gateway:8100/support/manifest"


async def test_updates_the_app_when_already_registered():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "abc", "name": "tg-gateway"}])
        return httpx.Response(200, json={"id": "abc"})

    async with _client(handler) as client:
        await app_registry.register_self(REGISTRY, "1.2.4", client=client)

    assert [(c.method, c.url.path) for c in calls] == [("GET", "/apps"), ("PATCH", "/apps/abc")]
    assert json.loads(calls[1].content)["version"] == "1.2.4"


async def test_registry_down_is_reported_not_raised():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with _client(handler) as client:
        assert await app_registry.register_self(REGISTRY, "1.2.3", client=client) is False


async def test_no_registration_without_a_registry_url():
    with patch.object(app_registry.settings, "APP_REGISTRY_URL", None):
        assert app_registry.start_registration() is None


def test_registry_url_requires_a_version():
    base = dict(
        TELEGRAM_BOT_TOKEN="123456789:AABBCCDDEEFFaabbccddeeff-1234567890",
        TELEGRAM_TARGET_CHAT_ID="-1001",
        DATABASE_URL="postgresql+psycopg://u:p@h:5432/d",
        CALLBACK_SIGNING_SECRET="test-signing-secret-32-chars-long!",
    )
    with pytest.raises(ValidationError, match="APP_VERSION"):
        Settings(_env_file=None, APP_REGISTRY_URL="http://r:8002", **base)
    ok = Settings(_env_file=None, APP_REGISTRY_URL="http://r:8002", APP_VERSION="0.1.51", **base)
    assert ok.APP_VERSION == "0.1.51"
