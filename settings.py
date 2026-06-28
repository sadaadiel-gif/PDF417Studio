DEFAULT_COLUMNS = 5
DEFAULT_SCALE   = 3
WINDOW_TITLE    = "PDF417 Studio"

# ── Preview / export canvas dimensions (shared by preview.py & exporter.py) ──
PREVIEW_MAX_WIDTH  = 560   # px  — max display width in the GUI preview
PREVIEW_MAX_HEIGHT = 220   # px  — max display height in the GUI preview

# Exported PDF canvas dimensions match the preview so WYSIWYG
EXPORT_IMG_WIDTH  = PREVIEW_MAX_WIDTH
EXPORT_IMG_HEIGHT = PREVIEW_MAX_HEIGHT

# ── AAMVA DL/ID Card Design Standard – physical constraints ─────────────────
# Ref: AAMVA DL/ID Card Design Standard, Section 2.7 (PDF417 barcode specs)

AAMVA_MAX_WIDTH_MM   = 75.565   # 2.975 in  — hard upper limit
AAMVA_MAX_HEIGHT_MM  = 38.100   # 1.50  in  — hard upper limit

# X-dimension (narrowest bar / module width)
AAMVA_X_MIN_MM   = 0.170        # 6.69 mils
AAMVA_X_MAX_MM   = 0.380        # 14.96 mils
AAMVA_X_MIN_MILS = 6.6          # 0.168 mm  (standard rounds to 6.6)
AAMVA_X_MAX_MILS = 15.0         # 0.381 mm  (standard rounds to 15)

# Row height must be at least 3× the X-dimension
AAMVA_Y_X_RATIO_MIN  = 3

# Quiet zone: ≥ 1X required, 2X strongly recommended
AAMVA_QUIET_ZONE_MIN = 1
AAMVA_QUIET_ZONE_REC = 2

# Prohibited compact variants
AAMVA_PROHIBITED = ("MicroPDF417", "Truncated PDF417")