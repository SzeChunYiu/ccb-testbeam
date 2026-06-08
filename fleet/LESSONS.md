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

## Project-specific (append as the fleet learns)
- _(none yet — Critics add entries here)_
