# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-002`
- **Stamp:** `2026-07-26T073041Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `67e019d5359d76cc82fa0634a8ae2161dd2a464c`
- **Validated implementation/evidence through:** `bed2267f0eaa7c1699bf6708ffd2f8a956250811`
- **Remote main after validated delivery:** `bed2267f0eaa7c1699bf6708ffd2f8a956250811`
- **Destination:** direct sequential commits to `main`; no task branch, PR merge, force-push, or history rewrite.
- **Focused acceptance:** figure-registry remediation `VALIDATED / COMPLETE`.
- **Repository acceptance:** cumulative paper-figure scientific review remains `PARTIAL`.

## Work completed

The prior `AUD-FIG-001` audit established that the shipped registry could not satisfy its own validator. This unit remediated the production registry and builder under policy:

`FIGURE_REGISTRY_STATUS_MUST_MAP_EXPLICITLY_TO_BUILD_DISPOSITION`

The controlled vocabulary now contains eleven statuses and three kinds. Scientific state is mapped explicitly to build behavior:

- `VALIDATED`, `TENSION` -> `BUILD`;
- `PRELIMINARY` -> `CONDITIONAL`;
- `EXTERNAL_BLOCKER` -> `BLOCKED`;
- `ILLUSTRATIVE` -> `ILLUSTRATIVE`;
- `SIMULATION_RESULT`, `MC_METHOD_CLOSURE`, `PARTIAL`, `GATED`, `BLOCKED`, and `SUPERSEDED` -> `QUARANTINED`.

This prevents a file's existence from silently authorizing a blocked, gated, partial, superseded, or MC-only scientific state.

## Code and result traceability

Updated production code:

- `tools/figure_registry/registry.py`
  - supports `quantitative`, `figure_sourced`, and `illustrative`;
  - records the full controlled status vocabulary;
  - applies path requirements conditionally by kind and scientific disposition;
  - exposes `Entry.disposition` and source-artifact semantics.
- `tools/figure_registry/builder.py`
  - records scientific and runtime disposition separately;
  - does not open numerical files for `BLOCKED` or `QUARANTINED` states;
  - requires finite central values and uncertainty only for build-authorized quantitative entries;
  - supports slash-delimited nested result keys;
  - copies source-only and illustrative artifacts into separate locations with SHA-256 and byte-count provenance;
  - preserves source-table SHA-256 checks;
  - publishes `build_report.json` atomically;
  - reports `PASS`, `FAIL`, `BLOCKED`, and `QUARANTINED` separately.
- `tools/figure_registry/__init__.py`
  - exports `STATUS_DISPOSITIONS`.
- `tests/test_figure_registry.py`
  - replaces the temporary governance-only relaxation from commit `67e019d...` with exact disposition-aware regressions and exact shipped-registry structural validation.

Pre-change blobs:

- registry: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`;
- builder: `de0a84ca4bde2c66f2482f1ff8ce2ffbdcbe95d2`;
- public exports: `3b918efcc9a7f9263cfc707eddeadfc64eaf5440`;
- tests: `60d6368e27a51ac6630b46d4a2333c55e961c3f9`;
- shipped registry: `5d03f284fd2e018fcda786313f46c64ea7a20105`.

Committed remediation blobs:

- registry: `b1381ccc471eb4711251cb2d0471950f60610c68`;
- builder: `ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`;
- public exports: `5ae7cb1d3549216b510552b2d97a63450e9ce7dc`;
- tests: `1d0037ae33be3d6f56728682209dd41aa791c35e`;
- evidence renderer: `a51193ed438ba20ac3c1aba9b64de6b0407ffc2a`.

## Validation

Executed:

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tools/figure_registry/builder.py \
  tools/figure_registry/__init__.py \
  tests/test_figure_registry.py \
  tools/audit/render_figure_registry_schema_remediation_evidence.py

pytest -q tests/test_figure_registry.py

