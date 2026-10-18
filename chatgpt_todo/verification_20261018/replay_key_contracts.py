#!/usr/bin/env python3
"""Replay key #1628 contract failures without real ROOT or Geant4.

From the repository: python chatgpt_todo/verification_20261018/replay_key_contracts.py
Exit 1 means an unmet contract; exit 2 means the harness failed to execute.
Sources are hashed in the output. --a09-functions is for the explicitly labelled
function-excerpt harness used in the original local execution, not real ROOT.
"""
from __future__ import annotations
import argparse, contextlib, csv, hashlib, importlib.util, io, json, sys, tempfile, types
from pathlib import Path
import numpy as np
import pandas as pd


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(root: Path, a09_path: Path, excerpt: bool) -> dict:
    paths = [root / 'scripts/check_rmax_formula.py', root / 'scripts/channel_polarity.py', a09_path]
    rmax, polarity, energy = [load(f'ccb1628_{i}', p) for i, p in enumerate(paths)]
    checks = []
    def record(name: str, ok: bool, observed: dict):
        checks.append({'id': name, 'contract_pass': bool(ok), 'observed': observed})
    def rejects(name: str, fn):
        try:
            fn()
        except ValueError as exc:
            record(name, True, {'rejected': type(exc).__name__})
        else:
            record(name, False, {'rejected': False})
    with tempfile.TemporaryDirectory(prefix='ccb1628-synthetic-') as temp:
        work = Path(temp); (work / 'docs').mkdir()
        wiki = '\n'.join(['Rmax — pile-up tolerance (canonical) | withheld',
            'Rmax is withheld pending S-STAT-003',
            'No accepted numerical Rmax until S-STAT-003 resolves the criterion'])
        first = dict.fromkeys(rmax.FIELDS, '')
        first.update(claim_id='CL-010', unit='MHz', truth_type='derived_model_conflicted',
            status='BLOCKED', allowed_status_validated='NO', ci_status='NOT_APPLICABLE_WITH_REASON',
            blocked_by='S-STAT-003', notes='accepted value is withheld; does not identify event-arrival rate; live exposure; absolute Rmax')
        second = dict.fromkeys(rmax.FIELDS, '')
        second.update(claim_id='CL-011', current_value=repr(rmax.TAU_CL011_NS), unit='ns',
            truth_type='data_measurement', status='DONE_DATA_ONLY')
        for case in ['valid_blocked','promoted','invented_rate','wrong_unit','missing_notice','forbidden_claim']:
            a,b = first.copy(), second.copy(); text = wiki
            if case == 'promoted': a.update(status='VALIDATED', allowed_status_validated='YES')
            if case == 'invented_rate': a['current_value'] = '99.0'
            if case == 'wrong_unit': b['unit'] = 'us'
            if case == 'missing_notice': text = ''
            if case == 'forbidden_claim': text += '\n3.05 MHz is measured (occupancy)'
            (work/'WIKI.md').write_text(text)
            with (work/'docs/claim_ledger.csv').open('w', newline='') as f:
                writer=csv.DictWriter(f, fieldnames=rmax.FIELDS);writer.writeheader();writer.writerows([a,b])
            with contextlib.redirect_stdout(io.StringIO()):
                rc=rmax.main(['--root', str(work), '--output-json', str(work/'out.json')])
            payload=json.loads((work/'out.json').read_text())
            record('RMAX_'+case, (rc==0)==(case=='valid_blocked'), {'exit':rc,'status':payload.get('status'),'scientific_acceptance':payload.get('scientific_acceptance')})
        for sign in [0,2,.5,1.5]:
            rejects('POLARITY_MAPPING_'+str(sign), lambda sign=sign: polarity.apply_polarity(np.ones((1,1,18)), {0:sign}))
        q=np.linspace(1.,10.,40)
        frame=pd.DataFrame({'run_id':['train']*40+['test']*40,'species':['proton']*80,
            'E_vis_MeV':np.tile(q,2),'n_detected_pe':np.tile(20*q+2,2)})
        def evaluate(table, held):
            return energy.evaluate_split(table, train_runs=('train',), heldout_runs=held,
                energy_target='E_vis', model='pooled_linear', rng=np.random.default_rng(1628))
        rejects('A09_MISSING_REQUIRED_HOLDOUT', lambda: evaluate(frame, ('test','absent')))
        rejects('A09_OVERLAPPING_SPLIT', lambda: evaluate(frame, ('train',)))
        invalid=frame.copy();invalid.loc[40:44,'E_vis_MeV']=0.;invalid.loc[45:47,'E_vis_MeV']=np.nan
        rejects('A09_NONFINITE_TARGET', lambda: evaluate(invalid, ('test',)))
        # Mock ROOT interface only; fixture bytes explicitly are NOT ROOT data.
        raw=pd.DataFrame({'event':np.arange(40),'particle':['proton']*40,'ke_MeV':[70.]*40,
            'edep_scint_MeV':q,'detected_readout':20*q+2,'pe_sat_readout':.9*(20*q+2)})
        class MockRoot:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def __getitem__(self,key):
                if key!='events': raise KeyError(key)
                return self
            def arrays(self,library):
                if library!='pd': raise ValueError(library)
                return raw.copy()
        fake=types.ModuleType('uproot');fake.open=lambda path:MockRoot();fake.KeyInFileError=KeyError
        old=sys.modules.get('uproot');sys.modules['uproot']=fake
        try:
            grid=work/'mock_grid';grid.mkdir();path=grid/'fixture.root'
            path.write_text('MOCK ONLY, NOT ROOT BYTES\n')
            path.with_suffix('.root.meta.json').write_text(json.dumps({'particle':'proton','kinetic_energy_MeV':70.,'n_events_requested':40}))
            try: decoded,_=energy.load_grid(grid)
            except ValueError: record('A09_MISSING_RAW_ENERGY',True,{'rejected':True})
            else:
                aliases='E_raw_MeV' in decoded and bool((decoded.E_raw_MeV==decoded.E_vis_MeV).all())
                record('A09_MISSING_RAW_ENERGY',not aliases,{'silently_aliased_to_visible':aliases})
        finally:
            if old is None:sys.modules.pop('uproot',None)
            else:sys.modules['uproot']=old
    sources=[]
    for path in paths:
        raw=path.read_bytes();sources.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),
            'git_blob_sha1':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
    return {'scope':'SYNTHETIC_CONTRACT_REPLAY_NO_BEAM_OR_GEANT4',
        'a09_execution':'unmodified function excerpts plus harness' if excerpt else 'functions imported from complete producer; ROOT decoder mocked',
        'sources':sources,'checks':checks,'failures':sum(not c['contract_pass'] for c in checks)}


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--a09-functions',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    path=args.a09_functions or args.source_root/'scripts/single_stave/paper_a09_heldout_edep_reconstruction.py'
    try:result=run(args.source_root,path,args.a09_functions is not None)
    except Exception as exc:
        print(json.dumps({'execution':'HARNESS_ERROR','error':str(exc)}));return 2
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    print(text);return int(result['failures']>0)
if __name__=='__main__':raise SystemExit(main())
