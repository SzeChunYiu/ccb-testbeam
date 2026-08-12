.PHONY: all pdf validate clean

all: pdf

validate:
	python3 scripts/validate_publication.py

pdf: validate
	./build.sh

clean:
	rm -rf build paper.pdf
