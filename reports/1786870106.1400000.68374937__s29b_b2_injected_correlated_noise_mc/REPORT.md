# S29b — injected correlated-noise MC discriminant for the B2 broad residual (#1400)

- **Ticket:** `1786870106.1400000.68374937` · **Worker:** testbeam-laptop · **Issue:** #1400 (spawned by #968 / S29a, PR #1398)
- **Study:** can any candidate mechanism, *injected* on top of the pooled downstream response, reproduce B2's pulse-to-pulse delay structure — the morphology AND the inter-stave residual distribution?
- **Script:** `scripts/s29b_1786870106_1400_68374937_b2_injected_correlated_noise_mc.py`
  · **Config:** `configs/1786870106.1400000.68374937_b2_injected_correlated_noise_mc.json`
  · **Figures:** `scripts/s29b_figs_1786870106.py` → fig1–fig6 (sha256 in `figures.json`)

## Design (non-circular)

The pooled **downstream** response (B4+B6+B8, low light; 57,465-shape empirical
library of all unsaturated interior-peak pulses) is the common baseline. Pulses are
drawn amplitude-matched, so waveforms carry their real noise at the right scale — no
synthetic noise model anywhere. **B2 is predicted, never fed its own shapes** (BOOT
uses B2's own library only as the harness check). B2's saturated pulses are
represented by the highest-amplitude downstream shapes (linear approximation,
documented below — its bias is *measured* by the secondary-rate observable).

V5 calibration touches only **waveform-domain** moments (per-amplitude-bin template
deficit vs the smooth-stratum elevation, in absolute sample index). Every gate
observable — delay spectra, load split, inter-stave KS, late-tail fractions, island
kpk mix, secondary rates — is a pure **distribution prediction**. Selecting library
shapes on delay would be circular; selection is by tail roughness and peak-index
window only.

Populations: no true clipping exists in the 33 runs (`digital_clip` False for every
pulse; max 14.5 kADC) — `saturation_amp_adc` = 7000 ADC is a **load split**. All
KS/late-tail references are the unsaturated population on both sides.

## Harness gates (measured, this run)

| gate | definition | result |
|---|---|---|
| **G1** bootstrap | per-stave bootstrap unsat delay KS ≤ 0.02 | KS {B2 0.0067, B4 0.0075, B6 0.0087, B8 0.0078} → **PASS** |
| **G1b** baseline split | \|V0 split − pooled downstream measured\| ≤ 2 ns | V0 +27.2 vs pooled +29.8 → \|Δ\| 2.6 → **FAIL (borderline, honest)** |
| **NC1** | V0 (no injection) must FAIL G2 | **PASS** (V0 KS 0.192 > 0.05) |
| **NC2** | load-independent excess must fail split clause | **PASS** (NC2 split +17.2 ns, \|Δ\|=8.3 > 2) |

**G1b reading.** The amp-matched baseline lands 2.6 ns below the pooled downstream
measured split — just outside the ±2 ns gate, reported as a FAIL, gate untouched.
The cause is *measured*, not assumed: the linear saturation approximation
represents B2's saturated pulses with the highest-amplitude downstream shapes, whose
saturated secondary **rate** is 0.222 (V0) vs 0.30–0.38 measured downstream — the
baseline under-populates exactly the (later-delayed) saturated secondaries that
carry the split, biasing it low. The split clause is interpreted with this
documented directional bias.

## Variant results (B2, gates: KS ≤ 0.05 AND \|split − (+8.9)\| ≤ 2 ns AND \|KS(B2syn,DNsyn) − 0.279\| ≤ 0.03 AND ltfΔ ≤ 0.02)

| variant | KS(B2, meas) | sat split (ns) | KS(B2syn, DNsyn) | max ltfΔ | G2 |
|---|---|---|---|---|---|
| measured B2 | — | **+8.9** | 0.279 (vs real DN) | — | — |
| V0 baseline (no injection) | 0.192 | +27.2 | 0.156 | 0.012 | FAIL |
| **V5 stratum reweighting (calibrated)** | **0.111** | **+21.1** | 0.315 | 0.011 | FAIL |
| NC2 (V5, constant p — negative control) | 0.122 | +17.2 | 0.327 | 0.023 | FAIL |
| V1 afterpulse / V2 delayed CT / V3 prompt CT / V4 combined | — | — | — | — | **SKIPPED** (literature params absent — distinct from checked-and-negative; rerun on the same seeds when the `literature` config block is populated) |

V5 is the best performer on the primary KS (0.192 → 0.111, closure of the
mean-template deficit 0.72, max per-k residual 0.192 vs V0 deficit 0.216) — the
calibration *works* as waveform-domain description — yet it still FAILS both
decisive clauses: split +21.1 vs +8.9 ± 2 (it moves the split the wrong direction:
the mechanism needs a B2-specific *reduction* relative to the universal downstream
shift, and V5's saturation promotion pushes later, not earlier) and inter-stave KS
0.315 vs measured 0.279 ± 0.03.

## Stage 1.5 manifold test — the family discriminator

Can *any* reweighting of downstream shapes produce the island? Measured B2 island
pulses (d = 9–11) vs the downstream library by amplitude-windowed nearest-neighbour
L2:

| population | NN L2 median | p90 |
|---|---|---|
| island (d 9–11) vs downstream lib | 0.064 | 0.117 |
| non-island (d 2–6) vs downstream lib | 0.047 | 0.085 |
| downstream self-distances (manifold scale) | 0.037 | 0.068 |

Island/scale ratio **1.35 < 2 → WITHIN the manifold** (pre-registered 2× rule): the
island shapes are reweightings of downstream response, not a foreign component.
Corroborated by tail roughness: island R median 0.1033 (q10 0.0874) vs downstream
library R min 0.0134 — frac(island R < lib min) = 0.000. The island is the
**smoothest-tail subpopulation** of the same response family.

**Verdict:** *effective representation supported* (downstream-shape reweighting
family), *microscopic mechanism NOT identified* — the misses are selector
mis-specification, not family exclusion.

## Why the calibrated reweighting misses — root cause, pinned in data

Two independent measured observables reconcile the apparent contradiction between
(a) the template deficit growing monotonically into saturation and (b) the delay
island being an *unsaturated* phenomenon (25.6% of B2 unsat secondaries at d = 9–11
vs 2.5–6.3% downstream; island mean amplitude 6185 vs 4636 ADC; island pretrigger
excursion p90 492 vs 1127 ADC — pre-pulse pile-up refuted):

**Secondary RATE by load band** (fraction of interior-peak pulses with ≥ 2 eligible
maxima; eligibility floor 5% of global max):

| population | mid-high [4.5k, 7k) ADC | sat ≥ 7k ADC |
|---|---|---|
| measured B2 | **0.862** | **0.659** |
| measured B4 | 0.643 | 0.336 |
| measured B6 | 0.632 | 0.300 |
| measured B8 | 0.621 | 0.385 |
| synthetic B2 V0 | 0.545 | 0.222 |
| synthetic B2 V5 | 0.363 | 0.117 |

Measured rates **fall** with load on every stave while the per-bin template deficit
**grows** into saturation: smooth saturated tails sink below the 5% eligibility
floor and leave the secondary population entirely — the template excess and the
unsaturated island are carried by **different populations**, which is exactly why a
single template-calibrated p(A) (V5's sat-bin p = 0.361) over-promotes saturation
and drives the split the wrong way. The same table quantifies the linear-approximation
bias (V0 sat 0.222 < downstream measured ≈ 0.33): representing B2 saturation with
highest-amplitude downstream shapes distorts population *membership*, a channel the
conditional-mean split never tested.

## Discriminant status (S29a schema) and #1401

```json
"discriminant_status": {
  "injected_correlated_noise_mc": "PARTIAL",
  "electronics_impulse_response": "STRUCTURALLY_UNAVAILABLE"
}
```

- `PARTIAL`: conclusive for the reweighting family (V0/V5/NC2 + manifold + gates
  above); the literature-parametric family V1–V4 is SKIPPED-literature-absent
  (exit 3), rerunnable on the same seeds when Hamamatsu S13360-3050CS parameters
  land in the config `literature` block.
- **#1401 electronics impulse response: STRUCTURALLY_UNAVAILABLE** — no bench/SPE
  electronics characterization exists in the 33 calibration runs or the extracted
  tree (searched run content lists, config registry, reports/ — scope-justified
  NOT_FOUND, distinct from checked-and-absent). Extracted pulse shapes conflate
  electronics response with light-production timing; only the conflated effective
  response is recoverable, which is why this study models the effective response
  empirically.

## Verdict for the paper

1. The B2 broad residual's delay structure **cannot be produced by any tested
   mass-adding or transforming injection** (five families refuted with numbers:
   additive delayed-light excess γ = 0/1/2, multiplicative tail boosts, convex tail
   regularisation, Bernoulli synthetic-tail mixture, and now calibrated stratum
   reweighting) — common root cause: added/transformed mass creates early eligible
   maxima or smears across the kpk spread, while the delay structure lives in the
   shape **distribution** (BOOT KS 0.0067).
2. The island is **within** the downstream response manifold (ratio 1.35, roughness
   support 0.000 below lib min): sensor/light-side structure remains the supported
   effective representation; no foreign (electronics-defect) component is needed or
   indicated.
3. The mechanism moves **unsaturated mid-high-load pulses into the island**; it does
   not push saturated pulses later — the load split (+8.9 vs universal +29.8) and
   the secondary-rate falloff pin this in data.
4. Open: microscopic identification (which smooth-tail physics selects ~25% of B2's
   unsaturated secondaries) and the V1–V4 literature-parametric injections.

Exit code 3 (literature absent) — all numbers above are from the executed
V0/V5/NC2/BOOT/manifold stages; seeds are config-pinned and the study is
deterministic.
