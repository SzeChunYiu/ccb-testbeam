"""Automated preflight checks for publication figures.

These checks do not replace human review.  They deliberately catch the common
regressions seen in the legacy wiki plots: clipped artists, font-size collapse,
boxed prose, annotation overload, and overlapping free text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

import matplotlib.figure
from matplotlib.text import Text
from PIL import Image
from pypdf import PdfReader

from .style import MM_PER_INCH


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class FileCheck:
    path: str
    ok: bool
    details: dict[str, object]


def _visible_text(fig: matplotlib.figure.Figure) -> list[Text]:
    return [
        artist for artist in fig.findobj(Text) if artist.get_visible() and artist.get_text().strip()
    ]


def _intersection_fraction(a: object, b: object) -> float:
    x0 = max(a.x0, b.x0)
    y0 = max(a.y0, b.y0)
    x1 = min(a.x1, b.x1)
    y1 = min(a.y1, b.y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    smaller = min(max(a.width * a.height, 1e-12), max(b.width * b.height, 1e-12))
    return intersection / smaller


def audit_figure(
    fig: matplotlib.figure.Figure,
    *,
    min_font_pt: float = 5.0,
    max_free_text: int = 18,
) -> list[QualityIssue]:
    """Return high-confidence layout defects for one rendered figure object."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    issues: list[QualityIssue] = []
    figure_box = fig.bbox
    texts = _visible_text(fig)

    # Axis labels, tick labels, offset text and legends are layout-managed.
    managed_ids: set[int] = set()
    for axis in fig.axes:
        managed = [
            axis.title,
            axis.xaxis.label,
            axis.yaxis.label,
            axis.xaxis.get_offset_text(),
            axis.yaxis.get_offset_text(),
        ]
        managed.extend(axis.get_xticklabels())
        managed.extend(axis.get_yticklabels())
        legend = axis.get_legend()
        if legend is not None:
            managed.extend(legend.get_texts())
            managed_ids.add(id(legend.get_title()))
        managed_ids.update(id(item) for item in managed)

    free_texts = [text for text in texts if id(text) not in managed_ids]
    for text in texts:
        if text.get_fontsize() < min_font_pt:
            issues.append(
                QualityIssue(
                    "error",
                    "FONT_TOO_SMALL",
                    f"{text.get_text()!r}: {text.get_fontsize():.2f} pt",
                )
            )
        if text.get_bbox_patch() is not None:
            issues.append(
                QualityIssue(
                    "error",
                    "TEXT_BOX",
                    f"boxed annotation is forbidden: {text.get_text()!r}",
                )
            )

    # Free annotations are not protected by constrained-layout and must remain in-canvas.
    for text in free_texts:
        box = text.get_window_extent(renderer=renderer)
        if box.width > 0 and box.height > 0:
            tolerance = 4.0
            if (
                box.x0 < figure_box.x0 - tolerance
                or box.y0 < figure_box.y0 - tolerance
                or box.x1 > figure_box.x1 + tolerance
                or box.y1 > figure_box.y1 + tolerance
            ):
                issues.append(
                    QualityIssue(
                        "error",
                        "TEXT_CLIPPED",
                        f"text extends beyond canvas: {text.get_text()!r}",
                    )
                )

    if len(free_texts) > max_free_text:
        issues.append(
            QualityIssue(
                "error",
                "ANNOTATION_DENSITY",
                f"{len(free_texts)} free text artists exceed limit {max_free_text}",
            )
        )

    free_boxes = [(text, text.get_window_extent(renderer=renderer)) for text in free_texts]
    for (left, left_box), (right, right_box) in combinations(free_boxes, 2):
        if _intersection_fraction(left_box, right_box) > 0.15:
            issues.append(
                QualityIssue(
                    "error",
                    "TEXT_OVERLAP",
                    f"{left.get_text()!r} overlaps {right.get_text()!r}",
                )
            )

    return issues


