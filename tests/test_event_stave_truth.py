import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import mc01_event_stave_truth as producer
from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_stave import (
    EVENT_STAVE_SCHEMA_ID,
    aggregate_b_stave_edep,
    build_compare_first_b_event_edep,
    build_event_stave_product,
    fingerprinted_regular_file_stream,
    validate_event_stave_product,
)


def test_step_splitting_preserves_event_stave_energy_but_not_record_count():
    one = aggregate_b_stave_edep([0], [1], [2212], [4.0])
    split = aggregate_b_stave_edep([0, 0], [1, 1], [2212, 2212], [1.5, 2.5])
    np.testing.assert_array_equal(one.total_edep_mev, split.total_edep_mev)
    np.testing.assert_array_equal(one.charged_edep_mev, split.charged_edep_mev)
    assert one.hit_count[0] == 1
    assert split.hit_count[0] == 2


def test_all_particle_total_and_charged_diagnostic_are_separate_measurands():
    out = aggregate_b_stave_edep(
        [0, 0, 0],
        [1, 1, 2],
        [2212, 2112, 2212],
        [2.0, 3.0, 50.0],
    )
    assert out.total_edep_mev[0] == pytest.approx(5.0)
    assert out.charged_edep_mev[0] == pytest.approx(2.0)
    assert out.hit_count[0] == 2
    assert out.charged_hit_count[0] == 1
    assert out.total_edep_mev.sum() == pytest.approx(5.0)


def test_multiple_charged_records_collapse_to_one_event_stave_total():
    out = aggregate_b_stave_edep(
        [2, 2, 2],
        [1, 1, 1],
        [2212, 1000010020, 11],
        [1.0, 2.0, 0.25],
    )
    assert out.total_edep_mev[2] == pytest.approx(3.25)
    assert out.charged_edep_mev[2] == pytest.approx(3.25)
    assert out.charged_hit_count[2] == 3


@pytest.mark.parametrize(
    ("layer", "layer1", "pdg", "edep"),
    [
        ([0], [1], [2212], [-1.0]),
        ([0], [1], [2212], [np.nan]),
        ([0.5], [1], [2212], [1.0]),
        ([8], [1], [2212], [1.0]),
        ([0], [1, 1], [2212], [1.0]),
    ],
)
def test_aggregation_fails_closed_on_malformed_event(layer, layer1, pdg, edep):
    with pytest.raises(DataContractError):
        aggregate_b_stave_edep(layer, layer1, pdg, edep)


def test_primary_event_weight_cardinality_permutation_falsifier(tmp_path, monkeypatch):
    """Inject a multi-element PrimaryWeight row among valid single-element rows.

    The builder must reject the event even when other events in the same batch
    have correct cardinality-1 weights. This falsifies a naive "first entry
    passes" implementation that only checks the first event.
    """
    chunk = {
        "Sci_bar_LayerID": _obj([[0], [0]]),
        "Sci_bar_LayerID1": _obj([[1], [1]]),
        "Sci_bar_PDG": _obj([[2212], [2212]]),
        "Sci_bar_EDep": _obj([[2.0], [3.0]]),
        "Sci_bar_Time": _obj([[10.0], [10.0]]),
        "PrimaryWeight": _obj([[2.0], [1.0, 3.0]]),  # second event has 2 entries
    }

    class FakeTree:
        def iterate(self, branches, **kwargs):
            yield chunk

    class FakeRoot:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def __contains__(self, key):
            return key == "hibeam"
        def __getitem__(self, key):
            return FakeTree()

    def fake_open(stream):
        return FakeRoot()

    monkeypatch.setitem(sys.modules, "uproot", SimpleNamespace(open=fake_open))
    source = Path(tmp_path) / "mc.root"
    source.write_bytes(b"fake-root-bytes")
    with pytest.raises(DataContractError, match="scalar_event_weight mode requires"):
        build_event_stave_product(
            source, coinc_ns=15.0, generator_measure_mode="scalar_event_weight"
        )


