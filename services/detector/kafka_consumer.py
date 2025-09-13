from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Callable

from aiokafka import AIOKafkaConsumer

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

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()

    async def run(self, handler: Callable[[Dict[str, Any]], None]):
        assert self.consumer is not None
        async for msg in self.consumer:
            tx = msg.value  # dict: {tx_id, user_id, amount, location, ts}
            # гарантия: приведём ts в datetime
            ts_str = tx.get("ts")
            if isinstance(ts_str, str):
                try:
                    tx["ts"] = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    tx["ts"] = datetime.now(timezone.utc)
            handler(tx)
