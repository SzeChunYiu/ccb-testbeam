#!/usr/bin/env python3
"""Compact source-bound H3 regression witness. Exit1=known defects, exit2=drift.

NOTE: no scientific release is authorized even if a future corrected source
makes this old witness no longer applicable. This is not production ROOT.
"""
from __future__ import annotations
import hashlib, json, math, runpy, sys
from pathlib import Path
import numpy as np

SOURCE = Path(__file__).with_name('stop_depth_original.py')
ORIGINAL = 'ca956eb7d07ea1e8044a61434d0c6bc273fb3736'

def main() -> int:
    try:
        raw = SOURCE.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blob!=ORIGINAL: raise ValueError('original source bytes changed')
        f=runpy.run_path(str(SOURCE))['summarize_stop_depth_h3']
        a=f(termination=['stop','stop'],stop_layer=[1.9,7.],weights=[1.,1.])
        b=f(termination=['stop'],stop_layer=[8.],weights=[1.])
        c=f(termination=['stop','escape'],stop_layer=[3.,float('nan')],weights=[0.,0.])
        with np.errstate(over='ignore',invalid='ignore'):
            d=f(termination=['stop','escape'],stop_layer=[1.,float('nan')],weights=[1e308,1e308])
        good=f(termination=['stop','escape','stop'],stop_layer=[1.,float('nan'),3.],weights=[1.,2.,3.])
        checks={
           'SD01_fractional_histogram_disagrees':sum(a['stop_distribution_unweighted'].values())==2 and a['stop_distribution_weighted_sum']==.5,
           'SD02_out_of_range_still_ok':b['mean_stop_layer_weighted_status']=='ok' and b['mean_stop_layer_weighted']==8.,
           'SD03_zero_weight_probs_reported_as_zeros':c['termination_prob_weighted_sum']==0. and 'termination_prob_weighted_status' not in c,
           'SD04_finite_weights_overflow_to_zero_probabilities':not math.isfinite(d['weight_sum_all']) and d['termination_prob_weighted_sum']==0.,
           'positive_ordinary_H3_still_normalizes':abs(good['termination_prob_weighted_sum']-1)<1e-14 and abs(good['stop_distribution_weighted_sum']-1)<1e-14
        }
        if not all(checks.values()): raise ValueError('witness no longer agrees with pinned source')
        print(json.dumps({'status':'KNOWN_SOURCE_DEFECTS_REPRODUCED','scientific_release':'NOT_AUTHORIZED',
           'source_git_blob':blob,'source_main':'a61427813344e29047ca9eb9b764182eb29e4c83',
           'issue_reporting':'NOT_POSTED_TOOL_SAFETY_BLOCK','checks':checks,
           'SD01':{'unweighted_count_sum':2,'weighted_probability_sum':a['stop_distribution_weighted_sum'],'mean_layer':a['mean_stop_layer_weighted']},
           'SD02':{'reported_layer':b['mean_stop_layer_weighted'],'weighted_hist_mass':b['stop_distribution_weighted_sum']},
           'SD03':{'weighted_termination_probability_sum':c['termination_prob_weighted_sum']},
           'SD04':{'source_total_weight_is_finite':math.isfinite(d['weight_sum_all']),
                   'source_weighted_termination_probability_sum':d['termination_prob_weighted_sum'],
                   'mathematically_correct_stop_fraction':.5},
           'physical_population_impact':'NOT_EVALUATED'},indent=2,sort_keys=True,allow_nan=False))
        return 1
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'SOURCE_OR_EXECUTION_DRIFT','error':str(error),
                          'scientific_release':'NOT_AUTHORIZED'}))
        return 2

if __name__=='__main__': sys.exit(main())
