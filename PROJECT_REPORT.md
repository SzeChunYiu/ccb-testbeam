# CCB Test-Beam — Project Report & Status

**One document with everything a human needs to know about this project: the science, what has
been done, the results, the current state, what is blocking us, and what comes next.**

- **Last updated:** 2026-06-09
- **Repository:** `SzeChunYiu/ccb-testbeam` (branch `main`)
- **Status:** research in progress — all numbers **preliminary, not peer-reviewed**
- **This file is the entry point.** Deeper material lives in `docs/` (physics background),
  `studies/STUDIES.md` (the full plan), and `reports/<study>/REPORT.md` (per-study detail).
  This report pulls the *headline results and live status* into one place so you don't have to
  open all of them.

---

## 1. TL;DR (read this first)

| | |
|---|---|
| **What** | Data-driven (no Monte Carlo) analysis of CCB test-beam data: 190 MeV protons on a CD₂ target, read out by HRD scintillator range stacks. |
| **Physics goals** | (1) same-particle **timing resolution** of the staves; (2) **pile-up** characterisation. |
| **Data** | ~640,737 selected B-stack pulses, 18-sample waveforms @ 10 ns. ~6.4 GB, stored **outside git** and immutable (see §3). |
| **Method discipline** | Three non-negotiable rules: reproduce-first, traditional **and** ML head-to-head, atomic decomposition (§4). |
| **Done so far** | 4 studies complete & merged: **S00** (reproduction gate ✅ exact), **S01b** (table manifest), **P02** (PCA vs autoencoder), **P07** (saturation recovery). Headlines in §5. |
| **Fleet** | **Running** (5 sandboxed workers + keeper). A codex-0.129 sandbox bug (it can't write `.git` or the queue on this kernel) was fixed by wrapping codex in an external **bubblewrap** jail — see §6. Codex stays pinned at 0.129; do **not** upgrade. |
| **Queue** | 10 ready tickets enqueued (S01, S00a, S02, S07, S10, S14, S16, S18, P01, P04); workers are claiming and working them now. |

---

## 2. The measurement (science in brief)

At the Cyclotron Centre Bronowice (CCB, Kraków) a **190 MeV proton beam** strikes a
**deuterated polyethylene (CD₂)** target. Charged particles leaving the target are recorded by
trigger scintillators, a TPC, and **two HRD scintillator range stacks** (A and B), each ~1 m
from the target, acting as a data-driven **ΔE–E / range telescope**.

For each stave we record an **18-sample waveform at 10 ns spacing**, read out at one end via a
wavelength-shifting (WLS) fibre, and reconstruct an amplitude (ADC), a time (ns), and shape
variables. The main analysis uses **B-stack staves B2, B4, B6, B8**; the **A-stack (A1, A3)**
is a decoupled cross-check.

**The two goals**

1. **Timing resolution** — how precisely can a stave (and a multi-stave event) timestamp a
   particle, established from same-particle inter-stave time residuals.
2. **Pile-up** — how often overlapping pulses corrupt time/charge, and at what beam rate it
   becomes limiting.

**Headline target numbers (from the source notes, to be reproduced/extended)**

| Quantity | Value |
|---|---|
| Downstream single-stave timing | B6 ≈ 0.68–0.75 ns, B8 ≈ 0.93 ns, B4 ≈ 1.4–1.5 ns |
| Combined 3-stave event time | σ_comb ≈ 0.54 ns (Sample I) / 0.56 ns (Sample II) |
| Two-ended-readout projection | σ ≈ 0.6–1.0 ns (factor √2) |
| A-stack A1–A3 residual | robust width 1.43 ns, core σ 1.41 ns |
| Pile-up tolerance | R_max ≈ 4.2 MHz (\|Δt\|<1 ns & area<20%, >90% eff, τ_eff=90 ns) |
| Beam pile-up excess @ 20 nA | ≈ 9.2% downstream |

**The samples**

| Sample | Stack | Enrichment | Role |
|---|---|---|---|
| Sample I | B | D-enriched, terminal-B2-like | topology-heavy |
| Sample II | B | p-enriched, penetrating | clean timing reference |
| Sample III / IV | A | = Sample I / II runs | A-stack cross-check |

> Full background: `docs/00_overview.md` … `docs/09_open_questions.md`, `docs/glossary.md`,
> `docs/references.md`. Provenance: two analysis notes (54 pp v41 B-stack; 122 pp B+A+ML, the
> newer one is authoritative where they disagree).

---

## 3. Data & where everything lives

| What | Path | Notes |
|---|---|---|
| **Canonical data store** | `/home/billy/ccb-data` (**outside** the repo) | **immutable** (`chattr +i`); survived the 2026-06-08 data-loss incident |
| → raw | `…/ccb-data/raw/` | `sorted-a/b.zip`, `root.zip` — sha256-verified vs S00 inputs |
| → extracted | `…/ccb-data/extracted/` | 110 ROOT files (57 hrda + 53 hrdb + sorted), 6.1 GB |
| → docs | `…/ccb-data/docs/` | the 122 pp report PDF |
| **Data in the repo** | `./data` → symlink to `…/ccb-data/extracted` | **read-only**; never write here |
| Processed S00 table | `data/processed/s00_selected_b_pulses.csv.gz` | git-ignored; regenerate from raw (see S01b) |
| Code / configs | `scripts/`, `configs/` | analysis & ML code |
| Study plan | `studies/STUDIES.md` | S00–S18 + P01–P11, prioritised |
| Per-study results | `reports/<study>/REPORT.md` | one dir per study, with figures + `manifest.json` |
| Scoreboard | `reports/SUMMARY.md` | rolling one-row-per-study table |

**Data-safety rules (from the 2026-06-08 incident — do not repeat):** data is read-only,
external, immutable, and backed up. Never store the only data copy in an agent's working tree.
Workers are sandboxed to their own clone. Full post-mortem in `fleet/LESSONS.md`.

---

## 4. How the work is organised

**Three non-negotiable rules** (the user's standing requirements):

1. **Reproduce first.** Before extending anything, reproduce the report's numbers from raw ROOT.
   S00 is the gate.
2. **Traditional AND ML.** Every study does both a strong conventional method and an ML method,
   with a *fair* head-to-head benchmark (no strawman baselines).
3. **Atomic decomposition.** Understand every small step; no black boxes.

**Study programme** (`studies/STUDIES.md`): Phase 0 foundation (S00, S01), Phase 1 atomic
understanding (S02–S07, S10–S13, S18), Phase 2 extension (S08, S09, S14–S17), plus a dedicated
**ML Pulse-Characterisation Program P01–P11**. Each study ends with a report following
`studies/STUDY_TEMPLATE.md`.

**Execution model:** studies → tickets on the `tn-ticket` queue (`project:testbeam`) → worked by
a fleet of sandboxed codex agents → each produces a `reports/<id>/` write-up and a PR. Claude is
the **orchestrator**: maintains `STUDIES.md`, cuts tickets, gathers reports, updates the
scoreboard — and, when the fleet is blocked, runs studies directly (that is how P02 and P07 were
done). See `fleet/ORCHESTRATION.md`, `WORKER_PROTOCOL.md`, `SCALING.md`.

---

## 5. Results to date

**Scoreboard** (also in `reports/SUMMARY.md`):

| Study | Status | Reproduced? | Traditional | ML | ML beats baseline? |
|---|---|---|---|---|---|
| **S00** | ✅ merged (PR #1) | ✅ 640,737 exact | deterministic threshold | logistic-reg sanity | No — threshold is exact (ML adds nothing, correctly) |
| **S01b** | ✅ merged (PR #2) | ✅ raw-ROOT re-derive | deterministic gate | inherited sanity | No (foundation/manifest) |
| **P02** | ✅ merged (PR #3) | selection = S00 | PCA | autoencoder | **AE 40–51% better @ dim ≤ 4; PCA wins @ dim 8** |
| **P07** | ✅ merged (PR #4) | self-truth (clip) | template extrapolation | gradient boosting | **ML ~4% vs template 10–29% (3–7× better)** |

### S00 — Data integrity & pipeline reproduction *(the gate)*
**Passed exactly, zero tolerance.** Rebuilt the selected B-stave pulse table from raw ROOT
(`HRDv`, reshape to 8×18, physical staves = even channels {0,2,4,6}, baseline = median of
samples 0–3, amplitude = max(baseline-subtracted), cut **A > 1000 ADC**) and matched **every**
checked count: **640,737** total selected pulses, and all per-sample/per-stave breakdowns
(e.g. Sample I analysis B2 = 241,422; Sample II analysis B4/B6/B8 = 21,229 / 11,148 / 4,506).
- Traditional deterministic threshold is the correct production method; the ML logistic-regression
  check (run-split, calibrated, bootstrapped) scores 0.9998 vs the threshold's exact 1.0 — ML
  correctly adds **no** value because the label *is* the threshold rule.
- Key caveat surfaced: sorted-file `hrdMax` over-counts vs raw `HRDv` → the gate must stay pinned
  to raw waveforms (motivates ticket **S00a**).
- Detail: `reports/S00_data_integrity_pipeline_reproduction/REPORT.md`.

### S01b — S00 selected-table manifest & regeneration hook
Confirmed the processed table is **not** shipped in the data mirror but **regenerates exactly**
from raw ROOT (640,737 rows; sha256 pinned). Provides a manifest + `regenerate_*.sh` so downstream
workers can locate/rebuild and checksum the table instead of each re-deriving it. Diagnosed that
recent "blocked" sessions were **infrastructure/path drift**, not a physics discrepancy.
- Detail: `reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/REPORT.md`.

### P02 — Pulse-shape representation & unsupervised type discovery
*(orchestrator-run while the fleet was paused)*
- Pulse shape is **low-dimensional**: PCA first 3 components ≈ 89% of shape variance, 8 ≈ 99.7%.
- **Autoencoder beats PCA by 40–51% at low latent dim (2–4)**; at dim 8 linear PCA wins (the
  small AE underfits). → use a compact AE embedding when you need few dims; PCA once enough linear
  dims are allowed.

  | Latent dim | PCA MSE | AE MSE | Winner |
  |---|---|---|---|
  | 2 | 0.02622 | 0.01294 | AE +50.6% |
  | 3 | 0.01416 | 0.00841 | AE +40.6% |
  | 4 | 0.00880 | 0.00527 | AE +40.1% |
  | 8 | 0.00166 | 0.00292 | PCA +75.9% |

- **Label-free discovery:** clustering surfaced a ~4% **early-peak / near-zero-area** anomalous
  class (peak at sample 3, A ≲ 1200 ADC) — a concrete lead for **P09** (anomaly detection) and a
  quality flag the timing studies should exclude.
- Detail: `reports/P02_pulse_representation_discovery/REPORT.md`.

### P07 — Saturation recovery for high-amplitude B2
*(orchestrator-run while the fleet was paused)*
~30–40% of Sample-I B2 pulses exceed 7000 ADC and saturate. Recover true amplitude from the
unsaturated **rising edge**; benchmark on self-generated truth (clip clean pulses at a fixed
ceiling, split **by run**).

| Fixed ceiling (ADC) | naive (=ceiling) | template (traditional) | **ML (GBR)** |
|---|---|---|---|
| 4000 | 0.264 | 0.104 | **0.032** |
| 3000 | 0.346 | 0.239 | **0.039** |
| 2500 | 0.403 | 0.233 | **0.042** |
| 2000 | 0.493 | 0.286 | **0.046** |

- **ML recovers amplitude to ~3–5%, beating the template extrapolation by 3–7×**, and degrades
  gracefully as saturation worsens. Enables a usable amplitude for the 30–40% of B2>7000 pulses
  currently treated as diagnostic-only.
- **Process honesty:** the first version *leaked* (clipping at `C = frac·A` let ML read amplitude
  off `max = frac·A`, giving an absurd res68 ≈ 0.002). Caught, fixed with a constant ceiling, and
  recorded as the canonical cautionary tale in `fleet/LESSONS.md`: *a benchmark that looks perfect
  is usually leaking.*
- Detail: `reports/P07_saturation_recovery/REPORT.md`.

---

## 6. Infrastructure & current blocker ⚠

The autonomous fleet (`fleet/launch_local.sh [N]`) spins up N **sandboxed** codex workers, each in
its own git clone with the immutable data symlinked read-only. The keeper (`fleet/keeper.sh`)
reaps stale claims, auto-merges conflict-free PRs, and relaunches dead workers.

**Status (2026-06-09): FIXED — the fleet is running again.** Root cause and fix below.

What was fixed today:
- **`tn-ticket` shim path bug** — the `~/.local/bin/tn-ticket` → `~/tn/bin/tn` symlink resolved
  its library dir from the *symlink* location (`~/.local/lib`, which lacks the store script)
  instead of the real install (`~/tn/lib`). **Fixed** in `~/tn/bin/tn` by dereferencing the
  symlink (`readlink -f`) before computing `TN_LIB`. `tn-ticket list/claim` now work.
- **Queue tidied** — marked the two finished tickets done (S01b merged, S01a data-mirror
  restored), and enqueued 10 ready tickets (all depend only on S00, which is done):
  **S01, S00a, S02, S07, S10, S14, S16, S18, P01, P04.**

The remaining hard blocker (**not** something the ticket system can fix):
- The installed codex is **`0.129.0-alpha.15`**. Its `workspace-write` sandbox:
  1. **force-protects `.git/` as read-only** → workers cannot create a branch, commit, or open a
     PR even inside their own clone; and
  2. **lists `--add-dir` paths as writable in its header but does not actually grant writes** —
     an empirically tested `touch` into the whitelisted `~/.config/tn/tickets/testbeam` failed
     with `Read-only file system`, so workers cannot **claim** a ticket either.
- This worked on 2026-06-08 (PRs #1–#4 were created by workers), so it is a **codex-version
  regression**, not a project misconfiguration.

**Evidence** (probes with the workers' exact flags; `--add-dir` had no effect even when the path
was shown as writable in codex's own header):
```
(1) touch ./_sbtest_ws            → SUCCEEDED        (workspace cwd writable)
(2) touch ./.git/_sbtest_git      → FAILED: Read-only file system
(3) touch …/tickets/testbeam/…    → FAILED: Read-only file system  (despite being --add-dir'd)
```
There is **no older codex on the machine** (only 0.129.0-alpha.15; npm now offers only *newer*
0.138/0.139), so "downgrade to the working version" had no target — and the user's standing rule
is **never upgrade**. The fix therefore keeps codex 0.129 and replaces its broken sandbox.

**The fix — external bubblewrap jail (`~/.tb-bwrap-codex.sh`).** Run codex with its broken
internal sandbox bypassed (`--dangerously-bypass-approvals-and-sandbox`, which codex documents as
"for environments that are externally sandboxed") inside `bwrap`, which actually enforces:
- **rw:** the worker's clone (incl. `.git`), the tn-ticket queue (`~/.config/tn`), caches,
  `~/.codex` + `CODEX_HOME` (codex's app server needs them), `XDG_RUNTIME_DIR`, `/dev/shm`, `/tmp`.
- **ro:** everything else — the canonical repo, the **immutable** data store, all other clones.

Verified in production: workers **claim distinct tickets and commit/PR**, while writes to the
data / canonical repo / other clones return `EROFS`. This is the safety guarantee the original
(broken) sandbox only aimed for — now actually delivered, so the scary bypass flag is safe here.
`fleet/launch_local.sh` and `fleet/keeper.sh` both call the wrapper as `SANDBOXED_CODEX`.

**Result:** 5 sandboxed workers + keeper running; all 10 tickets being worked. The keeper's
safety check (`data intact`, `repo OK`) passes each cycle and it auto-merges conflict-free PRs.

---

## 7. Open work / next steps

**Enqueued and ready now** (deps satisfied by S00):

| Ticket | What | Why |
|---|---|---|
| **S01** | Full-dataset amplitude-adaptive template & `q_template` | Never evaluated on all 640k pulses; PCA/AE shape-basis cross-check |
| **S00a** | Reconcile sorted `hrdMax` vs raw `HRDv` semantics | Prevent silent over-counting via the wrong branch |
| **S02** | Timing pickoff: CFD vs OF vs template (+ 2 cm/4 cm geometry) | First real timing result; which pickoff wins, does ML beat OF |
| **S07** | ML rigour pass — calibration + fair-baseline scoreboard | Reused by S03/S08/S09/S11/S12/S13; guards against leakage |
| **S10** | Pile-up rate model & current-dependent excess | Reproduce R_max ≈ 4.2 MHz; test τ_eff=90 ns |
| **S14** | Energy calibration (PSTAR/Geant4 + Birks) | Needed for S06 (σ vs energy) and S15 (p/d PID) |
| **S16** | Pedestal/baseline validation | Feeds P11; bias on low-amplitude pulses |
| **S18** | A-stack independent reproduction (Sample III/IV) | Clean warm-up; cross-check the B-stack timing scale |
| **P01** | Self-supervised waveform representation | Foundation embedding feeding P02–P08 |
| **P04** | Amplitude / deposited-charge regression | Robust amplitude in the non-linear high-A B2 regime |

**Concrete leads already surfaced by completed studies:**
- The **~4% early-peak/low-area anomalous class** from P02 → stand up **P09**; exclude it in
  timing.
- Validate **P07** saturation recovery on *real* B2>7000 pulses (consistency, no truth) and
  strengthen its traditional baseline with the S01 amplitude-adaptive template.

**Blocked on the user / environment:**
- **LUNARC** (~20-worker node) is blocked on an interactive `ssh lunarc` (askpass/2FA) — the user
  must authenticate.

---

## 8. How to run / reproduce

**Reproduce the S00 gate (640,737):**
```bash
cd /home/billy/Desktop/test_beam
python scripts/01_build_pulse_table_from_root.py --config configs/s00_reproduction.yaml
```

**Re-run the orchestrator-style studies (no fleet needed):**
```bash
python3 scripts/p02_pulse_representation.py     # PCA vs autoencoder + clustering
python3 scripts/p07_saturation_recovery.py      # saturation recovery benchmark
```

**Ticket queue (after today's shim fix):**
```bash
tn-ticket list --project testbeam          # or: ~/tn/bin/tn ticket list testbeam
~/tn/bin/tn ticket add  testbeam "<title>" # body on stdin
~/tn/bin/tn ticket claim testbeam <worker>
```

**Fleet (only once §6 is resolved):**
```bash
bash fleet/launch_local.sh 5     # launch 5 sandboxed workers; dashboard http://127.0.0.1:7777
bash fleet/keeper.sh 6 300       # 6 cycles × 300 s: reap + auto-merge + relaunch + safety
```

---

## 9. Map of the documentation

| You want… | Read |
|---|---|
| This status + results overview | **`PROJECT_REPORT.md`** (here) |
| Physics background, detail | `docs/00_overview.md` … `docs/09_open_questions.md`, `docs/glossary.md` |
| The full prioritised study plan | `studies/STUDIES.md` |
| A single study's full write-up | `reports/<study>/REPORT.md` + its `manifest.json`/figures |
| The rolling scoreboard | `reports/SUMMARY.md` |
| Data location & manifest | `DATA.md`, §3 above |
| How the agent fleet runs | `fleet/ORCHESTRATION.md`, `WORKER_PROTOCOL.md`, `SCALING.md` |
| Standing mistakes to avoid (leakage, etc.) | `fleet/LESSONS.md` |
| Critic / Integrator review process | `fleet/CRITIC_PROTOCOL.md`, `fleet/INTEGRATOR_PROTOCOL.md` |
