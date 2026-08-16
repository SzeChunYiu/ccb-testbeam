"""Single-stave CCB test-beam analysis toolchain.

Modules:
  - make_single_stave_fixture: deterministic synthetic event-table generator.
  - analyze_single_stave: schema-validating analyzer (tables + result.json + figures).
  - extract_g4_entry_energies: empirical stave-entry energy extractor from full-MC ROOT.

The three modules are standalone CLIs (each guarded by ``if __name__ == "__main__"``).
Importing this package does not execute any CLI. Unit tests import the pure
helper functions directly.
"""
