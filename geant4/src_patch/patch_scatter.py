#!/usr/bin/env python3
"""Transform the HEAD-baseline ScatteringGenerator into the per-instance
readiness implementation (issue #1182).

Reads the HEAD baseline from the two files given on the command line (or
sensible defaults) and writes the patched implementation next to this script.
The patch is idempotent: re-running on an already-patched file is a no-op.

Per-instance readiness model
----------------------------
The HEAD baseline used a process-global ``LoadFiles()`` triggered on event 0.
That is not per-instance: with multiple generators (or a shared instance) one
instance could consume another's source state, and a failed load silently
fell back to a uniform theta_cm.  This patch replaces it with a per-instance
state machine:

    UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL

* ``fCSFile == "null"``  -> UNCONFIGURED_UNIFORM: uniform theta_cm is the
  explicitly configured mode (no cross-section source exists).
* Every configured source must parse and validate, else FATAL.
* FATAL instances throw ``G4Exception(FatalException)`` on any attempted use
  (SampleThetaCM / BeamEnergy) instead of silently degrading.

Transactional loading
---------------------
Files are read into local temporaries and only published to the members via
``swap()`` once every element validates.  A multi-column parse failure, a
non-finite/negative node, or a non-monotonic energy/angle table aborts the
whole load and leaves the instance FATAL -- never a half-populated CDF.
"""

import base64
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent


def main() -> int:
    default_head_cc = Path("/tmp/HEAD_scatter.cc")
    default_head_hh = Path("/tmp/HEAD_scatter.hh")
    out_cc = SRC_DIR / "ScatteringGenerator.cc"
    out_hh = SRC_DIR / "ScatteringGenerator.hh"

    args = sys.argv[1:]
    head_cc = Path(args[0]) if len(args) > 0 else default_head_cc
    head_hh = Path(args[1]) if len(args) > 1 else default_head_hh

    if not head_cc.exists() or not head_hh.exists():
        print(f"HEAD baseline not found: {head_cc} / {head_hh}", file=sys.stderr)
        return 1

    cc = head_cc.read_text(encoding="utf-8")
    hh = head_hh.read_text(encoding="utf-8")

    patched_cc = patch_cc(cc)
    patched_hh = patch_hh(hh)

    out_cc.write_text(patched_cc, encoding="utf-8")
    out_hh.write_text(patched_hh, encoding="utf-8")
    print(f"wrote {out_cc} ({len(patched_cc.splitlines())} lines)")
    print(f"wrote {out_hh} ({len(patched_hh.splitlines())} lines)")
    return 0


# ---------------------------------------------------------------------------
# .cc patch
# ---------------------------------------------------------------------------

