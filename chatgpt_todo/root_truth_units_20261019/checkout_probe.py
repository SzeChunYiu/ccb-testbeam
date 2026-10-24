#!/usr/bin/env python3
"""Run source-exact, nonauthorising tests of the current MV1-MV3 truth converter.

Uses two explicit stubbed imports only to isolate `_records_from_truth_arrays`;
NOT a complete ROOT, trigger, or detector simulation. Exit 1 means confirmed
source failures persist, 2 means source changed or probe cannot execute.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import numpy as np

BLOB = 'a9b3f8ad064db4031521110e78ac741d2a61a7c6'
MASS = {2212:938.272, 1000010020:1875.613}

def jagged(*events):
    x=np.empty(len(events),dtype=object)
    for i,event in enumerate(events):x[i]=np.asarray(event)
    return x

def event(layer=(0,),arm=(1,),pdg=(2212,),edep=(3.,),time=(0.,),tracklen=(10.,),momx=(.4,)):
    n=len(layer)
    return {
        'Sci_bar_LayerID':jagged(layer),'Sci_bar_LayerID1':jagged(arm),
        'Sci_bar_PDG':jagged(pdg),'Sci_bar_EDep':jagged(edep),
        'Sci_bar_Time':jagged(time),'Sci_bar_TrackLength':jagged(tracklen),
        'Sci_bar_Momentum_X':jagged(momx),
        'Sci_bar_Momentum_Y':jagged([0.]*len(momx)),
        'Sci_bar_Momentum_Z':jagged([0.]*len(momx)),
    }

def oracle(p_gev,mass):
    with localcontext() as ctx:
        ctx.prec=60
        p=Decimal(str(p_gev))*Decimal(1000)
        m=Decimal(str(mass))
        return float((p*p+m*m).sqrt()-m)

def verify(root):
    source=root/'src/ccb_mc_validation/io/root_truth.py'
    raw=source.read_bytes()
    digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if digest!=BLOB:raise ValueError(f'unexpected source Git blob {digest}; re-audit, do not trust stale cases')
    for name in ('ccb_mc_validation','ccb_mc_validation.truth','ccb_mc_validation.truth.pdg','ccb_mc_validation.truth.trigger'):
        sys.modules.setdefault(name,types.ModuleType(name))
    sys.modules['ccb_mc_validation.truth.pdg'].mass_of=lambda p:MASS[int(p)]
    sys.modules['ccb_mc_validation.truth.trigger'].process_chunk=lambda l,a,p,t,c:{'sample_I':np.zeros(len(l),bool),'sample_II':np.zeros(len(l),bool)}
    spec=importlib.util.spec_from_file_location('pinned_root_truth',source)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    convert=mod._records_from_truth_arrays
    k0=float(convert(event())['ekin'][0]);correct=oracle(.4,MASS[2212]);assert correct>9e5*k0
    kd=float(convert(event(pdg=(1000010020,),momx=(.6,)))['ekin'][0])
    wrong=0
    for p in np.linspace(.02,.6,101):
        for species in MASS:
            measured=float(convert(event(pdg=(species,),momx=(float(p),)))['ekin'][0])
            if oracle(float(p),MASS[species])>1000*measured:wrong+=1
    assert wrong==202
    trunc=convert(event(layer=(0,1),arm=(1,1),pdg=(2212,2212),time=(1,2),edep=(2.,),momx=(.4,.3)))
    assert float(trunc['edep_tot'][0])==2 and int(trunc['nlayers'][0])==1
    a=convert(event(layer=(0,0),arm=(1,1),pdg=(2212,1000010020),time=(1,1),edep=(2,3),tracklen=(10,12),momx=(.4,.6)))
    b=convert(event(layer=(0,0),arm=(1,1),pdg=(1000010020,2212),time=(1,1),edep=(3,2),tracklen=(12,10),momx=(.6,.4)))
    assert int(a['pdg'][0])!=int(b['pdg'][0]) and float(a['edep_tot'][0])==float(b['edep_tot'][0])
    output={'status':'CONFIRMED_SOURCE_CONTRACT_FAILURES','scientific_release':'NOT_AUTHORIZED',
        'source_git_blob':digest,'dependent_imports':'STUBBED_MASS_AND_TRIGGER_FOR_ISOLATION',
        'reference_units':'GeV/c converted to MeV/c once',
        'proton_p0_4_GeV_c':{'source_ekin_MeV':k0,'independent_reference_ekin_MeV':correct},
        'deuteron_p0_6_GeV_c':{'source_ekin_MeV':kd,'independent_reference_ekin_MeV':oracle(.6,MASS[1000010020])},
        'unit_test_grid':{'momenta_per_species':101,'species':2,'failed_unit_conversions':wrong},
        'edep_length_mismatch':{'n_layers':2,'n_deposits':1,'source_total_edep':float(trunc['edep_tot'][0]),'exception_raised':False},
        'species_permutation':{'first_order':int(a['pdg'][0]),'reversed_order':int(b['pdg'][0]),
            'both_edep_tot':float(a['edep_tot'][0])},
        'real_ROOT_executed':False,'full_trigger_executed':False}
    return output

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,required=True)
    args=ap.parse_args()
    try:
        result=verify(args.repo)
        print(json.dumps(result,indent=2,allow_nan=False,sort_keys=True))
        return 1
    except (ValueError,OSError,AssertionError,ImportError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'BLOCKED_INSTRUMENT_OR_SOURCE','reason':str(exc),'scientific_release':'NOT_AUTHORIZED'}))
        return 2

if __name__=='__main__':raise SystemExit(main())
