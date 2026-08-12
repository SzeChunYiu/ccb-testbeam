# Merge-close residual (#1218)

## Residual

GitHub's squash/rebase merge UI and default commit-message templates can inject
`Closes #N` / `Fixes #N` even when the PR body and validated close-intent
manifest say otherwise. Repository CI can validate **repository-owned bytes**
(PR body file, commit message file, close-intent JSON) but cannot
deterministically bind the final GitHub merge API message without a network
permission/event contract.

## Required controls

1. PRs that touch scientific-universe issues use `Refs` / `does not close`, never auto-close keywords.
2. `.github/pull_request_template.md` requires explicit close-intent declaration for ARU parents.
3. `tools/gov/run_close_intent_gates.py` runs the hostile fixture matrix in CI; `validate_close_intent.py` and `check_merge_close_keywords.py` gate repository-owned text.
3. Human/AI pre-merge review checks the **actual** merge commit message.
4. Post-merge reconciliation: if an issue transitions `closed/completed` contrary to validated intent, reopen and record the audit (as with #1057).

## Non-claims

Passing this governance gate does **not** validate physics, Geant4 execution,
detector response, or any DATA↔MC claim.
