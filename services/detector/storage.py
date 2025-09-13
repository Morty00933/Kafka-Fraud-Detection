from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.sql import text as sa_text

_DB_URL_TPL = "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

class Storage:
    def __init__(self, host="postgres", port=5432, user="app", password="app", db="fraud"):
        url = _DB_URL_TPL.format(user=user, password=password, host=host, port=port, db=db)
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS fraud_alerts (
              tx_id      TEXT PRIMARY KEY,
              user_id    INT NOT NULL,
              amount     NUMERIC(12,2) NOT NULL,
              location   TEXT NOT NULL,
              ts         TIMESTAMPTZ NOT NULL,
              score      DOUBLE PRECISION NOT NULL,
              reason     TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );"""))

    async def upsert_alert(self, alert: Dict[str, Any]):
        # важно: ts ДОЛЖЕН быть datetime (не str)
        if isinstance(alert["ts"], str):
            raise TypeError("ts must be a datetime, not str")

        async with self.Session() as session:  # type: AsyncSession
            await session.execute(sa_text("""
                INSERT INTO fraud_alerts (tx_id, user_id, amount, location, ts, score, reason)
                VALUES (:tx_id, :user_id, :amount, :location, :ts, :score, :reason)
                ON CONFLICT (tx_id) DO UPDATE SET
                  score = EXCLUDED.score,
                  reason = EXCLUDED.reason
            """), alert)
            await session.commit()

    async def latest_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with self.Session() as session:
            rows = (await session.execute(sa_text("""
                SELECT tx_id, user_id, amount, location, ts, score, reason, created_at
                FROM fraud_alerts
                ORDER BY ts DESC
                LIMIT :limit
            """), {"limit": limit})).mappings().all()
            return [dict(r) for r in rows]
