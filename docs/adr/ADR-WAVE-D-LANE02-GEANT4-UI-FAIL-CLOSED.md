# ADR-WAVE-D-LANE02: Geant4 UI/macro command status fail-closed

**Status:** accepted (code contract)
**Date:** 2026-08-12
**Lane:** Wave D Lane 02
**Issues:** #998

## Context

`G4UImanager::ApplyCommand` returns a non-zero status on missing macros,
rejected commands, and many nested `/control/execute` failures. Ignoring that
status lets a campaign wrapper observe exit 0 and `CCB_STAVE_END` without the
intended run configuration.

## Decision

1. Production `geant4/single_stave/src/main.cc` wraps required UI commands in
   `apply_required`, aborting with exit code 4 on non-zero status.
2. Both macro mode (`/control/execute`) and batch verbose setup commands are
   covered.
3. Nested Geant4 command failures that still return status 0 inside a successful
   outer `/control/execute` remain a Geant4-engine limitation; campaigns must
   keep macros minimal and prefer CLI AppConfig over deep macro graphs.
4. Regression coverage is the static contract test
   `tests/test_geant4_ui_command_fail_closed.py`.

## Consequences

Authorising stave campaigns cannot treat a failed UI command as a successful
scientific run. No physics numbers were invented.
