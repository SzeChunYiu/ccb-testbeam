#!/usr/bin/env python3
"""P13A-LK01: source-function leakage witness, not raw ROOT or fit reproduction.

Exit 1: pinned-source defect reproduced; exit 2: source/execution drift.
No output of this program authorizes detector or publication claims.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from typing import Dict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE_MAIN = 'a61427813344e29047ca9eb9b764182eb29e4c83'
SOURCE_BLOB = '05f2175ff3cc587a5f16f6f00b855fa1d77cc575'
EXCERPT_SHA256 = 'c5d1080c983af3acfda246e1e62dd36ff4cb688e0cee442dd026f93c69096743'
HELPER_SHA256 = '13c42b4eb3342643cc32f31c0a6ee5375470507077ab65073a208f66a739937d'
SEED = 20261023
N = 18
STAVES = ['B2', 'B4', 'B6', 'B8']
CONFIG = {'samples_per_channel': N, 'phase_bins': {'all': list(range(N))}}


def load_source(root: Path = ROOT):
    ns = {'np': np, 'pd': pd, 'Dict': Dict, 'STAVE_NAMES': STAVES}
    for name, digest in [('phase_for_sample.py', HELPER_SHA256), ('row_view.py', EXCERPT_SHA256)]:
        path = root / 'source' / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'source excerpt drift: {name}')
        exec(compile(raw, str(path), 'exec'), ns)
    return ns['row_view']


def make_rows(waves: np.ndarray, runs=None, pulse_idx=None) -> dict:
    """Synthetic metadata follows scan_raw's max/argmax/sum expressions.

    This is NOT execution of scan_raw, ROOT ingestion, templates, or training.
    Template/interpolation arrays are zeros to isolate the full-area leak.
    """
    w = np.asarray(waves, dtype=np.float32)
    if w.ndim != 2 or w.shape[1] != N or not np.isfinite(w).all():
        raise ValueError('finite (n,18) waveforms required')
    m = len(w)
    meta = pd.DataFrame({
        'amplitude_adc': w.max(axis=1),
        'peak_sample': w.argmax(axis=1).astype(np.int8),
        'area_adc_samples': w.sum(axis=1).astype(np.float32),
        'run': np.full(m, 58, dtype=np.int16) if runs is None else runs,
        'stave_idx': np.arange(m, dtype=np.int8) % 4,
    })
    idx = np.arange(m) if pulse_idx is None else np.asarray(pulse_idx)
    zero = np.zeros((len(idx), N), dtype=np.float32)
    return load_source()(CONFIG, w, meta, idx, zero, zero)


def recover_from_features(x_tab: np.ndarray) -> np.ndarray:
    """No target argument or fit: normalized target = full area/A - context sum."""
    x = np.asarray(x_tab, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2*N + len(STAVES) + 6:
        raise ValueError('unexpected feature schema')
    area_col = 2*N + len(STAVES) + 2
    return x[:, area_col] - x[:, :N].sum(axis=1)


def blind_reference(raw: np.ndarray, j: int) -> np.ndarray:
    """Review-only invariance control: mask raw target BEFORE all preprocessing.

    Not a candidate detector calibration, not wired into any production path.
    """
    x = np.asarray(raw, dtype=np.float64).copy()
    if x.shape != (N,) or not 0 <= j < N or not np.isfinite(x).all():
        raise ValueError('invalid control waveform')
    keep = np.arange(N) != j
    x[j] = 0.0
    base_indices = [k for k in range(4) if k != j]
    base = np.median(x[base_indices])
    c = x - base
    c[j] = 0.0
    a = max(1.0, float(np.max(c[keep])))
    c /= a
    peak = np.flatnonzero(keep)[np.argmax(c[keep])]
    return np.r_[c, a, c[keep].sum(), peak, j]


def synthetic_waves(n: int = 4096) -> np.ndarray:
    # Independent artificial sample values; no pulse-physics information to learn.
    rng = np.random.default_rng(SEED)
    w = rng.integers(-2048, 12001, size=(n, N)).astype(np.float32)
    w[:, 9] = 16384.0  # synthetic fixed max, NOT an assertion about hardware bits.
    return w


def evaluate() -> dict:
    waves = synthetic_waves()
    rows = make_rows(waves, np.where(np.arange(len(waves)) % 2, 58, 65))
    pred = recover_from_features(rows['x_tab'])
    error = pred * rows['amp'].astype(float) - rows['target_adc'].astype(float)
    source_mask_pass = bool(np.all(rows['context'][np.arange(len(pred)), rows['sample_idx']] == 0))
    # Nonpeak intervention: retain amplitude, peak and all observed samples.
    w = np.arange(N, dtype=np.float32) * 64
    w[9] = 4096.0
    j = 7
    changed = w.copy(); changed[j] += 256.0
    a = make_rows(w[None, :]); b = make_rows(changed[None, :])
    changed_cols = np.flatnonzero(a['x_tab'][j] != b['x_tab'][j]).tolist()
    delta_reco = float((recover_from_features(b['x_tab'])[j] - recover_from_features(a['x_tab'])[j])*4096.)
    # Removing only area is insufficient: amplitude normalization still sees a hidden max.
    w2 = w.copy(); w2[9] = 8192.0
    c = make_rows(w2[None, :])
    cols_no_area = np.arange(46) != 42
    peak_leak = bool(np.any(a['x_tab'][9, cols_no_area] != c['x_tab'][9, cols_no_area]))
    # Power-of-two max case used separately for exact equality.
    exact_w = w[None, :]
    exact_rows = make_rows(exact_w)
    exact_error = recover_from_features(exact_rows['x_tab'])*exact_rows['amp'] - exact_rows['target_adc']
    if not source_mask_pass or changed_cols != [42] or delta_reco != 256.0:
        raise ValueError('pinned witness expectations changed')
    if float(np.max(np.abs(error))) > 0.01 or not peak_leak:
        raise ValueError('oracle or noninterference witness drift')
    rng=np.random.default_rng(SEED+1)
    arbitrary=rng.uniform(-2000,12000,(1024,N)).astype(np.float32)
    ar=make_rows(arbitrary)
    ae=recover_from_features(ar['x_tab'])*ar['amp']-ar['target_adc']
    return {
        'arbitrary_scale_masked_rows': len(ae),
        'arbitrary_scale_oracle_mae_adc': float(np.mean(np.abs(ae))),
        'arbitrary_scale_oracle_max_abs_error_adc': float(np.max(np.abs(ae))),
        'atom': 'P13A-LK01',
        'status': 'TARGET_LEAKAGE_REPRODUCED',
        'scientific_release': 'NOT_AUTHORIZED',
        'source_main': SOURCE_MAIN, 'source_git_blob': SOURCE_BLOB,
        'executed_scope': 'verbatim row_view function + phase helper, not full producer',
        'fixture_kind': 'SYNTHETIC_NONPHYSICAL_INDEPENDENT_INTEGER_SAMPLES',
        'seed': SEED, 'n_synthetic_waveforms': len(waves), 'n_masked_rows': len(pred),
        'feature_columns': rows['x_tab'].shape[1], 'full_area_feature_column_zero_based': 42,
        'context_target_zero_check_passes': source_mask_pass,
        'feature_only_oracle_mae_adc': float(np.mean(np.abs(error))),
        'feature_only_oracle_max_abs_error_adc': float(np.max(np.abs(error))),
        'exact_dyadic_fixture_max_abs_error_adc': float(np.max(np.abs(exact_error))),
        'nonpeak_target_intervention_adc': 256.0,
        'nonpeak_changed_feature_columns': changed_cols,
        'nonpeak_recovered_target_change_adc': delta_reco,
        'removing_only_area_still_leaks_hidden_peak': peak_leak,
        'raw_root_executed': False, 'historical_models_retrained': False,
        'complete_large_heldout_csv_acquired': False,
        'production_repair_integrated': False, 'human_review': 'NOT_OBTAINED',
        'detector_noise_or_metric_bias': 'NOT_ESTIMATED',
    }


def main() -> int:
    try:
        print(json.dumps(evaluate(), indent=2, sort_keys=True, allow_nan=False))
        return 1
    except Exception as exc:
        print(json.dumps({'status': 'SOURCE_OR_EXECUTION_ERROR', 'error': str(exc), 'scientific_release':'NOT_AUTHORIZED'}, sort_keys=True, allow_nan=False))
        return 2

if __name__ == '__main__':
    sys.exit(main())
