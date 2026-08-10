"""Pure S00 selector/config identity checks for producer preflight.

This module isolates the no-I/O semantic contract required by issue #1141.
It deliberately performs no filesystem access, ROOT access, artifact creation,
or detector inference. The canonical producer can call it immediately after
YAML parsing, before resolving output namespaces or creating staging paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ccb_mc_validation.selector import (
    S00_SELECTOR_V1_BASELINE_INDICES,
    S00_SELECTOR_V1_ID,
    SelectorInputError,
    _validate_v1_baseline_indices,
)


class S00SelectorConfigError(SelectorInputError):
    """Controlled failure for a config outside the frozen S00 selector contract."""


def validate_s00_selector_contract(config: Mapping[str, Any]) -> tuple[int, int, int, int]:
    """Validate the frozen selector identity without performing any I/O.

    Canonical S00 uses exactly ``v1_first_four_median`` with baseline indices
    ``(0, 1, 2, 3)``. ``baseline_samples`` remains in the historical YAML for
    provenance/backward compatibility, but it is an assertion of this named
    model rather than a free parameter. Alternate windows require a distinct
    selector/model identity and a non-authorising sensitivity namespace.

    The YAML field itself must be a sequence-style list. This prevents mapping,
    set, generator, or other iterable objects from acquiring canonical meaning
    merely because their iteration happens to yield ``0,1,2,3``.

    Returns the canonical tuple on success. Raises
    :class:`S00SelectorConfigError` on a controlled semantic-input failure.
    """
    if not isinstance(config, Mapping):
        raise S00SelectorConfigError("S00 config must be a mapping")
    if "baseline_samples" not in config:
        raise S00SelectorConfigError(
            f"{S00_SELECTOR_V1_ID} requires "
            f"baseline_samples={list(S00_SELECTOR_V1_BASELINE_INDICES)}"
        )

    baseline_samples = config["baseline_samples"]
    if not isinstance(baseline_samples, list):
        raise S00SelectorConfigError(
            "baseline_samples must be a YAML list exactly [0, 1, 2, 3]"
        )

    try:
        return _validate_v1_baseline_indices(baseline_samples)
    except SelectorInputError as exc:
        raise S00SelectorConfigError(str(exc)) from exc


def s00_selector_model_identity() -> dict[str, object]:
    """Return the immutable selector fragment for S00 manifest provenance."""
    return {
        "selector_id": S00_SELECTOR_V1_ID,
        "baseline_indices": list(S00_SELECTOR_V1_BASELINE_INDICES),
    }
