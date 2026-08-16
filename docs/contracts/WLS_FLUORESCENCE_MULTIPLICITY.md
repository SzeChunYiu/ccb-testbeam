# WLS Fluorescence Multiplicity Contract (issue #1088)

## Status

IMPLEMENTED (three-mode CLI contract). Production default
`geant4_default_one_secondary` is behavior-preserving relative to pre-2026-08-11
Geant4 semantics and now truthfully labelled; `bernoulli_thinned` is the
sourced-physics candidate; grid regeneration under a chosen mode is tracked as
a #1303 follow-up.

## The defect

Since f350ad9e (2026-08-11, #1246) `DetectorConstruction::BuildFibreCore`
unconditionally set the Y-11 MPT property `WLSMEANNUMBERPHOTONS = 1.0` while
the model label read `geant4_default_one_secondary`. In Geant4 11.2.2
`G4OpWLS` samples `Poisson(mean)` secondaries per absorption WHENEVER the
property exists — there is no `mean > 1` gate. At `mean = 1`:
`P(0) = e^-1 = 0.368`, `P(>=2) = 0.264`. So the actual multiplicity semantics
were Poisson(1) under a default-one label.

Consequence for the regenerated 2026-08 #1303 grid: build SHAs 533d58e8 and
42e67cad (receipts `reports/paper_1303_optical_campaign_20260815T2209Z/`)
are both descendants of f350ad9e, i.e. the 11.78 PE/MeV_vis grid was produced
under Poisson(1) multiplicity. The pooled MEAN is unaffected in expectation
(`E[Poisson(1)] = 1`), but per-event multiplicity variance and
saturation-adjacent observables carry Poisson(1) semantics under a
default-one label. The paper hold-note (chapter 08) records this.

Bernoulli(q) with q < 1 is NOT Poisson(q): Poisson has P(0) > 0 (a WLS
absorption can emit nothing) and P(>=2) > 0 (multi-photon re-emission);
Bernoulli thins an exactly-one re-emission. Means coincide when q = mu < 1,
variance and saturation behaviour do not.

## The three modes (`--wls-fluorescence-model`)

| Mode | Mechanism | Mean multiplicity | Per-absorption variance |
|------|-----------|-------------------|-------------------------|
| `geant4_default_one_secondary` | `WLSMEANNUMBERPHOTONS` property ABSENT | exactly 1 | 0 (deterministic) |
| `geant4_poisson_mean` | property set to mu | mu | mu (Poisson) |
| `bernoulli_thinned` | property absent + `StackingAction` kills each OpWLS re-emission with prob `1 - q` | q (effective) | q(1-q) around 1-then-thin |

* `--wls-mean-number-photons MU` (default 1.0; must be > 0; used only by
  `geant4_poisson_mean`).
* `--wls-fluorescence-yield Q` (default 0.70; must be in [0,1]; used only by
  `bernoulli_thinned`).
* `wls_fluorescence_status` is DERIVED from the mode at validation
  (`ASSUMPTION_UNIT_YIELD` / `EXPLICIT_POISSON_MEAN` / `EXTERNAL_QE_PRIOR`)
  so run metadata can never disagree with the mechanism in force.
* `bernoulli_thinned` draws a random number only when `q < 1` and only for
  OpWLS-created optical photons, so `q = 1` leaves the RNG stream untouched.

## Sourced physics for q

Y-11 fibre uses K27 dye; quantum yield q = 0.70 measured by Pla-Dalmau,
Foster, Zhang, Nucl. Instrum. Methods Phys. Res. A 361 (1995) 192-196, and
implemented in Geant4 as a Bernoulli 70% re-emission probability by Elpers,
Huang, Lang, Proga (arXiv:1911.03790, sec. 4). The ledger
(`configs/optical/optical_constants_ledger.conf`) records this; note the
ledger is provenance documentation — the binary consumes CLI/AppConfig
values (unconsumed-ledger defect tracked under #979).

## Known-answer observable

`n_wls_absorbed` (new per-event counter: optical photons whose transport
ended in the OpWLS process) and `n_wls_generated` (existing creator-process
counter) satisfy `E[n_wls_generated] = m * E[n_wls_absorbed]` with
`m in {1, mu, q}` for the three modes — every WLS photon creation is caused
by exactly one OpWLS absorption, independent of re-absorption chains.
`geant4/single_stave/tests/test_wls_multiplicity.py` (ctest
`ccb_stave_wls_multiplicity`, uproot, SKIP-77 without uproot) runs all modes
on one seed and asserts the ratio plus the default-vs-Poisson(1) per-event
variance discriminator. CI-level source contracts:
`tests/test_1088_wls_fluorescence_contract.py`.

## Digest

The optical digest is now `schema=optical_v2`, adding `wls_fluorescence_model`
and `wls_fluorescence_yield` (ADR-0005). v1 could not distinguish
default-one from Poisson(1) — the exact failure mode this contract closes.

## Rejection clause (from the issue)

This contract must not be closed by tuning PDE scale, fibre-SiPM coupling,
Y-11 attenuation or ADC gain: those change the downstream response, not the
upstream multiplicity semantics. Mode selection + known-answer discrimination
is the required evidence.
