"""Train/test split helpers for MC validation studies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml


@dataclass
class SplitRegistry:
    """Named split definitions loaded from ``configs/mc_validation/splits.yaml``."""

    name: str
    train_fraction: float
    seed: int
    strategy: str = "deterministic_index"

    @classmethod
    def from_config(cls, config: dict[str, Any], split_name: str | None = None) -> SplitRegistry:
        name = split_name or config.get("default_split", "legacy_parity")
        splits = config.get("splits", {})
        if name not in splits:
            raise KeyError(f"split {name!r} not found in splits config")
        entry = splits[name]
        return cls(
            name=name,
            train_fraction=float(entry.get("train_fraction", 0.5)),
            seed=int(entry.get("seed", 0)),
            strategy=str(entry.get("strategy", "deterministic_index")),
        )

    @classmethod
    def load(cls, path: str | Path, split_name: str | None = None) -> SplitRegistry:
        with Path(path).open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        return cls.from_config(config, split_name)

    def train_test_masks(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Return boolean (train, test) masks of length *n*."""
        if self.strategy == "legacy_parity":
            # Legacy parity with scripts/mv1_mv2_truth_pid_energy.py: idx % 2 == 0 → train.
            idx = np.arange(n)
            train = idx % 2 == 0
            return train, ~train
        if self.strategy == "deterministic_index":
            rng = np.random.default_rng(self.seed)
            perm = rng.permutation(n)
            n_train = int(round(n * self.train_fraction))
            train_idx = perm[:n_train]
            train = np.zeros(n, dtype=bool)
            train[train_idx] = True
            return train, ~train
        raise ValueError(f"unknown split strategy: {self.strategy}")


def legacy_parity_split(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic index parity split (legacy parity with original MV1/MV2 script)."""
    return SplitRegistry(
        name="legacy_parity",
        train_fraction=0.5,
        seed=0,
        strategy="legacy_parity",
    ).train_test_masks(n)
