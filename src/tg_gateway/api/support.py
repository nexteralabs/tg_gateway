"""Deploy checks for the SRE agent (internal: this API is not behind a public route).

After a new version registers, sre-core reads /support/manifest and calls each check; a 2xx passes.
A check must prove the version works, not only that it runs, and must have no side effect.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..app_registry import BASE_URL
from ..core import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", include_in_schema=False)


@router.get("/manifest")
async def manifest():
    return {
        "deploy_checks": [
            {"name": "healthz", "method": "GET", "url": f"{BASE_URL}/healthz"},
            {"name": "database", "method": "GET", "url": f"{BASE_URL}/support/checks/database"},
        ]
    }


@router.get("/checks/database")
async def check_database():
    """The database answers a read-only query. /healthz alone does not touch it."""
    try:
        async for conn in db.get_conn():
            row = await db.fetchone(conn, "SELECT 1 AS ok")
    except Exception as exc:
        logger.error("database check failed: %r", exc)
        return JSONResponse(status_code=503, content={"ok": False, "detail": repr(exc)})
    if not row or row.get("ok") != 1:
        return JSONResponse(
            status_code=503, content={"ok": False, "detail": f"unexpected answer: {row!r}"}
        )
    return {"ok": True}
