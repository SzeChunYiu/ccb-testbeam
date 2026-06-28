# ANALYSIS_GUIDE.md — A guide for someone new to the CCB test-beam analysis

This guide gets a newcomer (human or AI) productive fast. It explains what the experiment is, what
to read in what order, how to reproduce any result, how to run a new study, how to read the
ML-vs-traditional verdicts, and what the open questions are.

---

## 1. What this experiment is about (no jargon)

A beam of **protons at 190 MeV** is fired at a plastic target made of **deuterated polyethylene
(CD2)** at the Cyclotron Centre Bronowice in Krakow. When the beam hits the target, it knocks out
charged particles — mostly **protons and deuterons** (a deuteron is a heavier cousin of the proton,
a proton bound to a neutron). We want to (a) **time** those particles very precisely and (b)
understand **pile-up**: how often two particles arrive so close in time that their signals overlap
and corrupt the measurement.

The particles are caught by two stacks of plastic **scintillator bars** (called the A-stack and
B-stack). A scintillator flashes light when a charged particle passes through; the light is carried
out by a fibre and digitized into an **18-sample waveform** (one number every 10 nanoseconds). From
each waveform we read off an **amplitude** (how big the pulse is, in ADC counts) and a **time**. The
stack acts like a **range telescope**: light particles stop early (front bars), penetrating particles
reach the back bars. That depth pattern is what lets us tell protons from deuterons.

The twist: the real data has **no ground truth**. We never know for certain whether a given pulse was
a proton or a deuteron, or its true energy. So the whole project is built on two pillars:
**(1) data-driven analysis** (reproduce the published numbers, then extend them, always comparing a
classic physics method against a machine-learning method), and **(2) a GEANT4 Monte-Carlo
simulation** that *does* know the truth, used to validate the data conclusions where the data alone
cannot.

---

## 2. How to navigate the reports (what to read first)

Read in this order:

1. **`docs/ANALYSIS_GUIDE.md`** (this file) — orientation.
2. **`FINDINGS_SYNTHESIS.md`** — the distilled science: every conclusion, with confidence labels
   (✅ validated data+MC / ⚠️ data-only / ❌ corrected) and MC verdicts. Start with its "What we know
   for certain" section.
3. **`PROJECT_REPORT.md`** — status dashboard, MC validation table, key-findings ranking, infra,
   open human actions, next steps.
4. **`docs/REPORT_STANDARD.md`** — *before writing anything*, the rules every report obeys.
5. **`reports/SUMMARY.md`** — the rolling one-row-per-study scoreboard (~230 studies).
6. **`reports/<id>/REPORT.md`** — drill into any single study for full methodology and figures.
7. **`docs/00_overview.md` … `docs/09_open_questions.md`** + `docs/glossary.md` — physics background
   and the residual-risk list.

Rule of thumb: the synthesis tells you *what is true*; the standard tells you *how we know*; the
per-study reports are the evidence.

---

## 3. How to reproduce any result (step by step)

**Access LUNARC** (the canonical tree lives at
`/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`; fs10 is mounted on compute nodes):
```bash
ssh cosmos2            # from the LUNARC login node, mounts fs10 interactively
cd /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
```

**Reproduce the data gate (the entry condition for everything, 640,737 pulses):**
```bash
python scripts/01_build_pulse_table_from_root.py --config configs/s00_reproduction.yaml
# expect exactly 640,737 selected B-stave pulses; Sample I B2 = 241,422;
# Sample II B4/B6/B8 = 21,229 / 11,148 / 4,506. Delta from these MUST be 0.
```

**Reproduce an orchestrator-run study (no fleet needed):**
```bash
python3 scripts/p02_pulse_representation.py     # PCA vs autoencoder + clustering
python3 scripts/p07_saturation_recovery.py      # saturation recovery benchmark
```

**Reproduce a specific study:** open `reports/<id>/REPORT.md`, copy the command from its
**Reproduction gate** section, run it, and confirm the count delta is 0 before trusting any number.

**Reproduce / inspect the MC truth:**
```bash
# GEANT4 truth tree (1M events), built with conda env nnbar_env (GEANT4 11.2.2 / ROOT 6.32):
ls geant4/data/output_krakow_1M.root
cat geant4/results/sim_summary.json                       # per-layer p/d fractions
cat reports/mv1_mv2_truth_pid_energy_*/mv1_mv2_truth_summary.json   # MV1 PID AUCs
```

---

## 4. How to run a new study (with template)

1. **Pick the question** from `docs/09_open_questions.md` or the "Next steps" table in
   `PROJECT_REPORT.md`. Give it an ID (S## for analysis, P## for the ML program, MV# for an MC
   validation).
