.PHONY: all pdf rough validate clean

all: pdf

validate:
	python3 scripts/validate_publication.py

pdf: validate
	./build.sh

rough: validate
	mkdir -p build
	export SOURCE_DATE_EPOCH="$${SOURCE_DATE_EPOCH:-1786533311}"; \
	latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error -jobname=rough-paper -outdir=build rough.tex
	cp build/rough-paper.pdf rough-paper.pdf
	@printf 'ROUGH_PUBLICATION_PDF_BUILT: %s\n' "$(CURDIR)/rough-paper.pdf"

clean:
	rm -rf build paper.pdf rough-paper.pdf
