# S29a — B2 broad-residual mechanism discriminants on raw B-stack waveforms (#968)

- **Ticket:** `1786863177.1383050.cfc84ffc` · **Worker:** testbeam-laptop · **Issue:** #968
- **Study:** complete authorising 8×16 raw B-stack population (33 runs), exact s25b
  selection contract, executed 2026-08-16
- **Script:** `scripts/s29a_1786863177_968_cfc84ffc_b2_residual_discriminants.py`
  · **Config:** `configs/1786863177.1383050.cfc84ffc_b2_residual_discriminants.json`

## Population and contract reproduction

All 33 authorising runs (`hrdb_run_*.root`, tree `h101`): per-event `HRDv` reshaped
`(8, 18)` (channel-major), baseline = median(samples 0–3) per channel, even channels
B2/B4/B6/B8 = signal, odd = duplicate readout (polarity-flipped with `−`), selection =
baseline-subtracted even amplitude > 1000 ADC.

**640,737 / 640,737 selected pulses reproduced — bit-exact against the registered
s25b count (delta 0).** B2 carries 579,424 (90.5%); B4 36,116; B6 17,945; B8 7,252.

All vectorized observables validated **bit-exact** against the fail-closed contract
module `src/ccb_mc_validation/timing/b2_broad_residual_mechanisms.py` on 2,000 seeded
random pulses: `late_tail_fraction`, `secondary_peak_delay_samples`,
`pretrigger_excursion_adc` — **0/2000 mismatches each**.

## Discriminant 1 — duplicate_channel_parity

Late structure (late-tail fraction > 0.2) in the even (signal) channel vs the SAME
stave's odd duplicate readout chain:

| stave | n | P(late, even) | P(late, dup) | P(both) | P(both)\|indep. | φ | P(dup late \| even late) | even-only | ρ(ltf e,o) | ρ(amp e,o) |
|---|---|---|---|---|---|---|---|---|---|---|
| B2 | 579,424 | 0.9777 | 0.9628 | 0.9607 | 0.9414 | **0.693** | 0.9826 [0.982, 0.983] | 0.017 | 0.768 | 0.987 |
| B4 | 36,116 | 0.9270 | 0.8991 | 0.8752 | 0.8335 | **0.533** | 0.9441 [0.942, 0.947] | 0.056 | 0.746 | 0.908 |
| B6 | 17,945 | 0.9417 | 0.9149 | 0.8955 | 0.8613 | **0.519** | 0.9509 [0.948, 0.954] | 0.049 | 0.788 | 0.914 |
| B8 | 7,252 | 0.9337 | 0.9104 | 0.8869 | 0.8500 | **0.520** | 0.9499 [0.944, 0.955] | 0.050 | 0.746 | 0.917 |

