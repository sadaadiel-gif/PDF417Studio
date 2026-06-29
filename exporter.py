import os
import tempfile

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4

from settings import EXPORT_IMG_WIDTH, EXPORT_IMG_HEIGHT


def save_png(img, path: str) -> None:
    img.save(path)


_MARGIN_PT   = 36
_LABEL_GAP   = 14
_FONT_NAME   = "Helvetica"
_FONT_SIZE   = 11

_IMG_W_PT = EXPORT_IMG_WIDTH
_IMG_H_PT = EXPORT_IMG_HEIGHT


def export_pdf(img, path: str, title: str = "PDF417 Barcode") -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(tmp_fd)
        img.save(tmp_path, format="PNG")

        page_w, page_h = A4

        c = canvas.Canvas(path, pagesize=A4)

        title_x = _MARGIN_PT
        title_y = page_h - _MARGIN_PT
        c.setFont(_FONT_NAME + "-Bold", _FONT_SIZE)
        c.drawString(title_x, title_y, title)

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

        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.5)
        c.rect(img_x, img_y, _IMG_W_PT, _IMG_H_PT)

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