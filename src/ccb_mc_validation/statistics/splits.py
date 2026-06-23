"""Train/calibration split registry with event-block grouping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from ccb_mc_validation.exceptions import SplitLeakageError


@dataclass
class SplitRegistry:
    """Assign events to splits by block id to prevent run-level leakage."""

    block_to_split: dict[int | str, str] = field(default_factory=dict)
    event_to_block: dict[str, int | str] = field(default_factory=dict)

    def register_block(self, block_id: int | str, split: str) -> None:
        block_id = _canonical_block(block_id)
        if block_id in self.block_to_split and self.block_to_split[block_id] != split:
            raise SplitLeakageError(
                f"block {block_id!r} already assigned to {self.block_to_split[block_id]!r}"
            )
        self.block_to_split[block_id] = split

    def register_event(self, event_id: str, block_id: int | str, split: str) -> None:
        block_id = _canonical_block(block_id)
        self.register_block(block_id, split)
        if event_id in self.event_to_block and self.event_to_block[event_id] != block_id:
            raise SplitLeakageError(
                f"event {event_id!r} already mapped to block {self.event_to_block[event_id]!r}"
            )
        self.event_to_block[event_id] = block_id

    def split_for_event(self, event_id: str) -> str | None:
        block = self.event_to_block.get(event_id)
        if block is None:
            return None
        return self.block_to_split.get(block)

    def events_in_split(self, split: str) -> list[str]:
        return [ev for ev, block in self.event_to_block.items() if self.block_to_split.get(block) == split]

    def leakage_check(self) -> dict[str, object]:
        """Verify no block (and therefore no event) appears in multiple splits."""
        violations: list[dict[str, object]] = []
        block_splits: dict[int | str, set[str]] = {}
        for event_id, block_id in self.event_to_block.items():
            split = self.block_to_split.get(block_id)
            if split is None:
                violations.append({"event_id": event_id, "issue": "unassigned_block"})
                continue
            block_splits.setdefault(block_id, set()).add(split)

        for block_id, splits in block_splits.items():
            if len(splits) > 1:
                violations.append(
                    {
                        "block_id": block_id,
                        "issue": "block_in_multiple_splits",
                        "splits": sorted(splits),
                    }
                )

        event_splits: dict[str, set[str]] = {}
        for event_id in self.event_to_block:
            split = self.split_for_event(event_id)
            if split is not None:
                event_splits.setdefault(event_id, set()).add(split)
        for event_id, splits in event_splits.items():
            if len(splits) > 1:
                violations.append(
                    {
                        "event_id": event_id,
                        "issue": "event_in_multiple_splits",
                        "splits": sorted(splits),
                    }
                )

        ok = len(violations) == 0
        report = {
            "ok": ok,
            "n_events": len(self.event_to_block),
            "n_blocks": len(self.block_to_split),
            "violations": violations,
        }
        if not ok:
            raise SplitLeakageError(f"split leakage detected: {violations}")
        return report

    @classmethod
    def from_event_blocks(
        cls,
        event_ids: Iterable[str],
        block_ids: Iterable[int | str],
        split_names: Iterable[str],
    ) -> SplitRegistry:
        registry = cls()
        for event_id, block_id, split in zip(event_ids, block_ids, split_names):
            registry.register_event(str(event_id), block_id, str(split))
        return registry


def _canonical_block(block_id: int | str) -> int | str:
    if isinstance(block_id, str) and block_id.isdigit():
        return int(block_id)
    return block_id
