"""Layer/stave geometry registry from the canonical, versioned readout contract.

The previous implementation silently guessed a *one-to-one* layer->stave map
whenever a study config omitted the mapping, while ``scripts/mc01_trigger_split_truth.py``
merges MC layers *in pairs*.  That silent divergence is the GEO-001 defect.  The
fix here is:

* exactly one **versioned** default policy (:data:`READOUT_CONTRACT_VERSION`,
  :data:`DEFAULT_LAYER_MERGE_POLICY`) lives in code and is referenced verbatim
  by ``docs/contracts/GEOMETRY_READOUT_MAPPING_CONTRACT.md``;
* the builder fails closed (raises :class:`ConfigurationError`) whenever the
  number of MC layers is inconsistent with the declared policy / stave count,
  instead of guessing;
* the physical "which real bar is which stave" question remains
  ``BLOCKED_COMPUTE`` in the contract -- this module only guarantees that every
  code path uses the *same* versioned policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ccb_mc_validation.constants import A_ARM, B_ARM, NB_LAYERS
from ccb_mc_validation.exceptions import ConfigurationError

#: Single source of truth for the code-level readout contract version.  Bumping
#: this MUST be accompanied by an update to the contract doc.
READOUT_CONTRACT_VERSION: str = "2026.0-truth-geometry"

#: The canonical, code-level layer-merge policy used by geometry.py.  The
#: deployed krakow MC has ``NB_LAYERS == 8`` B bars and 4 instrumented staves
#: (B2/B4/B6/B8), so adjacent MC layers are merged in pairs to readout.  The
#: *physical* bar->stave assignment remains BLOCKED_COMPUTE in the contract.
DEFAULT_LAYER_MERGE_POLICY: str = "pair_merge"

VALID_LAYER_MERGE_POLICIES: frozenset[str] = frozenset({"one_to_one", "pair_merge"})

#: Canonical default B-arm stave labels -> even HRD channel index.
DEFAULT_B_STAVES: dict[str, int] = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}


def build_layer_to_stave(
    staves: dict[str, int],
    *,
    n_b_layers: int,
    policy: str = DEFAULT_LAYER_MERGE_POLICY,
) -> dict[int, str]:
    """Build ``{layer_id: stave_name}`` under a declared, versioned policy.

    Fails closed: raises :class:`ConfigurationError` if the layer/stave counts
    are inconsistent with ``policy`` (e.g. 8 layers + 4 staves requires
    ``pair_merge``; 4 layers + 4 staves requires ``one_to_one``).
    """
    policy = str(policy)
    if policy not in VALID_LAYER_MERGE_POLICIES:
        raise ConfigurationError(
            f"unknown layer_merge_policy {policy!r}; expected one of "
            f"{sorted(VALID_LAYER_MERGE_POLICIES)}"
        )
    ordered = sorted(staves.items(), key=lambda kv: kv[1])
    n_staves = len(ordered)
    if n_staves == 0:
        raise ConfigurationError("no B staves provided")
    if policy == "one_to_one":
        if n_b_layers != n_staves:
            raise ConfigurationError(
                f"one_to_one policy needs n_b_layers == n_staves, "
                f"got n_b_layers={n_b_layers} and {n_staves} staves; "
                f"use pair_merge or supply an explicit layer_to_stave map"
            )
        return {layer: name for layer, (name, _ch) in enumerate(ordered)}
    # pair_merge
    if n_b_layers != 2 * n_staves:
        raise ConfigurationError(
            f"pair_merge policy needs n_b_layers == 2*n_staves, "
            f"got n_b_layers={n_b_layers} and {n_staves} staves; "
            f"use one_to_one or supply an explicit layer_to_stave map"
        )
    mapping: dict[int, str] = {}
    for li, (name, _ch) in enumerate(ordered):
        mapping[2 * li] = name
        mapping[2 * li + 1] = name
    return mapping


@dataclass
class GeometryRegistry:
    """Map between MC layer indices, arms, and data stave labels."""

    b_arm: int = B_ARM
    a_arm: int = A_ARM
    n_b_layers: int = NB_LAYERS
    stave_to_channel: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_B_STAVES))
    layer_to_stave: dict[int, str] = field(default_factory=dict)
    layer_merge_policy: str = DEFAULT_LAYER_MERGE_POLICY
    readout_contract_version: str = READOUT_CONTRACT_VERSION

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> GeometryRegistry:
        """Build registry from a JSON/YAML study config dict.

        The layer->stave mapping is resolved from, in priority order: an explicit
        ``layer_to_stave`` map in the config; otherwise the versioned default
        :func:`build_layer_to_stave` driven by ``layer_merge_policy``.  The
        policy is never guessed -- it defaults to the canonical contract value
        so every caller agrees.
        """
        geom = config.get("geometry", config)
        staves = dict(geom.get("staves", config.get("staves", DEFAULT_B_STAVES)))
        if not staves:
            staves = dict(DEFAULT_B_STAVES)

        n_b_layers = int(geom.get("n_b_layers", NB_LAYERS))
        policy = str(geom.get("layer_merge_policy", DEFAULT_LAYER_MERGE_POLICY))

        layer_map_raw = geom.get("layer_to_stave", {})
        if layer_map_raw:
            layer_to_stave = {int(k): str(v) for k, v in layer_map_raw.items()}
            _validate_explicit_layer_to_stave(layer_to_stave, n_b_layers=n_b_layers)
        else:
            layer_to_stave = build_layer_to_stave(staves, n_b_layers=n_b_layers, policy=policy)

        return cls(
            b_arm=int(geom.get("b_arm", B_ARM)),
            a_arm=int(geom.get("a_arm", A_ARM)),
            n_b_layers=n_b_layers,
            stave_to_channel={str(k): int(v) for k, v in staves.items()},
            layer_to_stave=layer_to_stave,
            layer_merge_policy=policy,
            readout_contract_version=READOUT_CONTRACT_VERSION,
        )

    def stave_for_layer(self, layer_id: int) -> str | None:
        """Return data stave label for a B-stack ``Sci_bar_LayerID``."""
        return self.layer_to_stave.get(int(layer_id))

    def channel_for_stave(self, stave: str) -> int:
        """Return even HRD channel index for a stave label."""
        if stave not in self.stave_to_channel:
            raise ConfigurationError(f"unknown stave label: {stave!r}")
        return int(self.stave_to_channel[stave])

    def is_b_arm(self, layer_id1: int) -> bool:
        return int(layer_id1) == self.b_arm

    def is_a_arm(self, layer_id1: int) -> bool:
        return int(layer_id1) == self.a_arm


def _validate_explicit_layer_to_stave(
    layer_to_stave: dict[int, str], *, n_b_layers: int
) -> None:
    """An explicit map must cover exactly ``[0, n_b_layers)`` with no gaps."""
    expected = set(range(n_b_layers))
    got = set(layer_to_stave.keys())
    if got != expected:
        raise ConfigurationError(
            f"explicit layer_to_stave covers {sorted(got)} but expected {sorted(expected)} "
            f"for n_b_layers={n_b_layers}"
        )
