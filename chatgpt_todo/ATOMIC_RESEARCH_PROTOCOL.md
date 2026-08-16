# Atomic research protocol for ccb-testbeam

Status: active research protocol. This document is a handoff contract for AI sessions; it is not a physics result.

## Mandatory Atomic Research Universe standard

Every AI session that picks up a scientific/audit issue **must** use `chatgpt_todo/ATOMIC_RESEARCH_UNIVERSE_STANDARD.md` as the detailed execution standard. The short form is:

> Every atomic step becomes its own research universe. Recursively learn the mathematical descriptions and microscopic mechanisms for that step, collapse equivalent descriptions, eliminate impossible combinations, design discriminating experiments for the survivors, execute/falsify what is possible, and only then assemble globally compatible micro→meso→event→study→claim mechanics.

This is not optional issue-writing style. It is the required research method. A code fix is incomplete until the atom's competing mechanisms, equations/invariants, negative controls, uncertainty/provenance and cross-atom compatibility have been considered. A parent issue is incomplete while material child assumptions remain untested.

Before opening a new child issue, search existing open/closed issues and PRs, collapse equivalent formulations, and use one canonical leaf. Accidental duplicates must be closed/cross-linked rather than implemented twice.

## Goal

Review the project recursively at the smallest scientifically meaningful unit. A unit may be a byte-level data contract, one waveform transformation, one event-key rule, one estimator, one plot definition, one Geant4 material/property, one public claim, or one literature-dependent assumption. Do not close a parent topic merely because one implementation passes.

## Four role-separated passes

Every atomic task receives four explicit review passes. They are review lenses executed by AI sessions, not independent human collaborators.

1. **Domain/physics lead** — state the physical measurand, detector contract, and minimum model needed to answer the question.
2. **Adversarial reviewer** — construct counterexamples and alternative mechanisms that could reproduce the observed result without the preferred interpretation.
3. **Validation/statistics reviewer** — define independent data splits, weights, uncertainty, negative controls, synthetic corruption tests, and executable fail-closed acceptance criteria.
4. **Claims/provenance reviewer** — map every affected README/WIKI/report/claim-ledger/figure statement to immutable inputs, code commit, configuration, and evidence class.

For each pass record: evidence inspected, strongest counter-hypothesis, falsifier attempted, residual uncertainty, and vote (`ACCEPT`, `REVISE`, `BLOCK`, `REJECT`). `ACCEPT` requires all blocking criteria to pass; prose consensus cannot waive missing data or failed controls.

## Nature-skills workflow and limits

The requested public skill collection is `Yuan1z0825/nature-skills`. Its current `nature-reviewer` and `nature-academic-search` instructions are used as methodological constraints in this project when the corresponding reusable skill folders are not mounted natively in the active ChatGPT runtime.

### `nature-reviewer` rules adopted here

The public skill requires source-grounded assessment of originality, scientific importance, interdisciplinary readership, technical soundness, and readability, with stable concern IDs, `claim_pointer`, `evidence_pointer`, Major/Minor severity, and a blocking flag. It also requires individual reviewer reports to be generated in genuinely isolated contexts before synthesis.

This runtime does **not** expose isolated subagents for the present project audit. Therefore:

- never call the four review lenses mutually blind or independent peer reviewers;
- never invent reviewer identities, biographies, institutions, specialties, or editorial decisions;
- use the four role-separated passes as adversarial coverage lenses in one shared context;
- preserve disagreements and negative findings instead of rewriting passes to manufacture consensus;
- if a future runtime can provide genuinely isolated invocations, freeze those reports before cross-review synthesis as the public `nature-reviewer` skill requires.

### `nature-academic-search` rules adopted here

Use the public skill's source-routing logic rather than one-engine convenience search. For this physics/instrumentation project:

1. start with primary/authoritative sources: original peer-reviewed detector papers, DOI records/CrossRef, arXiv for physics preprints when appropriate, manufacturer documentation for device specifications, Geant4/NIST/PDG/CODATA for authoritative reference data;
2. use secondary discovery sources only to find the primary source, not as the final basis for a quantitative detector parameter when a primary source exists;
3. broaden queries and sources when a search returns nothing;
4. deduplicate by DOI/title/authors/year and verify identifiers before adding a reference to the project evidence map;
5. record source failures/rate limits rather than silently substituting memory;
6. distinguish peer-reviewed measurements, preprints, manufacturer representative values, collaboration/CAD records, and fitted CCB parameters in the detector-property ledger.

For MC, literature values are priors/comparison points. They do not establish the exact CCB hardware value unless the material/device/configuration is demonstrably the same. Unverified transfer values become nuisance/systematic ranges or `UNKNOWN_EXTERNAL`, not detector truth.

