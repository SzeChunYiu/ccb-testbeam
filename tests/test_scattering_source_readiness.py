from __future__ import annotations

from pathlib import Path

from tools.audit.research_scattering_source_readiness import (
    audit_source,
    audit_source_text,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "geant4/src_patch/ScatteringGenerator.cc"


def test_current_repository_source_has_static_fail_closed_readiness_contract() -> None:
    """Freeze the bounded #1182 implementation while keeping runtime claims gated."""

    result = audit_source(SOURCE)
    findings = result["findings"]

    assert findings["event_zero_load_gate"] is False
    assert findings["per_event_instance_readiness_call"] is True
    assert findings["uniform_fallback_on_empty_cdf"] is False
    assert findings["uniform_sampling_is_explicit_state"] is True
    assert findings["success_exit_on_input_open_failure"] is False
    assert findings["fatal_exception_with_abort_fallback"] is True
    assert findings["unchecked_cross_section_sscanf"] is False
    assert findings["checked_numeric_row_parser"] is True
    assert findings["empty_stopping_table_dereference_pattern"] is True
    assert findings["stopping_table_cardinality_guard"] is True
    assert findings["explicit_instance_readiness_state"] is True
    assert findings["configuration_identity_guard"] is True
    assert findings["transactional_table_publication"] is True
    assert findings["configured_cdf_state_is_fatal_not_uniform"] is True
    assert result["blockers"] == []
    assert result["verdict"] == (
        "STATIC_CONTRACT_IMPLEMENTED_COMPILED_VALIDATION_REQUIRED"
    )
    assert result["runtime_thread_mode"] == (
        "UNRESOLVED_REQUIRES_EXACT_EXECUTABLE_PROVENANCE"
    )


def test_legacy_event_zero_and_fail_open_fixture_is_blocked() -> None:
    source = r'''
    void GeneratePrimaryVertex(G4Event* event) {
        if(event->GetEventID()==0) LoadFiles();
    }
    void LoadCrossSection() {
        if(!infile.is_open()) { exit(0); }
        sscanf(line,"%lf\t%lf\t%*f\n",&tmpA,&tmpCS);
    }
    G4double SampleThetaCM() {
        if(cdfTheta.empty() || cdfVal.empty()) { return pi * G4UniformRand(); }
    }
    G4double EvalELoss(G4double in) { return dEdx[0]*in/Ene[0]; }
    '''
    result = audit_source_text(source)
    assert result["findings"]["event_zero_load_gate"] is True
    assert result["findings"]["uniform_fallback_on_empty_cdf"] is True
    assert result["findings"]["success_exit_on_input_open_failure"] is True
    assert result["findings"]["unchecked_cross_section_sscanf"] is True
    assert "unguarded_empty_stopping_table_dereference" in result["blockers"]
    assert result["verdict"] == "BLOCK_RUNTIME_AUTHORIZATION"


def test_readiness_token_alone_does_not_hide_fail_open_mechanisms() -> None:
    source = r'''
    enum class SourceState { UNINITIALIZED, UNCONFIGURED_UNIFORM, CONFIGURED_READY, FATAL };
    void EnsureSourceReady();
    void GeneratePrimaryVertex(G4Event*) { EnsureSourceReady(); }
    void LoadCrossSection() {
        if(!infile.is_open()) { exit(0); }
        sscanf(line,"%lf\t%lf\t%*f\n",&tmpA,&tmpCS);
    }
    G4double SampleThetaCM() {
        if(cdfTheta.empty() || cdfVal.empty()) { return pi * G4UniformRand(); }
    }
    '''
    result = audit_source_text(source)
    # Bare declarations/calls are deliberately weaker than the production audit,
    # which requires scoped readiness states and the class-qualified generator
    # implementation. They must not hide the independently detected fail-open paths.
    assert result["findings"]["explicit_instance_readiness_state"] is False
    assert result["findings"]["per_event_instance_readiness_call"] is False
    assert result["findings"]["success_exit_on_input_open_failure"] is True
    assert result["findings"]["uniform_fallback_on_empty_cdf"] is True
    assert result["verdict"] == "BLOCK_RUNTIME_AUTHORIZATION"


def test_uniform_sampling_requires_explicit_uniform_state() -> None:
    hidden = """
    G4double SampleThetaCM() {
        if(cdfTheta.empty()) { return pi * G4UniformRand(); }
    }
    """
    explicit = """
    G4double SampleThetaCM() {
        if(fSourceState == SourceState::UNCONFIGURED_UNIFORM) {
            return pi * G4UniformRand();
        }
        FatalSourceError("CCB_CS_CDF_STATE", "bad");
    }
    """
    hidden_result = audit_source_text(hidden)
    explicit_result = audit_source_text(explicit)
    assert hidden_result["findings"]["uniform_fallback_on_empty_cdf"] is True
    assert hidden_result["findings"]["uniform_sampling_is_explicit_state"] is False
    assert explicit_result["findings"]["uniform_fallback_on_empty_cdf"] is False
    assert explicit_result["findings"]["uniform_sampling_is_explicit_state"] is True
