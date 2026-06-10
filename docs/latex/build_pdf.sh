#!/bin/bash
# Render the full thesis-style PDF from the chapter files.
cd "$(dirname "$0")"
latexmk -pdf -interaction=nonstopmode main.tex 2>/dev/null || { pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex; }
echo "built: $(ls -la main.pdf 2>/dev/null | awk '{print $5}') bytes"
