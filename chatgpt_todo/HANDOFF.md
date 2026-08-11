# Latest Handoff

## SiPM history semantics and measured-impulse fail-closed behavior are composed in core; testbeam repair is staged

Protected testbeam main at the start of the repair is `0800a0cece4dff733c82e024b4c764e85ce947d9`. That merge changed the SiPM gitlink from validated `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518` to `5c6bb0278be4246f3da9007b71a5d13024b968ca`, a commit based on older `2027b06...`. Consequently live main temporarily regressed the validated pre-window DCR-history repair and the newer history-complete impulse-kernel repair while adding a separate measured-impulse fail-closed candidate.

The safe resolution is not to choose either side. Core PR #7 composes both semantic families on the current history-complete core lineage.

## Kernel-history contract and execution

For admitted avalanche `t_a` and recorded sample `t_i`, the encoded analog law is

`V_i = sum_a A_a h(t_i-t_a)` for `t_i >= t_a`.

With `N_out=floor((window_end-window_start)/dt)+1` and `H=max(0,window_start-history_start)`, the conservative uniform-grid elapsed-time kernel is

`N_kernel=N_out+ceil(H/dt)`.

At default history `-200 ns`, output window `[-20,250] ns`, and `dt=0.5 ns`, `N_out=541`, `N_kernel=901`, and an avalanche at the history boundary is 450 ns old at the final sample. The old output-length kernel covered only 270 ns.

The deterministic discriminator uses history `-20 ns`, output `[0,10] ns`, `dt=1 ns`, one history-boundary avalanche, and generic `h_raw(t)=exp(-t/25)-exp(-t/1)` with stochastic detector/electronics mechanisms disabled. Old code is identically zero because its 11-point kernel cannot reach required ages 20--30 ns. The repaired 31-point grid closes every output sample to the analytic peak-normalised reference at `1e-12`; first/last expected values are approximately 0.536747 and 0.359792. Collapsed-history and finite measured-support controls constrain the repair.

Core PR #5 exact head `454579870a8f1eb9b0f67e02df30486f778f7b67` passed Core CI `31520345468` / `93875571412`, then squash-merged as `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`; exact merged-main run `31520555652` / `93876260437` independently passed.

## Measured-impulse composition and #1067

The merged #1226 target had useful fail-closed intent but two material cross-atom defects. Its measured-support validator used only recorded waveform duration, although old admitted avalanches require the longer elapsed-time kernel. It also populated fields named as source/effective-kernel hashes with `LEN-<size>` placeholders rather than cryptographic content digests. #1067 was therefore reopened.

Core PR #7, branch `fix/compose-history-measured-impulse`, starts exactly from history-complete `main@68eadf3...`. It retains DCR support from `history_start_ns` and extended kernel convolution while adding measured-impulse validation: matched vector lengths, at least two finite strictly increasing time samples, nonzero peak, positive trapezoidal integral, hard failure instead of silent delta fallback, and explicit `IDEAL_DELTA_TEST_ONLY` only with `authorising=true`.

Its support validator uses the history-complete domain. A dedicated joint regression has history `-20 ns`, output `[0,10] ns`, `dt=1 ns`, and measured support `[20,22,25] ns` with amplitudes `{0,1,0}`. That response is beyond the recorded 10 ns duration but inside the 30 ns history-to-output domain; it must validate and contribute to an in-window sample. Support `[40,42,45] ns` must fail. Additional controls cover valid non-delta response, all-zero and negative-integral rejection, ideal-delta authorisation, and absence of fabricated digest placeholders.

Exact PR #7 head `0b18bc08c9e077eebe3e20c8bfd5005085de09f3` passed Core CI run `31522503501`, job `93882757978`: checkout, Configure, Build and Test all SUCCESS. PR #7 then squash-merged with an expected-head guard as `ccb-sipm-core@e71fd26c915a402590931d2a7657157f04277235`. Its independent main-push Core CI run `31522658182` completed SUCCESS.

The composed core intentionally leaves digest fields blank unless exact provenance is provided; that is safer than a false cryptographic claim, but it also means #1067 remains open until true source/effective-kernel digests and the remaining acceptance leaves are validated.

## Testbeam repair state

Fresh branch `fix/sipm-history-composition-integration` starts from exact protected `main@0800a0ce...`. Commit `7a7f06930855213d77bbcd30be93c507ac58b6ba` advances only `geant4/single_stave/sipm` to composed core `e71fd26c...`. Archive `chatgpt_todo/archive/2026-08-11T182700Z_ARU-SIPM-KERNEL-MEASURED-COMPOSITION-001.md` records mechanisms, equations, exact CI and role votes.

The earlier kernel-only testbeam PR #1227 was closed unmerged because it could no longer safely resolve the concurrent #1226 gitlink. Core conflict-probe PR #6 was likewise closed unmerged. Do not resurrect either; the descendant composition is the authoritative repair path.

## Four sequential AI review passes

**SiPM/electronics lead — ACCEPT bounded history-complete composition / REVISE physical response+horizon.** Evidence includes exact source lineage, time-domain contracts, analytic CR-RC fixture, measured-support fixture and exact Core CI. The strongest counter-hypothesis—that recorded waveform duration defines all electronics memory—is falsified by nonzero configured response from admitted older avalanches. Real CCB electronics impulse and sufficient physical prehistory remain uncalibrated.

**Adversarial mechanism reviewer — ACCEPT descendant composition / BLOCK #1065 sub-grid timing and exact-digest claims.** Selecting either concurrent git lineage independently loses validated semantics. The composed descendant retains both. Finite-support controls show array extension does not create physical tails. Continuous avalanche phase is still rounded by `lround`; existing #1065 owns that atom. Exact hash provenance remains unresolved.

**Independent statistics/validation reviewer — ACCEPT deterministic software oracle / BLOCK detector inference.** Expected generic-tail values are analytically independent of implementation, and the measured-support fixture discriminates output-duration versus history-domain validation. Exact PR and merged-main Core CI compile/run all C++ regressions. No beam, production MC or bench impulse population participates.

**Claims/provenance reviewer — ACCEPT bounded composition repair / BLOCK #1096 COMPLETE, #1067 COMPLETE and public detector claims.** The non-descendant #1226 gitlink and `LEN-*` placeholders falsified the proposition that the merge monotonically completed the SiPM provenance state. #1067 is reopened; #1096 remains PARTIAL.

## Surviving children and next atom

The provisional sampling child from the kernel audit is collapsed into existing #1065 `ARU-SIPM-SUBGRID-001` for pre-convolution continuous phase. Real DAQ aperture/clock sampling stays with #1009/#1014. #1010 remains the measured/generic electronics calibration universe.

The highest-value next atom after protected testbeam integration is `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`: extend `history_start_ns` systematically and require convergence of in-window observables under further history extension while scanning nuisance variables for DCR, recovery, fast/slow afterpulse time constants, delayed crosstalk and impulse tails. A parent is not complete until this convergence and downstream waveform/analysis compatibility are demonstrated.

No production Geant4 campaign, beam/production-MC ROOT bytes, measured CCB impulse, calibrated DCR, detector baseline, timing, pile-up, PID, event weights, ESS, p-value, rate, efficiency or detector-performance result was regenerated or promoted.
