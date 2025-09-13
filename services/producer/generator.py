from __future__ import annotations
import random
from datetime import datetime, timezone
from typing import Dict, Any

_LOCATIONS = ["DE", "FR", "NL", "BE", "PL", "ES", "IT", "IN", "US", "GB"]

def gen_tx(i: int) -> Dict[str, Any]:
    # базовые транзакции
    user_id = random.randint(1, 5000)
    base = random.choice([10, 20, 50, 100, 200, 500])
    jitter = random.random() * base * 0.5
    amount = round(abs(random.gauss(mu=base, sigma=base * 0.2)) + jitter, 2)
    location = random.choice(_LOCATIONS)

    # вкрапляем аномалии
    if random.random() < 0.02:
        amount = round(random.uniform(600, 2000), 2)
    if random.random() < 0.01:
        location = random.choice(["IN", "US"])  # редко встречающиеся страны в выборке

    return {
        "tx_id": f"tx_{i}",
        "user_id": user_id,
        "amount": amount,
        "location": location,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
