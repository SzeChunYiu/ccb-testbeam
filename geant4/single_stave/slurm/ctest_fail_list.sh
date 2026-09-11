#!/usr/bin/env bash
# Extract the authoritative failing-test list from a ctest log.
#
# Do NOT grep the per-test progress lines for "***Failed": CTest reports other
# non-passing states there too ("Subprocess aborted" for a signal death, and
# "***Timeout"), and a regex that only knows one of them reports a clean run
# while a test is crashing. That exact mistake produced a false "NEWLY broken:
# <none>" while ccb_stave_sipm_n_cells_nonsquare_fail was dying on SIGABRT.
#
# CTest's own trailer block lists every non-passing test with its state, so use
# that and fail loudly if it is absent (a killed or truncated run must not look
# like a pass).
set -uo pipefail
LOG="${1:?ctest log}"
if grep -q "The following tests FAILED:" "$LOG"; then
  sed -n '/The following tests FAILED:/,$p' "$LOG" \
    | grep -oE "^[[:space:]]+[0-9]+ - [A-Za-z_0-9]+" \
    | sed -E 's/.* - //' | sort -u
elif grep -qE "100% tests passed|tests passed, 0 tests failed" "$LOG"; then
  :  # genuinely clean
else
  echo "CTEST_LOG_UNPARSEABLE" >&2
  exit 3
fi