2. **Read `docs/REPORT_STANDARD.md`** end to end. Every study must: reproduce its anchor, run a
   strong traditional method AND an ML method on the same held-out data, report every number with a
   CI and a baseline comparison, run the three leakage controls, and state an explicit MC verdict.
3. **Start from the reproduction gate.** Confirm 640,737 (or the relevant subset) before doing
   anything new.
4. **Write the report** using the fillable template in `docs/REPORT_STANDARD.md` section 7, and the
   `manifest.json` schema in section 8. Produce the six required figures (section 3).
5. **Run the leakage controls** (target shuffle, LORO, event-block shuffle). If two of three reject
   the ML win, the verdict is **CORRECTED** — report it proudly; that is a real result.
6. **Close the loop:** update `FINDINGS_SYNTHESIS.md`, `reports/SUMMARY.md`, and `PROJECT_REPORT.md`
   in one pass (standard section 10).

---

## 5. How to read the ML-vs-traditional verdicts in this project

This project does **not** assume ML is better. It measures *where* ML helps. The taxonomy:

- **"ML wins"** — beats a *strong* traditional baseline on held-out runs with a CI excluding zero AND
  survives all three leakage controls. Examples: duplicate-readout amplitude (P04), saturation
  recovery (P07), two-pulse time-RMS (S11, but gated on failure rate).
- **"ML ties / loses"** — happens when an analytic physics model is already optimal. Examples: timing
  timewalk (analytic 1.49-1.55 ns beats ML residuals after controls), Poisson/live-time pile-up
  scaling, GEANT4 Birks energy calibration, deep-net timing (P03).
- **"CORRECTED"** — an apparent ML win that turned out to be **leakage** (the label was a disguised
  function of the input). Examples: D_t/curvature classifiers at AUC ~1.0 (S07b/e/g), the
  representation-superiority claim (P01a-f), the first saturation benchmark that clipped at C=frac*A.
  *A benchmark that looks perfect is usually leaking.*
- **"gated"** — real in-fold but not yet adoptable pending a transfer/leakage audit (e.g. S03k's
  1.107 ns timing model). Distinct from both "wins" and "CORRECTED".

The mental model: **ML wins when the truth is independent of the input and the missing information
lives in waveform shape.** It ties or loses when physics already has the optimal estimator, and it
"wins" spuriously when the label leaks into the features.

---

## 6. The remaining open questions and why they matter

| Question | Why it matters | Closes via |
|---|---|---|
| What is the 4% early-peak anomaly class? | Could be physics (light fragments/alphas) to keep, or an artifact to veto in timing | **MV6** (morphology vs GEANT4 truth) |
| Does sigma68 ~1.50 ns reproduce in MC? | Confirms the timing result is geometry+electronics, not a data artifact | **MV4** (digitize MC + analytic timewalk) |
| Does R_max ~3 MHz hold with real overlap truth? | The pile-up headline was revised down 30%; needs a known-rate cross-check | **MV5** (MC pulse overlays) |
| What is the LayerID <-> B-stave mapping? | MC penetration (1.3x) and data occupancy (40x) must be reconciled | **MV3** (stopping profile vs occupancy) |
| Can the learned pedestal be validated against truth? | There is no forced/random pedestal sample in data | **MV0** (emit zero-signal sample) |
| Can two-pulse ML control its failure rate on real data? | Lower RMS is useless if the failure rate (0.295) is too high | **MV5** + real high-current audit |

Already **closed by MC:** proton/deuteron PID (MV1, AUC 0.986) and the *limitation* that absolute
per-event energy is unreachable from data (MV2, confirmed the Birks lookup is the best method).

---

## 7. One-screen cheat sheet

- **Data anchor:** 640,737 selected B-pulses (median selector); 706,373 (dynamic). Never proceed on a
  drifted count.
- **Timing champion:** analytic amplitude timewalk, sigma68 ~1.49-1.55 ns (best trad 1.343 ns).
- **Pile-up:** R_max ~3.05 MHz (not 4.2); live10 = 124.79 ns, CI [123.33, 126.36].
- **PID:** MC-closed, HGB AUC 0.986; deuterons stop front, protons penetrate.
- **ML wins:** amplitude closure (P04), saturation (P07), two-pulse RMS (S11, gated).
- **ML CORRECTED:** representation superiority (P01), D_t/curvature classifiers (S07).
- **Biggest open item:** species of the 4% early-peak anomaly (MV6).
- **Before writing a report:** read `docs/REPORT_STANDARD.md`. Every number needs a CI and a baseline.
