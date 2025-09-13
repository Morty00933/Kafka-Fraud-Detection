from __future__ import annotations
import os

def env_str(key: str, default: str) -> str:
    return os.getenv(key, default)

def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

def env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except Exception:
        return default
