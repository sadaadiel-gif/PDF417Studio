from pdf417gen import encode as pdf417_encode, render_image as pdf417_render


def generate_barcode(
    data,          # str or bytes
    columns: int = 5,
    scale:   int = 3,
    ratio:   int = 3,
    padding: int = 2,
    rows:    int = 0,
):
    if isinstance(data, bytes):
        text = data.decode('utf-8')
    else:
        text = data

    codes = pdf417_encode(text, columns=columns)

    if rows > 0 and len(codes) != rows:
        for c in range(1, 31):
            trial = pdf417_encode(text, columns=c)
            if len(trial) >= rows:
                codes = trial
                break

    return pdf417_render(codes, scale=scale, ratio=ratio, padding=padding)


def pdf417_row_count(text: str, columns: int) -> int:
    return len(pdf417_encode(text, columns=columns))


def generate_code128(
    text:       str,
    bar_width:  float = 1.0,
    bar_height: float = 10.0,
    dpi:        int   = 300,
) -> "PIL.Image.Image":
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
        "font_size":     0,
        "text_distance": 0,
        "dpi":           dpi,
        "write_text":    False,
    }

    buf = BytesIO()
    code.write(buf, options=options)
    buf.seek(0)

    from PIL import Image
    return Image.open(buf).copy()