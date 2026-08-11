# Latest Handoff

## SiPM history and measured-impulse semantics are composed and integrated on protected main

The selected work began as `ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001` under open/PARTIAL #1096 and exposed a concurrent lineage conflict that required `ARU-SIPM-KERNEL-MEASURED-COMPOSITION-001` before the kernel child could be safely integrated.

Protected testbeam main moved during the session from `a83d3b64b87d3781211a2db42d5375bea8d4ae41` to `0800a0cece4dff733c82e024b4c764e85ce947d9` via #1226. That merge changed the SiPM gitlink to `ccb-sipm-core@5c6bb0278be4246f3da9007b71a5d13024b968ca`, a non-descendant of validated DCR-history core `f009b0d...` and kernel-history core `68eadf3...`. It therefore temporarily regressed validated pre-window history semantics while adding a separate measured-impulse fail-closed candidate.

The safe repair was a descendant composition rather than choosing either side. Core PR #7 was built from exact history-complete `main@68eadf3f6ac3a95b37e0d8c86843573736a5ea97`, and testbeam PR #1228 subsequently integrated the composed descendant.

## Exact contracts and discriminators

For admitted avalanche `t_a` and recorded sample `t_i`, the encoded analog law is `V_i = sum_a A_a h(t_i-t_a)` for `t_i >= t_a`. With `N_out=floor((window_end-window_start)/dt)+1` and `H=max(0,window_start-history_start)`, the conservative uniform-grid elapsed-time kernel is `N_kernel=N_out+ceil(H/dt)`.

At default history `-200 ns`, output window `[-20,250] ns`, and `dt=0.5 ns`, `N_out=541`, `N_kernel=901`, and an avalanche at the history boundary is 450 ns old at the final sample. The pre-repair output-length kernel represented only 270 ns.

The deterministic kernel discriminator uses history `-20 ns`, output `[0,10] ns`, `dt=1 ns`, one history-boundary avalanche, and generic `h_raw(t)=exp(-t/25)-exp(-t/1)` with stochastic detector/electronics mechanisms disabled. Old code is identically zero because its 11-point kernel cannot reach required ages 20--30 ns. The repaired 31-point grid closes every output sample to the analytic peak-normalised reference at `1e-12`; first/last expected values are approximately 0.536747 and 0.359792. Collapsed-history and finite measured-support controls prevent over-fixing.

Measured-impulse numerical semantics are fail-closed: matched lengths, at least two finite strictly increasing times, nonzero peak, positive trapezoidal integral, and no silent unit-delta fallback. `IDEAL_DELTA_TEST_ONLY` is separately gated by `authorising=true`. Measured-support overlap is evaluated against the history-complete elapsed-time domain, not merely the recorded waveform duration.

A joint fixture uses history `-20 ns`, output `[0,10] ns`, `dt=1 ns`, and sampled support `[20,22,25] ns` with amplitudes `{0,1,0}`. That response lies beyond the 10 ns output duration but inside the 30 ns history-to-output domain and must contribute in-window. Support `[40,42,45] ns` lies outside the history-complete domain and must fail.

## Exact execution and integration

Kernel core PR #5 exact head `454579870a8f1eb9b0f67e02df30486f778f7b67` passed Core CI `31520345468` / job `93875571412`, then squash-merged as `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`; merged-main Core CI `31520555652` / `93876260437` independently passed.

Composed core PR #7 exact head `0b18bc08c9e077eebe3e20c8bfd5005085de09f3` passed Core CI `31522503501` / job `93882757978` with checkout/configure/build/test all SUCCESS. It squash-merged with expected-head guard as `ccb-sipm-core@e71fd26c915a402590931d2a7657157f04277235`; independent main-push Core CI `31522658182` also completed SUCCESS.

Testbeam PR #1228 exact head `1eeca19ef51ecc63cfb2a7d3935f6cacce436b59` passed both exact-head protected contexts before merge: push MC Validation `31523046059` / job `93884607919` and pull-request MC Validation `31523087756` / job `93884744722`. Both completed checkout, package setup, ruff, unit tests, diagnostics upload and enforcement successfully. PR #1228 then squash-merged with expected-head guard as protected `main@a00dd8a80510b52380a76dd8fe7a5d4556b1c846`. Commit inspection confirms the gitlink transition `5c6bb027... -> e71fd26c...`, so the temporary live-main history regression is repaired on remote main.

Exact merged-main testbeam MC Validation run `31523505058`, job `93886095185`, then completed SUCCESS on `a00dd8a...`: checkout, setup, package install, ruff, unit tests, diagnostics upload, and enforcement all passed.

The immutable detailed record is `chatgpt_todo/archive/2026-08-11T182700Z_ARU-SIPM-KERNEL-MEASURED-COMPOSITION-001.md`.

## Provenance governance and newly isolated child

#1067 is reopened. The #1226 target had fields named as source/effective-kernel hashes populated by `LEN-<size>` placeholders, which are not cryptographic content provenance. The composed core removes that false implication by leaving those fields blank unless exact provenance is supplied. This is safer, but it intentionally leaves #1067 incomplete until true content-derived source/effective-kernel digests, canonical serialization/tamper tests, and remaining acceptance leaves are validated.

