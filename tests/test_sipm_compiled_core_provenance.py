"""Exact executable/source binding for the ccb-sipm-core gitlink (#977/#1067)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "geant4" / "single_stave" / "include" / "SipmBuildProvenance.hh"
SOURCE = ROOT / "geant4" / "single_stave" / "src" / "SipmBuildProvenance.cc"
GITLINK = "geant4/single_stave/sipm"


def _compiled_sha() -> str:
    text = HEADER.read_text()
    match = re.search(r'kSipmCoreCommit\[\]\s*=\s*\n?\s*"([0-9a-f]{40})"', text)
    assert match, "compiled SiPM core provenance must be one exact lowercase 40-hex SHA"
    return match.group(1)


def _gitlink_sha() -> str:
    proc = subprocess.run(
        ["git", "ls-tree", "HEAD", GITLINK],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    fields = proc.stdout.strip().split()
    assert len(fields) >= 3 and fields[0] == "160000" and fields[1] == "commit"
    return fields[2]


def test_compiled_core_sha_matches_superproject_gitlink() -> None:
    """A pin advance without an executable provenance update must fail CI."""
    assert _compiled_sha() == _gitlink_sha()


def test_binding_translation_unit_overwrites_hostile_environment(tmp_path: Path) -> None:
    """The executable must serialize its compiled identity, not caller input."""
    compiler = shutil.which("c++")
    assert compiler is not None, "protected CI must provide a C++ compiler"
    harness = tmp_path / "probe.cc"
    harness.write_text(
        '#include <cstdlib>\n'
        '#include <iostream>\n'
        'int main() {\n'
        '  const char* value = std::getenv("CCB_SIPM_CORE_COMMIT");\n'
        '  if (!value) return 2;\n'
        '  std::cout << value << "\\n";\n'
        '  return 0;\n'
        '}\n'
    )
    exe = tmp_path / "probe"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-I",
            str(ROOT / "geant4" / "single_stave" / "include"),
            str(SOURCE),
            str(harness),
            "-o",
            str(exe),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    env = os.environ.copy()
    env["CCB_SIPM_CORE_COMMIT"] = "deadbeef"
    proc = subprocess.run(
        [str(exe)], env=env, text=True, capture_output=True, check=True
    )
    assert proc.stdout.strip() == _compiled_sha()


def test_binding_source_is_part_of_single_stave_source_glob() -> None:
    """Guard the composition assumption that the binder is linked into the app."""
    cmake = (ROOT / "geant4" / "single_stave" / "CMakeLists.txt").read_text()
    assert 'file(GLOB_RECURSE CCB_STAVE_SOURCES CONFIGURE_DEPENDS' in cmake
    assert '"${PROJECT_SOURCE_DIR}/src/*.cc"' in cmake
    assert SOURCE.suffix == ".cc"
