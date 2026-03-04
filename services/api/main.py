import os
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import make_asgi_app
import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)

PG_USER = os.getenv("POSTGRES_USER", "app")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "app")
PG_DB   = os.getenv("POSTGRES_DB", "fraud")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    app.state.pg = await asyncpg.create_pool(
        user=PG_USER, password=PG_PASS, database=PG_DB, host=PG_HOST, port=PG_PORT
    )
    app.state.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    logger.info("API started (pg=%s:%s, redis=%s:%s)", PG_HOST, PG_PORT, REDIS_HOST, REDIS_PORT)
    yield
    await app.state.pg.close()
    await app.state.redis.aclose()
    logger.info("API shutdown")


app = FastAPI(title="Fraud Detection API", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TxIn(BaseModel):
    tx_id: str
    user_id: int
    amount: float
    location: str
    hour: int = Field(ge=0, le=23)
    timestamp: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness probe — checks Postgres and Redis."""
    checks = {}
    try:
        await app.state.pg.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    try:
        pong = await app.state.redis.ping()
        checks["redis"] = "ok" if pong else "error"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"ready": all_ok, "checks": checks},
        status_code=200 if all_ok else 503,
    )


@app.get("/alerts")
async def alerts(limit: int = 50):
    q = "SELECT tx_id, user_id, amount, location, ts, score, reason, created_at FROM fraud_alerts ORDER BY created_at DESC LIMIT $1"
    rows = await app.state.pg.fetch(q, limit)
    return [dict(r) for r in rows]


@app.get("/flags/{tx_id}")
async def flag(tx_id: str):
    val = await app.state.redis.get(f"fraud:{tx_id}")
    if not val:
        raise HTTPException(404, "not flagged")
    # Redis value is "1" (set by detector cache), not JSON
    if val == "1":
        return {"tx_id": tx_id, "flagged": True}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {"tx_id": tx_id, "flagged": True, "raw": val}


# Online scoring: simple heuristic for demo (detailed scoring done by detector)
@app.post("/score")
async def score(tx: TxIn):
    risky = 1.0 if tx.location in {"RU", "CN", "US", "BR", "IN"} else 0.0
    is_night = 1.0 if (tx.hour < 6 or tx.hour > 23) else 0.0
    s = min(1.0, (tx.amount / 5000.0) * 0.7 + risky * 0.2 + is_night * 0.1)
    if s >= 0.65:
        await app.state.redis.setex(
            f"fraud:{tx.tx_id}", 1800,
            json.dumps({"score": s, "reason": "online_score"}),
        )
    return {"tx_id": tx.tx_id, "score": s}