### `nature-skills` provenance

Project handoff documents should cite the public repository and exact skill path/commit when a review package materially relies on a rule from it. Do not vendor only `SKILL.md` while claiming the full skill was installed: the upstream installation guide notes that skills can depend on supporting `references/`, `static/`, scripts, and README context.

## Atomic evidence states

- `CONFIRMED_BUG`: exact code/data/report evidence demonstrates an error.
- `CONFIRMED_GAP`: required evidence is absent and a claim depends on it.
- `CANDIDATE`: plausible issue requiring exact execution or immutable inputs.
- `NEGATIVE_RESULT`: a hypothesis was tested and failed; preserve it to prevent repetition.
- `VALIDATED_METHOD`: method passed positive and adversarial controls on immutable inputs, but may still be non-authorising for detector performance.
- `VALIDATED_CLAIM`: source-bound claim with correct measurand, uncertainty, provenance, and independent closure.

Never promote `CANDIDATE` to a defect without evidence, and never promote method closure to detector-performance validation.

## Required issue body

Each GitHub issue should contain:

- stable audit ID and severity;
- atomic-universe contract card (input, transform/mechanism, output/measurand, units/truth type, parent/children);
- exact source pointers (commit/path/line or report/page/table);
- physical/software contract that is violated or missing;
- why the issue can bias physics conclusions;
- competing mechanism/hypothesis ledger and any equivalence classes collapsed;
- equation/invariant ledger with assumptions and limiting cases;
- hypotheses eliminated, with explicit evidence/reason;
- surviving hypotheses and unresolved nuisance/dependency variables;
- discriminating experiment matrix for separating the survivors;
- four expert-pass questions;
- smallest implementation unit;
- positive control and at least one adversarial negative control;
- deterministic acceptance **and rejection** criteria and non-zero failure status;
- required immutable inputs and SHA-256/provenance fields;
- weight/uncertainty/resampling treatment where applicable;
- cross-atom compatibility consequences;
- affected claims/plots/wiki text;
- dependencies, newly spawned child atoms, and next issue to unlock.

Prefer one issue per independently testable failure. Cross-link to broader supervisor issues rather than duplicating them.

## Data-first release gates

No timing, PID, light-collection, pile-up, or data/MC performance claim may be authorised until all applicable gates pass:

1. exact raw event schema and per-event waveform length;
2. canonical event key and complete key-set closure;
3. exact raw-to-sorted ADC-word closure or a documented irreversible transform with validation;
4. readout-channel-to-physical-stave mapping;
5. measured per-channel polarity;
6. final-channel survival and malformed-record quarantine;
7. immutable run ledger and calibration/analysis split;
8. identical reconstruction definition for data and digitised MC;
9. MC event-weight and effective-sample-size audit;
10. held-out validation plus systematic/nuisance scans.

## Recursive iteration rule

After resolving an issue, recurse into its assumptions. Ask:

- What data contract did the fix assume?
- What hidden transformation remains?
- What physical parameter entered without CCB-specific evidence?
- What statistical independence/weighting assumption entered the estimator?
- What uncertainty did the fix introduce or fail to propagate?
- What alternative mechanism remains observationally equivalent?
- What negative control could still falsify the result?
- Which public claim, figure, table, wiki paragraph, config, notebook, or cached artifact is now stale?
- Does the new method pass on deliberately corrupted inputs and fail when it should?
- Is the locally validated atom compatible with its parent and child atoms, or can compensating errors make the assembled chain look correct?

Create child issues only when they are independently actionable. Preserve negative results and superseded hypotheses so later AI sessions do not repeatedly rediscover them.

The review is complete only when all remaining leaves are either validated, explicitly blocked with an external dependency, or documented negative results with no untested material alternative under the stated scope, **and** the required micro→meso→event→study→claim interfaces have explicit compatibility closure.

## Review-status taxonomy contract (#990)

AI sessions must use `docs/contracts/REVIEW_STATUS_TAXONOMY.json` when emitting chapter/report badges.

Allowed levels only:

- `EDITORIAL_REVIEWED`
- `METHOD_REVIEWED`
- `SOURCE_VERIFIED`
- `EXECUTED_REPRODUCED`
- `CLAIM_AUTHORIZED`

Unqualified badges such as `ACCEPTED by nature-reviewer (3/3)` are forbidden. A chapter with open blocking claim IDs must not display `CLAIM_AUTHORIZED`. Nature-reviewer-style roles emit stable concern IDs and unresolved objections; they never silently promote claim status. Unless genuinely independent human/blinded reviewers are documented, badges must disclose AI role-separated review.

