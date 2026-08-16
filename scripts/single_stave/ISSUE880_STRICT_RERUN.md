# Issue #880 strict weighted rerun

Use `issues879_880_887_mc_study_strict.py` for every new issue #879/#880/#887 execution. The
historical `issues879_880_887_mc_study.py` is retained only to preserve the original study and is not
an accepted scientific entry point because it can coerce or fall back when weights are invalid.

## Required command

From a clean repository checkout:

```bash
python scripts/single_stave/issues879_880_887_mc_study_strict.py \
  --root geant4/data/output_krakow_1M.root \
  --tree hibeam \
  --entry-stop 0 \
  --out reports/issues879_880_887_mc_analysis_strict
```

The strict producer requires exactly one finite, nonnegative `PrimaryWeight` per event, at least one
positive weight in every weighted sample, a clean tracked worktree, stable ROOT bytes across the
read, and an unused output bundle unless `--overwrite` is explicitly supplied.

The output JSON records:

- ROOT path, byte count, SHA-256, tree, and loaded/available entry counts;
- git commit and clean-worktree state;
- exact command and runtime versions;
- SHA-256 of the strict producer, strict weighting module, and historical producer;
- event-weight validation policy, sums, ESS, and zero/positive counts;
- direction-explicit weighted/unweighted comparisons;
- hashes of every generated plot.

A successful run is still a simulation diagnostic. It does not authorize a calibration, detector
species tag, uncertainty claim, or data/MC closure without the additional checks listed in
`docs/validation/issue880_strict_producer_audit.md`.
