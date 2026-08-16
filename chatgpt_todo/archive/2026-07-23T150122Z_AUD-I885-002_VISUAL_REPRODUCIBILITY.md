# AUD-I885-002 supplement — canonical visual reproducibility

- **UTC:** 2026-07-23T15:01:22Z
- **Parent task:** `AUD-I885-002`
- **Initial parent handoff head:** `50ee0c149331e5d23fdef4d7176b5c7de278e044`
- **Purpose:** close a post-review reproducibility gap between the version-controlled compact SVG and the plotting side effect of the numerical refit command.

## Defect

The committed compact `P5_seed_averaged_calibration.svg` had been visually validated, but the documented refit command produced a Matplotlib SVG whose bytes and layout were not the canonical committed artifact. A version-controlled result plot must be reproducible by an explicit committed renderer rather than by hidden/manual rendering steps.

## Correction

Added:

- `scripts/single_stave/render_i885_refit_svg.py` v1.0.0;
- `tests/test_render_i885_refit_svg.py`;
- `docs/validation/i885_seed_averaged_visual_validation.json`.

The renderer consumes only:

- `geant4/single_stave/results/i885_v1/i885_fits.json`;
- `geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv`.

It fails closed when an accepted calibration fit is present, a required rejected proton diagnostic is absent, a deuteron insufficient-energy skip is absent, point values are missing/nonfinite/negative, or an unsupported particle appears. It emits axes, units, independent-energy points, combined error bars, rejected proton line diagnostics, deuteron skip text, 14-file/7,000-event provenance, and explicit `not detector data` / `No accepted calibration function` boundaries.

## Validation

```text
python -m py_compile \
  scripts/single_stave/refit_i885_campaign.py \
  scripts/single_stave/render_i885_refit_svg.py \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py

python -m pytest \
  tests/test_refit_i885_campaign.py \
  tests/test_render_i885_refit_svg.py -q

9 passed in 1.04s

python scripts/single_stave/render_i885_refit_svg.py \
  --fits geant4/single_stave/results/i885_v1/i885_fits.json \
  --points geant4/single_stave/results/i885_v1/i885_seed_averaged_points.csv \
  --output /tmp/i885_canonical.svg

cmp /tmp/i885_canonical.svg \
  geant4/single_stave/results/i885_v1/P5_seed_averaged_calibration.svg
```

Result:

- byte-for-byte equality: PASS;
- repeated renderer output: deterministic;
- SVG SHA-256: `725b592d9d217f43cf8624ca7682575a35cf5f4f1ec06d9ea7266a7a4f8a3332`;
- SVG bytes: 7,259;
- XML parse: PASS;
- all four focused Python files have maximum line length no greater than 100 characters;
- local Git blob hash for renderer: `a01999fc040880f1596b8d7bf71ce0d880ec4924`, matching GitHub;
- local Git blob hash for renderer test: `60710780598e4c13ed39f3971d9925087c0a1b03`, matching GitHub.

## Direct-to-main commits before this supplement

- `2a48931e93784658226c0f3f3d6adc61802cbe1e` — `feat(i885): render deterministic seed-averaged audit SVG`
- `4401c4d227fa2da63965fcb5a8d8e5b24568e63d` — `test(i885): cover deterministic audit SVG renderer`
- `45c1a6faf5a76bf144d97371f7b68cbee09bd42e` — `docs(validation): make issue 885 visual byte-reproducible`
- `c4810d0e0ae15d46429def445b47959520f5215b` — `docs(validation): record issue 885 visual reproducibility`
- `ca42994c23cc5c6c4790a5fa3430bc615ea5babf` — `docs(i885): document canonical deterministic visual renderer`
- `a8d5eeb7faffaa8ea9625606900bce9a57014195` — `docs(audit): bind issue 885 visual to canonical renderer`

## Boundary

This supplement validates artifact reproducibility only. It does not change the scientific result: no calibration fit is accepted, proton global lines remain rejected, deuteron lines remain skipped, no Geant4/ROOT simulation was rerun, and no real-data calibration or detector-performance claim is made.
