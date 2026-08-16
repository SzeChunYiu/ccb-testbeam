# I885 transverse phase-space coverage audit (issue #1092)

Status: **FIXED at campaign-schema level** — transverse y axis is now
explicit; central-track `y=0` curves are labelled as limited-scope, not
stave-averaged response.

## Change

`geant4/single_stave/slurm/make_i885_campaign.py` now emits:

- main KE scan at `(x=default, y=0)` — central-track response;
- attenuation/timing x scan at `y=0`;
- transverse map `y in {-1,0,+1} cm` at default x for 30/80 MeV
  protons and deuterons (fibre centres at ±1 cm).

Manifest uniqueness and the campaign validator key include `hit_y_cm`.
Main-grid coverage remains the central-track subset (`y=0`).

## Still open for physics closure

- Measuring response uniformity vs y on held-out positions;
- Integrating MC over measured `p_data(y)` if TPC/beam spots exist;
- Propagating y uncertainty into energy-response calibrations that claim
  detector-wide applicability.
