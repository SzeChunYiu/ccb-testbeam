# Autonomous-science systems: review & adoption roadmap

A survey of state-of-the-art AI-driven research systems and what we adopt for this fleet.
(Compiled 2026-06-08.)

## Where our fleet already stands
Our three rules are stronger than most surveyed systems on two of the field's worst failure
modes:
- **Reproduce-first** ≈ Aviary / MLAgentBench gold-target scoring → guards against *benchmark
  selection* and *data-leakage* failures.
- **Traditional + ML head-to-head** = a mandatory baseline most systems lack → guards against
  *metric misuse* and *inappropriate-benchmark* failures.
- **Atomic decomposition** ≈ tree-search staging + fine-grained provenance.

## Gaps the literature exposes (and our response)
| Gap | Risk | Borrowed from | Our action |
|---|---|---|---|
| No adversarial **critic** | plausible-but-wrong results pass | Virtual Lab "Scientific Critic"; AI co-scientist "Reflection" | **Critic role** — [CRITIC_PROTOCOL.md](CRITIC_PROTOCOL.md); no study accepted without a passing review |
| No **falsification** gate | automated p-hacking / post-hoc metric picking | Popper (ICML'25); "Hidden Pitfalls" | **Pre-registered metric + Falsification section** in the report template |
| Weak **provenance** | hidden failures invisible in the writeup | "Hidden Pitfalls"; PROV-AGENT; MLAgentBench | **Run manifest** (input hashes, commit, commands, seeds, output hashes) required |
| No **sandbox** | agent edits its own limits (Sakana incident) | Sakana AI Scientist incident | **Self-modification guard** in the worker protocol; container quotas (roadmap) |
| No **novelty/dedup** gate | re-grinding solved questions | Sakana v1 novelty check; SciAgents | novelty check vs `reports/` + LESSONS before cutting a ticket (roadmap) |
| FIFO "next experiment" | low-value work | Robot Scientist Adam/Eve; self-driving labs | **expected-information-gain** justification for queued tickets (roadmap) |

## Top-10 adoption roadmap (prioritised)
**Do first (done / in this commit):**
1. **Scientific Critic role** — adversarial review before acceptance. *(Virtual Lab, AI co-scientist)* ✅ added
2. **Falsification gate** — pre-register metric & significance; one explicit falsification test; corrected p/e-value. *(Popper)* ✅ in template
3. **Hardened report template** — explicit Threats-to-validity (benchmark choice, leakage, metric misuse, post-hoc selection). *(Hidden Pitfalls)* ✅ in template
4. **Provenance manifest** — machine-readable run record verified on acceptance. *(PROV-AGENT/MLAgentBench)* ✅ in template
5. **Self-modification guard** — workers may not edit orchestration/launcher/quota files. *(Sakana incident)* ✅ in protocol
6. **LESSONS.md meta-review** — recurring failure patterns mined from critic reviews, injected into new workers. *(AI co-scientist Meta-review)* ✅ seeded

**Do next (when corpus grows):**
7. **Novelty/dedup gate** before ticket creation. *(Sakana v1, SciAgents)*
8. **Findings knowledge graph** (dataset↔observable↔method↔result↔open-question) driving next tickets. *(SciAgents, ResearchAgent)*
9. **Elo scoreboard** for competing methods/hypotheses → principled "what next". *(Google AI co-scientist)*
10. **Information-gain-ranked backlog** (active learning instead of FIFO). *(Robot Scientist; BayBE)*

## Key failure modes to keep in view
Hallucinated results/ablation tables; data leakage via event-level shuffling; metric misuse;
post-hoc selection bias; LLM-reviewer bias (position bias flips 10–30% of verdicts → use rubric
+ randomized order + don't self-grade); reward-hacking the reviewer or the runtime.

## Primary sources
Sakana AI Scientist arxiv.org/abs/2408.06292 (v2 /2504.08066; incident: lesswrong.com/posts/ppafWk6YCeXYr4XpH) ·
Google AI co-scientist research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/ ·
Coscientist nature.com/articles/s41586-023-06792-0 · ChemCrow nature.com/articles/s42256-024-00832-8 ·
Robot Scientist aejournal.biomedcentral.com/articles/10.1186/1759-4499-2-1 ·
Virtual Lab biorxiv.org/content/10.1101/2024.11.11.623004v1 · SciAgents arxiv.org/abs/2409.05556 ·
ResearchAgent arxiv.org/abs/2404.07738 · AutoGen arxiv.org/abs/2308.08155 · Aviary arxiv.org/abs/2412.21154 ·
Popper arxiv.org/abs/2502.09858 · Hidden Pitfalls arxiv.org/abs/2509.08713 · RE-Bench arxiv.org/abs/2411.15114 ·
MLAgentBench arxiv.org/pdf/2310.03302 · PROV-AGENT arxiv.org/pdf/2508.02866 ·
LLM-judge bias openreview.net/forum?id=3GTtZFiajM
