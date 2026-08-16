"""GEOMETRY_DIGEST_V2 provenance contract (#986)."""
from __future__ import annotations

from ccb_mc_validation.geometry.provenance_hashes import digests_for_nominal
from ccb_mc_validation.provenance.geometry_digest import (
    canonical_payload,
    default_single_stave_fields,
    geometry_digest_hex,
)


def test_digest_stable_and_named():
    fields = default_single_stave_fields()
    payload = canonical_payload(fields)
    assert payload.startswith("schema_version=2.0.0;")
    assert "coating_thk_mm=" in payload
    assert "sensor_thk_mm=" in payload
    assert "far_end_mode=instrumented" in payload
    assert "birks" not in payload
    h1 = geometry_digest_hex(fields)
    h2 = geometry_digest_hex(fields)
    assert h1 == h2
    assert len(h1) == 64


def test_nominal_digest_matches_provenance_hashes_mirror():
    fields = default_single_stave_fields()
    mirror = digests_for_nominal()
    assert geometry_digest_hex(fields) == mirror["geometry_hash"]
    assert canonical_payload(fields) == mirror["geometry_canonical"]


def test_nominal_golden_hash_locks_cpp_constants():
    # Locks DetectorConstruction constexprs against silent drift (#986).
    expected = "e323b92195f9a6288944f0738dbadccf9386422f076362ca172fd0b6d119d1e1"
    assert geometry_digest_hex(default_single_stave_fields()) == expected


def test_far_end_mode_changes_digest():
    a = geometry_digest_hex(default_single_stave_fields(far_end_mode="instrumented"))
    b = geometry_digest_hex(default_single_stave_fields(far_end_mode="open"))
    assert a != b


def test_missing_field_fails_closed():
    fields = default_single_stave_fields()
    del fields["coating_thk_mm"]
    try:
        canonical_payload(fields)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "coating_thk_mm" in str(exc)
