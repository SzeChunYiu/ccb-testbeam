"""Tests for the #1317 setup/stave/channel-map figure producer.

Contract under test:
- every scientific annotation is traceable to the hardware BOM;
- geometry is converted to a common unit before drawing;
- the stave cross-section is dimensionally faithful;
- unresolved mapping is never silently chosen;
- provenance remains machine-readable rather than being rendered as figure clutter;
- outputs land as PDF + SVG + PNG with an annotation audit.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import issue_1317_setup_figures as producer  # noqa: E402

BOM_PATH = REPO_ROOT / "publication" / "tables" / "hardware_bom.csv"


@pytest.fixture(scope="module")
def bom():
    return producer.load_bom(str(BOM_PATH))


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    out = tmp_path_factory.mktemp("figs1317")
    bom_rows = producer.load_bom(str(BOM_PATH))
    manifest = {"figures": {}, "bom_rows": bom_rows}
    for name, fn in producer.FIGURES.items():
        rec = producer.Recorder(bom_rows)
        fn(bom_rows, rec, str(out / name))
        manifest["figures"][name] = rec.used
    return out, manifest


def test_bom_loads_with_expected_surfaces(bom):
    assert BOM_PATH.exists()
    for comp in ("stave_length", "B_channel_to_G4_layer_map",
                 "Sample_I_trigger_definition", "beam_test_optical_readout"):
        assert comp in bom, comp
    for row in bom.values():
        assert row.status in producer.STATUS_TAG, (row.component, row.status)


def test_all_figures_render_all_formats(bundle):
    out, _ = bundle
    for name in producer.FIGURES:
        for ext in (".pdf", ".svg", ".png"):
            f = out / (name + ext)
            assert f.exists(), f
            assert f.stat().st_size > 0, f


def test_every_annotation_is_bom_traceable(bundle):
    _, manifest = bundle
    bom_rows = manifest["bom_rows"]
    for name, annotations in manifest["figures"].items():
        assert annotations, f"{name} recorded no annotations"
        for comp, row in annotations.items():
            assert comp in bom_rows, f"{name}: {comp} not in BOM"
            assert row["value"] == bom_rows[comp].value
            assert row["status"] == bom_rows[comp].status
            assert row["evidence_path"] == bom_rows[comp].evidence_path


def test_required_components_covered(bundle):
    _, manifest = bundle
    for name, required in producer.REQUIRED_COMPONENTS.items():
        drawn = set(manifest["figures"][name])
        missing = required - drawn
        assert not missing, f"{name} missing required annotations: {missing}"


def test_length_units_are_converted_before_drawing(bom):
    # This is the historical figure bug: 2.0 mm and 1.8 mm were previously
    # plotted numerically as 2.0 cm and 1.8 cm.
    assert producer._to_cm(bom["fibre_hole_diameter"]) == pytest.approx(0.20)
    assert producer._to_cm(bom["WLS_fibre_outer_diameter"]) == pytest.approx(0.18)
    assert producer._to_cm(bom["stave_width"]) == pytest.approx(5.18)
    assert producer._to_cm(bom["stave_thickness_along_particle_path"]) == pytest.approx(2.0)


def test_stave_dimension_hierarchy_is_physical(bom):
    fibre = producer._to_cm(bom["WLS_fibre_outer_diameter"])
    hole = producer._to_cm(bom["fibre_hole_diameter"])
    thick = producer._to_cm(bom["stave_thickness_along_particle_path"])
    width = producer._to_cm(bom["stave_width"])
    length = producer._to_cm(bom["stave_length"])
    assert 0 < fibre < hole < thick < width < length


def test_visible_status_tags_removed_from_publication_artwork(bom):
    rec = producer.Recorder(bom)
    assert rec.tag("stave_length") == ""
    assert "stave_length" in rec.used
    src = inspect.getsource(producer.fig_stave)
    assert "STATUS_LEGEND" not in src


def test_parity_caveat_not_silently_dropped():
    src = inspect.getsource(producer.fig_channel_map)
    assert "PARITY_CAVEAT" in src
    assert "#869" in producer.PARITY_CAVEAT


def test_channel_map_uses_documented_contract(bom):
    pairs = [p.split("->") for p in
             bom["B_channel_to_G4_layer_map"].value.split(",")]
    assert len(pairs) == 4, pairs
    layers = sorted(int(lay) for _, lay in pairs)
    assert layers == [0, 2, 4, 6], layers


def test_main_writes_audit_bundle(tmp_path, monkeypatch):
    out = tmp_path / "bundle"
    monkeypatch.chdir(REPO_ROOT)
    rc = producer.main([
        "--bom", str(BOM_PATH), "--output-dir", str(out)])
    assert rc == 0
    audit = json.loads((out / "annotations.json").read_text())
    assert audit["schema"] == "ccb-paper-1317-setup-figures/2"
    assert audit["rendering"]["visible_provenance_tags"] is False
    assert audit["rendering"]["drawing_length_unit"] == "cm"
    assert set(audit["figures"]) == set(producer.FIGURES)
    table = (out / "source_table.csv").read_text().splitlines()
    assert table[0].startswith("component,quantity,value,unit,status")
    comps = [ln.split(",")[0] for ln in table[1:]]
    assert len(comps) == len(set(comps))
    assert set(comps) == {c for f in audit["figures"].values()
                          for c in f["annotations"]}
