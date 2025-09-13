from __future__ import annotations
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from prometheus_client import start_http_server, Counter
import uvicorn

from utils import env_str, env_int, env_float
from model_iforest import IsolationForestDetector, IFConfig
from storage import Storage
from cache import RedisCache
from kafka_consumer import TxConsumer
from http_api import create_app

# --------- ENV ----------
KAFKA_BOOTSTRAP  = env_str("KAFKA_BOOTSTRAP", "redpanda:9092")
TOPIC            = env_str("TOPIC_TRANSACTIONS", "transactions.v1")
GROUP_ID         = env_str("GROUP_ID", "fraud-detector")

REDIS_HOST       = env_str("REDIS_HOST", "redis")

PG_HOST          = env_str("POSTGRES_HOST", "postgres")
PG_PORT          = env_int("POSTGRES_PORT", 5432)
PG_USER          = env_str("POSTGRES_USER", "app")
PG_PASSWORD      = env_str("POSTGRES_PASSWORD", "app")
PG_DB            = env_str("POSTGRES_DB", "fraud")

MODEL_STRATEGY   = env_str("MODEL_STRATEGY", "iforest")

HTTP_HOST        = env_str("HOST", "0.0.0.0")
HTTP_PORT        = env_int("PORT", 8080)
PROM_PORT        = env_int("PROMETHEUS_PORT", 9000)

IF_CONTAMINATION = env_float("IF_CONTAMINATION", 0.02)
IF_TREES         = env_int("IF_TREES", 200)
IF_RETRAIN_EVERY = env_int("IF_RETRAIN_EVERY", 2000)
IF_BUFFER_MAX    = env_int("IF_BUFFER_MAX", 50000)

# --------- METRICS ----------
MET_ALERTS = Counter("fraud_alerts_total", "Total fraud alerts produced")
MET_SEEN   = Counter("transactions_seen_total", "Total transactions seen")
MET_ERRORS = Counter("detector_errors_total", "Total detector errors")

# --------- GLOBALS ----------
storage = Storage(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, db=PG_DB)
cache = RedisCache(host=REDIS_HOST)
consumer = TxConsumer(KAFKA_BOOTSTRAP, TOPIC, GROUP_ID)

if MODEL_STRATEGY == "iforest":
    detector = IsolationForestDetector(IFConfig(
        contamination=IF_CONTAMINATION,
        n_estimators=IF_TREES,
        retrain_every=IF_RETRAIN_EVERY,
        buffer_max=IF_BUFFER_MAX,
        score_threshold=None,
    ))
else:
    raise RuntimeError(f"Unknown MODEL_STRATEGY={MODEL_STRATEGY}")

app = create_app(storage)

# --------- HANDLER ----------
def on_tx(tx: Dict[str, Any]):
    MET_SEEN.inc()
    score, reason = detector.score(tx)
    is_anom = detector.is_anomalous(score)
    if not is_anom:
        return
    # alert
    alert = {
        "tx_id": tx["tx_id"],
        "user_id": int(tx["user_id"]),
        "amount": float(tx["amount"]),
        "location": str(tx["location"]),
        "ts": tx["ts"] if isinstance(tx["ts"], datetime) else datetime.now(timezone.utc),
        "score": float(score),
        "reason": reason,
    }
    # fire-and-forget (без await внутри consumer.loop)
    asyncio.create_task(cache.set_flag(alert["tx_id"]))
    asyncio.create_task(storage.upsert_alert(alert))
    MET_ALERTS.inc()

# --------- MAIN ----------
async def main():
    # метрики
    start_http_server(PROM_PORT)
    # инициализация
    await storage.init()
    await cache.connect()
    await consumer.start()

    loop = asyncio.get_running_loop()
    # поток обработки
    async def consume_task():
        try:
            await consumer.run(on_tx)
        except Exception:
            MET_ERRORS.inc()
            raise

    task = asyncio.create_task(consume_task())

    # HTTP API (FastAPI + Uvicorn) — запускаем в том же процессe
    config = uvicorn.Config(app, host=HTTP_HOST, port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config=config)

    async def serve_api():
        await server.serve()

    api_task = asyncio.create_task(serve_api())

    try:
        await asyncio.gather(task, api_task)
    finally:
        await consumer.stop()
        await cache.close()

if __name__ == "__main__":
    asyncio.run(main())
