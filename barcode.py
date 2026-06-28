"""
barcode.py
Barcode generation helpers for PDF417 Studio.

PDF417  — via pdf417gen
Code128 — via python-barcode (renders to Pillow Image)
"""

from pdf417gen import encode as pdf417_encode, render_image as pdf417_render


# ── PDF417 ────────────────────────────────────────────────────────────────────

def generate_barcode(
    text:    str,
    columns: int = 5,
    scale:   int = 3,          # narrow bar width in pixels (X-dimension)
    ratio:   int = 3,          # bar height = ratio × scale  (AAMVA min = 3)
    padding: int = 2,          # quiet-zone in modules
    rows:    int = 0,          # 0 = auto; >0 forces that many rows
):
    """
    Encode *text* as a PDF417 barcode and return a Pillow Image.

    Parameters
    ----------
    text    : payload string (AAMVA or arbitrary)
    columns : data columns  (AAMVA typically 4–10; 1–30 valid)
    scale   : pixel width of the narrowest bar  (X-dimension in px)
    ratio   : row height ÷ module width  (AAMVA minimum = 3)
    padding : quiet-zone thickness in modules
    rows    : force a specific row count (0 = let the library decide)
    """
    codes = pdf417_encode(text, columns=columns)

    # If a row count is requested and differs from what was generated,
    # re-encode with enough columns to hit the target row count.
    # pdf417gen doesn't expose a rows= param, so we iterate columns down
    # until len(codes) >= rows, then truncate — or just use as-is if rows=0.
    if rows > 0 and len(codes) != rows:
        # Try to find a column count that yields the requested row count
        for c in range(1, 31):
            trial = pdf417_encode(text, columns=c)
            if len(trial) >= rows:
                codes = trial
                break

    return pdf417_render(codes, scale=scale, ratio=ratio, padding=padding)


def pdf417_row_count(text: str, columns: int) -> int:
    """Return the number of rows pdf417gen would produce for *text*."""
    return len(pdf417_encode(text, columns=columns))


# ── Code 128 ─────────────────────────────────────────────────────────────────

def generate_code128(
    text:       str,
    bar_width:  float = 1.0,   # narrowest bar width in mm
    bar_height: float = 10.0,  # bar height in mm
    dpi:        int   = 300,
) -> "PIL.Image.Image":
    """
    Render *text* as a Code 128 barcode and return a Pillow Image.

    Requires the 'python-barcode' and 'Pillow' packages.
    """
    try:
        import barcode as _bc
        from barcode.writer import ImageWriter
    except ImportError:
        raise ImportError(
            "python-barcode is required for Code 128 generation.\n"
            "Run:  pip install python-barcode"
        )

    from io import BytesIO

    writer = ImageWriter()
    code   = _bc.get("code128", text, writer=writer)

    options = {
        "module_width":  bar_width,
        "module_height": bar_height,
        "quiet_zone":    2.0,
        "font_size":     0,        # no text under barcode
        "text_distance": 0,
        "dpi":           dpi,
        "write_text":    False,
    }

    buf = BytesIO()
    code.write(buf, options=options)
    buf.seek(0)

    from PIL import Image
    return Image.open(buf).copy()   # .copy() detaches from the BytesIO buffer