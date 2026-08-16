#!/usr/bin/env python3
"""Create a deterministic synthetic event table for testing analyze_single_stave.py."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--n", type=int, default=5000)
    p.add_argument("--seed", type=int, default=20260720)
    a=p.parse_args()
    rng=np.random.default_rng(a.seed)
    pdg=rng.choice([2212,1000010020], size=a.n, p=[0.65,0.35])
    ke=np.where(pdg==2212, rng.uniform(50,180,a.n), rng.uniform(30,130,a.n))
    x=rng.uniform(-25,25,a.n)
    edep=np.clip(rng.normal(np.where(pdg==2212,4.0,7.0),1.2),0.05,None)
    generated=rng.poisson(edep*9000)
    attenuation=np.exp(-(25-x)/350)
    end=rng.binomial(generated, np.clip(0.012*attenuation,0,1))
    pe=rng.binomial(end, 0.30)
    distance=25-x
    tmed=distance/17.0+rng.normal(0,0.4,a.n)
    df=pd.DataFrame({
        "run_id":"fixture",
        "event_id":np.arange(a.n),
        "particle_pdg":pdg,
        "kinetic_energy_MeV":ke,
        "entry_x_cm":x,
        "entry_y_cm":rng.uniform(-2.5,2.5,a.n),
        "entry_z_cm":-1.0,
        "incidence_angle_deg":0.0,
        "track_length_scint_cm":2.0,
        "edep_scint_MeV":edep,
        "edep_scint_raw_MeV":edep,  # synthetic fixture: raw == visible
        "n_scint_generated":generated,
        "n_end_selected":end,
        "n_detected_pe":pe,
        "first_photon_time_ns":np.maximum(0,tmed-rng.exponential(0.5,a.n)),
        "median_photon_time_ns":tmed,
        "photon_time_sigma68_ns":rng.uniform(0.3,1.2,a.n),
        "birks_kB_mm_per_MeV":rng.choice([0.10,0.126,0.15],a.n),
        "geometry_hash":"fixture",
        "optical_config_hash":"fixture",
    })
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.suffix==".parquet":
        df.to_parquet(a.output,index=False)
    else:
        df.to_csv(a.output,index=False)
    print(a.output)

if __name__=="__main__":
    main()
