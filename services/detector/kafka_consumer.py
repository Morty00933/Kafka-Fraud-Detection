from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)


class TxConsumer:
    def __init__(self, bootstrap: str, topic: str, group_id: str):
        self.bootstrap = bootstrap
        self.topic = topic
        self.group_id = group_id
        self.consumer: AIOKafkaConsumer | None = None

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap,
            group_id=self.group_id,
            enable_auto_commit=True,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("Kafka consumer started (topic=%s, group=%s)", self.topic, self.group_id)

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")

    async def run(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        assert self.consumer is not None
        async for msg in self.consumer:
            try:
                tx = msg.value  # dict: {tx_id, user_id, amount, location, ts}
                # Ensure ts is datetime
                ts_str = tx.get("ts")
                if isinstance(ts_str, str):
                    try:
                        tx["ts"] = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        tx["ts"] = datetime.now(timezone.utc)
                handler(tx)
            except Exception as exc:
                logger.error(
                    "Error processing message offset=%d partition=%d: %s",
                    msg.offset, msg.partition, exc,
                    exc_info=True,
                )
                # Continue processing next messages instead of crashing
                await asyncio.sleep(0.1)
