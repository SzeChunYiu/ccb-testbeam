from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
HEADER = REPO_ROOT / "geant4" / "single_stave" / "include" / "NpyWriter.hh"


CPP = r'''
#include "NpyWriter.hh"

#include <exception>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  if (argc != 3) return 64;
  const std::string mode = argv[1];
  const std::string path = argv[2];
  try {
    if (mode == "valid") {
      const float values[4] = {1.25f, -2.5f, 3.75f, 4.5f};
      CCB::write_npy_f32(path, values, {2, 2});
    } else if (mode == "empty") {
      CCB::write_npy_f32(path, nullptr, {0, 4, 4});
    } else if (mode == "null") {
      CCB::write_npy_f32(path, nullptr, {1});
    } else if (mode == "overflow") {
      const float value = 1.0f;
      CCB::write_npy_f32(
          path, &value, {std::numeric_limits<size_t>::max(), 2});
    } else {
      return 65;
    }
  } catch (const std::exception& exc) {
    std::cerr << exc.what() << "\n";
    return 2;
  }
  return 0;
}
'''


@pytest.fixture(scope="session")
def helper(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is unavailable")
    work = tmp_path_factory.mktemp("npy_writer")
    source = work / "helper.cc"
    executable = work / "helper"
    source.write_text(CPP, encoding="utf-8")
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{HEADER.parent}",
            str(source),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return executable


def run(helper: Path, mode: str, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(helper), mode, str(output)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_numpy_loads_exact_float32_payload(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "valid.npy"
    result = run(helper, "valid", output)
    assert result.returncode == 0, result.stderr
    array = np.load(output, allow_pickle=False)
    assert array.dtype == np.dtype("<f4")
    np.testing.assert_array_equal(
        array, np.array([[1.25, -2.5], [3.75, 4.5]], dtype="<f4")
    )


def test_header_length_is_explicit_little_endian(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "header.npy"
    assert run(helper, "valid", output).returncode == 0
    raw = output.read_bytes()
    header_len = int.from_bytes(raw[8:10], "little")
    assert raw[:8] == b"\x93NUMPY\x01\x00"
    assert raw[10 + header_len - 1 : 10 + header_len] == b"\n"
    source = HEADER.read_text(encoding="utf-8")
    assert "header_len_le" in source
    assert "reinterpret_cast<const char*>(&header_len)" not in source


def test_empty_array_is_valid(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "empty.npy"
    result = run(helper, "empty", output)
    assert result.returncode == 0, result.stderr
    array = np.load(output, allow_pickle=False)
    assert array.shape == (0, 4, 4)
    assert array.dtype == np.dtype("<f4")


def test_nonempty_null_payload_fails_closed(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "null.npy"
    result = run(helper, "null", output)
    assert result.returncode == 2
    assert "null" in result.stderr.lower()
    assert not output.exists()


def test_shape_product_overflow_fails_closed(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "overflow.npy"
    result = run(helper, "overflow", output)
    assert result.returncode == 2
    assert "overflows" in result.stderr
    assert not output.exists()


def test_unwritable_target_fails_closed(helper: Path, tmp_path: Path) -> None:
    output = tmp_path / "missing" / "out.npy"
    result = run(helper, "valid", output)
    assert result.returncode == 2
    assert "cannot open" in result.stderr
    assert not output.exists()
