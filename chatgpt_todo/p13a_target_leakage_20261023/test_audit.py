from __future__ import annotations
import csv
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import audit

class LeakageTests(unittest.TestCase):
    def test_source_and_archived_guard_bytes(self):
        audit.load_source()
        raw = (audit.ROOT/'source/leakage_checks.csv').read_bytes()
        got = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(got, '24eaaf8807f368c804cde11a6336c31cfefbc98b')
        rows = list(csv.DictReader(raw.decode().splitlines()))
        self.assertTrue(all(r['pass']=='True' for r in rows))

    def test_context_zero_guard_passes_despite_leak(self):
        r=audit.make_rows(audit.synthetic_waves(2))
        self.assertEqual(r['x_tab'].shape,(36,46))
        np.testing.assert_array_equal(r['context'][np.arange(36),r['sample_idx']],0)
        np.testing.assert_array_equal(audit.recover_from_features(r['x_tab'])*r['amp'],r['target_adc'])

    def test_all_dyadic_masked_rows_recover_exactly(self):
        r=audit.make_rows(audit.synthetic_waves())
        pred=audit.recover_from_features(r['x_tab'])*r['amp']
        np.testing.assert_array_equal(pred,r['target_adc'])

    def test_arbitrary_scale_roundoff(self):
        rng=np.random.default_rng(audit.SEED+1)
        w=rng.uniform(-2000,12000,(1024,18)).astype(np.float32)
        r=audit.make_rows(w)
        error=audit.recover_from_features(r['x_tab'])*r['amp']-r['target_adc']
        # Conservative floating-point envelope, not a detector/noise tolerance.
        eps=np.finfo(np.float32).eps
        bound=np.repeat(4*audit.N*eps*np.abs(w.astype(float)).sum(axis=1),audit.N)
        self.assertTrue(np.all(np.abs(error)<=bound))

    def test_feature_only_linear_coefficients(self):
        r=audit.make_rows(audit.synthetic_waves(3))
        coef=np.zeros(46);coef[:18]=-1;coef[42]=1
        np.testing.assert_array_equal(r['x_tab'].astype(float)@coef,audit.recover_from_features(r['x_tab']))

    def test_one_nonpeak_target_change_exposes_area(self):
        w=np.arange(18,dtype=np.float32)*64;w[9]=4096
        changed=w.copy();changed[7]+=256
        a=audit.make_rows(w[None,:]);b=audit.make_rows(changed[None,:])
        np.testing.assert_array_equal(a['context'][7],b['context'][7])
        self.assertEqual(np.flatnonzero(a['x_tab'][7]!=b['x_tab'][7]).tolist(),[42])
        self.assertEqual(float((audit.recover_from_features(b['x_tab'])[7]-audit.recover_from_features(a['x_tab'])[7])*4096),256)

    def test_area_only_removal_is_not_a_repair(self):
        w=np.arange(18,dtype=np.float32)*64;w[9]=4096
        changed=w.copy();changed[9]=8192
        a=audit.make_rows(w[None,:]);b=audit.make_rows(changed[None,:])
        keep=np.arange(46)!=42
        self.assertFalse(np.array_equal(a['x_tab'][9,keep],b['x_tab'][9,keep]))
        self.assertFalse(np.array_equal(a['context'][9],b['context'][9]))

    def test_auxiliary_route_carries_identical_area(self):
        r=audit.make_rows(audit.synthetic_waves(3))
        # CNN and attention are supplied context plus aux; aux column 24 contains area/A.
        np.testing.assert_array_equal(r['aux'][:,24],r['x_tab'][:,42])
        p=r['aux'][:,24].astype(float)-r['context'].astype(float).sum(axis=1)
        np.testing.assert_array_equal(p,audit.recover_from_features(r['x_tab']))

    def test_run_disjointness_does_not_remove_leak(self):
        w=audit.synthetic_waves(4)
        a=audit.make_rows(w,runs=[31,32,33,34])
        b=audit.make_rows(w,runs=[58,59,60,61])
        self.assertFalse(set(a['run']) & set(b['run']))
        np.testing.assert_array_equal(a['x_tab'],b['x_tab'])

    def test_oracle_target_not_required(self):
        r=audit.make_rows(audit.synthetic_waves(3))
        x=r['x_tab'].copy();expected=r['target_norm'].copy()
        del r
        np.testing.assert_array_equal(audit.recover_from_features(x),expected)

    def test_counterfactual_area_changes_oracle(self):
        r=audit.make_rows(audit.synthetic_waves(2));x=r['x_tab'].copy()
        x[:,42]+=1
        np.testing.assert_array_equal(audit.recover_from_features(x)-audit.recover_from_features(r['x_tab']),1)

    def test_blind_reference_invariant_all_raw_target_positions(self):
        rng=np.random.default_rng(audit.SEED+2)
        for w in rng.uniform(-1000,8000,(40,18)):
            for j in range(18):
                changed=w.copy();changed[j]=50000+j
                np.testing.assert_array_equal(audit.blind_reference(w,j),audit.blind_reference(changed,j))

    def test_tampered_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);shutil.copytree(audit.ROOT/'source',root/'source')
            with (root/'source/row_view.py').open('a') as f:f.write('# tamper\n')
            with self.assertRaisesRegex(ValueError,'drift'):audit.load_source(root)

    def test_cli_reports_known_flaw_with_nonzero_status(self):
        p=subprocess.run([sys.executable,str(audit.ROOT/'audit.py')],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,1,p.stdout+p.stderr)
        self.assertIn('TARGET_LEAKAGE_REPRODUCED',p.stdout)
        self.assertIn('NOT_AUTHORIZED',p.stdout)

if __name__=='__main__':unittest.main(verbosity=2)
