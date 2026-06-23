"""Tests for event-block split registry and leakage checks."""

from __future__ import annotations

import pytest

from ccb_mc_validation.exceptions import SplitLeakageError
from ccb_mc_validation.statistics.splits import SplitRegistry


def test_no_leakage_across_blocks() -> None:
    registry = SplitRegistry.from_event_blocks(
        event_ids=["e0", "e1", "e2", "e3"],
        block_ids=[10, 10, 20, 21],
        split_names=["train", "train", "test", "test"],
    )
    report = registry.leakage_check()
    assert report["ok"] is True
    assert set(registry.events_in_split("train")) == {"e0", "e1"}
    assert set(registry.events_in_split("test")) == {"e2", "e3"}


def test_leakage_raises_when_block_assigned_twice() -> None:
    registry = SplitRegistry()
    registry.register_event("e0", block_id=5, split="train")
    with pytest.raises(SplitLeakageError):
        registry.register_event("e1", block_id=5, split="test")
