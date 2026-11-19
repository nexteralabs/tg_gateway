"""Self-registration in the ASF App Registry (ne-app-registry-srv).

The SRE agent watches every app listed there: it probes `health_endpoint`, reads the deploy checks at
`support_manifest_endpoint` when the version goes up, and rolls back through this repo's `deploy.yml`.
The URLs are internal (container name on asf_asf-network).
"""

import asyncio
import logging

import httpx

from .core.config import settings

logger = logging.getLogger(__name__)

SERVICE_NAME = "tg-gateway"
BASE_URL = f"http://{SERVICE_NAME}:8100"

APP_RECORD = {
    "name": SERVICE_NAME,
    "repo_url": "https://github.com/nexteralabs/tg_gateway",
    "live_endpoint": "http://localhost:8100",
    "service_name": SERVICE_NAME,
    "health_endpoint": f"{BASE_URL}/healthz",
    "health_interval_s": 60,
    "support_manifest_endpoint": f"{BASE_URL}/support/manifest",
}

RETRY_S = 10
REFRESH_S = 600


async def register_self(
    registry_url: str, version: str, client: httpx.AsyncClient | None = None
) -> bool:
    """Create or update this app's record. Returns False (and logs) on failure, never raises.

    The registry has no upsert and names are unique: look the app up by name, PATCH it if it exists.
    """
    payload = {**APP_RECORD, "version": version}
    base = registry_url.rstrip("/")
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=10.0)
    try:
        resp = await http.get(f"{base}/apps")
        resp.raise_for_status()
        existing = next((a for a in resp.json() if a.get("name") == SERVICE_NAME), None)
        if existing:
            resp = await http.patch(f"{base}/apps/{existing['id']}", json=payload)
        else:
            resp = await http.post(f"{base}/apps", json=payload)
        resp.raise_for_status()
        logger.info("Registered in App Registry | name=%s version=%s", SERVICE_NAME, version)
        return True
    except httpx.HTTPError as exc:
        logger.error("App Registry registration failed | url=%s error=%r", base, exc)
        return False
    finally:
        if owns_client:
            await http.aclose()


async def register_forever(registry_url: str, version: str) -> None:
    """Register, retry every 10 s until it works, then again every 10 min (survives a registry reset).

    A registry that starts after this app (host reboot) is picked up without a restart.
    """
    while True:
        ok = await register_self(registry_url, version)
        await asyncio.sleep(REFRESH_S if ok else RETRY_S)


def start_registration() -> asyncio.Task | None:
    """Start the background registration, or return None when no registry is configured."""
    if not settings.APP_REGISTRY_URL:
        logger.info("APP_REGISTRY_URL not set - not registering in the App Registry")
        return None
    # APP_VERSION is guaranteed by the settings validator when APP_REGISTRY_URL is set.
    return asyncio.create_task(register_forever(settings.APP_REGISTRY_URL, settings.APP_VERSION))  # type: ignore[arg-type]
