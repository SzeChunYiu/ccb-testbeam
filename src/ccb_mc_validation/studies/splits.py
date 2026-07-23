"""Train/test split helpers for MC validation studies.

Split strategies
----------------
* ``legacy_parity`` / ``deterministic_index`` — row-index based. These are
  **not** group-aware and leak information whenever two rows share an immutable
  group (e.g. several tracks from the same physics event). They are retained
  only for back-comparison with ``scripts/mv1_mv2_truth_pid_energy.py``.
* ``group_holdout`` — group-disjoint holdout (sklearn ``GroupShuffleSplit``
  semantics): whole groups move into train or test together, so there is zero
  group overlap between folds. This is the default for any study that publishes
  a production number (ML-002).
* ``group_kfold`` — group-disjoint K-fold (sklearn ``GroupKFold``); the first
  fold is returned as the held-out test set.

Every group-aware strategy is validated by :func:`assert_group_disjoint`, which
raises :class:`SplitLeakageError` on any group overlap between train and test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ccb_mc_validation.exceptions import SplitLeakageError

# Strategies that operate on row indices only (NOT group-aware). Using these on
# data with shared groups leaks information; group-aware strategies below must
# be used for any production ML evaluation (ML-002).
ROW_INDEX_STRATEGIES: frozenset[str] = frozenset({"legacy_parity", "deterministic_index"})
GROUP_STRATEGIES: frozenset[str] = frozenset({"group_holdout", "group_kfold"})


@dataclass
class SplitRegistry:
    """Named split definition loaded from ``configs/mc_validation/splits.yaml``."""

    name: str
    train_fraction: float
    seed: int
    strategy: str = "deterministic_index"
    n_splits: int = 5

    @classmethod
    def from_config(cls, config: dict[str, Any], split_name: str | None = None) -> SplitRegistry:
        name = split_name or config.get("default_split", "group_holdout")
        splits = config.get("splits", {})
        if name not in splits:
            raise KeyError(f"split {name!r} not found in splits config")
        entry = splits[name]
        return cls(
            name=name,
            train_fraction=float(entry.get("train_fraction", 0.5)),
            seed=int(entry.get("seed", 0)),
            strategy=str(entry.get("strategy", "group_holdout")),
            n_splits=int(entry.get("n_splits", 5)),
        )

    @classmethod
    def load(cls, path: str | Path, split_name: str | None = None) -> SplitRegistry:
        with Path(path).open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        return cls.from_config(config, split_name)

    def train_test_masks(
        self,
        n: int,
        groups: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return boolean (train, test) masks of length *n*.

        For group-aware strategies ``groups`` is mandatory; passing ``None``
        raises ``ValueError`` rather than silently falling back to a leaking
        row-index split.
        """
        if self.strategy in GROUP_STRATEGIES:
            if groups is None:
                raise ValueError(
                    f"split strategy {self.strategy!r} requires `groups` "
                    "(pass records['event_id']); refusing to fall back to a "
                    "leaking row-index split (ML-002)."
                )
            groups = np.asarray(groups)
            train, test = self._group_masks(groups)
            assert_group_disjoint(train, test, groups)
            return train, test

        # Row-index strategies (legacy; not group-aware).
        if self.strategy == "legacy_parity":
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

    def _group_masks(self, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Group-disjoint boolean masks via sklearn GroupShuffleSplit/GroupKFold."""
        from sklearn.model_selection import GroupKFold, GroupShuffleSplit

        n = int(groups.shape[0])
        if self.strategy == "group_holdout":
            splitter = GroupShuffleSplit(
                n_splits=1,
                train_size=self.train_fraction,
                random_state=self.seed,
            )
            train_idx, test_idx = next(splitter.split(np.empty(n), groups=groups))
            train = np.zeros(n, dtype=bool)
            test = np.zeros(n, dtype=bool)
            train[train_idx] = True
            test[test_idx] = True
            return train, test
        if self.strategy == "group_kfold":
            n_splits = max(2, int(self.n_splits))
            splitter = GroupKFold(n_splits=n_splits)
            # First fold is the held-out test set; the union of the *test*
            # sets of the remaining folds is its group-disjoint complement
            # (the other groups). Using the other folds' train sides would
            # re-introduce the held-out groups and leak (caught by
            # assert_group_disjoint).
            folds = list(splitter.split(np.empty(n), groups=groups))
            _, test_idx = folds[0]
            train_idx = np.concatenate([te_i for _tr, te_i in folds[1:]])
            train = np.zeros(n, dtype=bool)
            test = np.zeros(n, dtype=bool)
            train[train_idx] = True
            test[test_idx] = True
            return train, test
        raise ValueError(f"not a group strategy: {self.strategy}")


def assert_group_disjoint(
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    groups: np.ndarray,
) -> None:
    """Raise :class:`SplitLeakageError` if any group appears in both folds.

    This is the hard contract for group-aware splits (ML-002): the train and
    test sets must be disjoint by immutable group key (event/run/source), not
    merely by row index.
    """
    groups = np.asarray(groups)
    train_groups = set(np.unique(groups[np.asarray(train_mask, dtype=bool)]).tolist())
    test_groups = set(np.unique(groups[np.asarray(test_mask, dtype=bool)]).tolist())
    overlap = train_groups & test_groups
    if overlap:
        raise SplitLeakageError(
            f"group leakage: {len(overlap)} group(s) appear in both train and test "
            f"(e.g. {sorted(overlap)[:5]}); use a group-disjoint split (ML-002)."
        )


def legacy_parity_split(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic index parity split (legacy parity with original MV1/MV2 script).

    .. warning::
        Row-index parity leaks whenever two rows share an event. Prefer
        :class:`SplitRegistry` with a ``group_holdout`` strategy for production.
    """
    return SplitRegistry(
        name="legacy_parity",
        train_fraction=0.5,
        seed=0,
        strategy="legacy_parity",
    ).train_test_masks(n)


def default_group_split(
    groups: np.ndarray,
    *,
    train_fraction: float = 0.5,
    seed: int = 171101,
) -> tuple[np.ndarray, np.ndarray]:
    """Convenience group-disjoint holdout used as the MV-study default (ML-002)."""
    return SplitRegistry(
        name="default_group_holdout",
        train_fraction=train_fraction,
        seed=seed,
        strategy="group_holdout",
    ).train_test_masks(int(np.asarray(groups).shape[0]), groups=groups)
