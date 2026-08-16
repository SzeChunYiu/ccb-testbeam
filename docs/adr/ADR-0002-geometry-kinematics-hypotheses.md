# ADR-0002: Geometry and kinematics contradictions as versioned hypotheses

**Status:** accepted (infrastructure); physical closure **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave A Lane 03  
**Issues:** #987, #989, #991, #992 (related #986, #999)

## Context

Independent project surfaces disagree on beam-test-critical numbers:

| Axis | Claim A | Claim B | Issue |
|---|---|---|---|
| Stave length | Geant4 / `stave-geometry.md`: **50 cm** (`kStaveHalfX=25 cm`) | Setup docs / Chapter 2 timing: **~1 m / 100 cm** | #991 |
| Fibre count | Geant4: **two** fibres at `y=±1 cm` | Chapter 2: **singular** “a … fibre” | #987 |
| Analysed-stave spacing | Newer report / Chapter 2: **4 cm** c-c `(0,4,8,12)` | Timing note TOF table: **2 cm** step | #992 |
| Deuteron energy scale | Chapter 2 p+d elastic: **~105 MeV** KE | B-stack note: **~15.8 MeV** ‘deuteron-like’ | #989 |

These are physics-model contradictions, not documentation typos. Silently
picking one number would bake the wrong attenuation, TOF, range, and light
collection into every downstream study.

## Decision

1. **Do not resolve** the contradictions in code by choosing a preferred number.
2. Publish each side as a **named HYPOTHESIS profile** under
   `configs/geometry/` in the versioned registry
   (`registry_version: 2026.0-waveA-lane03`).
3. **Fail closed** when `geometry_profile_id` is unset
   (`ccb_mc_validation.geometry.registry.require_geometry_profile`).
4. Profiles with `status: HYPOTHESIS` have `claims_authorized: false` and must
   not authorize beam-test physics claims.
5. Promote to `APPROVED` only after hardware/CAD/build/beam-log evidence fills
   the hardware ledger fields required by the issues; bump `registry_version`
   and record the evidence digest.
6. For #989, keep an **energy-dictionary** of estimand types; forbid using the
   same phrase “deuteron-like kinetic energy” for incompatible estimands.
7. Cite NIST PSTAR only for proton quantities; deuteron range method must be
   named separately.

## Registered hypothesis profiles

| profile_id | Axis | status |
|---|---|---|
| `hyp_mc_single_stave_50cm_2fibre` | length + fibres (MC code) | HYPOTHESIS |
| `hyp_docs_stave_100cm_1fibre` | length + fibres (docs) | HYPOTHESIS |
| `hyp_bstack_spacing_4cm_newer_report` | spacing 4 cm | HYPOTHESIS |
| `hyp_bstack_spacing_2cm_timing_note` | spacing 2 cm | HYPOTHESIS |
| `hyp_deuteron_ke_105MeV_elastic_kinematics` | ~105 MeV elastic KE | HYPOTHESIS |
| `hyp_deuteron_like_15p8MeV_bstack_note` | ~15.8 MeV sample proxy | HYPOTHESIS |

## Consequences

**Positive**

- Runs and studies must declare which hypothesis they assume.
- Digests change when the selected profile changes (feeds #986).
- Reviewers can see unresolved contradictions without invented “truth”.

**Negative / remaining blockers**

- #987 / #991 / #992 / #989 physical acceptance criteria remain **BLOCKED**
  until hardware/CAD/ROOT stack-table / kinematics expert closure.
- Geant4 compile-time constants still encode the 50 cm / 2-fibre MC prototype;
  selecting the 100 cm / 1-fibre profile documents analysis intent only until
  DetectorConstruction is rebuilt from an APPROVED ledger.

## Alternatives considered

1. **Pick the Geant4 numbers as truth** — rejected; contradicts beam-test docs
   that drive timing/light-collection claims.
2. **Pick the documentation numbers as truth** — rejected; executable model and
   geometry drawings disagree; no CAD citation yet.
3. **Leave hard-coded dual values** — rejected; silent divergence is the defect.

## Follow-ups

- Populate `docs/contracts/geometry_contract.template.json` from deployed ROOT.
- Hardware ledger for fibres/length/end treatment (#987, #991).
- Physical B-stack table deriving analysed-stave centres (#992, #869).
- Relativistic kinematics + deuteron stopping study (#989).
