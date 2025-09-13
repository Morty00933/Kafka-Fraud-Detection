from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest

def _to_vector(tx: Dict[str, Any]) -> np.ndarray:
    amount = float(tx.get("amount", 0.0))
    loc = str(tx.get("location", "XX"))
    loc_hash = (hash(loc) % 1000) / 1000.0
    return np.array([amount, loc_hash], dtype=np.float32)

@dataclass
class IFConfig:
    contamination: float = 0.02
    n_estimators: int = 200
    random_state: int = 42
    retrain_every: int = 2000
    buffer_max: int = 50000
    score_threshold: Optional[float] = None

class IsolationForestDetector:
    """
    Буфер скользящего окна + периодическое переобучение IsolationForest.
    score = score_samples; чем НИЖЕ, тем подозрительнее.
    """
    def __init__(self, cfg: IFConfig | None = None):
        self.cfg = cfg or IFConfig()
        self._X: List[np.ndarray] = []
        self._clf: Optional[IsolationForest] = None
        self._seen: int = 0
        self._threshold: Optional[float] = self.cfg.score_threshold

    def _maybe_retrain(self):
        need_min = max(1000, int(1.5 / max(self.cfg.contamination, 1e-4)))
        if len(self._X) < need_min:
            return
        if self._clf is None or (self._seen % self.cfg.retrain_every == 0):
            X = np.vstack(self._X[-self.cfg.buffer_max:])
            clf = IsolationForest(
                n_estimators=self.cfg.n_estimators,
                contamination=self.cfg.contamination,
                random_state=self.cfg.random_state,
            )
            clf.fit(X)
            self._clf = clf
            scores = clf.score_samples(X)
            self._threshold = float(np.quantile(scores, self.cfg.contamination))

    def score(self, tx: Dict[str, Any]) -> Tuple[float, str]:
        v = _to_vector(tx)
        self._X.append(v)
        self._seen += 1
        if len(self._X) > self.cfg.buffer_max:
            self._X = self._X[-self.cfg.buffer_max:]
        self._maybe_retrain()

        if self._clf is None:
            return 0.0, "cold_start"

        s = float(self._clf.score_samples(v.reshape(1, -1))[0])
        thr = self._threshold if self._threshold is not None else -1e9
        return s, f"iforest_score={s:.3f}; threshold={thr:.3f}"

    def is_anomalous(self, score: float) -> bool:
        thr = self._threshold if self._threshold is not None else -1e9
        return score < thr
