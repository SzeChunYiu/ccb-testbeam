"""Connector-inspected current-source fixture for stale-artifact auditing.

Repository: SzeChunYiu/ccb-testbeam
Ref: main at 8acfc727a1479ff5b616042e65743b0652900c25
Builder Git blob: 39dcd3b13d3886c43f3e9111291d420f86cc7c85
Relevant source ranges: tools/figure_registry/builder.py:368-493

This fixture preserves the control-flow semantics needed by the audit. It does not
claim to be a byte-identical copy of the complete 526-line builder module.
"""


class FigureRegistryError(RuntimeError):
    pass


def _base_record(entry):
    return {
        "id": entry.id,
        "disposition": None,
        "figure": None,
        "source_data": None,
    }


def _process_entry(entry, out_dir, paper_only, allow_preliminary):
    record = _base_record(entry)
    disposition = entry.disposition
    if disposition == "BLOCKED":
        record["disposition"] = "BLOCKED"
        record["reason"] = "scientific status EXTERNAL_BLOCKER is non-buildable"
        return record
    if disposition == "QUARANTINED":
        record["disposition"] = "QUARANTINED"
        record["reason"] = "retained but not paper-authorizing"
        return record
    if disposition == "CONDITIONAL" and paper_only and not allow_preliminary:
        record["disposition"] = "BLOCKED"
        record["reason"] = "PRELIMINARY excluded"
        return record
    return record


def build(entries, output):
    failures = []
    report = {"entries": []}
    for entry in entries:
        try:
            record = _process_entry(entry, output, True, False)
        except FigureRegistryError as exc:
            record = _base_record(entry)
            record["disposition"] = "FAIL"
            record["reason"] = str(exc)
            failures.append(str(exc))
        report["entries"].append(record)
    return report