A second, distinct authority-state gap is now isolated by core draft PR #8, `ARU-ELEC-IMPULSE-PROVENANCE-STATE-001`, based exactly on `e71fd26c...`. Its invariant is

`MEASURED_authorized => source_bound && source_digest_bound && effective_kernel_digest_bound && calibration_validation_passed`.

Current composed core still reconciles any numerically valid sampled vector to `impulse_model=MEASURED` and emits `impulse_response_status=MEASURED` even when exact source/effective-kernel digests are blank. PR #8 head `b0305fa0f1f5b22729ac944ea8f1def7b95ce5d6` supplies synthetic valid sampled kernels with no authoritative provenance and requires metadata not to claim `MEASURED`. Exact Core CI `31522917984` / job `93884187652` configured and built successfully but failed at the Test step, as the discriminator was designed to do. Do not merge the red PR; repair the state model on a descendant, distinguish non-authoritative custom sampled input from authoritative `MEASURED`, then make the discriminator green.

#1096 remains PARTIAL. The composed implementation closes DCR-history and numerical kernel-support compatibility gaps but does not establish how far physical history must extend, calibrate the real CCB impulse response, or validate downstream detector observables.

The provisional sampling child from the kernel audit is collapsed into existing #1065 `ARU-SIPM-SUBGRID-001` for continuous avalanche phase versus `lround` placement. Real DAQ sampling aperture/clock semantics remain #1009/#1014, and #1010 remains the measured/generic electronics calibration universe. Concurrent core PR #9 is a separate #1065 implementation candidate and must preserve the history-complete regressions.

Kernel-only testbeam PR #1227, duplicate integration PR #1229, and conflicting core probe PR #6 are closed unmerged and superseded by the descendant composition. Do not resurrect them as integration paths.

## Four sequential AI review passes

**SiPM/electronics lead — ACCEPT bounded history-complete composition / REVISE physical response+horizon.** Evidence: exact source lineage, time-domain contracts, analytic CR-RC fixture, sampled-support fixture, exact Core C++ CI, duplicate exact-head testbeam CI. Strongest counter-hypothesis: recorded waveform duration defines all electronics memory. Falsifier: admitted older avalanches have nonzero configured response at later in-window samples beyond that duration. Residual: real CCB electronics response and sufficient physical prehistory.

**Adversarial mechanism reviewer — ACCEPT descendant composition / BLOCK #1065 sub-grid timing and provenance authority.** Evidence: non-descendant git history, finite-support controls, support-beyond-output fixture, placeholder digest implementation, PR #8 red discriminator. Strongest counter-hypothesis: numerically valid sampled response is observationally equivalent to an authoritative measured response. Falsifier: identical vectors can be synthetic or measured; without source/digest/calibration state the numerical observable cannot identify provenance. Residual: continuous phase rounding and exact provenance state/digests.

**Independent statistics/validation reviewer — ACCEPT deterministic software oracle / BLOCK detector inference.** Evidence: independently derived analytic known answer, deterministic support controls, exact-head and merged-main Core CI, duplicate exact-head testbeam CI, deliberate PR #8 failing fixture. Strongest counter-hypothesis: tests only restate implementation. Falsifier: expected CR-RC values are independently derived, support fixtures distinguish two domains, and the provenance fixture changes only authorization evidence while holding sampled numerical content valid. Residual: no measured waveform population or production detector sample.

**Claims/provenance reviewer — ACCEPT bounded composition repair / BLOCK #1096 COMPLETE, #1067 COMPLETE and public detector claims.** Evidence: issue acceptance states, live gitlink transitions, CI identities, metadata semantics and PR #8 failure. Strongest counter-hypothesis: valid sampled vectors plus blank digests can still be publicly called `MEASURED`. Falsifier: the source/calibration origin is not identifiable from numerical samples alone, and #1067 explicitly requires exact bound provenance. Residual: provenance-state repair, digest closure, history convergence, calibration and downstream DATA/MC compatibility.

## Next atom

The highest-value next atom is now `ARU-ELEC-IMPULSE-PROVENANCE-STATE-001` because its exact red discriminator is already dependency-ready on the integrated core. Define a non-authoritative custom-sampled state distinct from `MEASURED`; authorize `MEASURED` only when source identity, exact source digest, exact effective-kernel digest and calibration/resampling validation are bound; preserve DCR/kernel-history semantics; then rerun exact-head Core CI and testbeam integration if the gitlink moves.

After that, continue `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`: vary `history_start_ns` farther into prehistory and require convergence of in-window observables under further extension, treating DCR, recovery, afterpulse fast/slow, delayed crosstalk, impulse tails, finite candidate cap and initial-state assumptions as explicit nuisance/dependency variables.

No production Geant4 campaign, beam/production-MC ROOT bytes, measured CCB impulse, calibrated DCR, detector baseline, timing, pile-up, PID, event weights, ESS, p-value, rate, efficiency or detector-performance result was regenerated or promoted.
