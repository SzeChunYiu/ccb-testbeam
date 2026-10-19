#!/usr/bin/env python3
"""Pinned-full-checkout probe. Expected legacy defect exit 1; blocked/drift exit 2."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

SOURCE_BLOB = "7a664c25c38efb0610e577814baa50ecb9835d59"

def fixture(momentum, *, weights=None, layers=None):
    layers = [0, 7, 7] if layers is None else layers
    n = len(layers)
    def arr(xs): return np.array([np.asarray(xs)],dtype=object)
    data = {"Sci_bar_TrackID":arr([7]*n),"Sci_bar_LayerID":arr(layers),
            "Sci_bar_LayerID1":arr([1]*n),"Sci_bar_PDG":arr([2212]*n),
            "Sci_bar_EDep":arr([1.0]*n),"Sci_bar_TrackLength":arr([1.0]*n),
            "Sci_bar_Momentum_X":arr(momentum),
            "Sci_bar_Momentum_Y":arr([0.0]*n),
            "Sci_bar_Momentum_Z":arr([0.0]*n)}
    if weights is not None: data["PrimaryWeight"] = arr(weights)
    return data

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    args=parser.parse_args()
    repo=args.repo.resolve()
    source=repo/'src/ccb_mc_validation/truth/track_builder.py'
    try:
        body=source.read_bytes()
        sha=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
        if sha!=SOURCE_BLOB:
            raise ValueError(f'source drift {sha} != {SOURCE_BLOB}; re-audit before interpretation')
        sys.path.insert(0,str(repo/'src'))
        from ccb_mc_validation.truth.track_builder import build_track_records
        weight_observations=[]
        for label,weights in [('missing_vector',[]),('nan',[float('nan')]),
                              ('negative',[-2.5]),('conflicting_replicas',[2,5])]:
            x=build_track_records(fixture([.5,.4,.001],weights=weights))
            weight_observations.append(dict(case=label,weight=x[0]['event_weight'],
                                             weighted=x[0]['weighted']))
        permutations=[]
        for label,pm in [('low_last',[.5,.5,.001]),('high_last',[.5,.001,.5])]:
            x=build_track_records(fixture(pm))
            permutations.append(dict(case=label,termination=x[0]['termination'],
                                     last_observed_layer=x[0]['last_observed_layer'],
                                     last_kinetic_energy=x[0]['ekin_last_observed']))
        result={'status':'LEGACY_DEFECTS_REPRODUCED','scientific_release':'NOT_AUTHORIZED',
                'source_git_blob':sha,'weights':weight_observations,'permutations':permutations}
        if not (weight_observations[0]['weight']==1 and weight_observations[0]['weighted']
                and weight_observations[1]['weight']==1 and weight_observations[2]['weight']<0
                and weight_observations[3]['weight']==2
                and {x['termination'] for x in permutations}=={'stop','escape'}):
            result['status']='SOURCE_BEHAVIOR_DIFFERS_FROM_FROZEN_WITNESS_REVIEW_REQUIRED'
        print(json.dumps(result,indent=2,allow_nan=False))
        return 1 if result['status']=='LEGACY_DEFECTS_REPRODUCED' else 2
    except (OSError, ValueError, KeyError, TypeError, ImportError, IndexError) as exc:
        print(json.dumps({'status':'BLOCKED_NOT_EXECUTED','reason':str(exc),
                          'scientific_release':'NOT_AUTHORIZED'}))
        return 2

if __name__=='__main__': raise SystemExit(main())
