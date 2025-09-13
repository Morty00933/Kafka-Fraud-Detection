from __future__ import annotations
from fastapi import FastAPI, Query
from typing import List, Dict, Any

def create_app(storage) -> FastAPI:
    app = FastAPI(title="Fraud Detector API")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/alerts")
    async def alerts(limit: int = Query(20, ge=1, le=1000)) -> List[Dict[str, Any]]:
        return await storage.latest_alerts(limit=limit)

    return app
