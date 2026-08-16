# ARU — HRD width/provenance CI-base refresh

During PR #1154 validation, `main` advanced to `f8da281e62bea9cf562314e953af5c0a93ec4bac` through merged PR #1153 (`fix(git): enforce gitlink-submodule integrity contract (#1152)`).

The earlier #1154 CI run was created against the prior main and is therefore not reused as merge authority. This handoff-only commit intentionally triggers a fresh pull-request merge-ref run against the current base.

The selected scientific/provenance atom is unchanged:

- #952 is reopened because #1146 closes the aggregate reshape corruption mechanism but not the full width-contract acceptance criteria;
- #993 remains open because 8×16↔8×18 byte/sample lineage is unproven;
- PR #1154 fixes the exact three-digest/33-count serialization defect, adds complete/missing-run provenance state and tests, and corrects report-local authority wording to match the canonical GATED CL-001 state;
- no raw ROOT artifact is regenerated in this runtime and no detector-performance number is changed.

Fresh exact-head/current-base CI is required before merge.