...........                                                              [100%]
11 passed in 0.52s
```

Also passed:

- validation JSON parse;
- SVG XML parse;
- maximum changed Python line length 97 characters;
- all 19 shipped entry IDs and all structural fields consumed by `validate_registry` represented in the connector-inspected structural fixture;
- build-authorized quantitative, source-only, illustrative, preliminary, external-blocker, quarantined, invalid-status/kind, duplicate-ID, uncertainty, finite-value, and source-hash cases.

Environment:

- Python `3.13.5`;
- PyYAML `6.0.3`;
- pandas `2.2.3`;
- matplotlib `3.10.8`;
- Linux `6.12.13-x86_64`.

The execution container could not resolve `github.com`. The local shipped-registry fixture is therefore labelled `CONNECTOR_INSPECTED_STRUCTURAL_FIELD_COPY`, not a byte-identical checkout. The exact shipped-file regression is committed for execution in a complete repository checkout.

## Evidence

- `docs/validation/figure_registry_schema_remediation_validation.json`
- `docs/validation/figure_registry_schema_remediation.svg`
- `docs/validation/figure_registry_schema_remediation_audit.md`
- `tools/audit/render_figure_registry_schema_remediation_evidence.py`
- `chatgpt_todo/archive/2026-07-26T073041Z_AUD-FIG-002_SCHEMA_REMEDIATION.md`

## Direct-main commit sequence

- `6b5b8d4d8262a9b0021b91908867cda96ccbd6dc` — `fix(figures): align registry schema with scientific states`;
- `413c7d931fde80b65d587803dfab9181b8d5b507` — `fix(figures): map scientific states to build dispositions`;
- `bd7f41d9ed4e0d6b26fc4ddc500c9f68e79ec15d` — `fix(figures): export disposition contract`;
- `bd46218b36c1169bacdd904844edab7385693f40` — `test(figures): cover disposition-aware registry builder`;
- `d9b0637e734edf4ee5f7d00ced94adc114a18adb` — `docs(validation): add figure-registry remediation renderer`;
- `4e1657d102da9c7308bd0965baf2262c3c41dd46` — `docs(validation): record figure-registry remediation`;
- `95c4af313e33f2f190a3878ffdaffe22ab067fda` — `docs(validation): add figure-registry remediation visual`;
- `ce9a647f93126aeb55545627ce98c86da16f9c8c` — `docs(validation): document figure-registry remediation`;
- `1433af6ad11d348bdc79a637cf715dad9d2a09a2` — `docs(audit): complete figure-registry remediation task`;
- `bed2267f0eaa7c1699bf6708ffd2f8a956250811` — `docs(audit): archive figure-registry remediation`.

GitHub returned a successful commit SHA for each direct-main contents write. Post-write history showed the sequence consecutively on remote `main`. There was no terminal-style `git push` output because delivery used authenticated GitHub contents writes; no force update was used.

## Scientific boundary

This is software-governance and artifact-provenance validation. No paper figure was regenerated from production inputs. No figure value, uncertainty, calibration, PID metric, timing resolution, stopping profile, pile-up rate, simulation-to-data transfer, or detector-performance claim was validated or changed.

## Unrun checks and unresolved risks

- repository-wide pytest and ruff were not run in this isolated environment;
- no GitHub Actions result was attached to the delivered commits at handoff time;
- no production paper build was executed;
- scientific authorization and content-addressed provenance of every individual registry entry remain separate review tasks;
- source-artifact copying intentionally preserves bytes but does not validate the artifact's scientific content.

## Next exact unit

Run the exact shipped registry and builder in a complete checkout, inspect repository-wide CI, then audit each `BUILD` entry's source value, uncertainty, result hash, source artifact, and paper-caption semantics before regenerating publication artifacts.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but not replaced. The connector exposes whole-file replacement while complete append-only contents are returned through paged or truncated views; a partial reconstruction could erase unrelated or concurrent provenance. The immutable archive contains the complete append-equivalent record. This mandatory synchronization gap remains explicit and is not reported as completed.
