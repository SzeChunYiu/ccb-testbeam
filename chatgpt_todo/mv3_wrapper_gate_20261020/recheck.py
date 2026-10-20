#!/usr/bin/env python3
"""Source-pinned MV3 standalone wrapper check. Synthetic uproot double only.

exit 1: known defects reproduced; exit 2: source drift/execution error.
No beam ROOT, Geant4, hardware, or publication permission is inferred.
"""
from __future__ import annotations
import contextlib
from decimal import Decimal, getcontext
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "src/ccb_mc_validation/truth/tracks.py": "f84b17a2cc589e428f87e662648f96ebcbb97f36",
    "src/ccb_mc_validation/studies/mv3_stopping_depth.py": "9b0dfeaa6e74401345bc78c7ab82b33d7868b665",
    "src/ccb_mc_validation/studies/common.py": "a6a3da4aa58c8346758c26ac64d23c4f827c90aa",
    "scripts/mv3_stopping_depth.py": "5587135ff100195240a69c5a93860975d64182e8",
}

def main():
    digests = {}
    for path, expected in PINS.items():
        b = (ROOT / path).read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
        if sha != expected:
            raise ValueError("source drift: " + path)
        digests[path] = {"git_blob": sha, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    sys.path.insert(0, str(ROOT / "src"))
    from ccb_mc_validation.truth import tracks
    from ccb_mc_validation.studies import mv3_stopping_depth as mv3
    for mod, path in ((tracks, "src/ccb_mc_validation/truth/tracks.py"),
                      (mv3, "src/ccb_mc_validation/studies/mv3_stopping_depth.py")):
        if Path(mod.__file__).resolve() != (ROOT / path).resolve():
            raise ValueError("unexpected imported code: " + path)
    hits = {
        "Sci_bar_TrackID": [[1, 1, 1], [1, 1]],
        "Sci_bar_LayerID": [[0, 2, 7], [0, 7]],
        "Sci_bar_LayerID1": [[1, 1, 1], [1, 1]],
        "Sci_bar_PDG": [[2212] * 3, [1000010020] * 2],
        "Sci_bar_EDep": [[1., 2., 2.], [2., 3.]],
        "Sci_bar_TrackLength": [[1., 1., 1.], [2., 2.]],
        "Sci_bar_Momentum_X": [[.4, .4, .4], [.6, .6]],
        "Sci_bar_Momentum_Y": [[0., 0., 0.], [0., 0.]],
        "Sci_bar_Momentum_Z": [[0., 0., 0.], [0., 0.]],
    }
    chunk = {}
    for name, events in hits.items():
        a = np.empty(len(events), dtype=object)
        for i, event in enumerate(events):
            a[i] = np.asarray(event)
        chunk[name] = a

    class FakeTree:
        def iterate(self, branches, step_size, library, entry_stop):
            assert library == "np" and entry_stop is None
            yield {key: chunk[key] for key in branches}

    class FakeRoot:
        def __getitem__(self, name):
            assert name == "hibeam"
            return FakeTree()

    fake_uproot = types.SimpleNamespace(open=lambda _: FakeRoot())
    with patch.dict(sys.modules, {"uproot": fake_uproot}):
        records = tracks.load_tracks_from_root("FAKE_NOT_REAL.root")
        original = mv3.run_mv3(records)
        expanded = dict(records)
        expanded["layer_hits"] = np.array([[1, 0, 1, 0, 0, 0, 0, 1],
                                            [1, 0, 0, 0, 0, 0, 0, 1]], dtype=bool)
        after_mask = mv3.run_mv3(expanded)
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text("mc_file: FAKE_NOT_REAL.root\ntree: hibeam\n"
                              "output_dir: ignored\nn_layers: 8\n", encoding="utf-8")
            out = Path(tmp) / "output"
            prior_argv = sys.argv
            stdout = io.StringIO()
            try:
                sys.argv = [str(ROOT / "scripts/mv3_stopping_depth.py"),
                            "--config", str(config), "--out", str(out)]
                with contextlib.redirect_stdout(stdout):
                    runpy.run_path(str(ROOT / "scripts/mv3_stopping_depth.py"),
                                   run_name="__main__")
            finally:
                sys.argv = prior_argv
            saved = json.loads((out / "study_result.json").read_text())
    getcontext().prec = 60
    energies = []
    for i, (pdg, p_str, m_str) in enumerate(((2212, ".4", "938.272"),
                                               (1000010020, ".6", "1875.613"))):
        p, mass = Decimal(p_str) * 1000, Decimal(m_str)
        energies.append({
            "pdg": pdg, "p_GeV_c": float(p_str),
            "source_ekin_MeV": float(records["ekin"][i]),
            "reference_ekin_MeV": float(p*p / ((mass*mass + p*p).sqrt() + mass)),
        })
    assert original.status.value == after_mask.status.value == saved["status"] == "BLOCKED"
    assert records["sample_label"].tolist() == ["", ""]
    assert "layer_hits" not in records and "edep_per_layer" not in records
    assert "[ok] wrote" in stdout.getvalue()
    assert all(e["source_ekin_MeV"] < e["reference_ekin_MeV"] / 100000
               for e in energies)
    return {
        "status": "SOURCE_WRAPPER_RETURNS_SUCCESS_WHILE_STUDY_BLOCKED",
        "scientific_release": "NOT_AUTHORIZED",
        "input": "fake-uproot synthetic hit arrays, not real ROOT",
        "source_main": "a61427813344e29047ca9eb9b764182eb29e4c83",
        "source_bindings": digests,
        "loader_keys": sorted(records),
        "loader_labels": records["sample_label"].tolist(),
        "mask_available": False,
        "original_status": original.status.value,
        "after_mask_only_status": after_mask.status.value,
        "wrapper_completed_normally": True,
        "wrapper_written_status": saved["status"],
        "wrapper_printed_ok": True,
        "unit_path": energies,
        "historical_ROOT_impact": "NOT_EVALUATED",
    }

if __name__ == "__main__":
    try:
        print(json.dumps(main(), indent=2, sort_keys=True, allow_nan=False))
        raise SystemExit(1)  # deliberate negative witness, NOT scientific PASS
    except (ValueError, RuntimeError, OSError, AssertionError) as err:
        print(json.dumps({"status": "EXECUTION_OR_SOURCE_DRIFT", "error": str(err),
                          "scientific_release": "NOT_AUTHORIZED"}))
        raise SystemExit(2)