def _valid_product():
    return dict(
        event_id=np.array(["a", "b"]),
        entry_index=np.array([3, 4]),
        sample_i=np.array([True, False]),
        sample_ii=np.array([True, True]),
        event_weight=np.array([2.0, 0.5]),
        total_edep_mev=np.array([[5.0] + [0.0] * 7, [1.0] + [0.0] * 7]),
        charged_edep_mev=np.array([[2.0] + [0.0] * 7, [1.0] + [0.0] * 7]),
        hit_count=np.array([[2] + [0] * 7, [1] + [0] * 7]),
        charged_hit_count=np.array([[1] + [0] * 7, [1] + [0] * 7]),
    )


def test_product_validator_accepts_nested_trigger_event_universe():
    validate_event_stave_product(**_valid_product())


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_id", "broken_subset", "outside_ii", "charged_gt_total"],
)
def test_product_validator_rejects_identity_topology_and_measurand_corruption(mutation):
    p = _valid_product()
    if mutation == "duplicate_id":
        p["event_id"] = np.array(["a", "a"])
    elif mutation == "broken_subset":
        p["sample_ii"] = np.array([False, True])
    elif mutation == "outside_ii":
        p["sample_i"] = np.array([False, False])
        p["sample_ii"] = np.array([True, False])
    elif mutation == "charged_gt_total":
        p["charged_edep_mev"] = p["charged_edep_mev"].copy()
        p["charged_edep_mev"][0, 0] = 6.0
    with pytest.raises(DataContractError):
        validate_event_stave_product(**p)


def test_fingerprinted_stream_hashes_exact_opened_bytes(tmp_path):
    source = tmp_path / "mc.root"
    source.write_bytes(b"source-bytes")
    with fingerprinted_regular_file_stream(source, block_size=3) as (stream, identity):
        assert stream.read() == b"source-bytes"
        assert identity.sha256 == hashlib.sha256(b"source-bytes").hexdigest()
        assert identity.bytes == len(b"source-bytes")


def test_fingerprinted_stream_rejects_in_place_mutation_during_consumer(tmp_path):
    source = tmp_path / "mc.root"
    source.write_bytes(b"source-bytes")
    with pytest.raises(DataContractError, match="consumer held"):
        with fingerprinted_regular_file_stream(source) as (stream, _identity):
            assert stream.read(2) == b"so"
            source.write_bytes(b"changed-source-bytes")


def _obj(rows):
    return np.asarray([np.asarray(row) for row in rows], dtype=object)


