"""ccbprov — provenance & reproducibility infrastructure for CCB test-beam.

Public API::

    from tools.ccbprov import (
        sha256_file, file_record,
        RunManifest,
        ClosureRow, write_closure_matrix, CLOSURE_STATUSES,
        validate_record, load_schema,
        init_report_dir, utc_stamp_now,
    )
"""

from __future__ import annotations

from .closure import CLOSURE_STATUSES, ClosureRow, write_closure_matrix
from .hashing import file_record, sha256_file
from .manifest import RunManifest, default_environment, detect_git_commit
from .report import init_report_dir, utc_stamp_now
from .validate import HAVE_JSONSCHEMA, load_schema, validate_record

__all__ = [
    "sha256_file",
    "file_record",
    "RunManifest",
    "detect_git_commit",
    "default_environment",
    "ClosureRow",
    "write_closure_matrix",
    "CLOSURE_STATUSES",
    "validate_record",
    "load_schema",
    "HAVE_JSONSCHEMA",
    "init_report_dir",
    "utc_stamp_now",
]

__version__ = "0.1.0"
