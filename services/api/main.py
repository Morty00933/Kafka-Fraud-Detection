import os, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import make_asgi_app
import asyncpg
import redis.asyncio as redis

PG_USER = os.getenv("POSTGRES_USER", "app")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "app")
PG_DB   = os.getenv("POSTGRES_DB", "fraud")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

app = FastAPI(title="Fraud Detection API")
app.mount("/metrics", make_asgi_app())

class TxIn(BaseModel):
    tx_id: str
    user_id: int
    amount: float
    location: str
    hour: int = Field(ge=0, le=23)
    timestamp: str

@app.on_event("startup")
async def startup():
    app.state.pg = await asyncpg.create_pool(
        user=PG_USER, password=PG_PASS, database=PG_DB, host=PG_HOST, port=PG_PORT
    )
    app.state.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    await app.state.pg.close()
    await app.state.redis.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

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
    return json.loads(val)

# Онлайновый скоринг: для демо просто пишем в Redis и (опционально) в БД
@app.post("/score")
async def score(tx: TxIn):
    # Лёгкий heurstic для онлайн-API (детальный скоринг выполняет detector)
    risky = 1.0 if tx.location in {"RU","CN","US","BR","IN"} else 0.0
    is_night = 1.0 if (tx.hour < 6 or tx.hour > 23) else 0.0
    score = min(1.0, (tx.amount/5000.0) * 0.7 + risky*0.2 + is_night*0.1)
    if score >= 0.65:
        await app.state.redis.setex(f"fraud:{tx.tx_id}", 1800, json.dumps({"score": score, "reason": "online_score"}))
    return {"tx_id": tx.tx_id, "score": score}