def test_builder_preserves_event_identity_trigger_topology_and_one_weight(monkeypatch, tmp_path):
    source = tmp_path / "mc.root"
    source_bytes = b"fake-root-stream-for-uproot-spy"
    source.write_bytes(source_bytes)
    chunk = {
        "Sci_bar_LayerID": _obj([[0, 0], [0, 0, 1], [0]]),
        "Sci_bar_LayerID1": _obj([[1, 1], [1, 2, 1], [2]]),
        "Sci_bar_PDG": _obj([[2212, 2112], [2212, 2212, 2212], [2212]]),
        "Sci_bar_EDep": _obj([[2.0, 3.0], [4.0, 0.5, 1.0], [9.0]]),
        "Sci_bar_Time": _obj([[10.0, 11.0], [10.0, 12.0, 14.0], [10.0]]),
        "PrimaryWeight": _obj([[2.0], [0.5], [3.0]]),
    }

    class FakeTree:
        def iterate(self, branches, **kwargs):
            assert set(branches) == set(chunk)
            yield chunk

    class FakeRoot:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __contains__(self, key):
            return key == "hibeam"

        def __getitem__(self, key):
            assert key == "hibeam"
            return FakeTree()

    seen = {}

    def fake_open(stream):
        seen["arg"] = stream
        assert hasattr(stream, "read") and not isinstance(stream, (str, bytes))
        return FakeRoot()

    monkeypatch.setitem(sys.modules, "uproot", SimpleNamespace(open=fake_open))
    payload, meta = build_event_stave_product(
        source, coinc_ns=15.0, generator_measure_mode="scalar_event_weight"
    )

    assert meta["schema_id"] == EVENT_STAVE_SCHEMA_ID
    assert meta["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert meta["n_entries_read"] == 3
    assert meta["n_sample_II_events"] == 2
    assert meta["n_sample_I_events"] == 1
    assert meta["detector_closure"] is False
    np.testing.assert_array_equal(payload["sample_I"], [False, True])
    np.testing.assert_array_equal(payload["sample_II"], [True, True])
    np.testing.assert_allclose(payload["event_weight"], [2.0, 0.5])
    np.testing.assert_allclose(payload["b_stave_edep_mev"][:, 0], [5.0, 4.0])
    np.testing.assert_allclose(payload["b_stave_charged_edep_mev"][:, 0], [2.0, 4.0])
    np.testing.assert_allclose(payload["b_stave_edep_mev"][:, 1], [0.0, 1.0])
    assert len(set(payload["event_id"].tolist())) == 2
    assert not isinstance(seen["arg"], (str, bytes))


def test_compare_first_b_export_preserves_generator_cluster_identity():
    """Issue #1164: compare export must carry entry_index as cluster IDs."""
    payload = {
        "entry_index": np.array([10, 20, 30], dtype=np.int64),
        "sample_I": np.array([True, False, True], dtype=bool),
        "sample_II": np.array([True, True, True], dtype=bool),
        "event_weight": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "b_stave_edep_mev": np.array(
            [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]], dtype=np.float64
        ),
    }
    export = build_compare_first_b_event_edep(payload)
    np.testing.assert_array_equal(export["sampleII_cluster_id"], [10, 20, 30])
    np.testing.assert_array_equal(export["sampleI_cluster_id"], [10, 30])
    assert export["cluster_key"][0] == "generator_event_index"
    assert export["statistical_unit"][0] == "event_stave_edep"


def test_compare_first_b_export_fails_closed_when_incomplete():
    with pytest.raises(DataContractError, match="missing payload keys"):
        build_compare_first_b_event_edep({"entry_index": np.array([0])})


def _publication_fixture():
    payload = {
        "event_id": np.array(["abc"], dtype="U16"),
        "entry_index": np.array([0], dtype=np.int64),
        "sample_I": np.array([False]),
        "sample_II": np.array([True]),
        "event_weight": np.array([1.0]),
        "b_stave_edep_mev": np.zeros((1, 8)),
        "b_stave_charged_edep_mev": np.zeros((1, 8)),
        "b_stave_hit_count": np.zeros((1, 8), dtype=np.int64),
        "b_stave_charged_hit_count": np.zeros((1, 8), dtype=np.int64),
    }
    metadata = {
        "source_sha256": "a" * 64,
        "tree_name": "hibeam",
        "coinc_ns": 15.0,
        "weighting_enabled": True,
        "authorisation_state": "NONAUTHORISING_TRUTH_DIAGNOSTIC",
    }
    return payload, metadata


def test_publication_exposes_product_and_manifest_as_one_immutable_generation(tmp_path):
    payload, metadata = _publication_fixture()
    product, manifest, record = producer._publish_generation(
        tmp_path, payload, metadata, max_events=0
    )
    assert product.is_file()
    assert manifest.is_file()
    assert product.parent == manifest.parent
    assert product.parent.name == record["generation_id"]
    assert record["product_sha256"] == hashlib.sha256(product.read_bytes()).hexdigest()
    before = product.read_bytes()
    with pytest.raises(DataContractError, match="generation already exists"):
        producer._publish_generation(tmp_path, payload, metadata, max_events=0)
    assert product.read_bytes() == before


def test_publication_failure_leaves_no_visible_generation(monkeypatch, tmp_path):
    payload, metadata = _publication_fixture()

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("injected product write failure")

    monkeypatch.setattr(producer.np, "savez_compressed", fail_save)
    with pytest.raises(RuntimeError, match="injected"):
        producer._publish_generation(tmp_path, payload, metadata, max_events=0)
    generations = tmp_path / "generations"
    assert generations.is_dir()
    assert [path for path in generations.iterdir() if path.is_dir()] == []
