from __future__ import annotations
import asyncio
import json
import os
from typing import Dict, Any
try:
    import uvloop  # noqa
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass

from aiokafka import AIOKafkaProducer
from generator import gen_tx

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
TOPIC = os.getenv("TOPIC_TRANSACTIONS", "transactions.v1")
RATE_PER_SEC = float(os.getenv("RATE_PER_SEC", "50"))

async def main():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=10,
        acks="all",
    )
    await producer.start()
    try:
        i = 0
        period = 1.0 / max(RATE_PER_SEC, 1.0)
        while True:
            tx = gen_tx(i)
            await producer.send_and_wait(TOPIC, tx)
            i += 1
            await asyncio.sleep(period)
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(main())
