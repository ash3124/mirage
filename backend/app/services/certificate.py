"""Generate a self-generated Mirage photo protection record PDF."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as ReportImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..schemas import CloakResult
from .utils import load_rgb_image

if TYPE_CHECKING:
    from ..jobs import JobRecord

TOOL_VERSION = "1.0.0"
DISCLAIMER = (
    "Self-generated record. Not a legal notarization. Keep your original files."
)


def _thumbnail(path: Path) -> BytesIO:
    image = load_rgb_image(path)
    image.thumbnail((82 * mm, 82 * mm), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def create_certificate(
    record: "JobRecord",
    image_directory: str | Path,
    owner_name: str | None = None,
) -> bytes:
    """Return a PDF certificate for a completed cloak job."""
    if not isinstance(record.result, CloakResult):
        raise ValueError("A completed cloak job result is required.")

    result = record.result
    image_directory = Path(image_directory)
    original_path = image_directory / "original.png"
    cloaked_path = image_directory / "cloaked.png"

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Photo Protection Record",
        author="Mirage",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MirageTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#26324A"),
        spaceAfter=8 * mm,
    )
    body_style = styles["BodyText"]
    elements = [
        Paragraph("Photo Protection Record", title_style),
    ]

    thumbnails = [
        ReportImage(_thumbnail(original_path), width=78 * mm, height=65 * mm),
        ReportImage(_thumbnail(cloaked_path), width=78 * mm, height=65 * mm),
    ]
    thumbnail_table = Table(
        [[thumbnails[0], thumbnails[1]], ["Original", "Cloaked"]],
        colWidths=[82 * mm, 82 * mm],
        hAlign="CENTER",
    )
    thumbnail_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#26324A")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3 * mm),
                ("TOPPADDING", (0, 1), (-1, 1), 2 * mm),
            ]
        )
    )
    elements.extend([thumbnail_table, Spacer(1, 9 * mm)])

    metadata = [
        ("SHA-256 (cloaked)", result.hashes.sha256_cloaked),
        ("pHash (original)", result.hashes.phash_original),
        ("UTC timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        ("Strength", record.strength.value if record.strength else "standard"),
        ("Tool version", TOOL_VERSION),
    ]
    if owner_name:
        metadata.insert(0, ("Owner name", owner_name))
    if record.owner_tag:
        metadata.append(("Watermark tag", record.owner_tag))

    rows = [
        [
            Paragraph(f"<b>{escape(label)}</b>", body_style),
            Paragraph(escape(value), body_style),
        ]
        for label, value in metadata
    ]
    details_table = Table(rows, colWidths=[43 * mm, 120 * mm], hAlign="LEFT")
    details_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6DAE2")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F4F8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    elements.extend([details_table, Spacer(1, 12 * mm)])
    elements.append(
        Paragraph(
            f"<i>{escape(DISCLAIMER)}</i>",
            ParagraphStyle(
                "MirageDisclaimer",
                parent=body_style,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#5B6474"),
            ),
        )
    )

    document.build(elements)
    return output.getvalue()
