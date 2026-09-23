#!/usr/bin/env python3
"""Independent numeric check of the executed raw-PID notebook.

Reads the hash-bound input artifact, not the notebook's derived observables.
No waveform selection occurs before reconstruction. No input bytes are modified.
Run: python reproduce_core.py --inputs inputs --out independent_check.json
The full notebook additionally supplies plots, bootstrap intervals and diagnostics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HF_REV = '0b25f28e0144a3d1597afcdd3446ad1abd3d2d74'
MC_SHA = 'd67b0bf47e1485877af9b9732b0139bbf5a2fd88733e6a7c2d4e2266184c5c40'
SEED = 20260907
RUNS_I = tuple(range(44, 58))
RUNS_II = tuple(range(58, 64)) + (65,)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.inputs / 'manifest.json').read_text())
    require(manifest['revision'] == HF_REV, 'HF revision mismatch')
    require(not manifest.get('failures'), 'incomplete retrieval')
    require(digest(args.inputs / 'raw_adc.npz') == manifest['raw_npz_sha256'], 'raw transport hash mismatch')
    with np.load(args.inputs / 'raw_adc.npz', allow_pickle=False) as z:
        words = z['adc_words']
        runs = z['run_no']
        ordinal = z['event_idx']
    require(words.shape == (len(runs), 128), 'one 128-word row per event required')
    require(len(runs) == manifest['n_events'], 'manifest row count mismatch')
    require(set(runs) == set(RUNS_I + RUNS_II), 'incomplete or unexpected run set')
    require(np.isfinite(words).all(), 'nonfinite raw word: no zero replacement allowed')
    require(not pd.DataFrame({'run': runs, 'row': ordinal}).duplicated().any(), 'source-row collision')
    # Documented truncated channel-major 8x18 frame. Primary channels fit in prefix.
    amplitudes = np.column_stack([
        words[:, start:start+18].max(axis=1) - np.median(words[:, start:start+4], axis=1)
        for start in (0, 36, 72, 108)
    ])
    delta = amplitudes[:, 0]
    residual = amplitudes[:, 1:].sum(axis=1)
    selected = delta > 1000.0
    downstream = (amplitudes[:, 1:] > 1000.0).any(axis=1)
    results: dict = {'input_revision': HF_REV, 'raw_events': len(runs), 'raw_samples': []}
    for sample, group in [('I', RUNS_I), ('II', RUNS_II)]:
        population = np.isin(runs, group)
        mask = population & selected
        results['raw_samples'].append({
            'sample': sample, 'raw_events': int(population.sum()), 'B2_anchor_events': int(mask.sum()),
            'median_delta_adc': float(np.median(delta[mask])),
            'median_residual_adc': float(np.median(residual[mask])),
            'pearson_r': float(np.corrcoef(delta[mask], residual[mask])[0, 1]),
            'any_downstream_gt1000_fraction': float(downstream[mask].mean()),
        })
    results['correct_layout_channel_counts_gt1000'] = (amplitudes > 1000.0).sum(axis=0).tolist()
    del words
    mcmeta = manifest.get('mc', {})
    require(mcmeta.get('sha256') == MC_SHA, 'MC original source hash mismatch')
    require(digest(args.inputs / 'mc_deposits.csv.gz') == mcmeta.get('csv_sha256'), 'MC transport hash mismatch')
    mc = pd.read_csv(args.inputs / 'mc_deposits.csv.gz')
    require(not mc.duplicated(['source_file_id', 'run_id', 'event_id']).any(), 'MC key collision')
    d = mc[[f'edep_layer_{j}' for j in range(8)]].to_numpy(float)
    require(np.isfinite(d).all() and (d >= 0).all(), 'invalid physical deposit')
    require((mc.PrimaryWeight == 1).all(), 'this check is for the bound unit-weight campaign')
    de, es, ef = d[:, 1], d[:, [3, 5, 7]].sum(1), d[:, 2:].sum(1)
    results['mc_sum'] = {
        'events': len(mc), 'stored_full_wrong_events': int((np.abs(mc.E_mc_full_mev.to_numpy()-ef)>1e-8).sum()),
        'stored_full_equals_sparse_all': bool(np.allclose(mc.E_mc_full_mev, es)),
        'full_minus_sparse_median_mev': float(np.median(ef-es)),
    }
    binary = mc.truth_species.isin(['p', 'd']).to_numpy()
    y = mc.truth_species.to_numpy()[binary] == 'd'
    groups = mc.event_id.to_numpy()[binary] // 10000
    features = {
        'sparse2_logistic': np.log1p(np.column_stack([de, es])[binary]),
        'sparse2_HGB': np.log1p(np.column_stack([de, es])[binary]),
        'four_readout_HGB': np.log1p(d[binary][:, [1, 3, 5, 7]]),
        'full2_HGB_diagnostic': np.log1p(np.column_stack([de, ef])[binary]),
    }
    folds = list(GroupKFold(5).split(features['sparse2_logistic'], y, groups))
    results['mc_models'] = []
    for name, x in features.items():
        score = np.full(len(y), np.nan)
        for train, test in folds:
            require(not set(groups[train]) & set(groups[test]), 'group leakage')
            if name.endswith('logistic'):
                model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=1.0, random_state=SEED))
            else:
                model = HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, learning_rate=.07,
                    min_samples_leaf=30, early_stopping=False, random_state=SEED)
            model.fit(x[train], y[train])
            score[test] = model.predict_proba(x[test])[:, 1]
        require(np.isfinite(score).all(), 'incomplete out-of-fold predictions')
        results['mc_models'].append({'model': name, 'events': len(y),
            'ROC_AUC': float(roc_auc_score(y, score)), 'AP': float(average_precision_score(y, score))})
    results['beam_species_identification_validated'] = False
    results['scope'] = 'Raw ADC conditional on prefix contract; MC stored-label agreement, not detector PID performance'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, allow_nan=False))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
