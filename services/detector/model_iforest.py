from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

# Known locations for one-hot encoding (top locations)
DEFAULT_LOCATIONS = ["US", "CN", "RU", "BR", "IN", "DE", "JP", "GB", "FR", "KR"]


def _to_vector(tx: Dict[str, Any], known_locations: List[str]) -> np.ndarray:
    """Build a feature vector from a transaction."""
    amount = float(tx.get("amount", 0.0))
    loc = str(tx.get("location", "XX"))

    # One-hot encoding for location (instead of hash)
    loc_features = [1.0 if loc == known else 0.0 for known in known_locations]
    # "Other" flag if location not in known list
    loc_other = 0.0 if loc in known_locations else 1.0

    return np.array([amount] + loc_features + [loc_other], dtype=np.float32)


@dataclass
class IFConfig:
    contamination: float = 0.02
    n_estimators: int = 200
    random_state: int = 42
    retrain_every: int = 2000
    buffer_max: int = 50000
    score_threshold: Optional[float] = None
    known_locations: List[str] = field(default_factory=lambda: list(DEFAULT_LOCATIONS))


class IsolationForestDetector:
    """
    Sliding window buffer + periodic retraining of IsolationForest.
    score = score_samples; lower = more suspicious.
    """

    def __init__(self, cfg: IFConfig | None = None):
        self.cfg = cfg or IFConfig()
        self._X: List[np.ndarray] = []
        self._clf: Optional[IsolationForest] = None
        self._seen: int = 0
        self._threshold: Optional[float] = self.cfg.score_threshold
        # Amount normalization stats
        self._amount_sum: float = 0.0
        self._amount_sq_sum: float = 0.0
        self._amount_mean: float = 0.0
        self._amount_std: float = 1.0

    def _update_stats(self, amount: float) -> None:
        """Update running statistics for amount normalization."""
        self._amount_sum += amount
        self._amount_sq_sum += amount * amount
        n = self._seen
        if n > 1:
            self._amount_mean = self._amount_sum / n
            variance = (self._amount_sq_sum / n) - (self._amount_mean ** 2)
            self._amount_std = max(np.sqrt(max(variance, 0.0)), 1e-6)

    def _maybe_retrain(self) -> None:
        need_min = max(1000, int(1.5 / max(self.cfg.contamination, 1e-4)))
        if len(self._X) < need_min:
            return
        if self._clf is None or (self._seen % self.cfg.retrain_every == 0):
            X = np.vstack(self._X[-self.cfg.buffer_max:])
            # Normalize amount column (index 0) for training
            if self._amount_std > 1e-6:
                X_norm = X.copy()
                X_norm[:, 0] = (X_norm[:, 0] - self._amount_mean) / self._amount_std
            else:
                X_norm = X
            clf = IsolationForest(
                n_estimators=self.cfg.n_estimators,
                contamination=self.cfg.contamination,
                random_state=self.cfg.random_state,
            )
            clf.fit(X_norm)
            self._clf = clf
            scores = clf.score_samples(X_norm)
            self._threshold = float(np.quantile(scores, self.cfg.contamination))
            logger.info(
                "Retrained IsolationForest: samples=%d, threshold=%.4f",
                len(X), self._threshold,
            )

    def score(self, tx: Dict[str, Any]) -> Tuple[float, str]:
        v = _to_vector(tx, self.cfg.known_locations)
        self._X.append(v)
        self._seen += 1
        self._update_stats(float(tx.get("amount", 0.0)))

        if len(self._X) > self.cfg.buffer_max:
            self._X = self._X[-self.cfg.buffer_max:]
        self._maybe_retrain()

        if self._clf is None:
            # Cold start: flag as suspicious until model is trained
            return -1.0, "cold_start (flagged as suspicious until model trains)"

        # Normalize amount for scoring
        v_norm = v.copy()
        v_norm[0] = (v_norm[0] - self._amount_mean) / self._amount_std

        s = float(self._clf.score_samples(v_norm.reshape(1, -1))[0])
        thr = self._threshold if self._threshold is not None else -1e9
        return s, f"iforest_score={s:.3f}; threshold={thr:.3f}"

    def is_anomalous(self, score: float) -> bool:
        thr = self._threshold if self._threshold is not None else -1e9
        return score < thr
