# ADR-0004: Configurable physics list with fail-closed unset; ensemble validation BLOCKED

**Status:** accepted (fail-closed infrastructure); physics-model ensemble **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 03  
**Issues:** #1006 (related #1089, #1095, #1091, #986, #997)

## Context

`geant4/single_stave` previously hard-coded `PhysicsList::Build("QGSP_BIC", …)`
and **warning-fell back** to `QGSP_BIC` when an unsupported list was requested.
Stopping-depth / PID / material-budget claims therefore rested on an unversioned
reference list. Geant4 provides materially different applicable models (BIC vs
INCL++ vs data-driven HP options) in the 2–190 MeV p/d domain; a silent default
cannot establish model uncertainty.

## Decision

1. **Require** an explicit `--physics-list NAME` on the Geant4 executable
   (`AppConfig.physics_list`); refuse empty/unset (no silent QGSP_BIC).
2. **Fail closed** in `PhysicsList::Build` if the factory cannot provide the
   requested reference list — never warning-fallback.
3. Persist `physics_list` in `Describe()` and run-metadata JSON.
4. Publish a Python **hypothesis registry** (`configs/physics/`,
   `ccb_mc_validation.physics`) that also fails closed when
   `physics_list_profile_id` is unset; all profiles have
   `claims_authorized: false` until applicability + external validation exist.
5. **Do not** invent a preferred nominal or average inapplicable lists.
6. Full ensemble comparison (applicability matrix, cut/step policy coupling
   #1089/#1095, neutron time cut #1091, external stopping/range validation) remains
   **BLOCKED** — see Consequences.

## Registered hypothesis profiles

| profile_id | Geant4 list | status |
|---|---|---|
| `hyp_qgsp_bic_legacy_hardcoded` | QGSP_BIC | HYPOTHESIS |
| `hyp_qgsp_inclxx_candidate` | QGSP_INCLXX | HYPOTHESIS |
| `hyp_ftfp_bert_out_of_domain_control` | FTFP_BERT | HYPOTHESIS (control) |

## Consequences

**Positive**

- Production runs cannot silently change hadronic model via fallback.
- Provenance records the requested list; analysis must declare a profile id.

**BLOCKED (no invented physics numbers)**

- Applicability matrix for p/d × energy grid × C/H/coating materials.
- Cut/step/window policy must be fixed before attributing differences to
  hadronic model choice (#1089, #1095, #1090).
- External validation vs authoritative stopping/range and p/d interaction data.
- Nominal-model choice justified against held-out detector evidence.

Until those close, no stopping-depth/PID claim may treat any registered profile
as APPROVED truth.

## Alternatives considered

1. Keep hard-coded QGSP_BIC as default — rejected (#1006 silent model lock).
2. Warning-fallback to QGSP_BIC — rejected (fail-open).
3. Average BIC+INCL+++FTFP without applicability — rejected (not a systematic).
