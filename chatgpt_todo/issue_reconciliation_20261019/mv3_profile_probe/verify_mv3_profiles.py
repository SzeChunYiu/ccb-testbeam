#!/usr/bin/env python3
"""Exact-module synthetic MV3 checks; not ROOT or detector validation.

Default: run observations and emit strict JSON to stdout, exit 1 when retained
source defects are reproduced. --test runs contract/reference unittests.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE / 'source' / 'src'
PINNED = {
 'ccb_mc_validation/studies/common.py': 'a6a3da4aa58c8346758c26ac64d23c4f827c90aa',
 'ccb_mc_validation/studies/mv3_stopping_depth.py': '9b0dfeaa6e74401345bc78c7ab82b33d7868b665',
}

def verify_sources():
    result = []
    for name, expected in PINNED.items():
        raw = (SRC / name).read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual != expected:
            raise ValueError('source drift: '+name)
        result.append({'path': 'src/'+name, 'git_blob': actual,
                       'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    return result

verify_sources()
sys.path.insert(0, str(SRC))
from ccb_mc_validation.studies import mv3_stopping_depth as mv3
from ccb_mc_validation.studies import common
from ccb_mc_validation.studies.common import StudyStatus, write_study_result

# Ensure an installed same-name package cannot replace the pinned modules.
for module, relative in [(common, "ccb_mc_validation/studies/common.py"),
                         (mv3, "ccb_mc_validation/studies/mv3_stopping_depth.py")]:
    if Path(module.__file__).resolve() != (SRC / relative).resolve():
        raise RuntimeError("module import escaped pinned source: " + relative)

MAPPING = {0:'B2',1:'B2',2:'B4',3:'B4',4:'B6',5:'B6',6:'B8',7:'B8'}

def records(hits, labels, stops):
    n = len(labels)
    return {'pdg': np.full(n,2212), 'stop_layer': np.asarray(stops),
            'edep_tot': np.ones(n), 'layer_hits': np.asarray(hits),
            'sample_label': np.asarray(labels, dtype=object)}


def occupancy_reference(hits, labels, group, mapping=MAPPING):
    """Unweighted track-stave presence, given a declared shared mask contract.

    Explicitly NOT a hardware-trigger, stopping, or weighted-event estimator.
    One track contributes at most once per stave even with multiple hit layers.
    """
    h=np.asarray(hits)
    labs=np.asarray(labels)
    if h.dtype.kind not in 'biu' or not np.all((h==0)|(h==1)):
        raise ValueError('finite binary mask required')
    if h.ndim != 2 or h.shape[1] != len(mapping) or labs.shape != (h.shape[0],):
        raise ValueError('exact track/layer/label schema required')
    if not np.isin(labs,['I','II','NONE']).all() or group not in ('I','II'):
        raise ValueError('unknown selection label')
    keys=sorted(set(mapping.values()))
    inds=[i for i,label in enumerate(labs) if label==group]
    counts=[sum(any(bool(h[i,j]) for j in mapping if mapping[j]==s) for i in inds) for s in keys]
    mass=sum(counts)
    return {'sample':group,'n_tracks':len(inds),'stave_order':keys,'stave_hit_counts':counts,
            'per_track_occupancy': [v/len(inds) for v in counts] if inds else None,
            'normalized_stave_hit_profile': [v/mass for v in counts] if mass else None,
            'status':'ESTIMABLE' if inds and mass else 'NOT_ESTIMABLE',
            'scientific_release':'NOT_AUTHORIZED'}


def observe():
    # One valid, declared track-level selection, touching every readout stave.
    crossing = records([[1,0,1,0,1,0,0,1]], ['I'], [7])
    control = mv3.run_mv3(crossing, data_profiles={'sample_i_stave_fractions': np.full(4,.25)})
    expected=occupancy_reference(crossing['layer_hits'],crossing['sample_label'],'I')
    # Hold Sample I fixed; add only a different sample to isolate population leakage.
    single=records([[1,0,0,0,0,0,0,0]],['I'],[0])
    extra=records([[1,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,1]],['I','II'],[0,7])
    target={'sample_i_stave_fractions': np.array([1.,0.,0.,0.])}
    before=mv3.run_mv3(single,data_profiles=target)
    after=mv3.run_mv3(extra,data_profiles=target)
    excluded=copy.deepcopy(extra); excluded['sample_label'][1]='NONE'
    if excluded['sample_label'][1] != 'NONE':
        raise RuntimeError('excluded label was truncated')
    excluded_out=mv3.run_mv3(excluded,data_profiles=target)
    invalid=records([[np.nan,-1.,0.,0.,0.,0.,0.,0.]],['I'],[0])
    invalid_out=mv3.run_mv3(invalid)
    nan_edep=copy.deepcopy(single); nan_edep.pop('layer_hits')
    nan_edep['edep_per_layer']=np.array([[np.nan,0.,0.,0.,0.,0.,0.,0.]])
    nan_edep_out=mv3.run_mv3(nan_edep)
    short=records([[True,False]],['I'],[0]); short_out=mv3.run_mv3(short)
    absent=copy.deepcopy(single); absent.pop('layer_hits'); absent_out=mv3.run_mv3(absent)
    nonfinite=mv3.run_mv3(single,data_profiles={'sample_i_stave_fractions': np.array([np.nan,0.,0.,0.])})
    with tempfile.TemporaryDirectory() as temp:
        saved=write_study_result(nonfinite,temp).read_text()
    return {
      'status':'SOURCE_DEFECTS_REPRODUCED', 'scientific_release':'NOT_AUTHORIZED',
      'source_main':'a61427813344e29047ca9eb9b764182eb29e4c83',
      'scope':'complete source-hash-matched MV3 module AND original common.py dependency; no stubs; synthetic in-memory records and actual JSON writer; not ROOT/CLI/Geant4',
      'sources':verify_sources(),
      'MP01_measurand':{'source_status':control.status.value,'source_deepest_layer_counts':control.metrics['truth_stave_counts'],
        'source_score':control.metrics['mapping_hypothesis_scores']['sample_i_stave_fractions'],
        'matching_occupancy_reference':expected,'matched_occupancy_score':0.0},
      'MP02_sample_pooling':{'source_score_before':before.metrics['mapping_hypothesis_scores']['sample_i_stave_fractions'],
        'source_score_after_other_sample':after.metrics['mapping_hypothesis_scores']['sample_i_stave_fractions'],
        'source_score_after_excluded_sample':excluded_out.metrics['mapping_hypothesis_scores']['sample_i_stave_fractions'],
        'source_I_occupancy_before':before.metrics['layer_occupancy_sample_I'],
        'source_I_occupancy_after':after.metrics['layer_occupancy_sample_I'],
        'reference_I_before':occupancy_reference(single['layer_hits'],single['sample_label'],'I'),
        'reference_I_after':occupancy_reference(extra['layer_hits'],extra['sample_label'],'I')},
      'MP03_input_and_denominators':{'nan_and_negative_mask_status':invalid_out.status.value,
        'nan_and_negative_mask_occupancy':invalid_out.metrics['layer_occupancy_sample_I'],
        'nan_edep_status':nan_edep_out.status.value,'nan_edep_occupancy':nan_edep_out.metrics['layer_occupancy_sample_I'],
        'empty_II_n':control.cutflow['n_sample_II'],'empty_II_source':control.metrics['layer_occupancy_sample_II'],
        'empty_II_reference':occupancy_reference(crossing['layer_hits'],crossing['sample_label'],'II'),
        'short_mask_status':short_out.status.value,'short_mask_reported_layers':len(short_out.metrics['layer_occupancy_sample_I'])},
      'MP04_writer':{'source_status':nonfinite.status.value,
        'mapping_score_is_nan':bool(np.isnan(nonfinite.metrics['mapping_hypothesis_scores']['sample_i_stave_fractions'])),
        'writer_accepted':True, 'literal_NaN_in_written_JSON': 'NaN' in saved},
      'positive_control_missing_mask':{'source_status':absent_out.status.value,'reason':absent_out.metrics['reason'],
        'boundary':'This protection prevents converter-shaped inputs with no per-layer mask from executing MV3 profiles. Do NOT attribute new numerical MV3 results to root_truth alone.'},
      'production_impact':'NOT_EVALUATED',
      'review_perspectives':'detector measurands, transport hit vs endpoint, statistical population, source/serialization; one assistant, not independent human signoff'
    }

class Tests(unittest.TestCase):
    def test_exact_source_identities(self): self.assertEqual(len(verify_sources()),2)
    def test_known_occupancy_not_endpoint(self):
        o=observe()['MP01_measurand']; self.assertEqual(o['source_score'],1.5)
        self.assertEqual(o['matching_occupancy_reference']['normalized_stave_hit_profile'],[.25]*4)
    def test_other_sample_alters_legacy_score(self):
        o=observe()['MP02_sample_pooling']; self.assertEqual(o['source_score_before'],0.)
        self.assertEqual(o['source_score_after_other_sample'],1.)
        self.assertEqual(o['reference_I_before'],o['reference_I_after'])
    def test_excluded_sample_alters_legacy_score(self):
        self.assertEqual(observe()['MP02_sample_pooling']['source_score_after_excluded_sample'],1.)
    def test_source_mask_nan_is_true(self):
        self.assertEqual(observe()['MP03_input_and_denominators']['nan_and_negative_mask_occupancy'][:2],[1.,1.])
    def test_source_nan_edep_is_false(self):
        self.assertEqual(observe()['MP03_input_and_denominators']['nan_edep_occupancy'],[0.]*8)
    def test_source_empty_group_fabricates_zeros(self):
        o=observe()['MP03_input_and_denominators']; self.assertEqual(o['empty_II_n'],0)
        self.assertEqual(o['empty_II_source'],[0.]*8); self.assertIsNone(o['empty_II_reference']['per_track_occupancy'])
    def test_source_accepts_incomplete_layer_schema(self):
        o=observe()['MP03_input_and_denominators']; self.assertEqual(o['short_mask_status'],'PRODUCTION')
        self.assertEqual(o['short_mask_reported_layers'],2)
    def test_actual_writer_accepts_nonstandard_nan(self):
        o=observe()['MP04_writer']; self.assertTrue(o['mapping_score_is_nan']); self.assertTrue(o['literal_NaN_in_written_JSON'])
        self.assertEqual(o['source_status'],'PRODUCTION')
    def test_missing_layer_mask_remains_blocked(self):
        self.assertEqual(observe()['positive_control_missing_mask']['source_status'],'BLOCKED')
    def test_missing_sample_labels_remains_blocked(self):
        r=records([[1]*8],['NONE'],[7]); self.assertEqual(mv3.run_mv3(r).status,StudyStatus.BLOCKED)
    def test_reference_rejects_nonbinary_and_nonfinite(self):
        for val in [np.nan,-1,2,np.inf,'False']:
            with self.subTest(val=str(val)),self.assertRaises(ValueError): occupancy_reference([[val]*8],['I'],'I')
    def test_reference_requires_complete_geometry(self):
        with self.assertRaises(ValueError): occupancy_reference([[True]],['I'],'I')
    def test_reference_rejects_unknown_population(self):
        with self.assertRaises(ValueError): occupancy_reference([[True]*8],['typo'],'I')
    def test_reference_no_double_count_of_same_stave(self):
        r=occupancy_reference([[1,1,0,0,0,0,0,0]],['I'],'I')
        self.assertEqual(r['stave_hit_counts'],[1,0,0,0])
    def test_reference_all_permutations_preserve_event_membership(self):
        h=np.array([[1,1,0,0,0,0,0,0],[1]*8,[0,0,1,1,0,0,0,0],[0,0,0,0,0,0,1,1]])
        labels=np.array(['I','II','I','NONE']); want=occupancy_reference(h,labels,'I')
        for perm in itertools.permutations(range(4)):
            ix=list(perm); self.assertEqual(occupancy_reference(h[ix],labels[ix],'I'),want)
    def test_no_observed_hit_normalization_is_not_estimable(self):
        r=occupancy_reference([[0]*8],['I'],'I'); self.assertIsNone(r['normalized_stave_hit_profile'])
    def test_observations_are_strict_json(self):
        s=json.dumps(observe(),allow_nan=False,sort_keys=True)
        self.assertEqual(json.loads(s)['scientific_release'],'NOT_AUTHORIZED')

if __name__=='__main__':
    if '--test' in sys.argv:
        unittest.main(argv=[sys.argv[0]],verbosity=2)
    else:
        print(json.dumps(observe(),indent=2,sort_keys=True,allow_nan=False))
        raise SystemExit(1)
