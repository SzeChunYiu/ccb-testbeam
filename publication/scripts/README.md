# Publication analysis / plotting scripts

This folder is an **index via symlinks**, not a fork of production analysis code.

- `gated/`: current result producers whose outputs are explicitly invalidated or non-authorising under the Cycle-3 audit.
- `utilities/`: generic publication/plot utilities.
- `validate_publication.py`: checks the package structure and guards against accidental loss of the publication-hold layout.

When a corrected producer supersedes a gated one, update the canonical script at its repository source path and then update this index plus the corresponding result/claim/figure references. Do not create divergent copies here.
