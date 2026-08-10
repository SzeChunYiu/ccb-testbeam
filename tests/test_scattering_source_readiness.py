from __future__ import annotations

from pathlib import Path

from tools.audit.research_scattering_source_readiness import (
    audit_source,
    audit_source_text,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "geant4/src_patch/ScatteringGenerator.cc"


def test_current_repository_source_exhibits_pre_fix_readiness_blockers() -> None:
    """Freeze the exact pre-fix mechanisms so #1182 cannot disappear silently."""

    result = audit_source(SOURCE)
    findings = result["findings"]

    assert findings["event_zero_load_gate"] is True
    assert findings["uniform_fallback_on_empty_cdf"] is True
    assert findings["success_exit_on_input_open_failure"] is True
    assert findings["unchecked_cross_section_sscanf"] is True
    assert findings["empty_stopping_table_dereference_pattern"] is True
    assert findings["explicit_instance_readiness_state"] is False
    assert result["verdict"] == "BLOCK_RUNTIME_AUTHORIZATION"
    assert result["runtime_thread_mode"] == (
        "UNRESOLVED_REQUIRES_EXACT_EXECUTABLE_PROVENANCE"
    )


def test_event_zero_gate_is_distinct_from_explicit_instance_readiness() -> None:
    source = """
    void GeneratePrimaryVertex(G4Event* event) {
        if(event->GetEventID()==0) LoadFiles();
    }
    """
    result = audit_source_text(source)
    assert result["findings"]["event_zero_load_gate"] is True
    assert result["findings"]["explicit_instance_readiness_state"] is False


def test_explicit_readiness_token_does_not_erase_other_fail_open_mechanisms() -> None:
    source = r'''
    void EnsureSourceReady();
    void LoadCrossSection() {
        if(!infile.is_open()) { exit(0); }
        sscanf(line,"%lf\t%lf\t%*f\n",&tmpA,&tmpCS);
    }
    G4double SampleThetaCM() {
        if(cdfTheta.empty() || cdfVal.empty()) { return pi * G4UniformRand(); }
    }
    '''
    result = audit_source_text(source)
    assert result["findings"]["explicit_instance_readiness_state"] is True
    assert result["findings"]["success_exit_on_input_open_failure"] is True
    assert result["findings"]["unchecked_cross_section_sscanf"] is True
    assert result["findings"]["uniform_fallback_on_empty_cdf"] is True
    assert result["verdict"] == "BLOCK_RUNTIME_AUTHORIZATION"


def test_clean_synthetic_contract_has_no_frozen_blocker_match() -> None:
    source = """
    enum class SourceState { UNINITIALIZED, UNCONFIGURED_UNIFORM, CONFIGURED_READY, FATAL };
    void EnsureSourceReady();
    """
    result = audit_source_text(source)
    assert result["findings"]["explicit_instance_readiness_state"] is True
    assert result["blockers"] == []
    assert result["verdict"] == "NO_FROZEN_BLOCKER_MATCH"
