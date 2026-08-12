# ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001 — adversarial correction

This addendum preserves a material flaw found after the initial derivation archive rather than rewriting that pre-review record.

## Stable concern: CCB-977-CAMPAIGN-MANIFEST-SOURCE-LABEL-001

The first implementation required the manifest fields

- `expected_core.path = geant4/single_stave/sipm`,
- `expected_core.source = SUPERPROJECT_GITLINK:geant4/single_stave/sipm`, and
- `expected_core.authorising_source = true`,

but `verify` only checked those strings structurally. A hand-authored canonical manifest could therefore name an arbitrary 40-hex core revision while retaining the correct source-label string. A matching SHA-256 would freeze the forged bytes but would not prove the claimed relation

`H_expected(I) = H_link(I)`.

The adversarial reviewer therefore voted **REVISE** on the first implementation.

## Corrected invariant

The verifier now resolves the manifest's exact recorded `superproject_commit` in the Git object database and executes the semantic relation

`git ls-tree <superproject_commit> geant4/single_stave/sipm`.

The returned entry must be a gitlink (`mode 160000`, object type `commit`), and its exact object SHA must equal `expected_core.commit`. Thus a source-label assertion is no longer sufficient; the recorded Git object is the evidence.

At campaign creation, `superproject_commit` and `expected_core.commit` are both derived from current `HEAD`. At every orchestrator/job/analyzer verification, `--repo-root` is mandatory and the declared relationship is checked against the recorded superproject commit even if the current checkout later advances.

## New discriminating control

A deterministic test creates a temporary Git repository, commits a gitlink whose object identity is `3333333333333333333333333333333333333333`, constructs an otherwise canonical manifest that claims expected core `ffffffffffffffffffffffffffffffffffffffff` with the correct source label, and requires `verify_source_binding()` to reject with `manifest expected core ... != gitlink ...`.

The focused suite after this correction returned:

`8 passed in 0.06s`

`python -m py_compile scripts/single_stave/sipm_campaign_manifest.py` and `bash -n` for both shell launchers also remained clean in the local fixture. Ruff remains unavailable locally; protected exact-final-head CI is still mandatory.

## Residual uncertainty

This semantic Git-object check binds **campaign source intent**. It still does not prove the `ccb_stave_sim` binary in `CCB_CAMPASSIGN_BUILD` was built from the manifest's `superproject_commit`; that remains `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001` / `ARU-SIPM-CAMPAIGN-SUPERPROJECT-BUILD-CLOSURE-001`. The job also invokes the verifier helper from the shared checkout; binding launcher/verifier bytes and the full executable/toolchain remains part of that build-manifest family.

No detector physics result or historical sidecar authenticity is established by this correction.