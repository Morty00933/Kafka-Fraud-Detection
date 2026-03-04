from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.sql import text as sa_text

logger = logging.getLogger(__name__)

_DB_URL_TPL = "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


class Storage:
    def __init__(self, host="postgres", port=5432, user="app", password="app", db="fraud"):
        url = _DB_URL_TPL.format(user=user, password=password, host=host, port=port, db=db)
        self.engine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
        )
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self):
        """Create table + index matching migrations/001_init.sql schema."""
        async with self.engine.begin() as conn:
            await conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS fraud_alerts (
              id         BIGSERIAL PRIMARY KEY,
              tx_id      VARCHAR(64) UNIQUE NOT NULL,
              user_id    BIGINT NOT NULL,
              amount     NUMERIC(12,2) NOT NULL,
              location   VARCHAR(64) NOT NULL,
              ts         TIMESTAMPTZ NOT NULL,
              score      DOUBLE PRECISION NOT NULL,
              reason     TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );"""))
            await conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_fraud_alerts_user_ts
            ON fraud_alerts(user_id, ts);
            """))
        logger.info("Storage initialized (table + index ensured)")

    async def upsert_alert(self, alert: Dict[str, Any]) -> None:
        if isinstance(alert["ts"], str):
            raise TypeError("ts must be a datetime, not str")

        async with self.Session() as session:  # type: AsyncSession
            try:
                await session.execute(sa_text("""
                    INSERT INTO fraud_alerts (tx_id, user_id, amount, location, ts, score, reason)
                    VALUES (:tx_id, :user_id, :amount, :location, :ts, :score, :reason)
                    ON CONFLICT (tx_id) DO UPDATE SET
                      score = EXCLUDED.score,
                      reason = EXCLUDED.reason
                """), alert)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.error("Failed to upsert alert tx_id=%s: %s", alert.get("tx_id"), exc)
                raise

    async def bulk_upsert_alerts(self, alerts: List[Dict[str, Any]]) -> int:
        """Batch upsert multiple alerts in a single transaction."""
        if not alerts:
            return 0
        async with self.Session() as session:
            try:
                for alert in alerts:
                    if isinstance(alert["ts"], str):
                        raise TypeError("ts must be a datetime, not str")
                    await session.execute(sa_text("""
                        INSERT INTO fraud_alerts (tx_id, user_id, amount, location, ts, score, reason)
                        VALUES (:tx_id, :user_id, :amount, :location, :ts, :score, :reason)
                        ON CONFLICT (tx_id) DO UPDATE SET
                          score = EXCLUDED.score,
                          reason = EXCLUDED.reason
                    """), alert)
                await session.commit()
                return len(alerts)
            except Exception as exc:
                await session.rollback()
                logger.error("Bulk upsert failed (%d alerts): %s", len(alerts), exc)
                raise

    async def latest_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with self.Session() as session:
            rows = (await session.execute(sa_text("""
                SELECT tx_id, user_id, amount, location, ts, score, reason, created_at
                FROM fraud_alerts
                ORDER BY ts DESC
                LIMIT :limit
            """), {"limit": limit})).mappings().all()
            return [dict(r) for r in rows]

    async def close(self) -> None:
        await self.engine.dispose()
