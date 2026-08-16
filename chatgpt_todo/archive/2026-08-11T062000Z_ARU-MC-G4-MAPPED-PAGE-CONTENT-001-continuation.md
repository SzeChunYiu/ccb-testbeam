# ARU-MC-G4-MAPPED-PAGE-CONTENT-001 — adversarial EOF-page refinement

Status: `ACTIVE / REVISED_BEFORE_MERGE / EXACT_HEAD_CI_PENDING / REAL_HIBEAM_RUNTIME_BLOCKED / PHYSICS_INFERENCE_BLOCKED`

This continuation preserves a material adversarial correction discovered after the initial branch implementation but before merge. The earlier record remains historical provenance rather than being rewritten.

## Concern `G4-MEM-005` — whole pages beyond EOF are not zero-fill evidence

The first implementation used

`file_bytes = min(mapping_length, file_size - file_offset)`

and synthesized zero bytes for every remaining mapping byte. That was too broad. Linux/POSIX guarantee zero filling only for the **partial final page** of a mapped object. Whole pages following the object end are not equivalent to a zero-filled file projection; accesses can raise `SIGBUS`. Authoritative Linux man-pages 6.18 describe both the partial-page zero-fill rule and `SIGBUS` for a page beyond the mapped object.

Source: https://man7.org/linux/man-pages/man2/mmap.2.html

This matters to provenance even if ordinary ELF executable mappings rarely exercise the hostile geometry: inventing zeros for a whole beyond-EOF page would turn an unbound address range into apparently content-bound evidence.

## Revised invariant

Let page size be `P = sysconf(_SC_PAGE_SIZE)`, backing length `L`, file offset `o`, and mapping length `m`. Define

`L_page = ceil(L/P) * P`.

Require first:

`o < L`

and

`o + m <= L_page`.

Only then use

`n = min(m, L-o)`

and compare the live memory with

`F[o:o+n] || 0^(m-n)`.

Thus only the remainder of the final partial page can be synthesized as the documented expected zero suffix. A mapping that extends into a whole page beyond EOF is `BLOCKED` rather than guessed.

## Repository repair

- `b85970ed42f5a6ea76e3fe0191eae9ec0eb75dab` — source guard using the system page size and rounded EOF.
- `0426228b6ca98d53e8668026445cdf0f8836f50d` — hostile regression `test_whole_page_beyond_eof_is_not_synthesized_as_zero`.

The focused suite now contains 10 deterministic fixtures. The new exact-head CI result is not yet available at the time of this record, so no PASS count is claimed for the revised repository head.

## Review-role update

- **Linux/Geant4 runtime provenance lead — REVISE then ACCEPT revised mathematical boundary.** The original zero-extension formula failed the limiting case `o+m > ceil(L/P)P`; the rounded-EOF guard removes that invalid region.
- **Adversarial systems reviewer — REJECT original unlimited zero synthesis / ACCEPT fail-closed guard.** Strongest falsifier is a 0x1800-byte file with a mapping from file offset 0x1000 spanning 0x2000 bytes: the original algorithm would synthesize 0x1800 zero bytes, while only 0x800 belongs to the final partial page.
- **Independent validation reviewer — BLOCK revised implementation until exact-head tests/CI pass.** The new regression is committed but repository-level validation is pending.
- **Claims/provenance reviewer — unchanged BLOCK on CL-021.** This correction changes only the bounded runtime-code evidence model.

No Geant4 event, beam data, production MC, detector observable or public physics claim is affected or promoted by this software-provenance correction.
