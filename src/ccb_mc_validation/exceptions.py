"""Exception hierarchy and CLI exit-code mapping for MC validation."""

from __future__ import annotations

EXIT_CODES: dict[str, int] = {
    "success": 0,
    "MCValidationError": 1,
    "ConfigurationError": 2,
    "InputNotFoundError": 3,
    "SchemaMismatchError": 4,
    "UnitValidationError": 5,
    "DataContractError": 6,
    "SplitLeakageError": 7,
    "ManifestError": 8,
    "CalibrationError": 9,
    "StudyBlockedError": 10,
    "ReportValidationError": 10,
    "UnsafeOverwriteError": 10,
}


class MCValidationError(Exception):
    """Base error for the MC validation program."""

    exit_code: int = EXIT_CODES["MCValidationError"]

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(MCValidationError):
    """Raised when configuration is invalid or incomplete."""

    exit_code = EXIT_CODES["ConfigurationError"]


class InputNotFoundError(MCValidationError):
    """Raised when a required input file or directory is missing."""

    exit_code = EXIT_CODES["InputNotFoundError"]


class SchemaMismatchError(MCValidationError):
    """Raised when input schema does not match the expected contract."""

    exit_code = EXIT_CODES["SchemaMismatchError"]


class UnitValidationError(MCValidationError):
    """Raised when a physical unit is unknown or inconsistent."""

    exit_code = EXIT_CODES["UnitValidationError"]


class DataContractError(MCValidationError):
    """Raised when tabular or ROOT data violates the study contract."""

    exit_code = EXIT_CODES["DataContractError"]


class SplitLeakageError(MCValidationError):
    """Raised when train/test or calibration/analysis splits overlap."""

    exit_code = EXIT_CODES["SplitLeakageError"]


class ManifestError(MCValidationError):
    """Raised when manifest metadata is missing or inconsistent."""

    exit_code = EXIT_CODES["ManifestError"]


class CalibrationError(MCValidationError):
    """Raised when calibration anchors fail validation."""

    exit_code = EXIT_CODES["CalibrationError"]


class StudyBlockedError(MCValidationError):
    """Raised when a study cannot run because prerequisites are unmet."""

    exit_code = EXIT_CODES["StudyBlockedError"]


class ReportValidationError(MCValidationError):
    """Raised when generated report artifacts fail validation."""

    exit_code = EXIT_CODES["ReportValidationError"]


class UnsafeOverwriteError(MCValidationError):
    """Raised when an operation would overwrite protected outputs."""

    exit_code = EXIT_CODES["UnsafeOverwriteError"]


def exit_code_for(exc: BaseException) -> int:
    """Map an exception instance to a process exit code."""
    if isinstance(exc, MCValidationError):
        return exc.exit_code
    return EXIT_CODES["MCValidationError"]
