#!/usr/bin/env python3
"""Versioned per-channel polarity lock for amplitude/timing extraction (#954).

Signed pulse reconstruction is:

    y[e,c,s] = polarity[c] * (raw[e,c,s] - baseline[e,c])

with polarity[c] in {-1, +1}. Ambiguous channels must be quarantined rather than
forced positive via abs().
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

DEFAULT_POLARITY_PATH = Path(__file__).resolve().parents[1] / "configs" / "channel_polarity_v2.json"


@dataclass(frozen=True)
class ChannelPolarityMap:
    version: str
    sample_period_ns: float
    baseline_samples: list[int]
    channel_polarity: dict[str, int]
    stave_channel: dict[str, int]
    status: str
    provenance: dict

    def polarity_for_channel(self, channel: int) -> int:
        key = str(int(channel))
        if key not in self.channel_polarity:
            raise KeyError(f"channel {channel} missing from polarity map {self.version}")
        value = int(self.channel_polarity[key])
        if value not in (-1, 1):
            raise ValueError(f"polarity for channel {channel} must be ±1, got {value}")
        return value

    def polarity_vector(self, n_channels: int) -> np.ndarray:
        return np.asarray(
            [self.polarity_for_channel(ch) for ch in range(n_channels)],
            dtype=float,
        )

    def to_dict(self) -> dict:
        return asdict(self)


def load_polarity_map(path: Path | None = None) -> ChannelPolarityMap:
    target = Path(path) if path is not None else DEFAULT_POLARITY_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    return ChannelPolarityMap(
        version=str(payload["version"]),
        sample_period_ns=float(payload["sample_period_ns"]),
        baseline_samples=[int(x) for x in payload["baseline_samples"]],
        channel_polarity={str(k): int(v) for k, v in payload["channel_polarity"].items()},
        stave_channel={str(k): int(v) for k, v in payload["stave_channel"].items()},
        status=str(payload["status"]),
        provenance=dict(payload.get("provenance", {})),
    )


def apply_polarity(
    waveforms: np.ndarray,
    polarity: np.ndarray | Mapping[int, int] | ChannelPolarityMap,
) -> np.ndarray:
    """Apply per-channel polarity to baseline-corrected waveforms.

    ``waveforms`` shape: (n_events, n_channels, n_samples) or (n_pulses, n_samples)
    when ``polarity`` is a scalar ±1 broadcast via a length-1 vector.
    """
    wave = np.asarray(waveforms, dtype=float)
    if isinstance(polarity, ChannelPolarityMap):
        if wave.ndim != 3:
            raise ValueError("ChannelPolarityMap requires waveforms shaped (n, n_channels, n_samples)")
        vec = polarity.polarity_vector(wave.shape[1])
        return wave * vec[None, :, None]
    if isinstance(polarity, Mapping):
        if wave.ndim != 3:
            raise ValueError("mapping polarity requires 3-D waveforms")
        vec = np.asarray([int(polarity[ch]) for ch in range(wave.shape[1])], dtype=float)
        return wave * vec[None, :, None]
    vec = np.asarray(polarity, dtype=float)
    if not np.all(np.isin(vec, (-1.0, 1.0))):
        raise ValueError(f"polarity values must be ±1, got {vec.tolist()}")
    if wave.ndim == 3:
        if vec.shape != (wave.shape[1],):
            raise ValueError("polarity vector length must match n_channels")
        return wave * vec[None, :, None]
    if wave.ndim == 2:
        if vec.size == 1:
            return wave * float(vec.reshape(-1)[0])
        raise ValueError("2-D waveforms require a scalar polarity or use 3-D apply")
    raise ValueError("waveforms must be 2-D or 3-D")


def mask_isolated_dropouts(corrected: np.ndarray) -> np.ndarray:
    """Zero isolated single-sample outliers (e.g. ADC low-word defects, #954).

    A sample is masked when its absolute deviation exceeds 4x the next-largest
    deviation in the same waveform AND both immediate neighbours stay below 25%
    of it. Physical pulses span several samples, so a genuine pulse is never
    masked; an isolated corrupt word cannot outvote it.
    """
    y = np.asarray(corrected, dtype=float).copy()
    absd = np.abs(y)
    n = y.shape[-1]
    order = np.argsort(absd, axis=-1)
    idx = order[..., -1]
    largest = np.take_along_axis(absd, idx[..., None], axis=-1)[..., 0]
    second = np.take_along_axis(absd, order[..., -2:-1], axis=-1)[..., 0]
    left = np.take_along_axis(absd, np.clip(idx - 1, 0, n - 1)[..., None], axis=-1)[..., 0]
    right = np.take_along_axis(absd, np.clip(idx + 1, 0, n - 1)[..., None], axis=-1)[..., 0]
    lonely = (left < 0.25 * largest) & (right < 0.25 * largest)
    dominant = largest > 4.0 * np.maximum(second, 1.0)
    mask = lonely & dominant
    if not np.any(mask):
        return y
    peaks = np.take_along_axis(y, idx[..., None], axis=-1)
    np.put_along_axis(y, idx[..., None], np.where(mask[..., None], 0.0, peaks), axis=-1)
    return y


def infer_channel_polarity(
    raw_waveforms: np.ndarray,
    baseline_samples: list[int],
    *,
    snr_cut: float = 8.0,
) -> tuple[np.ndarray, dict]:
    """Infer ±1 polarity per channel from high-SNR pulses.

    Uses the sign of the largest absolute excursion after baseline subtraction.
    Returns (polarity[n_channels], diagnostic dict). Does not invent confidence
    beyond empirical fraction agreement among selected pulses.
    """
    raw = np.asarray(raw_waveforms, dtype=float)
    if raw.ndim != 3:
        raise ValueError("raw_waveforms must be (n_events, n_channels, n_samples)")
    n_events, n_channels, _ = raw.shape
    base = np.median(raw[:, :, baseline_samples], axis=-1)
    corrected = raw - base[:, :, None]
    corrected = mask_isolated_dropouts(corrected)
    polarities = np.ones(n_channels, dtype=int)
    diagnostics: dict[str, dict] = {}
    for ch in range(n_channels):
        y = corrected[:, ch, :]
        peak_pos = np.max(y, axis=-1)
        peak_neg = np.min(y, axis=-1)
        noise = np.median(np.abs(y[:, baseline_samples]), axis=-1) + 1e-9
        snr_pos = peak_pos / noise
        snr_neg = (-peak_neg) / noise
        use_pos = snr_pos >= snr_cut
        use_neg = snr_neg >= snr_cut
        # Prefer the stronger SNR class when both qualify.
        signed = np.where(snr_pos >= snr_neg, 1, -1)
        strong = (snr_pos >= snr_cut) | (snr_neg >= snr_cut)
        if not np.any(strong):
            # Fail closed for authorising use: do not invent +1 (#954).
            polarities[ch] = 0
            diagnostics[str(ch)] = {
                "status": "UNMEASURED_LOW_SNR",
                "n_strong": 0,
                "frac_positive_preference": None,
                "assigned": None,
                "authorising": False,
            }
            continue
        frac_pos = float(np.mean(signed[strong] > 0))
        assigned = 1 if frac_pos >= 0.5 else -1
        ambiguous = 0.3 < frac_pos < 0.7
        polarities[ch] = 0 if ambiguous else assigned
        diagnostics[str(ch)] = {
            "status": "AMBIGUOUS" if ambiguous else "MEASURED",
            "n_strong": int(np.count_nonzero(strong)),
            "n_pos_candidates": int(np.count_nonzero(use_pos)),
            "n_neg_candidates": int(np.count_nonzero(use_neg)),
            "frac_positive_preference": frac_pos,
            "assigned": None if ambiguous else int(assigned),
            "authorising": (not ambiguous),
        }
    return polarities, {"n_events": int(n_events), "channels": diagnostics}