**Reading.** The late structure replicates pulse-by-pulse in the duplicate chain
(φ = 0.52–0.69; ρ(ltf) = 0.75–0.79; ρ(amp) = 0.91–0.99; chain-independent defects
would give φ ≈ 0). Single-chain electronics defects (one chain's ADC low-word, one
chain's shaping fault) are excluded as the **dominant** cause: they would appear as
even-only structure, bounded at 1.7% (B2) … 5.6% (B4).
**Limitation (stated):** the two chains share the buffer clock, so *common-mode*
electronics (clock/buffer phase) replicates by construction and cannot be excluded
by parity alone — that is deferred to the impulse-response discriminant.

## Discriminant 2 — delay_spectrum

Secondary-peak delay (module semantics; ×10 ns; non-positive delays = leading-edge
peak with no resolvable post-peak structure — 0.0% everywhere):

| stave | n (with 2nd peak) | median | mean | τ̂ (exp. MLE) | frac ≤ 20 ns |
|---|---|---|---|---|---|
| B2 all | 383,252 | 40 ns | 53.8 ns | 53.8 ns | 0.054 |
| B2 unsaturated (<7000 ADC) | 262,559 | 40 ns | 51.0 ns | 51.0 ns | 0.044 |
| **B2 saturated (≥7000 ADC)** | 120,693 | 40 ns | **59.9 ns** | 59.9 ns | 0.077 |
| B4 | 18,483 | 30 ns | 34.8 ns | 34.8 ns | 0.164 |
| B6 | 7,643 | 30 ns | 34.0 ns | 34.0 ns | 0.162 |
| B8 | 4,060 | 30 ns | 34.9 ns | 34.9 ns | 0.124 |

- **KS B2 vs pooled downstream: D = 0.268, p ≈ 0** — B2's secondary structure is
  systematically later than B4/B6/B8 (which are mutually consistent).
- **Saturation shifts B2 later**: 51.0 → 59.9 ns mean (unsat → sat). The B2 residual
  couples to light load. (Saturated subsets of B4/B6/B8 are n = 47/3/5 — not evaluable.)
- Not a clean exponential and not flat (Fig 1): a 30–40 ns core with a B2-heavy tail.

## Discriminant 3 — current_rate_dependence

Two-particle pile-up **requires** positive rate dependence. Three independent rate
proxies over 33 runs + within-run ±500-event windows:

| proxy | slope | bootstrap 95% CI | Spearman |
|---|---|---|---|
| per-run EVT-skip fraction | −0.271 | [−10, +4.11] | −0.067 |
| per-run mean multiplicity | −0.00366 | [−0.0173, +0.0056] | −0.657 |
| within-run local-skip mean | −0.439 | [−10, +3.79] | −0.069 |

Within-run local-rate terciles (late fraction t1/t2/t3): **0.9737 / 0.9738 / 0.9729**
— flat to <0.1%.

**No positive rate dependence in any proxy.** Pile-up is unsupported as the B2
broad-residual mechanism at these operating rates. Caveats: (i) the EVT counter
resets 4,784 times over 1,096,728 rows (≈67 full-wraps expected), so skip fractions
mix true skips with counter restarts — the multiplicity and within-run proxies do
not depend on the counter; (ii) this bounds the mechanism **at the rates actually
present in the authorising sample**, and does not extrapolate to higher-rate running.

## Discriminant 4 — raw_word_defect_flags

| stave | digital clip (≥16370) | boundary peak (s0/s17) | pretrigger excursion >150 ADC | saturated (≥7000) |
|---|---|---|---|---|
| B2 | **0 / 579,424** | 0.0128 | 0.2512 | 0.3161 |
| B4 | 0 | 0.0663 | 0.2867 | 0.0040 |
| B6 | 0 | 0.0563 | 0.2385 | 0.0006 |
| B8 | 0 | 0.0611 | 0.2362 | 0.0019 |

Zero digital clipping in the whole population → **ADC low-word / clipping defects
excluded**. Pretrigger excursions >150 ADC are common (~24–29%) — consistent with
shaping/baseline structure feeding the module's ELECTRONICS_SHAPING/BUFFER_PHASE
support terms. B2 is the light-loaded stave (31.6% saturation vs <0.5% downstream).

## Discriminant 5 — exact_event_key_closure

- `EVENTNO` is a **global counter that chains across run-file boundaries**
  (run 31 ends 431,385 → run 32 starts 431,386, … across all 33 files).
- Within-file gaps exist in 27/33 runs (rows < max−min+1); total missing ~0.7%.
- `EVT` (14-bit) is monotone-modulo-wrap within files but resets 4,784× and skips
  7,457/1,096,728 (0.68%) — quantified above as the rate proxy.

Status **PARTIAL**: keys are consistent and chained (no corruption, no reordering),
but the stream is not gapless; recorded per-run in `result.json`.

## Not executed on this data (fail-closed)

| discriminant | status | reason |
|---|---|---|
| `track_tpc_association` | NOT_EXECUTED | structurally unavailable — no TPC in the testbeam |
| `injected_correlated_noise_mc` | NOT_EXECUTED | needs its own MC injection study (follow-up) |
| `electronics_impulse_response` | NOT_EXECUTED | needs single-photoelectron/bench impulse data (follow-up) |

## Support table and labels

Module `rank_mechanism_support` over a 35,238-pulse subsample (≤350/run/stave;
waveform-scalar observables + duplicate mismatch): mean support
two_particle_pileup 0.306, sipm_afterpulse_recovery 0.210, electronics_shaping 0.171,
terminal_primary_secondary 0.124, buffer_phase 0.122, polarity_mapping 0.054,
adc_low_word_defect 0.036. Leading-mechanism counts per stave are dominated by
`unresolved` + `two_particle_pileup` + `electronics_shaping` — i.e. **waveform shape
alone does not resolve the mechanism**, exactly why the cross-cutting discriminants
above carry the evidential weight. Cross-cutting evidence removes pile-up (no rate
dependence), ADC-word defects (zero clipping) and single-chain defects (parity φ),
leaving sensor/light-side structure — scintillation tail + WLS + SiPM recovery,
saturation-coupled on B2 — as the effective representation supported by the data.
Per the module this is an **effective-representation** statement, **not** a
microscopic mechanism identification.

Module class labels (non-authorizing): `b2_broad_residual_unresolved` /
`b2_broad_residual_mechanism_ambiguous`. Mapped to the issue-#968 required
mechanism-neutral labels:

- **`B2_BROAD_RESIDUAL`** — the population class: every selected B2 pulse belongs
  here; the measured population properties are the delay-spectrum shift,
  saturation coupling and duplicate-chain replication above.
- **`LATE_COMPONENT_CANDIDATE`** — the sub-population with a resolvable
  secondary peak (module `has_secondary`): 383,252/579,424 B2 pulses (66.1%),
  18,483/36,116 B4, 7,643/17,945 B6, 4,060/7,252 B8. "Candidate" is the strongest
  permitted word: the microscopic identity stays undetermined.

No stronger (microscopic) label is used anywhere in this report.

## Authorization gate outcome

`authorize_pileup_like_wording` → **BLOCKED_MECHANISM_UNDISCRIMINATED**,
authorized = **false**, missing = {`track_tpc_association`,
`injected_correlated_noise_mc`, `electronics_impulse_response`,
`exact_event_key_closure`}. The fail-closed contract holds: no pile-up-like
microscopic wording is authorized by this study, and none is used above.

## Figures

1. `fig1_delay_spectrum.png` — delay spectrum per stave (log y) + B2 saturation split.
2. `fig2_duplicate_parity.png` — P(late in duplicate | late in signal) with Wilson 95% CIs.
3. `fig3_rate_dependence.png` — per-run late-fraction vs skip fraction + within-run terciles.
4. `fig4_amplitude_structure.png` — B2 amplitude vs late-tail fraction (2D) + delay CDFs.

## Falsification and revival path

- **Parity would have failed** if φ ≈ 0 / P(dup late | even late) ≈ P(late dup):
  single-chain electronics would produce exactly that. Measured φ = 0.52–0.69.
- **Pile-up would have survived** with positive slope CI excluding 0 in any proxy or
  a monotone tercile trend. All three CIs include 0 (two centred negative); terciles flat.
- **Revival path for pile-up**: demonstrate positive rate dependence at higher-rate
  running (the present data's deadtime is ~0.7%, so the bound is regime-limited),
  or independent multi-particle evidence (TPC association — not available here).
- **Open discriminants** (their own iterations): injected correlated-noise MC;
  electronics impulse response (would also close the common-mode limitation of the
  parity test).

`result.json` carries all per-run closure records, per-proxy regression numbers,
per-stave delay histograms and the full support table; `pulses.parquet` holds the
per-pulse observable table.

## Issue acceptance coverage

| #968 acceptance | status |
|---|---|
| mechanism-neutral labels (`B2_BROAD_RESIDUAL`, `LATE_COMPONENT_CANDIDATE`) | used; no stronger label |
| discriminating observables per mechanism | delivered (parity → single-chain electronics; rate proxies → pile-up; clip counts → ADC-word; delay shape/scales → afterpulse/WLS vs buffer) |
| mechanisms reproducing waveform morphology **and** inter-stave residual distribution | morphology-level discrimination done here (B2-vs-downstream KS D=0.268); full reproduction requires the injected-MC discriminant — explicitly NOT_EXECUTED, follow-up |
| pile-up claims need rate dependence or multi-particle evidence | rate dependence measured ABSENT in three proxies; no pile-up claim made |
| classification / timing-calibration separation | untouched: this study classifies waveforms only and does not modify any timing-extraction or calibration path |

## References (primary-method, from the repo literature map)

- J. Rosado & J. M. Hidalgo, *Characterization and modeling of crosstalk and
  afterpulsing in Hamamatsu silicon photomultipliers*, arXiv:1509.02286 —
  prompt/delayed crosstalk + afterpulse separation via amplitude-delay
  distributions and MC; the method family the delay-spectrum discriminant
  instantiates (amplitude-delay, not morphology alone).
- Gallego et al., *Modeling crosstalk in silicon photomultipliers*,
  arXiv:1302.1455 — finite-neighbour crosstalk models with recovery/dead-time
  effects and dedicated waveform measurements; the reproduction standard the
  injected-MC follow-up must meet (morphology + inter-stave residuals).
- Literature map: `chatgpt_todo/LITERATURE_AND_METHOD_MAP_20260808.md`.
