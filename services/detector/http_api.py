from __future__ import annotations
import logging
from fastapi import FastAPI, Query
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def create_app(storage, cache=None, consumer=None) -> FastAPI:
    app = FastAPI(title="Fraud Detector API")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        """Readiness probe — checks Postgres, Redis, Kafka connectivity."""
        checks: Dict[str, str] = {}

        # Postgres
        try:
            rows = await storage.latest_alerts(limit=1)
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"

        # Redis
        if cache is not None:
            try:
                pong = await cache.ping()
                checks["redis"] = "ok" if pong else "error: no pong"
            except Exception as exc:
                checks["redis"] = f"error: {exc}"

        # Kafka consumer
        if consumer is not None:
            checks["kafka"] = "ok" if consumer.consumer is not None else "not connected"

        all_ok = all(v == "ok" for v in checks.values())
        status_code = 200 if all_ok else 503
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={"ready": all_ok, "checks": checks},
            status_code=status_code,
        )

    @app.get("/alerts")
    async def alerts(limit: int = Query(20, ge=1, le=1000)) -> List[Dict[str, Any]]:
        return await storage.latest_alerts(limit=limit)

    return app
