"""
exporter.py
Save barcode images to PNG/JPEG/BMP or embed them in a single-page PDF.

The PDF canvas size (EXPORT_IMG_WIDTH × EXPORT_IMG_HEIGHT) is imported from
settings so it matches the preview widget exactly — what you see is what
you get in the exported document.
"""

import os
import tempfile

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4

from settings import EXPORT_IMG_WIDTH, EXPORT_IMG_HEIGHT


# ── PNG / raster ────────────────────────────────────────────────────────────

def save_png(img, path: str) -> None:
    """Save *img* (Pillow Image) to *path* as PNG."""
    img.save(path)


# ── PDF ─────────────────────────────────────────────────────────────────────

# Margins & layout (points; 1 pt = 1/72 in)
_MARGIN_PT   = 36          # 0.5 in margin on all sides
_LABEL_GAP   = 14          # gap between title and barcode image (pt)
_FONT_NAME   = "Helvetica"
_FONT_SIZE   = 11

# The barcode image box on the PDF page mirrors the preview canvas exactly
_IMG_W_PT = EXPORT_IMG_WIDTH   # 1 px ≈ 1 pt at 72 DPI — consistent with preview
_IMG_H_PT = EXPORT_IMG_HEIGHT


def export_pdf(img, path: str, title: str = "PDF417 Barcode") -> None:
    """
    Embed *img* (Pillow Image) in a single-page PDF at *path*.

    Layout
    ------
    • Page size  : A4 portrait
    • Title text : top-left, Helvetica 11
    • Barcode    : below title, width=EXPORT_IMG_WIDTH pt, height=EXPORT_IMG_HEIGHT pt
                   (same proportions as the on-screen preview)
    • Footer     : bottom-left, file path + page number
    """
    # Write barcode to a temp PNG so ReportLab can embed it
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(tmp_fd)
        img.save(tmp_path, format="PNG")

        page_w, page_h = A4  # 595 × 842 pt

        c = canvas.Canvas(path, pagesize=A4)

        # ── Title ─────────────────────────────────────────────────────────
        title_x = _MARGIN_PT
        title_y = page_h - _MARGIN_PT
        c.setFont(_FONT_NAME + "-Bold", _FONT_SIZE)
        c.drawString(title_x, title_y, title)

        # ── Barcode image ─────────────────────────────────────────────────
        img_x = _MARGIN_PT
        img_y = title_y - _LABEL_GAP - _IMG_H_PT
        c.drawImage(
            tmp_path,
            img_x, img_y,
            width=_IMG_W_PT,
            height=_IMG_H_PT,
            preserveAspectRatio=True,
            anchor="c",
        )

        # ── Border around image (matches preview sunken relief) ───────────
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.5)
        c.rect(img_x, img_y, _IMG_W_PT, _IMG_H_PT)

        # ── Footer ────────────────────────────────────────────────────────
        c.setFont(_FONT_NAME, 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(_MARGIN_PT, _MARGIN_PT / 2,
                     f"{os.path.abspath(path)}  |  Page 1")

        c.save()

    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass