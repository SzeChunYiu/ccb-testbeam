#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/validate_publication.py
mkdir -p build
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1786533311}"
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build main.tex
cp build/main.pdf paper.pdf
python3 scripts/write_build_receipt.py
printf 'PUBLICATION_PDF_BUILT: %s\n' "$(pwd)/paper.pdf"
