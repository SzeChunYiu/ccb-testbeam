# P07e saturation-recovery claim audit

## Scope

This audit reconstructs the evidence chain behind `CL-016`, formerly the malformed generic claim
`Saturation recovery ML`. The reviewed source-backed study is P07e ticket
`1781018174.2030.05ac1ce2`, which evaluates a B2 saturation ratio-transfer model against the
paired odd duplicate channel using leave-one-run-out validation.

Repository evidence was read from the exact current `main` blobs for:

- `docs/claim_ledger.csv`;
- `reports/1781018174.2030.05ac1ce2/REPORT.md`;
- `reports/1781018174.2030.05ac1ce2/result.json`;
- `reports/1781018174.2030.05ac1ce2/manifest.json`;
- `configs/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.json`;
- `scripts/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.py`.

No raw ROOT data were available in this environment and no detector result was regenerated.

## Confirmed scientific distinction

The committed result contains two materially different tests:

1. **Pseudo-saturation closure** on clean pulses, where the ML model has median
   `res68_abs_frac = 0.03669062665507541`.
2. **External duplicate-readout closure** on 183,132 held-out high-amplitude B2 rows, where the
   ML model has charge `res68_abs_frac = 0.1763577793605039` with run-block 95% interval
   `[0.17304334869529975, 0.18060166173702746]`.

The uncorrected waveform has external duplicate charge `res68_abs_frac =
0.12079374117700271` with run-block 95% interval
`[0.11700387021774719, 0.12536373643016782]`.

The independently reconstructed difference is:

```text
0.1763577793605039 - 0.12079374117700271
= 0.05556403818350119
```

The ML lower interval bound is above the raw upper interval bound. For this metric and recorded
run-block bootstrap, the real-data duplicate closure is therefore worse after ML correction.
The strong pseudo-saturation result is a synthetic closure check and cannot authorize applying
the correction to real high-amplitude pulses.

Policy:

```text
P07E_EXTERNAL_DUPLICATE_CLOSURE_OVERRIDES_PSEUDO_SATURATION
```

Scientific decision:

```text
WITHHOLD_ML_CORRECTION
```

## Provenance defect

The manifest records execution `git_commit =
f20e1b0bceac4eeae4532c9e871a363d6dce08d7`, but that commit is the earlier S05e rate-study
commit and does not contain the P07e producer path. The P07e producer and outputs were later
introduced by commit `d30d91bc4b2988d3b1fffa8d7d44e58e1130603b`.

The producer records only `git rev-parse HEAD`. The manifest does not record:

- the producer script SHA-256;
- a clean/dirty worktree state;
- a patch or content-addressed source snapshot.

Consequently, the exact producer bytes used for the recorded run are not recoverable from the
manifest alone. Output files are hash-bound, and raw ROOT input hashes are listed, but execution
code provenance remains incomplete.

## Ledger remediation

`CL-016` is reconstructed to the external duplicate-readout charge-res68 result rather than the
pseudo-saturation metric. It remains `GATED` and is blocked by `BLK-P07E-001`. The row records:

- exact point estimate and run-block interval;
- 183,132 external validation rows and 33 held-out runs;
- uncorrected raw baseline and signed degradation;
- current report/script/result/config/manifest paths;
- `data_external_duplicate_readout` truth type;
- explicit producer-byte provenance limitation.

The row is not a detector calibration and does not establish a production saturation correction.

## Validation

Executable validation used source-faithful fixtures with the exact recorded metric values and
schema contract:

```text
python -m py_compile \
  tools/audit/audit_p07e_saturation_claim.py \
  tests/test_audit_p07e_saturation_claim.py

python -m pytest tests/test_audit_p07e_saturation_claim.py -q

4 passed in 0.62s
```

The tests cover malformed current-like ledger input, an aligned content-addressed corrected chain,
manifest output-hash mismatch, controlled nonzero CLI behavior, JSON output, and SVG evidence.
The tool and test files have maximum line length 100 characters.

The exact repository source facts were checked independently through authenticated GitHub blob and
commit reads. The executable fixtures are not represented as detector data.

## Acceptance boundary

Validated here:

- claim interpretation and source-artifact consistency;
- the pseudo-versus-external validation hierarchy;
- exact arithmetic for the ML degradation;
- the fail-closed ledger/provenance audit implementation;
- accessible version-controlled visual evidence.

Not validated here:

- raw ROOT extraction or event selection;
- rerunning ExtraTrees or Huber calibration;
- bootstrap resampling;
- cross-stave or newly acquired run closure;
- producer worktree state at the historical execution;
- a production saturation correction or detector-performance improvement.
