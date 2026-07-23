# Single-stave analysis handoff — 2026-07-23

## Next executable task

Run `single_stave_diagnostics.py` from the delivered ZIP against:

1. the five calibration-grid ROOT files;
2. `gpu_stave_1t.root`;
3. `gpu_stave_48t.root`;
4. `gpu_stave_48t_seed[2-4].root`.

Copy the generated `result.json`, `manifest.json`, all source tables, and plots into a new provenance-stamped report directory.

## Mandatory code fixes before rerun

- add current event-tree branch aliases to the repository analyzer;
- correct raw versus Birks-visible energy bookkeeping;
- create distinct inner/outer cladding materials;
- implement or remove the advertised fast mode.

## Acceptance

No physics claim may use `edep_scint_MeV` as Birks-visible energy until raw/visible semantics are fixed and regression-tested. No fast-mode claim may be made until optical transport is actually bypassed and held-out closure is demonstrated.
