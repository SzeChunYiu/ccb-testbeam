# Claim Evidence Matrix

| Claim ID | Claim | Evidence class | Current evidence | Validation state | Limitation / required evidence |
|---|---|---|---|---|---|
| CL-G4-001 | Single-stave optical simulation produced ~178 detected PE/event | Prior simulation observation | Commit `d51159fc3c41a70c804c5da329b20041617dd506` and associated documentation | FLAWED | Must be regenerated on current code with configuration, seed/thread provenance, event and seed uncertainty, ROOT/meta hashes, and plots |
| CL-G4-002 | ~10.6 PE/MeV deposited follows from 178 PE and 16.8 MeV deposited | Independent arithmetic on prior simulation values | `178 / 16.8 = 10.595...` | PARTIAL | Denominator is deposited energy, not incident 100 MeV; inputs remain preliminary and uncalibrated |
| CL-G4-003 | Same-seed event output is invariant to effective thread count | Hypothesis under test | Validator implemented on PR #868; synthetic tests passed | BLOCKED | Requires real 1-thread and 4-thread ROOT outputs and exact event-keyed comparison |
| CL-G4-004 | Photon population is invariant to effective thread count | Hypothesis under test | Canonical photon-multiset validator implemented on PR #868 | BLOCKED | Requires real optical outputs; no persistent photon ID exists, so row order is not a physical key |
| CL-G4-005 | Different configured seeds produce independent, stable streams | Hypothesis under test | Multiseed validator implemented on PR #868 | BLOCKED | Requires preregistered thresholds and >=4 unique seeds per effective-thread group |

Evidence classes must be explicit: repository fact, measured data, simulation result, independent calculation, literature-backed fact, assumption, hypothesis, or unresolved question.
