"""Layer and stave geometry registry from study configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ccb_mc_validation.constants import A_ARM, B_ARM, NB_LAYERS
from ccb_mc_validation.exceptions import ConfigurationError


@dataclass
class GeometryRegistry:
    """Map between MC layer indices, arms, and data stave labels."""

    b_arm: int = B_ARM
    a_arm: int = A_ARM
    n_b_layers: int = NB_LAYERS
    stave_to_channel: dict[str, int] = field(default_factory=dict)
    layer_to_stave: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> GeometryRegistry:
        """Build registry from a JSON/YAML study config dict."""
        geom = config.get("geometry", config)
        staves = dict(geom.get("staves", config.get("staves", {})))
        if not staves:
            staves = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}

        layer_map_raw = geom.get("layer_to_stave", {})
        if layer_map_raw:
            layer_to_stave = {int(k): str(v) for k, v in layer_map_raw.items()}
        else:
            layer_to_stave = _default_layer_to_stave(staves)

        return cls(
            b_arm=int(geom.get("b_arm", B_ARM)),
            a_arm=int(geom.get("a_arm", A_ARM)),
            n_b_layers=int(geom.get("n_b_layers", NB_LAYERS)),
            stave_to_channel={str(k): int(v) for k, v in staves.items()},
            layer_to_stave=layer_to_stave,
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


def _default_layer_to_stave(staves: dict[str, int]) -> dict[int, str]:
    """Default mapping: sort staves by channel and assign consecutive layers."""
    ordered = sorted(staves.items(), key=lambda kv: kv[1])
    if len(ordered) != 4:
        raise ConfigurationError(
            f"expected four B staves (B2/B4/B6/B8), got {list(staves)}"
        )
    return {layer: name for layer, (name, _ch) in enumerate(ordered)}
