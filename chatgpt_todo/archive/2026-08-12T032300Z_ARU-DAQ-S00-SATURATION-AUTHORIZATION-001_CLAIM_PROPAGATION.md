# ARU-DAQ-S00-SATURATION-AUTHORIZATION-001 — claim-propagation addendum

Status: `PARTIAL / CLAIM_GOVERNANCE_REPAIRED`  
Parent: #1073 / #1014  
Branch: `audit/s00-saturation-field-authorization-v1`

## Downstream claim discovered

`reports/P07_saturation_recovery/REPORT.md` was still interpreting the high-amplitude B2 population above 7000 ADC as likely digitiser saturation and stated that its synthetic clipping benchmark directly enabled recovery of real B2 pulses.

That claim is incompatible with the live ADC saturation-world registry, which remains `BLOCKED_HARDWARE_EVIDENCE`: neither 7000, 4095 nor 16383 is currently source-bound as the physical CCB censoring rail, and the native-to-stored transfer is unresolved.

## Scientific distinction

The P07 benchmark is a valid *conditional synthetic-transform comparison* if its input/sample/split provenance is accepted:

1. begin with a selected waveform and use its pre-injection amplitude as pseudo-truth;
2. apply an artificial constant hard clip `x'_s = min(x_s, C)`;
3. reconstruct the pre-injection amplitude from the transformed waveform;
4. compare reconstruction errors under that injected transform.

This does not imply

`high DATA code/amplitude => physical ADC saturation`,

nor does it establish that the hard-clip map is the real detector transfer function.

## Claim repair

The report was rewritten without changing the retained historical benchmark table. It now:

- labels P07 `GATED / SYNTHETIC-CLIPPING ONLY`;
- calls 7000 ADC an analysis region rather than a proven hardware rail;
- calls the pre-injection amplitude pseudo-truth;
- preserves the historical hard-clip benchmark numbers only as properties of that injected task;
- withdraws the statement that the benchmark directly authorizes recovery of real B2 high-amplitude pulses;
- demotes the quenching/nonlinearity explanation for the GBR advantage to an unresolved mechanism hypothesis;
- requires #1014/#1073 source-bound transfer evidence before real saturation recovery can be validated.

The report change commit is `34203ddad8c72438e8902e47d52bd3f4dbe7b220` on the audit branch; the rewritten report blob is `fe4b9e92b44683843a36b3218243a55d82e5ebec`.

## Historical numerical table retained, not independently regenerated

| injected C (ADC) | N clipped test | naive | template | GBR |
|---:|---:|---:|---:|---:|
| 4000 | 8873 | 0.264 | 0.104 | 0.032 |
| 3000 | 20254 | 0.346 | 0.239 | 0.039 |
| 2500 | 27971 | 0.403 | 0.233 | 0.042 |
| 2000 | 33823 | 0.493 | 0.286 | 0.046 |

These are retained historical report values. This run did not access the immutable P07 input bytes or regenerate its result artifacts.

## Cross-atom compatibility

The report can coexist with the new `ccb-s00-saturation-field/1` only if the synthetic transform remains explicitly hypothetical/non-authorising. Any future production recovery path must instead bind the DATA saturation/censoring label to the resolved transfer contract and then validate recovery on held-out source-bound evidence with run/event-aware uncertainty.

## Claim boundary

No measured saturation fraction, hardware rail, real saturated-pulse truth, energy/PID correction, timing correction, pile-up mechanism or detector-performance metric is promoted by this addendum.
