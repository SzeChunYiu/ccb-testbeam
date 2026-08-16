# Ticket 2413: tn-ticket Null Claim Guard

## Abstract

The required single claim command for `testbeam-laptop-2`,

```bash
tn-ticket claim testbeam-laptop-2 --project testbeam
```

exited successfully but returned a null pseudo-ticket:

```text
null
# null

null
```

Issue `#2413`, **Fix tn-ticket claim null pseudo-ticket handling**, documents the
same failure mode.  The repository now contains a reviewable helper copy at
`tools/tn-ticket` and a regression test at `tests/test_tn_ticket_claim.py`.

## Failure Mode

The deployed helper first checks whether the worker already holds a claimed
ticket.  The vulnerable pattern was equivalent to

```bash
existing=$(gh issue list ... --jq '.[0] | "\(.number)|\(.title)|\(.body)"')
if [ -n "$existing" ] && [ "$existing" != "null" ]; then
  ...
fi
```

When the claimed-ticket query is empty, GitHub CLI/JQ combinations can still
produce a pipe-delimited null payload such as

```text
null|null|null
```

That string is non-empty and is not exactly `null`, so the helper enters the
idempotent-return path and prints a fake ticket with number, title, and body all
set to null.  It never reaches the oldest-open-ticket query.

## Fix

The repository-local helper changes both the producer and consumer sides of the
guard:

```bash
--jq 'if length == 0 then empty else .[0] | "\(.number)|\(.title)|\(.body)" end'
```

and then accepts the idempotent path only when the first field is a numeric issue
number:

```bash
existing_number=$(printf '%s' "$existing" | cut -d'|' -f1)
if [ -n "$existing" ] && printf '%s' "$existing_number" | grep -Eq '^[0-9]+$'; then
  ...
fi
```

These two checks are deliberately redundant.  The JQ expression prevents the
known empty-list case; the numeric shell guard prevents future malformed payloads
from being promoted to tickets.

## Regression Test

The test `tests/test_tn_ticket_claim.py` installs a fake `gh` executable on
`PATH`.  The fake first returns `null|null|null` for the existing claimed-ticket
query, then returns issue `2413` for the open queue.  The expected behavior is:

1. the helper does not print `# null`;
2. it edits issue `2413` with `factory:claimed` and `worker:testbeam-laptop-2`;
3. it prints issue `2413` on stderr and the real title/body on stdout.

This is a deterministic unit-level reproduction of the ticket defect and does
not require live GitHub state.

## Scope and Caveats

The deployed `/home/billy/bin/tn-ticket` file is outside this repository and is
mounted read-only in this worker environment, so it could not be patched in
place.  The PR therefore carries a maintained repository-local helper plus an
executable regression test.  Deploying this fix requires copying or symlinking
`tools/tn-ticket` into the operator-managed helper location after review.

This ticket is not a raw ROOT physics benchmark.  The raw ROOT reproduction and
ML benchmark requirements from the generic worker prompt were not applicable to
the actual first ticket returned by the queue, which was a tooling-defect ticket.
