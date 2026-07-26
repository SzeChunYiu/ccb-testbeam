# Active Task

- **Task ID:** `AUD-FIG-004`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T160640Z`
- **Initial remote main SHA:** `cd4c299dbd67e285950a69610e4b27caed4413e1`
- **Scope:** prevent duplicate YAML figure IDs or nested registry fields from silently replacing earlier scientific evidence before validation and paper-figure build decisions.
- **Policy:** `FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH`.
- **Assumptions:** registry YAML must be unambiguous; exact duplicate keys are input errors rather than last-definition-wins overrides; this unit changes software/schema integrity only.
- **Files:** `tools/figure_registry/registry.py`, package exports, focused tests, evidence renderer, validation JSON/SVG/report, and matching `chatgpt_todo/` records.
- **Commands:** Python compile; focused pytest; deterministic legacy/corrected controls; JSON and SVG parse checks; source line-length and digest checks.
- **Validation plan:** reproduce PyYAML last-key-wins behavior; require top-level and nested duplicates plus invalid UTF-8 to fail closed; verify valid registries remain accepted; bind entries/hash/size to one retained byte snapshot.
- **Progress:** implementation and validation prepared against current-main source; direct-main publication and coordination updates in progress.
- **Acceptance:** `ACTIVE`.
- **Scientific boundary:** no paper figure, central value, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance claim is regenerated or authorized.