def check_png(path: Path, *, width_mm: float, height_mm: float, dpi: int = 600) -> FileCheck:
    with Image.open(path) as image:
        expected = (
            round(width_mm / MM_PER_INCH * dpi),
            round(height_mm / MM_PER_INCH * dpi),
        )
        actual = image.size
        dpi_info = image.info.get("dpi")
    dimensions_ok = abs(actual[0] - expected[0]) <= 1 and abs(actual[1] - expected[1]) <= 1
    dpi_ok = (
        isinstance(dpi_info, tuple)
        and len(dpi_info) == 2
        and all(abs(float(value) - dpi) <= 1.0 for value in dpi_info)
    )
    return FileCheck(
        str(path),
        dimensions_ok and dpi_ok,
        {
            "actual_px": actual,
            "expected_px": expected,
            "embedded_dpi": dpi_info,
            "dpi_ok": dpi_ok,
        },
    )


def _font_is_embedded(font: object) -> bool:
    resolved = font.get_object()
    descendants = resolved.get("/DescendantFonts")
    if descendants:
        return all(_font_is_embedded(item) for item in descendants)
    descriptor = resolved.get("/FontDescriptor")
    if descriptor is None:
        return False
    descriptor = descriptor.get_object()
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def check_pdf(path: Path, *, width_mm: float, height_mm: float) -> FileCheck:
    reader = PdfReader(str(path))
    if len(reader.pages) != 1:
        return FileCheck(str(path), False, {"pages": len(reader.pages)})
    page = reader.pages[0]
    box = page.mediabox
    actual_mm = (
        float(box.width) / 72.0 * MM_PER_INCH,
        float(box.height) / 72.0 * MM_PER_INCH,
    )
    resources = page.get("/Resources", {}).get_object()
    fonts = resources.get("/Font", {}).get_object()
    font_records = {str(name): _font_is_embedded(font) for name, font in fonts.items()}
    metadata = dict(reader.metadata or {})
    timestamp_keys = {"/CreationDate", "/ModDate"}
    has_timestamp_metadata = any(key in metadata for key in timestamp_keys)
    dimensions_ok = abs(actual_mm[0] - width_mm) <= 1.0 and abs(actual_mm[1] - height_mm) <= 1.0
    fonts_ok = bool(font_records) and all(font_records.values())
    ok = dimensions_ok and fonts_ok and not has_timestamp_metadata
    return FileCheck(
        str(path),
        ok,
        {
            "actual_mm": actual_mm,
            "expected_mm": (width_mm, height_mm),
            "embedded_fonts": font_records,
            "timestamp_metadata": has_timestamp_metadata,
        },
    )


def check_svg(path: Path, *, width_mm: float, height_mm: float) -> FileCheck:
    text = path.read_text(encoding="utf-8")
    width_match = re.search(r'<svg[^>]*width="([0-9.]+)pt"', text)
    height_match = re.search(r'<svg[^>]*height="([0-9.]+)pt"', text)
    has_editable_text = "<text" in text
    has_timestamp_metadata = "<dc:date>" in text
    if not width_match or not height_match:
        return FileCheck(str(path), False, {"reason": "missing SVG point dimensions"})
    actual_mm = (
        float(width_match.group(1)) / 72.0 * MM_PER_INCH,
        float(height_match.group(1)) / 72.0 * MM_PER_INCH,
    )
    ok = (
        abs(actual_mm[0] - width_mm) <= 1.0
        and abs(actual_mm[1] - height_mm) <= 1.0
        and has_editable_text
        and not has_timestamp_metadata
    )
    return FileCheck(
        str(path),
        ok,
        {
            "actual_mm": actual_mm,
            "expected_mm": (width_mm, height_mm),
            "editable_text": has_editable_text,
            "timestamp_metadata": has_timestamp_metadata,
        },
    )


def checks_to_dict(checks: Iterable[FileCheck]) -> list[dict[str, object]]:
    return [asdict(item) for item in checks]
