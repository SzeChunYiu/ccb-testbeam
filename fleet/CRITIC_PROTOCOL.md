# Scientific Critic protocol

An adversarial review role, borrowed from the Stanford Virtual Lab ("Scientific Critic") and
Google's AI co-scientist ("Reflection" agent). **No study is accepted into the scoreboard
without a passing Critic review.** The Critic does **not** redo the study — it tries to break it.

## Who
A **different** worker/model than the one that did the study (never self-grade — LLM judges have
10–30% position/own-work bias). Launch a critic pane with the critic prompt, or assign an open
`critic:` ticket.

## Input
A closed study PR + its `reports/S<NN>_*/REPORT.md` + `manifest.json`.

## The Critic does
1. **Re-run the manifest** — does the headline number actually reproduce? If not → `reject`.
2. **Attack each section against this checklist:**
   - Reproduction: does it match the report value within the stated tolerance?
   - Traditional method: strong baseline or strawman? uncertainties + χ²/ndf present?
   - ML method: split by run? any label-defining feature leaking? calibrated? CIs on small
     classes?
   - Benchmark: same data, same metric, fair?
   - **Falsification:** was the metric pre-registered (predates the result)? correction for N
     tries? Could the effect be a fluctuation?
   - **Threats to validity:** are leakage / metric-misuse / post-hoc-selection genuinely ruled
     out, or just asserted?
   - Physics sanity: does the number make sense vs the detector (sampling, geometry, known
     scales)?
3. **Verdict** (post as a PR comment, label the ticket):
   - `critic:accept` — sound; orchestrator may merge and score it.
   - `critic:revise` — list the specific fixes; bounce back to a worker.
   - `critic:reject` — fundamental flaw (non-reproducing, leakage, p-hacked); explain.
4. **Feed the meta-review:** if the flaw is a *recurring* pattern, add one line to
   [LESSONS.md](LESSONS.md).

## Rules
- Default to skeptical. "Looks plausible" is not acceptance — find the test that would break it.
- Be specific: cite the file/line/number, name the exact failure mode.
- One critic verdict per study; if `revise`, re-review after the fix.
