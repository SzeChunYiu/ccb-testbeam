# Lessons — standing guidance for every worker

Read this before starting. It is the fleet's living meta-review: recurring mistakes (from
Critic reviews and the autonomous-science literature) that you must not repeat. Critics append
new lessons here when they catch a *recurring* failure.

## Known failure modes (from the literature — avoid by construction)
- **Data leakage via event-level shuffling.** Always split **by run**, never by random pulse/
  event. Calibration constants come only from calibration runs.
- **Label leakage.** Never feed a feature that (partly) defines the label (e.g. the timing span
  that defines a "clean" label, or D_t in the App. I classifier). The notes are careful here —
  stay careful.
- **Post-hoc metric/cut selection (p-hacking).** Pre-register the metric and cuts in the ticket
  *before* looking at results. If you scan N options, correct for N.
- **Narrow-core σ masquerading as resolution.** Report robust width and **full RMS** alongside
  any core σ, plus χ²/ndf and tail fractions.
- **Strawman baselines.** The traditional method must be the *best* reasonable conventional
  approach, not a deliberately weak one, or the ML "win" is meaningless.
- **Miscalibrated probabilities.** RF/NN scores are rankings, not probabilities — add isotonic/
  logistic calibration + a reliability diagram before quoting any probability.
- **Tiny positive classes.** (e.g. the 72-event pile-up class) — bootstrap CIs; report PR not
  just ROC; do not quote a point estimate as if precise.
- **Hallucinated results / fabricated tables.** Every number must trace to a committed artifact
  via the provenance manifest. If you can't regenerate it, it doesn't go in the report.

## Safety (from the Sakana AI-Scientist self-modification incident)
- **Never edit orchestration/launcher/quota files** — not `codex-supervisor*`, not
  `.codex-supervisor.toml`, not `codex-prompts*`, not `~/.config/csup/*`, not the tn-ticket
  CLI. Adapt to limits; never raise your own.
- Do not spawn supervisors, relaunch yourself, or write unbounded checkpoints.

## Data safety (from the 2026-06-08 data-loss incident — DO NOT REPEAT)
On 2026-06-08 an unsandboxed worker deleted the entire shared checkout **including the only
local copy of the 6 GB data**. Root cause: data lived inside the agents' working tree, and
workers ran with `--dangerously-bypass-approvals-and-sandbox` (full filesystem access).
Permanent fixes now in force — every worker MUST respect them:
- **Data is read-only.** It lives OUTSIDE the repo at `/home/billy/ccb-data` (immutable,
  `chattr +i`), exposed as `./data` (a read-only symlink). **Never** write to, delete, move,
  `git clean`, or `rm` anything under `./data` or its target. Read only.
- **You are sandboxed.** Workers run `codex --sandbox workspace-write`: writes outside your own
  clone are blocked by the OS. Do not attempt to escape it.
- **Never `rm -rf`, `git clean -xfd`, or re-clone the repo at a shared path.** Work only inside
  your own clone. If something seems broken, report it — do not "reset" by deleting.
- The canonical repo and every other worker's clone are off-limits.

## Project-specific (append as the fleet learns)
- **A benchmark that looks perfect is usually leaking.** (P07) Clipping at `C=frac*A` let the ML read amplitude off `max=frac*A` (res68~0.002). Make the truth INDEPENDENT of the inputs; fixed-ceiling clipping fixed it. When ML hugely beats everything, hunt for leakage before celebrating.
