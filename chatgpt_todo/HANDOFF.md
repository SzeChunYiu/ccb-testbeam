# Latest Handoff

## Trigger/gain recovery separation exposed an independent correlated-noise recovery law

Selected atom: `ARU-SIPM-RECOVERY-CORRELATED-NOISE-COUPLING-001`, child of #1066 and #1071.

### Live repository state

Protected testbeam `main` advanced from `e25d59be37f59b8fddf7dd897295bcaa7bee14d0` to `d9992a48d86a34f03f18a1e4f9426c97f6cf399b` when PR #1235 integrated `ccb-sipm-core@692857bde0c1c6c2ed59aac5a56c94740da31354`. #1066 remains OPEN; this integration is PARTIAL and must not be interpreted as recovery-model validation.

Core PR #13 exact head `c2b79d83642852b458299b181d50dd94b733bdb7` passed Core CI run `31533574607`; merged core main `692857b...` passed independent push Core CI run `31533753427`. Testbeam PR #1235 exact head `4cb06465c2aaf30b4319e43f003578b18c953d8c` passed MC Validation run `31534733706`, job `93923024769`: ruff clean and pytest `1642 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 124.43 s`. The testbeam CI is Python/static and does not compile the C++ submodule; the upstream Core CI is the C++ execution evidence.

### Atomic contract

For a previously fired cell, the core forms

`r(dt)=1-exp(-dt/tau_recovery)`.

PR #13 made two accepted-parent response quantities explicit:

- `P_fire/P_full = F_trigger(r)`;
- `Q/Q_full = F_gain(r)`.

Current selectors are `trigger_recovery_model=EXPONENTIAL`, `gain_recovery_model=EXPONENTIAL_H1_SHARED`, and gain alternative `FULL_RECOVERY`.

The cross-atom contradiction is that correlated-noise generation from the accepted parent avalanche is still anonymous and hard-wired to raw `r`:

- prompt crosstalk `N ~ Poisson((-ln(1-p_prompt))*r)`;
- delayed crosstalk Bernoulli(`p_delayed*r`);
- fast/slow afterpulse scheduling Bernoulli(`p_after*r`).

The scheduled child is later subjected to its own target/same-cell recovery gate. Parent secondary generation and child triggering are therefore separate physical state transitions.

At `dt=tau`, `r=0.6321205588285577`. With `gain_recovery_model=FULL_RECOVERY`, the modeled accepted parent has full gain while secondary generation remains at 63.212% of the fully recovered nominal multiplier. For the representative uncalibrated profile, prompt `p=0.03` gives `lambda=0.030459207484708546` and current `lambda*r=0.01925389125670895`; fast/slow afterpulse scheduling becomes `0.006321205588285576` / `0.003160602794142788`. These are simulator-law calculations, not CCB measurements.

### Equivalence and mechanism review

The crucial identifiability result is that raw-recharge coupling `C=r` and parent-gain coupling `C=g` collapse to the same observable model under default `EXPONENTIAL_H1_SHARED`, because `g=r`. Existing H1-only tests therefore cannot validate which correlated-noise coupling is intended. `FULL_RECOVERY` (`g=1`) breaks that degeneracy.

Surviving hypotheses are: named legacy `C=r`; gain/charge-coupled parent generation; mechanism-specific prompt/delayed/afterpulse recovery surfaces; and an explicit `C=1` negative-control family with child recovery retained downstream. No physical winner is selected without actual secondary-pulse delay×amplitude calibration at the relevant device, overvoltage and temperature.

Hamamatsu guidance and primary Hamamatsu-SiPM correlated-noise studies motivate keeping avalanche amplitude, delay, crosstalk and afterpulse observables explicit; they do not authorize a CCB-specific `C=r` or `C=g` law from manufacturer defaults.

### Repository actions

- Added stable concern `CCB-1071-RECOVERY-COUPLING-001` to existing #1071 instead of creating a duplicate issue.
- Added cross-atom partial-completion evidence and four-role review to #1066; issue remains OPEN.
- Reframed PR #1235 before integration as `fix(sipm): integrate partial trigger/gain recovery separation (#1066)` with exact upstream/testbeam CI and claim boundary.
- PR #1235 merged as testbeam main `d9992a48d86a34f03f18a1e4f9426c97f6cf399b`. Main-push MC Validation run `31535409449` was in progress when this handoff was written; do not claim a post-merge PASS until its conclusion is inspected.
- Immutable record: `chatgpt_todo/archive/2026-08-11T205700Z_ARU-SIPM-RECOVERY-CORRELATED-NOISE-COUPLING-001.md`.

### Four sequential AI votes

**SiPM/device lead — ACCEPT bounded trigger/gain refactor / REVISE physical recovery model.** Exact code separates trigger/gain but leaves correlated-noise generation coupled to raw `r`. Actual CCB delay×amplitude calibration is absent.

**Adversarial mechanism reviewer — BLOCK implicit coupling.** `C=r` and `C=g` are only indistinguishable under H1; `FULL_RECOVERY` produces a 36.8% separation at `dt=tau`.

**Independent statistics/validation reviewer — ACCEPT software/source diagnosis / BLOCK detector inference.** Green H1 tests cannot discriminate collapsed parameterizations; held-out two-pulse/secondary-pulse data are required for physical model selection.

**Claims/provenance reviewer — BLOCK #1066/#1071 completion and saturation/pile-up/late-component promotion.** The representative profile is explicitly not a CCB calibration, and downstream physics studies have not been re-evaluated over the surviving model family.

### Child atoms / next work

Highest-value next atom: `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`. Make the currently hidden parent-generation recovery law explicit and serializable per mechanism, retain raw-`r` as a named legacy hypothesis, add `C=1` and gain-coupled test hypotheses where appropriate, and construct paired fixed-seed controls that break the H1 degeneracy. This is a software-model interface atom; it must not choose detector truth in the absence of calibration.

Physical child: `ARU-SIPM-CORRELATED-NOISE-TWO-PULSE-CALIBRATION-001`, requiring source-bound secondary-pulse delay×amplitude data and held-out validation at the actual device operating point.

Other independent dependencies remain: `ARU-SIPM-RECOVERY-DISTINCT-TAU-001` because trigger/gain selectors still consume one shared raw `r`/`tau`; #1072 operating-point response surfaces; #1096 physical history-horizon convergence; #1067 measured-impulse source/calibration authorization.

No beam data, production Geant4 sample, detector calibration, pile-up efficiency, saturation closure, timing/PID result, rate, ESS, p-value or public detector-performance quantity was generated or promoted.