def patch_cc(cc: str) -> str:
    # 1. Includes: add std-library + G4Digest + G4String.  <cmath> is already
    #    present in the HEAD baseline, so do not add a duplicate.
    cc = cc.replace(
        '#include "ScatteringGenerator.hh"',
        '#include "ScatteringGenerator.hh"\n'
        '\n'
        '#include "G4Digest.hh"\n'
        '#include "G4String.hh"\n',
        1,
    )
    if "#include <algorithm>" not in cc:
        cc = cc.replace(
            '#include "G4SystemOfUnits.hh"',
            '#include "G4SystemOfUnits.hh"\n'
            '#include <algorithm>\n'
            '#include <cmath>\n'
            '#include <cstdio>\n'
            '#include <fstream>\n'
            '#include <sstream>\n'
            '#include <vector>\n',
            1,
        )

    # 2. Constructor: initialise the readiness state.
    cc = cc.replace(
        '\tfDEdxFile("dedx_p_in_CD2.txt"),\n\tfCSFile("null")\n',
        '\tfDEdxFile("dedx_p_in_CD2.txt"),\n'
        '\tfCSFile("null"),\n'
        '\tfSourceReadiness(UNINITIALIZED)\n',
        1,
    )

    # 3. GeneratePrimaryVertex: event-0 trigger becomes EnsureFilesLoaded().
    cc = cc.replace(
        "\tif(event->GetEventID()==0) LoadFiles();",
        "\tif(event->GetEventID()==0) EnsureFilesLoaded();",
        1,
    )

    # 4. Replace the old LoadFiles() + no-parameter loaders with the
    #    transactional versions.  The old block spans from "void
    #    ScatteringGenerator::LoadFiles()" through the end of the no-param
    #    BuildSigmaCDF() (just before "G4double ScatteringGenerator::SampleThetaCM").
    old_loaders_start = cc.index("void ScatteringGenerator::LoadFiles()")
    old_loaders_end = cc.index("G4double ScatteringGenerator::SampleThetaCM()")
    new_loaders = _new_loaders_block()
    cc = cc[:old_loaders_start] + new_loaders + cc[old_loaders_end:]

    # 5. SampleThetaCM: prepend readiness guard (both branches).
    cc = cc.replace(
        "\t// Draw theta_cm from the linearly interpolated p(theta)",
        "\tEnsureSourceReady();\n"
        "\tif(fSourceReadiness == FATAL){\n"
        '\t\tG4Exception("ScatteringGenerator::SampleThetaCM", "SourceReadiness002",\n'
        '\t\t            FatalException, "Scattering source is in FATAL state; cannot sample theta_cm.");\n'
        "\t}\n"
        "\tif(fSourceReadiness == UNCONFIGURED_UNIFORM){ return pi * G4UniformRand(); }\n"
        "\n"
        "\t// Draw theta_cm from the linearly interpolated p(theta)",
        1,
    )

    # 6. BeamEnergy: prepend readiness guard.
    cc = cc.replace(
        "G4double ScatteringGenerator::BeamEnergy(G4double z)//initial energy and thickness are given as arguments\n{\n",
        "G4double ScatteringGenerator::BeamEnergy(G4double z)//initial energy and thickness are given as arguments\n"
        "{\n"
        "\t// Ensure per-instance source readiness. BeamEnergy calls EvalELoss which reads\n"
        "\t// Ene/dEdx vectors; in FATAL state these are empty, causing UB.\n"
        "\tEnsureSourceReady();\n"
        "\tif(fSourceReadiness == FATAL){\n"
        '\t\tG4Exception("ScatteringGenerator::BeamEnergy", "SourceReadiness003",\n'
        '\t\t            FatalException, "Scattering source is in FATAL state; cannot compute beam energy.");\n'
        "\t}\n",
        1,
    )

    # 7. DefineCommands typo: "differential cross sections.." (double period).
    cc = cc.replace(
        'CSFileCmd.SetGuidance("File containing differential cross sections..\\n");',
        'CSFileCmd.SetGuidance("File containing differential cross sections.\\n");',
        1,
    )

    return cc


