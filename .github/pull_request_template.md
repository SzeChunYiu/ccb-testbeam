## Summary

<!-- What changed and why. For scientific-universe issues, state bounded scope only. -->

## Scientific-universe close intent (#1218)

<!-- REQUIRED when this PR references a scientific-universe / ARU parent issue. -->

- [ ] This PR does **not** use `Closes` / `Fixes` / `Resolves` for scientific-universe parents with unresolved material leaves.
- [ ] Issue references use `Refs #N` and, when partial, explicit `does not close #N`.
- [ ] Pre-merge reviewer verified the **actual squash/rebase merge commit message** matches this body (see `docs/contracts/MERGE_CLOSE_RESIDUAL.md`).
- Close disposition (if closing any scientific issue): `ACCEPTANCE_COMPLETE` | `EXPLICIT_SUCCESSOR_TRANSFER` | `SUPERSEDED` | `PARTIAL_NO_CLOSE` | N/A
- Successor issue IDs (if transfer/supersede): <!-- e.g. #1182 -->

Local gate:

```bash
python tools/gov/run_close_intent_gates.py --pr-text-file <(printf '%s' "$PR_BODY")
python tools/gov/check_merge_close_keywords.py --text-file <pr-body-file>
```

Schema: `docs/contracts/CLOSE_INTENT.schema.json`. Witness fixtures: `tests/fixtures/gov/close_intent/`.

## Test plan

- [ ]
