# CL-011 effective-live-time source-binding audit

## Scope

This audit reviews the canonical `CL-011` effective-live-time claim against the
tracked primary S10b measurement artifacts and the later MV5 pile-up study. It is
a documentation, provenance, estimand, and uncertainty-semantics audit. It does
not reprocess the raw ROOT files or establish a detector-wide dead-time model.

Policy:

`TAU_EFF_CLAIM_MUST_BIND_TO_PRIMARY_S10B_MEASUREMENT`

## Repository state inspected

- initial remote `main`: `53bf42c8d414c9d11bcc1f9d5ab2d088da5a7600`;
- claim ledger Git blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`;
- primary S10b report Git blob: `dd33a29d2ccb62fd367a5b19a152fa36f669e69d`;
- primary S10b result Git blob: `57d82d091b1f21d9d4c400cf92c9db2893aa7ffb`;
- primary S10b manifest Git blob: `cc3713c2615bc5a5d2b5e493ef58a2b460e1aa92`;
- primary S10b held-out summary Git blob: `71bc0cbe761c831c79efa5242191a9d2bd9ab78e`;
- primary S10b producer Git blob: `7805c39db6dab458f4ea40412454a770d0f944c7`;
- secondary MV5 report Git blob: `96ede7778cdb30cfab420abeb69c23f0a98b6974`;
- secondary MV5 summary Git blob: `646d55e027f3ddc6def4ca43514c46ef9935e6d4`.

The primary manifest records source commit
`da9651c56ef6495ce9656d84b69b600daa6d8f86`, Python 3.7.6, random seed
10102, exact SHA-256 values for fourteen ROOT inputs, and output hashes.

## Primary source reconstruction

The S10b producer measures one 10% template-crossing value per run after CFD20
alignment. The reported central value is the equal-weight mean of the fourteen
run-level estimates, not a pulse-weighted mean and not a universal electronics
dead time.

From `heldout_run_summary.csv`:

- runs: 14;
- selected pulses: 252,266;
- independently reconstructed run-average estimate:
  `124.79018394263471 ns`.

The source RNG stream was reconstructed exactly. Before the bootstrap, the
producer performs a 60,000-of-63,067 generator choice and shuffles an array of
252,266 pulse targets. With `numpy.default_rng(10102)`, 5,000 bootstrap draws,
and fourteen run units, the reconstructed percentile interval is:

`[123.33094981246663, 126.35875117626817] ns`.

This exactly reproduces the tracked `result.json` in binary64 arithmetic.

## Confirmed canonical-ledger defects

The current exact-width `CL-011` row has 30 fail-closed findings. The important
scientific and provenance defects are:

1. It cites the later MV5 report and producer as the primary source, although MV5
   hard-codes `tau_eff_new_ns = 124.8` and uses that value as an input.
2. It cites `reports/mv5_pileup_1782678353/results.json`, which does not exist;
   the tracked MV5 machine-readable file is `mv5_pileup_summary.json`.
3. It rounds the primary estimate and CI to `124.79`, `[123.5, 126.0]` instead
   of binding the exact tracked values.
4. It publishes `stat_unc=0.5`, `syst_unc=1.0`, and `total_unc=1.12`, but the
   primary source provides no statistical/systematic decomposition.
5. It omits the fourteen-run count and records 213,843 data objects, while the
   tracked held-out summary contains 252,266 selected pulses.
6. It labels the claim `VALIDATED` and `data_mc_self_consistent`. The MV5 study
   is not an independent validation of the measured window: it inserts rounded
   124.8 ns into an exponential-gap simulation and analytic expression.
7. It calls the quantity generic `tau_eff`, obscuring that the estimand is the
   equal-weight mean of run-level 10% template crossings relative to CFD20 for
   the selected pulse population.

## Required remediation contract

A corrected `CL-011` record should:

- name the estimand as the S10b run-average 10% template live-time relative to
  CFD20;
- bind the S10b report, producer, result, manifest, and source commit;
- record the exact estimate and exact run-bootstrap interval;
- record 14 runs and 252,266 selected pulses;
- leave `stat_unc`, `syst_unc`, and `total_unc` empty;
- use `truth_type=data_measurement` and `status=DONE_DATA_ONLY`;
- state that MV5 uses the value as an input rather than independently validating
  it;
- state that the result is not a detector-wide universal dead time;
- remain gated by `BLK-S10B-001` until the estimand, waveform threshold,
  run-weighting choice, systematic uncertainty, and independent rerun/closure
  are accepted.

The root WIKI, executive summary, pile-up chapter, LaTeX chapter, and any figure
metadata that present the unsupported uncertainty decomposition or `VALIDATED`
status must be synchronized in the remediation unit.

## Executable validation

Commands:

```text
python -m py_compile \
  tools/audit/audit_tau_eff_claim_binding.py \
  tests/test_audit_tau_eff_claim_binding.py

PYTHONPATH=. pytest -q tests/test_audit_tau_eff_claim_binding.py

6 passed in 1.08s
```

Environment:

- Python 3.13.5;
- NumPy 2.3.5;
- pytest 9.0.2.

Coverage includes the current-like flawed row, a corrected zero-finding fixture,
manifest-content mutation, duplicate `CL-011`, invalid UTF-8, and destructive
output alias rejection. JSON parsing and SVG XML parsing passed. Changed Python
files contain no line longer than 100 characters.

Validated file SHA-256 values:

- validator: `091df1075683eb97d5fd0f278620a88374ef5a84692c9305e6d70dce3cb7439c`;
- tests: `0d8b5e906199878c0854d13208890dbb0449e24ff4be0456827303e9efc9fda2`;
- validation JSON: `f64a7d38020788a65c59815e5965ba2575b7f1525d07164dbb62e4b113e4f17e`;
- SVG: `2126018b531bd6a161d72e9232b2661609043e4d357848469ff8eb056d33a9de`.

## Acceptance boundary

The audit implementation, exact arithmetic reconstruction, tests, JSON record,
and visual evidence are validated. `AUD-LEDGER-003` remains `PARTIAL` because
this unit does not rewrite the canonical claim row or downstream public text.

No raw ROOT bytes were re-read, no waveform fit was rerun, and no new detector
measurement or uncertainty estimate was produced. The tracked fixed result is
reproducible from its derived artifacts, but scientific acceptance still
requires an explicit estimand decision, systematic studies, a clean independent
rerun, and cross-method or external closure that does not reuse 124.8 ns as an
input.