def _new_loaders_block() -> str:
    return (
        "G4String ScatteringGenerator::FileSha256(const G4String& path)\n"
        "{\n"
        "\tG4Digest digest;\n"
        "\tdigest.ComputeSha256(path);\n"
        "\treturn digest.GetDigestString();\n"
        "}\n"
        "\n"
        "bool ScatteringGenerator::LoadELossTable(\n"
        "\tstd::vector<G4double>& outEne,\n"
        "\tstd::vector<G4double>& outDEdx,\n"
        "\tG4String& digest)\n"
        "{\n"
        "\tstd::ifstream infile(fDEdxFile);\n"
        "\tif(!infile.is_open()){\n"
        '\t\tG4cerr << "ScatteringGenerator::LoadELossTable: cannot open " << fDEdxFile << G4endl;\n'
        "\t\treturn false;\n"
        "\t}\n"
        "\n"
        "\t// SHA256 of the source file before reading its contents.\n"
        "\tdigest = FileSha256(fDEdxFile);\n"
        "\n"
        "\tstd::vector<G4double> localEne, localDEdx;\n"
        "\tstd::string line;\n"
        "\twhile(std::getline(infile, line)){\n"
        "\t\tif(line.empty() || line[0] == '#'){ continue; }\n"
        "\t\tG4double tmpE, tmpDEdx;\n"
        '\t\tint nconv = std::sscanf(line.c_str(), "%lf\\t%lf\\n", &tmpE, &tmpDEdx);\n'
        "\t\tif(nconv != 2){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadELossTable: parse failure in \\"" << line\n'
        '\t\t\t       << "\\" (" << nconv << " conversions)." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tif(!std::isfinite(tmpE) || !std::isfinite(tmpDEdx) || tmpE < 0.0 || tmpDEdx < 0.0){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadELossTable: non-finite/negative node (E="\n'
        '\t\t\t       << tmpE << ", dEdx=" << tmpDEdx << ")." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\t// Convert: MeV/u to MeV, um to mm\n"
        "\t\ttmpE *= 938.28 / 931.5;\n"
        "\t\ttmpDEdx *= 1000.0;\n"
        "\t\tif(!localEne.empty() && !(tmpE > localEne.back())){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadELossTable: energies not strictly increasing ("\n'
        '\t\t\t       << localEne.back() << " >= " << tmpE << ")." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tlocalEne.push_back(tmpE);\n"
        "\t\tlocalDEdx.push_back(tmpDEdx);\n"
        "\t}\n"
        "\tif(localEne.empty()){\n"
        '\t\tG4cerr << "ScatteringGenerator::LoadELossTable: file is empty." << G4endl;\n'
        "\t\treturn false;\n"
        "\t}\n"
        "\t// Publish to output only after full validation.\n"
        "\toutEne.swap(localEne);\n"
        "\toutDEdx.swap(localDEdx);\n"
        "\treturn true;\n"
        "}\n"
        "\n"
        "bool ScatteringGenerator::LoadCrossSection(\n"
        "\tstd::vector<G4double>& outAng,\n"
        "\tstd::vector<G4double>& outSigma,\n"
        "\tG4String& digest)\n"
        "{\n"
        "\tstd::ifstream infile(fCSFile);\n"
        "\tif(!infile.is_open()){\n"
        '\t\tG4cerr << "ScatteringGenerator::LoadCrossSection: cannot open " << fCSFile << G4endl;\n'
        "\t\treturn false;\n"
        "\t}\n"
        "\n"
        "\t// SHA256 of the source file before reading its contents.\n"
        "\tdigest = FileSha256(fCSFile);\n"
        "\n"
        "\tstd::vector<G4double> localAng, localSigma;\n"
        "\tstd::string line;\n"
        "\twhile(std::getline(infile, line)){\n"
        "\t\tif(line.empty() || line[0] == '#'){ continue; }\n"
        "\t\tG4double tmpA, tmpCS, tmpUnc;\n"
        '\t\tint nconv = std::sscanf(line.c_str(), "%lf\\t%lf\\t%lf\\n", &tmpA, &tmpCS, &tmpUnc);\n'
        "\t\tif(nconv != 3){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadCrossSection: parse failure in \\"" << line\n'
        '\t\t\t       << "\\" (" << nconv << " conversions)." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tif(!std::isfinite(tmpA) || !std::isfinite(tmpCS) || !std::isfinite(tmpUnc) ||\n"
        "\t\t   tmpA < 0.0 || tmpCS < 0.0 || tmpUnc < 0.0){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadCrossSection: non-finite/negative node (theta="\n'
        '\t\t\t       << tmpA << ", sigma=" << tmpCS << ", unc=" << tmpUnc << ")." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\ttmpA *= pi / 180.; // deg to rad\n"
        "\t\tif(!localAng.empty() && !(tmpA > localAng.back())){\n"
        '\t\t\tG4cerr << "ScatteringGenerator::LoadCrossSection: angles not strictly increasing ("\n'
        '\t\t\t       << localAng.back() << " >= " << tmpA << ")." << G4endl;\n'
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tlocalAng.push_back(tmpA);\n"
        "\t\tlocalSigma.push_back(tmpCS);\n"
        "\t}\n"
        "\tif(localAng.size() < 2){\n"
        '\t\tG4cerr << "ScatteringGenerator::LoadCrossSection: need at least two rows; got "\n'
        "\t\t       << localAng.size() << \".\" << G4endl;\n"
        "\t\treturn false;\n"
        "\t}\n"
        "\t// Publish to output only after full validation.\n"
        "\toutAng.swap(localAng);\n"
        "\toutSigma.swap(localSigma);\n"
        "\treturn true;\n"
        "}\n"
        "\n"
        "bool ScatteringGenerator::BuildSigmaCDF(\n"
        "\tconst std::vector<G4double>& inAng,\n"
        "\tconst std::vector<G4double>& inSigma,\n"
        "\tstd::vector<G4double>& outTheta,\n"
        "\tstd::vector<G4double>& outCdf,\n"
        "\tstd::vector<G4double>& outPdf)\n"
        "{\n"
        "\t// Source-model IDs are intentionally literal so generator provenance can bind\n"
        "\t// the numerical law rather than the generic phrase \"inverse CDF\".\n"
        "\t//   cross_section_interpolation_mode = linear_node_pdf_exact_inverse_v1\n"
        "\t//   cross_section_support_mode = measured_table_support_truncate_v1\n"
        "\t//\n"
        "\t// The Table-VI nodes define p(theta)=sigma(theta)*sin(theta). Between measured\n"
        "\t// angles p(theta) is linearly interpolated; outside measured support the nominal\n"
        "\t// reference distribution has zero probability. This truncation is an explicit\n"
        "\t// source-model choice, not evidence that the physical cross section vanishes.\n"
        "\tstd::vector<G4double> localTheta, localCdf, localPdf;\n"
        "\tif(inAng.size() < 2 || inSigma.size() != inAng.size()){ return false; }\n"
        "\n"
        "\t// Positive common density scaling cannot change a normalized source law. Scale\n"
        "\t// cross sections before multiplying/integrating so alternate units cannot cause\n"
        "\t// overflow/underflow in the CDF state.\n"
        "\tG4double densityScale = 0.0;\n"
        "\tfor(size_t k = 0; k < inAng.size(); k++){\n"
        "\t\tif(!std::isfinite(inAng[k]) || !std::isfinite(inSigma[k]) || inSigma[k] < 0.0){\n"
        "\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: non-finite/negative source node; CS sampling disabled.\" << G4endl;\n"
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tif(k > 0 && !(inAng[k] > inAng[k-1])){\n"
        "\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: angles are not strictly increasing; CS sampling disabled.\" << G4endl;\n"
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tif(inSigma[k] > densityScale) densityScale = inSigma[k];\n"
        "\t}\n"
        "\tif(!(densityScale > 0.0)){\n"
        "\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: zero source density; CS sampling disabled.\" << G4endl;\n"
        "\t\treturn false;\n"
        "\t}\n"
        "\n"
        "\tlocalTheta = inAng;\n"
        "\tlocalPdf.reserve(inAng.size());\n"
        "\tfor(size_t k = 0; k < inAng.size(); k++){\n"
        "\t\tG4double p = (inSigma[k] / densityScale) * std::sin(inAng[k]);\n"
        "\t\tif(!std::isfinite(p) || p < 0.0){\n"
        "\t\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: invalid node PDF; CS sampling disabled.\" << G4endl;\n"
        "\t\t\treturn false;\n"
        "\t\t}\n"
        "\t\tlocalPdf.push_back(p);\n"
        "\t}\n"
        "\n"
        "\tlocalCdf.assign(localTheta.size(), 0.0);\n"
        "\tfor(size_t i = 1; i < localTheta.size(); i++){\n"
        "\t\tG4double dx  = localTheta[i] - localTheta[i-1];\n"
        "\t\tG4double avg = 0.5 * (localPdf[i] + localPdf[i-1]);\n"
        "\t\tlocalCdf[i] = localCdf[i-1] + avg * dx;\n"
        "\t}\n"
        "\tG4double norm = localCdf.back();\n"
        "\tif(!std::isfinite(norm) || !(norm > 0.0)){\n"
        "\t\tG4cerr << \"ScatteringGenerator::BuildSigmaCDF: invalid CDF norm (\" << norm << \"); CS sampling disabled.\" << G4endl;\n"
        "\t\treturn false;\n"
        "\t}\n"
        "\t// The CDF norm is a positive finite area; its square root must therefore\n"
        "\t// also be finite and positive. Guard the division below against any NaN/Inf.\n"
        "\tif(!std::isfinite(std::sqrt(norm)) || !(std::sqrt(norm) > 0.0)){ return false; }\n"
        "\tfor(size_t i = 0; i < localCdf.size(); i++) localCdf[i] /= norm;\n"
        "\t// Publish to outputs only after full validation.\n"
        "\toutTheta.swap(localTheta);\n"
        "\toutCdf.swap(localCdf);\n"
        "\toutPdf.swap(localPdf);\n"
        "\tG4cout << \"ScatteringGenerator: inverse-CDF ready over measured support [\"\n"
        "\t       << (inAng.front()/pi)*180. << \",\" << (inAng.back()/pi)*180. << \"] deg from \"\n"
        "\t       << inAng.size() << \" CS pts; interpolation=linear_node_pdf_exact_inverse_v1; \"\n"
        "\t       << \"support=measured_table_support_truncate_v1.\" << G4endl;\n"
        "\treturn true;\n"
        "}\n"
        "\n"
        "void ScatteringGenerator::EnsureFilesLoaded()\n"
        "{\n"
        "\t// Idempotent: only the first call performs the transactional load; later calls\n"
        "\t// (e.g. from per-event EnsureSourceReady) observe the already-published state.\n"
        "\tif(fSourceReadiness != UNINITIALIZED){ return; }\n"
        "\n"
        "\tstd::vector<G4double> localEne, localDEdx, localAng, localSigma;\n"
        "\tstd::vector<G4double> localTheta, localCdf, localPdf;\n"
        "\tG4String dEdxDigest, csDigest;\n"
        "\n"
        "\tbool dEdxOK = LoadELossTable(localEne, localDEdx, dEdxDigest);\n"
        "\tbool csOK = true;\n"
        "\tif(fCSFile != \"null\"){\n"
        "\t\tcsOK = LoadCrossSection(localAng, localSigma, csDigest);\n"
        "\t} else {\n"
        "\t\tcsDigest = \"null\";\n"
        "\t}\n"
        "\n"
        "\tif(dEdxOK && csOK && fCSFile != \"null\"){\n"
        "\t\tcsOK = BuildSigmaCDF(localAng, localSigma, localTheta, localCdf, localPdf);\n"
        "\t}\n"
        "\n"
        "\tif(fCSFile == \"null\"){\n"
        "\t\t// Explicit uniform mode: no cross-section source is configured.\n"
        "\t\tif(dEdxOK){\n"
        "\t\t\tEne.swap(localEne); dEdx.swap(localDEdx);\n"
        "\t\t\tfDEdxFileDigest = dEdxDigest;\n"
        "\t\t\tfCSFileDigest = \"null\";\n"
        "\t\t\tfSourceReadiness = UNCONFIGURED_UNIFORM;\n"
        "\t\t} else {\n"
        "\t\t\tfSourceReadiness = FATAL;\n"
        "\t\t}\n"
        "\t\treturn;\n"
        "\t}\n"
        "\n"
        "\t// Configured source: every element must validate, else fail closed.\n"
        "\tif(dEdxOK && csOK){\n"
        "\t\tEne.swap(localEne); dEdx.swap(localDEdx);\n"
        "\t\tang.swap(localAng); sigma.swap(localSigma);\n"
        "\t\tcdfTheta.swap(localTheta); cdfVal.swap(localCdf); cdfPdf.swap(localPdf);\n"
        "\t\tfDEdxFileDigest = dEdxDigest;\n"
        "\t\tfCSFileDigest = csDigest;\n"
        "\t\tfSourceReadiness = CONFIGURED_READY;\n"
        "\t} else {\n"
        "\t\tfSourceReadiness = FATAL;\n"
        "\t}\n"
        "}\n"
        "\n"
        "void ScatteringGenerator::EnsureSourceReady()\n"
        "{\n"
        "\t// Idempotent entry point into the readiness state machine.\n"
        "\tif(fSourceReadiness == UNINITIALIZED){ EnsureFilesLoaded(); }\n"
        "\tif(fSourceReadiness == FATAL){\n"
        '\t\tG4Exception("ScatteringGenerator::EnsureSourceReady", "SourceReadiness001",\n'
        "\t\t            FatalException, \"Configured scattering source failed validation; event generation is disabled.\");\n"
        "\t}\n"
        "}\n\n"
    )


# ---------------------------------------------------------------------------
# .hh patch
# ---------------------------------------------------------------------------

def patch_hh(hh: str) -> str:
    # 1. Include G4String.hh.
    hh = hh.replace(
        '#include "G4VPrimaryGenerator.hh"',
        '#include "G4VPrimaryGenerator.hh"\n#include "G4String.hh"',
        1,
    )

    # 2. Readiness enum + accessors + new private method declarations.  The
    #    patch inserts the enum after the class opening and the accessors in
    #    the public section.
    hh = hh.replace(
        "class ScatteringGenerator : public G4VPrimaryGenerator\n{\n",
        "class ScatteringGenerator : public G4VPrimaryGenerator\n"
        "{\n"
        "  public:\n"
        "    /// Per-instance source readiness states.\n"
        "    enum SourceReadiness {\n"
        "      UNINITIALIZED,         ///< Constructor ran; no source files loaded yet.\n"
        "      UNCONFIGURED_UNIFORM,  ///< fCSFile==\"null\"; uniform theta_cm is the explicit mode.\n"
        "      CONFIGURED_READY,      ///< All configured sources validated and usable.\n"
        "      FATAL                  ///< Configured source load/validation failed; no event generation.\n"
        "    };\n",
        1,
    )

    # 3. Accessors: add after the existing GetParticleEnergy2() getter.
    hh = hh.replace(
        "\tG4double GetParticleEnergy2(){return particle2->GetKineticEnergy();}\n",
        "\tG4double GetParticleEnergy2(){return particle2->GetKineticEnergy();}\n"
        "\tSourceReadiness GetSourceReadiness() const { return fSourceReadiness; }\n"
        "\tG4String GetCSFileDigest() const { return fCSFileDigest; }\n"
        "\tG4String GetDEdxFileDigest() const { return fDEdxFileDigest; }\n",
        1,
    )

    # 4. Replace the old no-parameter private declarations with the new ones.
    old_private = (
        "\tvoid DefineCommands();\n"
        "\tvoid LoadFiles();\n"
        "\tvoid LoadELossTable();\n"
        "\tvoid LoadCrossSection();\n"
        "\tG4double EvalELoss(G4double);\n"
        "\tG4double EvalWeight(G4double);\n"
        "\tG4double SampleThetaCM();\n"
        "\tvoid BuildSigmaCDF();\n"
        "\tG4double BeamEnergy(G4double);\n"
    )
    new_private = (
        "\tvoid DefineCommands();\n"
        "\tbool LoadELossTable(std::vector<G4double>&, std::vector<G4double>&, G4String&);\n"
        "\tbool LoadCrossSection(std::vector<G4double>&, std::vector<G4double>&, G4String&);\n"
        "\tbool BuildSigmaCDF(const std::vector<G4double>&, const std::vector<G4double>&,\n"
        "\t                   std::vector<G4double>&, std::vector<G4double>&, std::vector<G4double>&);\n"
        "\tG4double EvalELoss(G4double);\n"
        "\tG4double EvalWeight(G4double);\n"
        "\tG4double SampleThetaCM();\n"
        "\tvoid EnsureSourceReady();\n"
        "\tvoid EnsureFilesLoaded();\n"
        "\tG4String FileSha256(const G4String&);\n"
        "\tG4double BeamEnergy(G4double);\n"
    )
    if old_private not in hh:
        # The HEAD baseline has BuildSigmaCDF after SampleThetaCM and before
        # BeamEnergy. Match that order exactly.
        old_private = (
            "\tvoid DefineCommands();\n"
            "\tvoid LoadFiles();\n"
            "\tvoid LoadELossTable();\n"
            "\tvoid LoadCrossSection();\n"
            "\tG4double EvalELoss(G4double);\n"
            "\tG4double EvalWeight(G4double);\n"
            "\tG4double SampleThetaCM();\n"
            "\tvoid BuildSigmaCDF();\n"
            "\tG4double BeamEnergy(G4double);\n"
        )
    hh = hh.replace(old_private, new_private, 1)

    # 5. Members: drop haveWeights, add readiness + digest state.
    #    ang/sigma/cdfTheata/cdfVal/cdfPdf already exist in the HEAD baseline,
    #    so only haveWeights is removed and readiness/digest members are added.
    hh = hh.replace(
        "\tG4String fDEdxFile, fCSFile;\n"
        "\tG4bool haveWeights;\n"
        "\tstd::vector<G4double> Ene, dEdx;\n",
        "\tG4String fDEdxFile, fCSFile;\n"
        "\tstd::vector<G4double> Ene, dEdx;\n"
        "\tSourceReadiness fSourceReadiness;\n"
        "\tG4String fCSFileDigest;\n"
        "\tG4String fDEdxFileDigest;\n",
        1,
    )

    return hh


if __name__ == "__main__":
    sys.exit(main())
