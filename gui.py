"""
gui.py
PDF417 Studio — main window.

Tabs
----
  Information  — AAMVA field entry + output text
  PDF417       — barcode settings + preview
  Code 128     — Code 128 generator + preview
  Scanner      — paste / load raw barcode text and parse AAMVA fields back
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from aamva import AAMVAData, AAMVABuilder
from barcode import generate_barcode, generate_code128, pdf417_row_count
from preview import BarcodePreview
from exporter import export_pdf, save_png
from mrz_engine import default_pipeline, default_td3_pipeline, default_universal_pipeline, MRZTransliterator
from models import RawTD1Document, RawTD2Document, RawTD3Document
from exceptions import MRZError
from settings import (
    DEFAULT_COLUMNS, DEFAULT_SCALE, WINDOW_TITLE,
    AAMVA_MAX_WIDTH_MM, AAMVA_MAX_HEIGHT_MM,
    AAMVA_X_MIN_MILS, AAMVA_X_MAX_MILS,
    AAMVA_Y_X_RATIO_MIN, AAMVA_QUIET_ZONE_REC,
)

_SEX_OPTIONS = ["1 – M", "2 – F", "9 – X"]
_SEX_WIRE    = {"1 – M": "1", "2 – F": "2", "9 – X": "9"}

_STATE_IIN = {
    # ── US States ────────────────────────────────────────────────────────────
    "VA": "636000",   # Virginia
    "NY": "636001",   # New York
    "MA": "636002",   # Massachusetts
    "MD": "636003",   # Maryland
    "NC": "636004",   # North Carolina
    "SC": "636005",   # South Carolina
    "CT": "636006",   # Connecticut
    "LA": "636007",   # Louisiana
    "MT": "636008",   # Montana
    "NM": "636009",   # New Mexico  (some sources 636013 — using official AAMVA value)
    "FL": "636010",   # Florida
    "DE": "636011",   # Delaware
    "CA": "636014",   # California
    "TX": "636015",   # Texas
    "IA": "636018",   # Iowa
    "CO": "636020",   # Colorado
    "AR": "636021",   # Arkansas
    "KS": "636022",   # Kansas
    "OH": "636023",   # Ohio
    "VT": "636024",   # Vermont
    "PA": "636025",   # Pennsylvania
    "AZ": "636026",   # Arizona
    "OR": "636029",   # Oregon
    "MO": "636030",   # Missouri
    "WI": "636031",   # Wisconsin
    "MI": "636032",   # Michigan
    "AL": "636033",   # Alabama
    "IL": "636035",   # Illinois
    "NJ": "636036",   # New Jersey
    "IN": "636037",   # Indiana
    "MN": "636038",   # Minnesota
    "NH": "636039",   # New Hampshire
    "UT": "636040",   # Utah
    "ME": "636041",   # Maine
    "SD": "636042",   # South Dakota
    "DC": "636043",   # District of Columbia
    "WA": "636045",   # Washington
    "KY": "636046",   # Kentucky
    "HI": "636047",   # Hawaii
    "NV": "636049",   # Nevada
    "ID": "636050",   # Idaho
    "MS": "636051",   # Mississippi
    "RI": "636052",   # Rhode Island
    "TN": "636053",   # Tennessee
    "NE": "636054",   # Nebraska
    "GA": "636055",   # Georgia
    "OK": "636058",   # Oklahoma
    "AK": "636059",   # Alaska
    "WY": "636060",   # Wyoming
    "WV": "636061",   # West Virginia
    "VI": "636062",   # U.S. Virgin Islands
    # States not yet in the official AAMVA published list (placeholder)
    "ND": "636034",   # North Dakota
    "WY": "636060",   # Wyoming (duplicate safety)
}

# Reverse IIN → state name for scanner display
_IIN_STATE = {v: k for k, v in _STATE_IIN.items()}

# All known AAMVA DL element tags → human label
_AAMVA_TAGS = {
    "DAQ": "License Number",
    "DCS": "Last Name",
    "DAC": "First Name",
    "DBC": "First Name / Sex",
    "DAD": "Middle Name",
    "DBB": "Date of Birth",
    "DBA": "Expiry Date",
    "DBD": "Issue Date",
    "DBC": "Sex",
    "DAG": "Address",
    "DAI": "City",
    "DAJ": "State",
    "DAK": "ZIP Code",
    "DAU": "Height",
    "DAY": "Eye Colour",
    "DAB": "Hair Colour",
    "DCA": "License Class",
    "DAW": "Weight",
    "DCF": "Document Discriminator",
    "DCG": "Country",
    "DDA": "Compliance Type",
    "DDK": "Donor",
    "DDB": "Card Revision Date",
    "DAT": "Endorsement",
    "DCK": "Inventory",
    "DAR": "Restriction",
    "DCL": "Race / Ethnicity",
    "DCJ": "Audit Information",
    "DAR": "Restrictions",
    "DAE": "Name Suffix",
    "DAF": "Name Prefix",
    "DBF": "Alias Last Name",
    "DBG": "Alias First Name",
    "DBI": "Alias Middle Name",
    "DCB": "Restriction Code",
    "DCC": "Endorsement Code",
    "DCD": "Status Code",
    "DCE": "Weight Range",
    "DCH": "Federal Commercial Vehicle Code",
    "DCI": "Place of Birth",
    "DCM": "Standard Vehicle Code",
}


def _lbl(parent, text, **kw):
    return ttk.Label(parent, text=text, **kw)

def _entry(parent, var=None, width=None, **kw):
    kw2 = dict(kw)
    if var:   kw2["textvariable"] = var
    if width: kw2["width"] = width
    return ttk.Entry(parent, **kw2)

def _combo(parent, var, values, width=6):
    return ttk.Combobox(parent, textvariable=var, values=values,
                        width=width, state="readonly")

def _spin(parent, var, from_, to, width=5):
    return tk.Spinbox(parent, textvariable=var, from_=from_, to=to,
                      width=width, increment=1)


def _resource(filename: str) -> str:
    """Return absolute path to a bundled resource (works frozen + dev)."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundles everything flat into _MEIPASS
        base = sys._MEIPASS
    else:
        # Running from source — assets live in the assets/ subfolder
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    return os.path.join(base, filename)


# ─────────────────────────────────────────────────────────────────────────────

class PDF417Studio:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("980x720")
        self.root.resizable(True, True)

        self._set_icons()

        self._opt_vars: dict[str, tk.BooleanVar] = {}
        self._build_ui()

    # ── icon / logo ──────────────────────────────────────────────────────────

    def _set_icons(self):
        """
        Set the window icon (titlebar + taskbar) and embed the logo in the
        top toolbar strip.

        Works in three environments:
          • Windows .exe (PyInstaller): iconbitmap via .ico
          • Windows dev:               iconbitmap via .ico
          • Linux / macOS dev:         iconphoto via .png (no .ico support)
        """
        from PIL import Image, ImageTk

        # ── taskbar / titlebar icon ──────────────────────────────────────
        ico_path = _resource("app.ico")
        png_path = _resource("logo.png")

        try:
            if sys.platform == "win32" and os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                img = Image.open(png_path).resize((64, 64), Image.LANCZOS)
                self._icon_img = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            pass   # silently ignore if icon files are missing

        # ── toolbar logo strip ───────────────────────────────────────────
        if os.path.exists(png_path):
            try:
                logo_img = Image.open(png_path).resize((36, 36), Image.LANCZOS)
                self._logo_tk = ImageTk.PhotoImage(logo_img)

                toolbar = tk.Frame(self.root, bg="#1a1a2e", height=46)
                toolbar.pack(fill="x", side="top")
                toolbar.pack_propagate(False)

                tk.Label(toolbar, image=self._logo_tk,
                         bg="#1a1a2e").pack(side="left", padx=(8, 4), pady=5)
                tk.Label(toolbar, text="PDF417 Studio",
                         bg="#1a1a2e", fg="white",
                         font=("Helvetica", 14, "bold")).pack(side="left", pady=5)
            except Exception:
                pass

    # ── top-level UI ─────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=4, pady=4)

        self.tab_info      = ttk.Frame(self.nb)
        self.tab_pdf417    = ttk.Frame(self.nb)
        self.tab_code128   = ttk.Frame(self.nb)
        self.tab_scanner   = ttk.Frame(self.nb)
        self.tab_mrz       = ttk.Frame(self.nb)
        self.tab_downloads = ttk.Frame(self.nb)
        self.tab_security  = ttk.Frame(self.nb)

        self.nb.add(self.tab_info,      text="Information")
        self.nb.add(self.tab_pdf417,    text="PDF417")
        self.nb.add(self.tab_code128,   text="Code 128")
        self.nb.add(self.tab_scanner,   text="🔍 Scanner")
        self.nb.add(self.tab_mrz,       text="🪪 MRZ")
        self.nb.add(self.tab_downloads, text="⬇ Downloads")
        self.nb.add(self.tab_security,  text="🔒 Security")

        self._build_information_tab()
        self._build_pdf417_tab()
        self._build_code128_tab()
        self._build_scanner_tab()
        self._build_mrz_tab()
        self._build_downloads_tab()
        self._build_security_tab()

    # ═══════════════════════════════════════════════ Tab 1 — Information

    def _build_information_tab(self):
        root = ttk.Frame(self.tab_info, padding=6)
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="both", expand=True)

        self._build_main_info(top)
        self._build_output_panel(top)
        self._build_optional_section(root)

    def _build_main_info(self, parent):
        lf = ttk.LabelFrame(parent, text="Main Information", padding=8)
        lf.pack(side="left", fill="both", expand=True, padx=(0, 6))
        g = lf

        _lbl(g, "IIN  (State)").grid(row=0, column=0, sticky="w")
        _lbl(g, "Ver").grid(row=0, column=1, sticky="w", padx=(6,0))
        _lbl(g, "Jur").grid(row=0, column=2, sticky="w", padx=(6,0))
        _lbl(g, "Subfile Len").grid(row=0, column=3, sticky="w", padx=(6,0))
        _lbl(g, "First Tag").grid(row=0, column=4, sticky="w", padx=(6,0))

        # IIN dropdown — sorted by state abbreviation, shows "636025 — PA"
        _IIN_OPTIONS = sorted(
            [f"{iin}  —  {state}" for state, iin in _STATE_IIN.items()],
            key=lambda x: x.split("—")[1].strip()
        )
        self._iin_var = tk.StringVar(value="636000  —  VA")
        self.issuer_id_combo = ttk.Combobox(
            g, textvariable=self._iin_var,
            values=_IIN_OPTIONS, width=16, state="normal"
        )
        self.issuer_id_combo.grid(row=1, column=0, sticky="ew")
        self._iin_var.trace_add("write", self._on_iin_change)

        # Keep a plain entry reference for aamva builder (holds just the 6-digit IIN)
        self.issuer_id = self.issuer_id_combo   # alias so _collect_fields still works
        self.version = _entry(g, width=4)
        self.version.insert(0, "01")
        self.version.grid(row=1, column=1, sticky="ew", padx=(6,0))
        self.jurisdiction = _entry(g, width=4)
        self.jurisdiction.insert(0, "01")
        self.jurisdiction.grid(row=1, column=2, sticky="ew", padx=(6,0))
        self.subfile_length_var = tk.StringVar(value="0278")
        self.subfile_length = ttk.Combobox(
            g, textvariable=self.subfile_length_var,
            values=[
                "0278",   # PA, most common
                "0256",   # VA, NC, SC
                "0300",   # CA, TX, FL
                "0320",   # NY, IL
                "0350",   # GA, OH, MI
                "0400",   # WA, OR
                "0200",   # minimal / test
            ],
            width=6, state="normal"
        )
        self.subfile_length.grid(row=1, column=3, sticky="ew", padx=(6,0))
        self.first_tag_var = tk.StringVar(value="DAC")
        _combo(g, self.first_tag_var, ["DAC", "DBC"], width=5).grid(
            row=1, column=4, sticky="ew", padx=(6,0))

        _lbl(g, "First").grid(row=2, column=0, sticky="w", pady=(6,0))
        _lbl(g, "Middle").grid(row=2, column=1, sticky="w", padx=(6,0), pady=(6,0))
        _lbl(g, "Last").grid(row=2, column=2, sticky="w", padx=(6,0), pady=(6,0))

        self.first  = _entry(g, width=14); self.first.grid(row=3, column=0, sticky="ew")
        self.middle = _entry(g, width=10); self.middle.grid(row=3, column=1, sticky="ew", padx=(6,0))
        self.last   = _entry(g, width=16); self.last.grid(row=3, column=2, sticky="ew", padx=(6,0))

        _lbl(g, "License Num").grid(row=4, column=0, sticky="w", pady=(6,0))
        _lbl(g, "Sex").grid(row=4, column=1, sticky="w", padx=(6,0), pady=(6,0))
        _lbl(g, "Class").grid(row=4, column=2, sticky="w", padx=(6,0), pady=(6,0))

        self.lic = _entry(g, width=14); self.lic.grid(row=5, column=0, sticky="ew")
        self.sex_var = tk.StringVar(value="1 – M")
        _combo(g, self.sex_var, _SEX_OPTIONS, width=8).grid(row=5, column=1, sticky="ew", padx=(6,0))
        self.cls = _entry(g, width=10); self.cls.grid(row=5, column=2, sticky="ew", padx=(6,0))

        _lbl(g, "Birth Date (MMDDYYYY)").grid(row=6, column=0, sticky="w", pady=(6,0))
        _lbl(g, "Exp Date (MMDDYYYY)").grid(row=6, column=1, sticky="w", padx=(6,0), pady=(6,0))
        _lbl(g, "Issue Date (MMDDYYYY)").grid(row=6, column=2, sticky="w", padx=(6,0), pady=(6,0))

        self.birth = _entry(g, width=14); self.birth.grid(row=7, column=0, sticky="ew")
        self.exp   = _entry(g, width=14); self.exp.grid(row=7, column=1, sticky="ew", padx=(6,0))
        self.issue = _entry(g, width=14); self.issue.grid(row=7, column=2, sticky="ew", padx=(6,0))

        _lbl(g, "Address").grid(row=8, column=0, sticky="w", pady=(6,0))
        _lbl(g, "City").grid(row=8, column=2, sticky="w", padx=(6,0), pady=(6,0))

        self.address = _entry(g); self.address.grid(row=9, column=0, columnspan=2, sticky="ew")
        self.city    = _entry(g); self.city.grid(row=9, column=2, sticky="ew", padx=(6,0))

        _lbl(g, "State").grid(row=10, column=0, sticky="w", pady=(6,0))
        _lbl(g, "Zip Code").grid(row=10, column=1, sticky="w", padx=(6,0), pady=(6,0))

        self.state_var = tk.StringVar()
        state_list = [
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
            "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
            "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
            "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
            "WI","WY","DC",
        ]
        state_cb = _combo(g, self.state_var, state_list, width=6)
        state_cb.grid(row=11, column=0, sticky="w")
        self.state_var.trace_add("write", self._on_state_change)

        self.zip = _entry(g, width=12); self.zip.grid(row=11, column=1, sticky="ew", padx=(6,0))

        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)
        g.columnconfigure(2, weight=2)

    def _build_output_panel(self, parent):
        lf = ttk.LabelFrame(parent, text="Output", padding=8)
        lf.pack(side="left", fill="both", expand=True)

        self.output = tk.Text(lf, height=12, font=("Courier", 9), wrap="none")
        sb_y = ttk.Scrollbar(lf, orient="vertical",   command=self.output.yview)
        sb_x = ttk.Scrollbar(lf, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side="right",  fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.output.pack(fill="both", expand=True)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="Generate", command=self.generate_aamva).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="Copy",     command=self.copy_output).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="About",    command=self._about).pack(side="left")

    def _build_optional_section(self, parent):
        lf = ttk.LabelFrame(parent, text="Optional", padding=8)
        lf.pack(fill="x", pady=(6, 0))

        self.eyes       = self._opt_field(lf, "Eyes",              0, 0, 6)
        self._opt_check(lf, "Height", 2, 0)
        self.height     = _entry(lf, width=5)
        self.height.grid(row=1, column=2, sticky="w", padx=(8,2))
        ttk.Label(lf, text="in″", foreground="#888").grid(row=1, column=3, sticky="w")
        self.weight     = self._opt_field(lf, "Weight",            4, 0, 6)
        self.hair       = self._opt_field(lf, "Hair",              6, 0, 6)
        self.compliance = self._opt_field(lf, "Compliance Type",   8, 0, 6)

        self.donor_var = tk.BooleanVar()
        donor_cb = ttk.Frame(lf); donor_cb.grid(row=0, column=10, sticky="w", padx=4)
        self._opt_vars["donor_check"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(donor_cb, text="Donor", variable=self._opt_vars["donor_check"]).pack(side="left")
        self.donor_val = tk.BooleanVar()
        ttk.Checkbutton(donor_cb, variable=self.donor_val).pack(side="left")

        self.card_rev    = self._opt_field(lf, "Card Revision Date", 12, 0, 10)
        self.endorsement = self._opt_field(lf, "Endorsement",         0, 2, 8)
        self.inventory   = self._opt_field(lf, "Inventory",            4, 2, 14)
        self.discriminator = self._opt_field(lf, "Discriminator",      8, 2, 14)
        self.restriction = self._opt_field(lf, "Restriction",         12, 2, 8)
        self.race        = self._opt_field(lf, "Race/Ethnicity",      16, 2, 8)
        self.audit       = self._opt_field(lf, "Audit Information",   20, 2, 10)

    def _opt_check(self, parent, label, col, row):
        var = tk.BooleanVar(value=True)
        self._opt_vars[label] = var
        ttk.Checkbutton(parent, text=label, variable=var).grid(
            row=row, column=col, sticky="w", padx=(8, 2))
        return var

    def _opt_field(self, parent, label, col, row, width=8):
        var = tk.BooleanVar(value=True)
        self._opt_vars[label] = var
        ttk.Checkbutton(parent, text=label, variable=var).grid(
            row=row, column=col, sticky="w", padx=(8, 2))
        e = _entry(parent, width=width)
        e.grid(row=row+1, column=col, sticky="ew", padx=(8, 2))
        return e

    # ═══════════════════════════════════════════════ Tab 2 — PDF417

    def _build_pdf417_tab(self):
        root = ttk.Frame(self.tab_pdf417, padding=6)
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="x")

        out_lf = ttk.LabelFrame(top, text="Output", padding=8)
        out_lf.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.output2 = tk.Text(out_lf, height=6, font=("Courier", 9), wrap="none")
        sb2 = ttk.Scrollbar(out_lf, orient="vertical", command=self.output2.yview)
        self.output2.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        self.output2.pack(fill="both", expand=True)

        btn2 = ttk.Frame(out_lf)
        btn2.pack(fill="x", pady=(4,0))
        ttk.Button(btn2, text="Generate", command=self.generate_aamva).pack(side="left", padx=(0,4))
        ttk.Button(btn2, text="Copy",     command=self.copy_output).pack(side="left")

        bc_lf = ttk.LabelFrame(top, text="Barcode  [AAMVA DL/ID Standard]", padding=8)
        bc_lf.pack(side="left", fill="y")

        _lbl(bc_lf, "Bar Height").grid(row=0, column=0, sticky="w", pady=1)
        self.bar_height_var = tk.IntVar(value=3)
        _spin(bc_lf, self.bar_height_var, 1, 20, width=4).grid(row=0, column=1, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Narrow Bar Width").grid(row=0, column=2, sticky="w", padx=(14,0), pady=1)
        self.narrow_bar_var = tk.IntVar(value=3)
        _spin(bc_lf, self.narrow_bar_var, 1, 10, width=4).grid(row=0, column=3, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Column Count").grid(row=1, column=0, sticky="w", pady=1)
        self.col_count = tk.IntVar(value=DEFAULT_COLUMNS)
        _spin(bc_lf, self.col_count, 1, 30, width=4).grid(row=1, column=1, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Row Count").grid(row=1, column=2, sticky="w", padx=(14,0), pady=1)
        self.row_count_var = tk.IntVar(value=0)
        _spin(bc_lf, self.row_count_var, 0, 90, width=4).grid(row=1, column=3, padx=(6,0), sticky="w")
        _lbl(bc_lf, "(0 = auto)").grid(row=1, column=4, sticky="w", padx=(4,0), pady=1)

        _lbl(bc_lf, "DPI").grid(row=2, column=0, sticky="w", pady=1)
        self.dpi_var = tk.StringVar(value="300")
        _combo(bc_lf, self.dpi_var, ["150","200","300","600","1200"],
               width=6).grid(row=2, column=1, padx=(6,0), sticky="w")

        _lbl(bc_lf, "X-Dim (6.6–15 mils)").grid(row=2, column=2, sticky="w", padx=(14,0), pady=1)
        self.x_mils = tk.DoubleVar(value=10.0)
        _entry(bc_lf, var=self.x_mils, width=6).grid(row=2, column=3, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Y Ratio (≥3)").grid(row=3, column=0, sticky="w", pady=1)
        self.y_ratio = tk.IntVar(value=3)
        _spin(bc_lf, self.y_ratio, 3, 20, width=4).grid(row=3, column=1, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Quiet Zone (X, ≥2)").grid(row=3, column=2, sticky="w", padx=(14,0), pady=1)
        self.quiet_zone = tk.IntVar(value=AAMVA_QUIET_ZONE_REC)
        _spin(bc_lf, self.quiet_zone, 1, 10, width=4).grid(row=3, column=3, padx=(6,0), sticky="w")

        _lbl(bc_lf, "Error Correction Level").grid(row=4, column=0, sticky="w", pady=1)
        self.ecl_var = tk.StringVar(value="Level 5")
        _combo(bc_lf, self.ecl_var,
               ["Level 0","Level 1","Level 2","Level 3",
                "Level 4","Level 5","Level 6","Level 7","Level 8"],
               width=9).grid(row=4, column=1, columnspan=2, padx=(6,0), sticky="w")

        btn_row = ttk.Frame(bc_lf)
        btn_row.grid(row=5, column=0, columnspan=5, pady=(10,0), sticky="ew")
        ttk.Button(btn_row, text="AAMVA Preset",    command=self._apply_aamva_preset).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="Generate Barcode", command=self.generate_barcode).pack(side="left", padx=(0,4))
        ttk.Button(btn_row, text="Save Barcode",     command=self.save_barcode_png).pack(side="left")

        self._phys_var = tk.StringVar(value="")
        ttk.Label(bc_lf, textvariable=self._phys_var,
                  font=("Courier", 8), foreground="#333").grid(
            row=6, column=0, columnspan=5, pady=(6,0), sticky="w")

        prev_lf = ttk.LabelFrame(root, text="Preview", padding=8)
        prev_lf.pack(fill="both", expand=True, pady=(8,0))

        self.preview = BarcodePreview(prev_lf)
        self.preview.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════ Tab 3 — Code 128

    def _build_code128_tab(self):
        root = ttk.Frame(self.tab_code128, padding=10)
        root.pack(fill="both", expand=True)

        cfg_lf = ttk.LabelFrame(root, text="Code 128 Settings", padding=8)
        cfg_lf.pack(fill="x")

        _lbl(cfg_lf, "Text / Data").grid(row=0, column=0, sticky="w")
        self.c128_text_var = tk.StringVar()
        _entry(cfg_lf, var=self.c128_text_var, width=40).grid(
            row=0, column=1, columnspan=5, sticky="ew", padx=(6,0))

        _lbl(cfg_lf, "Narrow Bar Width (mm)").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.c128_bar_width = tk.DoubleVar(value=0.35)
        _entry(cfg_lf, var=self.c128_bar_width, width=6).grid(
            row=1, column=1, sticky="w", padx=(6,0), pady=(8,0))

        _lbl(cfg_lf, "Bar Height (mm)").grid(row=1, column=2, sticky="w", padx=(14,0), pady=(8,0))
        self.c128_bar_height = tk.DoubleVar(value=10.0)
        _entry(cfg_lf, var=self.c128_bar_height, width=6).grid(
            row=1, column=3, sticky="w", padx=(6,0), pady=(8,0))

        _lbl(cfg_lf, "DPI").grid(row=1, column=4, sticky="w", padx=(14,0), pady=(8,0))
        self.c128_dpi_var = tk.StringVar(value="300")
        _combo(cfg_lf, self.c128_dpi_var, ["150","200","300","600","1200"],
               width=6).grid(row=1, column=5, padx=(6,0), sticky="w", pady=(8,0))

        cfg_lf.columnconfigure(1, weight=1)

        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x", pady=(8,0))
        ttk.Button(btn_row, text="Generate Code 128", command=self.generate_code128_barcode).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Save Image…",        command=self._save_c128_image).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Download PDF…",      command=self._save_c128_pdf).pack(side="left")

        self._c128_status = tk.StringVar()
        ttk.Label(root, textvariable=self._c128_status,
                  font=("Courier", 8), foreground="#333").pack(anchor="w", pady=(4,0))

        prev_lf = ttk.LabelFrame(root, text="Preview", padding=8)
        prev_lf.pack(fill="both", expand=True, pady=(8,0))

        self.preview_c128 = BarcodePreview(prev_lf)
        self.preview_c128.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════ Tab 4 — Scanner

    def _build_scanner_tab(self):
        """
        Scanner tab: paste raw barcode text (from a USB wedge or manual entry),
        parse all AAMVA tags and display them in a structured table.
        Offers a 'Send to Information Tab' button to pre-fill the form.
        """
        root = ttk.Frame(self.tab_scanner, padding=10)
        root.pack(fill="both", expand=True)

        # ── Input area ────────────────────────────────────────────────────
        in_lf = ttk.LabelFrame(root, text="Raw Barcode Input", padding=8)
        in_lf.pack(fill="x")

        hint = (
            "Paste scanned barcode text here  (from a USB barcode wedge scanner,\n"
            "or copy from the Output box on the Information / PDF417 tab)."
        )
        _lbl(in_lf, hint, foreground="#555").pack(anchor="w", pady=(0,4))

        input_frame = ttk.Frame(in_lf)
        input_frame.pack(fill="x")

        self.scanner_input = tk.Text(input_frame, height=5,
                                     font=("Courier", 9), wrap="none")
        sb_scan_y = ttk.Scrollbar(input_frame, orient="vertical",
                                  command=self.scanner_input.yview)
        sb_scan_x = ttk.Scrollbar(input_frame, orient="horizontal",
                                  command=self.scanner_input.xview)
        self.scanner_input.configure(yscrollcommand=sb_scan_y.set,
                                     xscrollcommand=sb_scan_x.set)
        sb_scan_y.pack(side="right", fill="y")
        sb_scan_x.pack(side="bottom", fill="x")
        self.scanner_input.pack(fill="x", expand=True)

        btn_row = ttk.Frame(in_lf)
        btn_row.pack(fill="x", pady=(6,0))
        ttk.Button(btn_row, text="▶  Parse",
                   command=self._scanner_parse).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Load from Output tab",
                   command=self._scanner_load_from_output).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Clear",
                   command=self._scanner_clear).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="⇢  Send to Information Tab",
                   command=self._scanner_send_to_info).pack(side="right")

        # ── Status bar ────────────────────────────────────────────────────
        self._scan_status = tk.StringVar(value="Waiting for input…")
        ttk.Label(root, textvariable=self._scan_status,
                  font=("Helvetica", 9, "italic"),
                  foreground="#444").pack(anchor="w", pady=(6,2))

        # ── Parsed fields table ───────────────────────────────────────────
        tbl_lf = ttk.LabelFrame(root, text="Parsed Fields", padding=8)
        tbl_lf.pack(fill="both", expand=True, pady=(4,0))

        cols = ("tag", "field", "value")
        self._scan_tree = ttk.Treeview(tbl_lf, columns=cols,
                                       show="headings", selectmode="browse")
        self._scan_tree.heading("tag",   text="Tag")
        self._scan_tree.heading("field", text="Field Name")
        self._scan_tree.heading("value", text="Value")
        self._scan_tree.column("tag",   width=55,  stretch=False)
        self._scan_tree.column("field", width=200, stretch=False)
        self._scan_tree.column("value", width=400, stretch=True)

        tree_sb_y = ttk.Scrollbar(tbl_lf, orient="vertical",
                                  command=self._scan_tree.yview)
        self._scan_tree.configure(yscrollcommand=tree_sb_y.set)
        tree_sb_y.pack(side="right", fill="y")
        self._scan_tree.pack(fill="both", expand=True)

        # Alternating row colours
        self._scan_tree.tag_configure("odd",  background="#f7f9fc")
        self._scan_tree.tag_configure("even", background="#ffffff")
        self._scan_tree.tag_configure("hdr",  background="#dce8f5",
                                              font=("Helvetica", 9, "bold"))

        # ── Decoded summary card ──────────────────────────────────────────
        summary_lf = ttk.LabelFrame(root, text="Summary", padding=8)
        summary_lf.pack(fill="x", pady=(8,0))

        self._scan_summary = tk.StringVar(value="")
        ttk.Label(summary_lf, textvariable=self._scan_summary,
                  font=("Helvetica", 10), justify="left").pack(anchor="w")

        # Internal store of last parsed data
        self._last_scan: dict[str, str] = {}

    # ── Scanner helpers ───────────────────────────────────────────────────────

    def _scanner_parse(self):
        """Parse the raw text and populate the treeview."""
        raw = self.scanner_input.get("1.0", "end").strip()
        if not raw:
            self._scan_status.set("⚠  Nothing to parse.")
            return

        fields, header_info, errors = self._parse_aamva(raw)
        self._last_scan = fields

        # Clear tree
        for row in self._scan_tree.get_children():
            self._scan_tree.delete(row)

        if header_info:
            self._scan_tree.insert("", "end",
                values=("—", "── Header ──", header_info),
                tags=("hdr",))

        parity = 0
        for tag, value in fields.items():
            label = _AAMVA_TAGS.get(tag, f"Unknown ({tag})")
            tag_str = ("odd", "even")[parity % 2]
            self._scan_tree.insert("", "end",
                values=(tag, label, value.strip()),
                tags=(tag_str,))
            parity += 1

        if errors:
            for err in errors:
                self._scan_tree.insert("", "end",
                    values=("ERR", "Parse Warning", err),
                    tags=("hdr",))

        count = len(fields)
        self._scan_status.set(
            f"✓  Parsed {count} field{'s' if count != 1 else ''}"
            + (f"  ·  {len(errors)} warning(s)" if errors else "")
        )
        self._update_scan_summary(fields)

    def _parse_aamva(self, raw: str) -> tuple[dict, str, list]:
        """
        Parse a raw AAMVA barcode string into a dict of {tag: value}.

        Returns (fields_dict, header_summary_str, warnings_list).
        """
        fields: dict[str, str] = {}
        errors: list[str] = []
        header_info = ""

        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # First line: "@"
            if line == "@":
                continue

            # Header line: starts with "ANSI "
            if line.startswith("ANSI "):
                try:
                    iin  = line[5:11]
                    ver  = line[11:13]
                    jur  = line[13:15]
                    # The rest of the header line may contain the first DAQ
                    # element embedded — extract it
                    dl_idx = line.find("DLDAQ", 15)
                    if dl_idx != -1:
                        daq_val = line[dl_idx+5:]
                        fields["DAQ"] = daq_val
                    state_name = _IIN_STATE.get(iin, "Unknown")
                    header_info = (f"IIN={iin} ({state_name})  "
                                   f"Ver={ver}  Jur={jur}")
                except Exception as exc:
                    errors.append(f"Header parse error: {exc}")
                continue

            # Data lines: first 3 chars = tag
            if len(line) >= 3:
                tag = line[:3]
                val = line[3:]

                # Guard: skip non-alpha tags (header cruft)
                if not tag.isalpha():
                    continue

                # DBC can appear twice (first name + sex); handle gracefully
                if tag == "DBC" and "DBC" in fields:
                    # Second DBC is sex
                    fields["DBC_SEX"] = val
                else:
                    fields[tag] = val

        if not fields:
            errors.append("No AAMVA data elements found. Is this a valid barcode string?")

        return fields, header_info, errors

    def _update_scan_summary(self, fields: dict):
        """Build and display a human-readable card summary."""
        def g(tag, alt=""):
            return fields.get(tag, alt).strip()

        first = g("DAC") or g("DBC")
        last  = g("DCS")
        mid   = g("DAD")
        name  = " ".join(p for p in [first, mid, last] if p) or "—"

        dob  = g("DBB")
        exp  = g("DBA")
        sex_raw = g("DBC_SEX") or g("DBC")
        sex  = {"1": "Male", "2": "Female", "9": "Non-binary / X"}.get(sex_raw, sex_raw)

        lic  = g("DAQ")
        cls  = g("DCA")
        addr = g("DAG")
        city = g("DAI")
        st   = g("DAJ")
        zipc = g("DAK")

        lines = [
            f"Name:          {name}",
            f"Date of Birth: {dob}       Sex: {sex}",
            f"License #:     {lic}       Class: {cls}",
            f"Address:       {addr}, {city}, {st}  {zipc}",
            f"Expiry:        {exp}",
        ]
        self._scan_summary.set("\n".join(lines))

    def _scanner_load_from_output(self):
        """Copy the AAMVA text from the Information tab output box."""
        text = self.output.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Nothing to load",
                                   "Generate AAMVA data on the Information tab first.")
            return
        self.scanner_input.delete("1.0", "end")
        self.scanner_input.insert("1.0", text)
        self._scan_status.set("Loaded from Information tab output — click Parse.")

    def _scanner_clear(self):
        self.scanner_input.delete("1.0", "end")
        for row in self._scan_tree.get_children():
            self._scan_tree.delete(row)
        self._scan_summary.set("")
        self._scan_status.set("Cleared.")
        self._last_scan = {}

    def _scanner_send_to_info(self):
        """
        Pre-fill the Information tab form fields from the last parsed scan.
        Switches to the Information tab when done.
        """
        f = self._last_scan
        if not f:
            messagebox.showwarning("Nothing to send",
                                   "Parse a barcode first.")
            return

        def s(tag, alt=""):
            return f.get(tag, alt).strip()

        def _set(widget, value):
            widget.delete(0, "end")
            widget.insert(0, value)

        _set(self.first,   s("DAC") or s("DBC"))
        _set(self.middle,  s("DAD"))
        _set(self.last,    s("DCS"))
        _set(self.lic,     s("DAQ"))
        _set(self.cls,     s("DCA"))
        _set(self.birth,   s("DBB"))
        _set(self.exp,     s("DBA"))
        _set(self.issue,   s("DBD"))
        _set(self.address, s("DAG"))
        _set(self.city,    s("DAI"))
        _set(self.zip,     s("DAK"))
        _set(self.height,  s("DAU"))
        _set(self.eyes,    s("DAY"))
        _set(self.hair,    s("DAB"))
        _set(self.weight,  s("DAW"))
        _set(self.discriminator, s("DCF"))
        _set(self.endorsement,   s("DAT"))
        _set(self.restriction,   s("DAR"))
        _set(self.inventory,     s("DCK"))
        _set(self.race,          s("DCL"))
        _set(self.audit,         s("DCJ"))
        _set(self.compliance,    s("DDA"))

        # State combo
        st = s("DAJ")
        if st:
            self.state_var.set(st)

        # Sex combo
        sex_raw = s("DBC_SEX") or s("DBC")
        sex_map = {"1": "1 – M", "2": "2 – F", "9": "9 – X"}
        if sex_raw in sex_map:
            self.sex_var.set(sex_map[sex_raw])

        self.nb.select(self.tab_info)
        self._scan_status.set("✓  Fields sent to Information tab.")

    # ═══════════════════════════════════════════════ helpers

    def _on_iin_change(self, *_):
        """When user picks from the IIN combo, sync the state dropdown."""
        val = self._iin_var.get().strip()
        # Extract IIN (first 6 digits) and state (after "—")
        if "—" in val:
            parts = val.split("—")
            iin   = parts[0].strip()
            state = parts[1].strip()
            # Sync state dropdown without triggering _on_state_change loop
            if state in _STATE_IIN and self.state_var.get() != state:
                self.state_var.set(state)

    def _get_iin(self) -> str:
        """Extract the 6-digit IIN from the combo value."""
        val = self._iin_var.get().strip()
        if "—" in val:
            return val.split("—")[0].strip()
        # User may have typed a raw IIN directly
        return val[:6] if len(val) >= 6 else val
        val = val.strip().replace("-", "/").replace(" ", "")
        if not val:
            return val
        if len(val) == 8 and val.isdigit():
            if int(val[:4]) > 1900:
                return val
            return val[4:8] + val[0:2] + val[2:4]
        try:
            return datetime.strptime(val, "%m/%d/%Y").strftime("%Y%m%d")
        except ValueError:
            pass
        return val

    # Known subfile lengths per state (from real scan data)
    _STATE_SUBFILE = {
        "PA":"0278","VA":"0256","NC":"0256","SC":"0256","CA":"0300",
        "TX":"0300","FL":"0300","NY":"0320","IL":"0320","GA":"0350",
        "OH":"0350","MI":"0350","WA":"0400","OR":"0400","AZ":"0278",
        "CO":"0278","MD":"0278","MA":"0278","NJ":"0278","IN":"0278",
        "MN":"0278","UT":"0278","WI":"0278","TN":"0278","MO":"0278",
        "KY":"0278","NV":"0278","ID":"0278","MS":"0278","RI":"0278",
        "NE":"0278","OK":"0278","AK":"0278","WY":"0278","WV":"0278",
        "CT":"0256","LA":"0256","MT":"0256","NM":"0256","DE":"0256",
        "IA":"0256","KS":"0256","ME":"0256","SD":"0256","DC":"0256",
        "HI":"0256","AL":"0256","AR":"0256","ND":"0256","NH":"0256",
        "VT":"0256","VI":"0256",
    }

    def _on_state_change(self, *_):
        state = self.state_var.get()
        iin = _STATE_IIN.get(state)
        if iin:
            self._iin_var.set(f"{iin}  —  {state}")
        subfile = self._STATE_SUBFILE.get(state)
        if subfile:
            self.subfile_length_var.set(subfile)

    # ═══════════════════════════════════════════════ data collection

    def _collect_fields(self) -> AAMVAData:
        def _opt(entry_widget, key):
            if self._opt_vars.get(key, tk.BooleanVar(value=True)).get():
                return entry_widget.get()
            return ""

        return AAMVAData(
            issuer_id      = self._get_iin(),
            version        = self.version.get(),
            jurisdiction   = self.jurisdiction.get(),
            subfile_length = self.subfile_length_var.get().strip(),
            first_tag      = self.first_tag_var.get(),
            last           = self.last.get().upper(),
            first          = self.first.get().upper(),
            middle         = self.middle.get().upper(),
            birth_date     = self._fmt_date(self.birth.get()),
            expiry_date    = self._fmt_date(self.exp.get()),
            issue_date     = self._fmt_date(self.issue.get()),
            sex            = _SEX_WIRE.get(self.sex_var.get(), self.sex_var.get()),
            license_class  = self.cls.get().upper(),
            license_number = self.lic.get().upper(),
            address        = self.address.get().upper(),
            city           = self.city.get().upper(),
            state          = self.state_var.get(),
            zip_code       = self.zip.get(),
            document_discriminator = _opt(self.discriminator, "Discriminator"),
            eyes           = _opt(self.eyes,   "Eyes").upper(),
            height         = self.height.get() if self._opt_vars.get("Height", tk.BooleanVar(value=True)).get() else "",
            weight         = _opt(self.weight, "Weight"),
            hair           = _opt(self.hair,   "Hair").upper(),
            compliance_type     = _opt(self.compliance,  "Compliance Type"),
            donor               = "1" if self._opt_vars.get("donor_check", tk.BooleanVar()).get() and self.donor_val.get() else "",
            card_revision_date  = _opt(self.card_rev,    "Card Revision Date"),
            endorsement         = _opt(self.endorsement, "Endorsement"),
            inventory           = _opt(self.inventory,   "Inventory"),
            restriction         = _opt(self.restriction, "Restriction"),
            race_ethnicity      = _opt(self.race,        "Race/Ethnicity"),
            audit_information   = _opt(self.audit,       "Audit Information"),
        )

    # ═══════════════════════════════════════════════ actions — Information tab

    def generate_aamva(self):
        data = self._collect_fields()
        text = AAMVABuilder().build(data)
        for box in (self.output, self.output2):
            box.delete("1.0", "end")
            box.insert("1.0", text)

    def copy_output(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.output.get("1.0", "end"))

    # ═══════════════════════════════════════════════ actions — PDF417 tab

    def generate_barcode(self):
        data = self.output.get("1.0", "end").strip()
        if not data:
            messagebox.showwarning("No data", "Generate or paste AAMVA data first.")
            return

        try:
            dpi       = int(self.dpi_var.get())
            x_mils    = self.x_mils.get()
            ratio     = self.y_ratio.get()
            padding   = self.quiet_zone.get()
            columns   = self.col_count.get()
            rows      = self.row_count_var.get()
            bar_h     = self.bar_height_var.get()
            narrow_bw = self.narrow_bar_var.get()
        except (tk.TclError, ValueError) as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        if not (AAMVA_X_MIN_MILS <= x_mils <= AAMVA_X_MAX_MILS):
            messagebox.showerror(
                "AAMVA Violation",
                f"X-Dimension {x_mils} mils is outside the AAMVA valid range "
                f"{AAMVA_X_MIN_MILS}–{AAMVA_X_MAX_MILS} mils.\n\nUse 'AAMVA Preset'."
            )
            return

        if ratio < AAMVA_Y_X_RATIO_MIN:
            messagebox.showerror(
                "AAMVA Violation",
                f"Y Ratio {ratio} is below the AAMVA minimum of {AAMVA_Y_X_RATIO_MIN}."
            )
            return

        scale_from_xdim = max(1, round(dpi * x_mils / 1000.0))
        scale = narrow_bw if narrow_bw > 0 else scale_from_xdim

        try:
            img = generate_barcode(
                data, columns=columns, scale=scale,
                ratio=bar_h, padding=padding, rows=rows,
            )
        except Exception as exc:
            messagebox.showerror("Barcode error", str(exc))
            return

        self._last_img = img
        self._last_dpi = dpi
        self.preview.show(img)

        w_mm = img.width  / dpi * 25.4
        h_mm = img.height / dpi * 25.4
        ok_w = w_mm <= AAMVA_MAX_WIDTH_MM
        ok_h = h_mm <= AAMVA_MAX_HEIGHT_MM
        compliance = "✓ AAMVA" if (ok_w and ok_h) else "✗ EXCEEDS AAMVA LIMITS"
        self._phys_var.set(
            f"{w_mm:.2f} × {h_mm:.2f} mm  "
            f"({w_mm/25.4:.4f}″ × {h_mm/25.4:.4f}″)  "
            f"| scale={scale}px  ratio={bar_h}  {compliance}"
        )

        if not (ok_w and ok_h):
            issues = []
            if not ok_w: issues.append(f"Width  {w_mm:.2f} mm > {AAMVA_MAX_WIDTH_MM} mm")
            if not ok_h: issues.append(f"Height {h_mm:.2f} mm > {AAMVA_MAX_HEIGHT_MM} mm")
            messagebox.showwarning(
                "AAMVA Size Warning",
                "Barcode exceeds physical limits:\n  • " + "\n  • ".join(issues) +
                "\n\nReduce Column Count or X-Dimension."
            )

    def save_barcode_png(self):
        img = getattr(self, "_last_img", None)
        if img is None:
            messagebox.showwarning("No barcode", "Generate a barcode first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if path:
            dpi = getattr(self, "_last_dpi", 300)
            img.save(path, dpi=(dpi, dpi))
            self._phys_var.set(self._phys_var.get().rstrip() + f"  →  saved at {dpi} DPI")

    def _apply_aamva_preset(self):
        self.dpi_var.set("300")
        self.x_mils.set(10.0)
        self.y_ratio.set(3)
        self.bar_height_var.set(3)
        self.narrow_bar_var.set(3)
        self.quiet_zone.set(AAMVA_QUIET_ZONE_REC)
        self.col_count.set(DEFAULT_COLUMNS)
        self.row_count_var.set(0)
        self.ecl_var.set("Level 5")
        self._phys_var.set(
            "AAMVA preset applied  (DPI=300, X=10 mils → scale=3px, ratio=3, quiet=2)  "
            "— click Generate Barcode"
        )

    # ═══════════════════════════════════════════════ actions — Code 128 tab

    def generate_code128_barcode(self):
        text = self.c128_text_var.get().strip()
        if not text:
            messagebox.showwarning("No text", "Enter text to encode.")
            return
        try:
            bar_width  = float(self.c128_bar_width.get())
            bar_height = float(self.c128_bar_height.get())
            dpi        = int(self.c128_dpi_var.get())
        except (tk.TclError, ValueError) as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        try:
            img = generate_code128(text, bar_width=bar_width,
                                   bar_height=bar_height, dpi=dpi)
        except ImportError as exc:
            messagebox.showerror("Missing package", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Code 128 error", str(exc))
            return

        self._last_c128_img = img
        self._last_c128_dpi = dpi
        self.preview_c128.show(img)
        self._c128_status.set(
            f"{img.width} × {img.height} px  |  "
            f"bar_width={bar_width} mm  bar_height={bar_height} mm  DPI={dpi}"
        )

    def _save_c128_image(self):
        img = getattr(self, "_last_c128_img", None)
        if img is None:
            messagebox.showwarning("No image", "Generate a Code 128 barcode first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image","*.png"),("JPEG image","*.jpg"),("All files","*.*")],
        )
        if path:
            img.save(path)
            self._c128_status.set(self._c128_status.get() + f"  →  {path}")

    def _save_c128_pdf(self):
        img = getattr(self, "_last_c128_img", None)
        if img is None:
            messagebox.showwarning("No image", "Generate a Code 128 barcode first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF document","*.pdf"),("All files","*.*")],
        )
        if path:
            try:
                export_pdf(img, path, title="Code 128 Barcode")
                self._c128_status.set(self._c128_status.get() + f"  →  PDF: {path}")
            except Exception as exc:
                messagebox.showerror("PDF export failed", str(exc))

    # ═══════════════════════════════════════════════ Tab 6 — Downloads

    def _build_downloads_tab(self):
        """
        Downloads tab — links to the PSD FILES Google Drive folder.
        Opens links in the default browser via webbrowser.open().
        """
        import webbrowser

        DRIVE_FOLDER = "https://drive.google.com/drive/folders/1eZCoztfcGjwAskhKmlwDAuTTeC0LDSuo"

        root = ttk.Frame(self.tab_downloads, padding=16)
        root.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg="#1a1a2e")
        hdr.pack(fill="x", pady=(0, 16))

        tk.Label(hdr, text="⬇  Downloads", bg="#1a1a2e", fg="white",
                 font=("Helvetica", 16, "bold"), pady=14).pack(side="left", padx=16)
        tk.Label(hdr, text="PSD Files & Design Assets",
                 bg="#1a1a2e", fg="#7a83a6",
                 font=("Helvetica", 10)).pack(side="left")

        # ── Info card ─────────────────────────────────────────────────────
        info_lf = ttk.LabelFrame(root, text="PSD Files — Google Drive", padding=16)
        info_lf.pack(fill="x", pady=(0, 16))

        desc = (
            "Download PSD templates, card backgrounds, and design assets from the\n"
            "official PDF417 Studio Google Drive folder. Files open directly in\n"
            "Google Drive — sign in to download individual files or the full folder."
        )
        ttk.Label(info_lf, text=desc, font=("Helvetica", 10),
                  foreground="#444", justify="left").pack(anchor="w", pady=(0, 12))

        url_frame = ttk.Frame(info_lf)
        url_frame.pack(fill="x")

        url_entry = ttk.Entry(url_frame, font=("Courier", 9), width=60)
        url_entry.insert(0, DRIVE_FOLDER)
        url_entry.config(state="readonly")
        url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(url_frame, text="Copy Link",
                   command=lambda: (
                       self.root.clipboard_clear(),
                       self.root.clipboard_append(DRIVE_FOLDER)
                   )).pack(side="left", padx=(0, 4))

        ttk.Button(url_frame, text="🌐  Open in Browser",
                   command=lambda: webbrowser.open(DRIVE_FOLDER)).pack(side="left")

        # ── Quick access buttons ──────────────────────────────────────────
        btns_lf = ttk.LabelFrame(root, text="Quick Access", padding=16)
        btns_lf.pack(fill="x", pady=(0, 16))

        items = [
            ("📁", "PSD Files Folder",
             "All PSD card templates and design assets",
             DRIVE_FOLDER),
            ("🌐", "PDF417 Studio Website",
             "Landing page with usage guide and documentation",
             "https://muyaallan.github.io/PDF417Studio/"),
            ("💾", "Latest Release (.exe)",
             "Download the latest PDF417Studio.exe directly",
             "https://github.com/muyaallan/PDF417Studio/releases/latest/download/PDF417Studio.exe"),
            ("📖", "GitHub Repository",
             "Source code, issues, and release history",
             "https://github.com/muyaallan/PDF417Studio"),
        ]

        for i, (icon, title, desc, url) in enumerate(items):
            row = i // 2
            col = i %  2
            card = ttk.Frame(btns_lf, relief="groove", padding=12)
            card.grid(row=row, column=col, sticky="ew", padx=6, pady=6)

            top_row = ttk.Frame(card)
            top_row.pack(fill="x")
            ttk.Label(top_row, text=f"{icon}  {title}",
                      font=("Helvetica", 11, "bold")).pack(side="left")
            ttk.Button(top_row, text="Open →",
                       command=lambda u=url: webbrowser.open(u)).pack(side="right")
            ttk.Label(card, text=desc,
                      font=("Helvetica", 9), foreground="#666").pack(anchor="w", pady=(4, 0))

        btns_lf.columnconfigure(0, weight=1)
        btns_lf.columnconfigure(1, weight=1)

        # ── How to download ───────────────────────────────────────────────
        how_lf = ttk.LabelFrame(root, text="How to Download PSD Files", padding=16)
        how_lf.pack(fill="x")

        steps = [
            ("1", "Click  'Open in Browser'  above — the Google Drive folder opens."),
            ("2", "Sign in to your Google account if prompted."),
            ("3", "Right-click any file → 'Download'  to save it to your computer."),
            ("4", "To download everything: click the folder name → ⋮ → 'Download all'."),
        ]

        for num, text in steps:
            row = ttk.Frame(how_lf)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=num, width=2, bg="#4f8ef7", fg="white",
                     font=("Helvetica", 9, "bold"),
                     relief="flat", padx=4, pady=2).pack(side="left", padx=(0, 10))
            ttk.Label(row, text=text, font=("Helvetica", 10)).pack(side="left")

    # ═══════════════════════════════════════════════ Tab 7 — Security

    def _build_security_tab(self):
        root = ttk.Frame(self.tab_security, padding=0)
        root.pack(fill="both", expand=True)

        # ── Dark header ───────────────────────────────────────────────────
        hdr = tk.Frame(root, bg="#0d0f1a")
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔒  Security, Legal & Terms of Use",
                 bg="#0d0f1a", fg="white",
                 font=("Helvetica", 15, "bold"), pady=16).pack(side="left", padx=20)
        tk.Label(hdr, text="PDF417Studio v1.0.0  ·  © 2026 PDF417Studio. All Rights Reserved.",
                 bg="#0d0f1a", fg="#7a83a6",
                 font=("Helvetica", 9)).pack(side="right", padx=20)

        # ── Scrollable content ────────────────────────────────────────────
        canvas = tk.Canvas(root, highlightthickness=0, bg="#f8f9fc")
        vsb = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas, padding=24)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mouse wheel scroll
        def _on_scroll(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_scroll)

        # ── Section builder ───────────────────────────────────────────────
        def section(title, body, icon=""):
            lf = ttk.LabelFrame(inner, text=f"  {icon}  {title}" if icon else f"  {title}",
                                padding=14)
            lf.pack(fill="x", pady=(0, 14))
            ttk.Label(lf, text=body, wraplength=860, justify="left",
                      font=("Helvetica", 10), foreground="#333").pack(anchor="w")

        def warning_banner(text):
            f = tk.Frame(inner, bg="#fff3cd", bd=1, relief="solid")
            f.pack(fill="x", pady=(0, 14))
            tk.Label(f, text=text, bg="#fff3cd", fg="#856404",
                     font=("Helvetica", 10, "bold"),
                     wraplength=860, justify="left", pady=10, padx=14).pack(anchor="w")

        # ── Content ───────────────────────────────────────────────────────
        warning_banner(
            "⚠  This software is intended solely for lawful, authorized, and ethical "
            "applications. Misuse for fraud, identity deception, document forgery, or any "
            "unlawful purpose is strictly prohibited and may be subject to criminal prosecution."
        )

        section("Overview", (
            "PDF417Studio is a comprehensive desktop application engineered for creating, "
            "editing, and exporting PDF417 barcodes, as well as handling industry-standard "
            "data serialization formats including TD1, TD2, TD3, and Code 128.\n\n"
            "The application is designed exclusively for legitimate business workflows, "
            "educational instruction, systems testing, inventory management, logistics "
            "optimization, document management, and professional research purposes."
        ), "📋")

        section("Intended Use", (
            "This software is intended solely for lawful, authorized, and ethical applications. "
            "It must only be deployed within professional environments where operators possess "
            "the explicit legal rights, permissions, and mandates to process the data being managed."
        ), "✅")

        section("Security & Privacy", (
            "Local Processing:  PDF417Studio processes all data locally on the user's device "
            "and does not intentionally transmit user data or telemetry to external services.\n\n"
            "User Responsibility:  Users retain sole responsibility for securing all files, "
            "project data, and printed assets generated by the application.\n\n"
            "Regulatory Compliance:  Users must ensure that all operations conducted within "
            "the software comply strictly with local, national, and international privacy laws "
            "and data protection regulations."
        ), "🔒")

        section("Safety Measures", (
            "Data Authorization:  Ensure all data fields are populated using only authorized, "
            "legally obtained data streams.\n\n"
            "Verification Protocols:  The software does not warrant the accuracy, completeness, "
            "or validity of user-supplied data. Users are solely responsible for verifying all "
            "generated output and performing hardware scanning tests prior to operational use.\n\n"
            "Backup Procedures:  Maintain independent, redundant backups of all critical "
            "configuration parameters and project datasets.\n\n"
            "Lifecycle Management:  Utilize the latest official version of the software to "
            "ensure compliance with updated security practices and performance baselines."
        ), "🛡️")

        section("Third-Party Components", (
            "PDF417Studio may include third-party libraries distributed under their respective "
            "licenses. Ownership and licensing of such components remain with their respective "
            "copyright holders."
        ), "📦")

        section("Terms of Use", (
            "1.  Prohibition of Illegal Activity:  This software must not be used, directly or "
            "indirectly, for any illegal, fraudulent, or malicious activities.\n\n"
            "2.  Malicious Misuse Restrictions:  Use of this application for fraud, identity "
            "deception, unauthorized systems access, document forgery, or any form of unlawful "
            "misrepresentation is strictly prohibited.\n\n"
            "3.  Distribution Limitations:  Redistribution, modification, reverse engineering, "
            "decompilation, or resale of the software is prohibited except where such restrictions "
            "are unenforceable under applicable law.\n\n"
            "4.  Export Compliance:  Users are responsible for ensuring compliance with all "
            "applicable export control laws and regulations governing the use, transfer, or "
            "distribution of this software.\n\n"
            "5.  Binding Agreement:  Downloading, installing, running, or otherwise utilizing "
            "the software signifies immediate, full acceptance of these terms.\n\n"
            "6.  Governing Law:  This Agreement shall be governed by and construed in accordance "
            "with the laws of Kenya."
        ), "📜")

        section("Disclaimer", (
            "PDF417Studio is provided on an \"AS IS\" and \"AS AVAILABLE\" basis without "
            "warranties of any kind, whether express, implied, statutory, or otherwise, including "
            "but not limited to any warranties of merchantability, fitness for a particular "
            "purpose, or non-infringement.\n\n"
            "To the maximum extent permitted by applicable law, the developers, authors, and "
            "copyright holders shall not be liable for any direct, indirect, incidental, "
            "consequential, special, exemplary, or punitive damages, including loss of profits, "
            "loss of data, business interruption, or other commercial damages arising from or "
            "related to the use, inability to use, performance, or misuse of this software."
        ), "⚠️")

        section("License Notice", (
            "PDF417Studio is proprietary software. All intellectual property rights, including "
            "the software, source code, executable binaries, user interface designs, "
            "documentation, assets, and layout structures, remain the exclusive property of the "
            "copyright owner.\n\n"
            "This software is not open source and is not intended for public resale, "
            "redistribution, or commercial sub-licensing unless explicitly authorized by a "
            "separate, signed agreement from the copyright owner."
        ), "©️")

        section("Trademark", (
            "\"PDF417Studio\" is a trademark or product name of PDF417Studio. Unauthorized use "
            "of the name in connection with modified or redistributed versions of the software "
            "is prohibited without prior written permission."
        ), "™️")

        section("Support", (
            "For technical inquiries, operational guidance, deployment assistance, or official "
            "licensing documentation, please contact the software author directly through the "
            "official communication channels designated by the copyright owner.\n\n"
            "GitHub:  https://github.com/muyaallan/PDF417Studio"
        ), "💬")

        # ── Footer ────────────────────────────────────────────────────────
        foot = tk.Frame(inner, bg="#0d0f1a")
        foot.pack(fill="x", pady=(8, 0))
        tk.Label(foot, text="PDF417Studio  ·  Release 1.0.0  ·  Copyright © 2026 PDF417Studio. All Rights Reserved.  ·  Governed by the laws of Kenya.",
                 bg="#0d0f1a", fg="#7a83a6",
                 font=("Helvetica", 8), pady=12).pack()

    def _about(self):
        messagebox.showinfo("PDF417 Studio", "PDF417 Studio\nAAMVA 2016")

    # ═══════════════════════════════════════════════ Tab 5 — MRZ

    def _build_mrz_tab(self):
        root = ttk.Frame(self.tab_mrz, padding=10)
        root.pack(fill="both", expand=True)

        # ── Format selector ───────────────────────────────────────────────
        fmt_row = ttk.Frame(root)
        fmt_row.pack(fill="x", pady=(0, 8))

        _lbl(fmt_row, "MRZ Format:").pack(side="left", padx=(0, 10))
        self._mrz_format = tk.StringVar(value="TD1")

        _FORMAT_OPTS = [
            "TD1 — ID Card        (3 × 30 chars)",
            "TD2 — Official ID    (2 × 36 chars)",
            "TD3 — Passport       (2 × 44 chars)",
        ]
        self._mrz_fmt_combo = _combo(fmt_row, self._mrz_format,
                                     _FORMAT_OPTS, width=36)
        self._mrz_fmt_combo.pack(side="left")
        self._mrz_format.trace_add("write", lambda *_: self._mrz_on_format_change())

        # Format quick-reference label
        self._mrz_fmt_hint = tk.StringVar(
            value="TD1: I / ID / A / C  ·  3 lines × 30 chars  ·  ICAO 9303 Part 5")
        ttk.Label(fmt_row, textvariable=self._mrz_fmt_hint,
                  font=("Helvetica", 8), foreground="#666").pack(
            side="left", padx=(12, 0))

        # ── Form (shared fields live here, optional-2 hidden for TD3) ─────
        self._mrz_form_lf = ttk.LabelFrame(root, padding=10,
                                            text="TD1 — ID Card Fields  (ICAO 9303)")
        self._mrz_form_lf.pack(fill="x")
        g = self._mrz_form_lf

        # Row 0/1 — doc type / country / doc number
        _lbl(g, "Doc Type").grid(        row=0, column=0, sticky="w")
        _lbl(g, "Issuing Country").grid( row=0, column=1, sticky="w", padx=(10,0))
        _lbl(g, "Document Number").grid( row=0, column=2, sticky="w", padx=(10,0))
        _lbl(g, "Optional Data 1").grid( row=0, column=3, sticky="w", padx=(10,0))

        self.mrz_doc_type_var = tk.StringVar(value="ID")
        self._mrz_doc_type_combo = _combo(g, self.mrz_doc_type_var,
                                          ["I","ID","A","C"], width=4)
        self._mrz_doc_type_combo.grid(row=1, column=0, sticky="ew")
        self.mrz_country    = _entry(g, width=6);  self.mrz_country.grid( row=1, column=1, sticky="ew", padx=(10,0))
        self.mrz_doc_num    = _entry(g, width=12); self.mrz_doc_num.grid( row=1, column=2, sticky="ew", padx=(10,0))
        self.mrz_opt1       = _entry(g, width=18); self.mrz_opt1.grid(    row=1, column=3, sticky="ew", padx=(10,0))

        # Row 2/3 — surname / given / nationality / opt2
        _lbl(g, "Surname").grid(         row=2, column=0, sticky="w", pady=(8,0))
        _lbl(g, "Given Names").grid(     row=2, column=1, sticky="w", padx=(10,0), pady=(8,0))
        _lbl(g, "Nationality").grid(     row=2, column=2, sticky="w", padx=(10,0), pady=(8,0))
        self._mrz_opt2_lbl = _lbl(g, "Optional Data 2")
        self._mrz_opt2_lbl.grid(         row=2, column=3, sticky="w", padx=(10,0), pady=(8,0))

        self.mrz_surname     = _entry(g, width=18); self.mrz_surname.grid(    row=3, column=0, sticky="ew")
        self.mrz_given       = _entry(g, width=18); self.mrz_given.grid(      row=3, column=1, sticky="ew", padx=(10,0))
        self.mrz_nationality = _entry(g, width=6);  self.mrz_nationality.grid(row=3, column=2, sticky="ew", padx=(10,0))
        self.mrz_opt2        = _entry(g, width=14); self.mrz_opt2.grid(       row=3, column=3, sticky="ew", padx=(10,0))

        # Row 4/5 — DOB / gender / expiry
        _lbl(g, "Date of Birth (YYMMDD)").grid(row=4, column=0, sticky="w", pady=(8,0))
        _lbl(g, "Gender").grid(               row=4, column=1, sticky="w", padx=(10,0), pady=(8,0))
        _lbl(g, "Expiry Date (YYMMDD)").grid( row=4, column=2, sticky="w", padx=(10,0), pady=(8,0))

        self.mrz_dob = _entry(g, width=10); self.mrz_dob.grid(row=5, column=0, sticky="ew")
        self.mrz_gender_var = tk.StringVar(value="M")
        _combo(g, self.mrz_gender_var, ["M","F","<"], width=4).grid(
            row=5, column=1, sticky="w", padx=(10,0))
        self.mrz_expiry = _entry(g, width=10); self.mrz_expiry.grid(row=5, column=2, sticky="ew", padx=(10,0))

        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)
        g.columnconfigure(2, weight=1)
        g.columnconfigure(3, weight=2)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_row, text="Generate MRZ",           command=self._mrz_generate).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Copy MRZ",               command=self._mrz_copy).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Clear",                  command=self._mrz_clear).pack(side="left", padx=(0,6))
        ttk.Button(btn_row, text="Fill from Information Tab",
                   command=self._mrz_fill_from_info).pack(side="right")

        # ── Status ────────────────────────────────────────────────────────
        self._mrz_status = tk.StringVar(value="Select format, fill fields, then click Generate MRZ.")
        ttk.Label(root, textvariable=self._mrz_status,
                  font=("Helvetica", 9, "italic"),
                  foreground="#444").pack(anchor="w", pady=(6, 2))

        # ── MRZ output ────────────────────────────────────────────────────
        self._mrz_out_lf = ttk.LabelFrame(root, text="MRZ Output  (3 × 30 characters — TD1)", padding=10)
        self._mrz_out_lf.pack(fill="x", pady=(4, 0))

        self.mrz_output = tk.Text(
            self._mrz_out_lf, height=2,
            font=("Courier New", 14, "bold"),
            bg="#0d0d0d", fg="#00ff88",
            insertbackground="#00ff88",
            relief="flat", padx=12, pady=10,
            wrap="none",
        )
        self.mrz_output.pack(fill="x")

        # ── Breakdown table ───────────────────────────────────────────────
        breakdown_lf = ttk.LabelFrame(root, text="Field Breakdown", padding=8)
        breakdown_lf.pack(fill="both", expand=True, pady=(8, 0))

        cols = ("line", "pos", "field", "value", "chk")
        self._mrz_tree = ttk.Treeview(breakdown_lf, columns=cols,
                                      show="headings", selectmode="browse", height=10)
        self._mrz_tree.heading("line",  text="Line")
        self._mrz_tree.heading("pos",   text="Pos")
        self._mrz_tree.heading("field", text="Field")
        self._mrz_tree.heading("value", text="Value")
        self._mrz_tree.heading("chk",   text="Check")
        self._mrz_tree.column("line",  width=45,  stretch=False)
        self._mrz_tree.column("pos",   width=60,  stretch=False)
        self._mrz_tree.column("field", width=220, stretch=False)
        self._mrz_tree.column("value", width=300, stretch=True)
        self._mrz_tree.column("chk",   width=55,  stretch=False)

        tree_sb = ttk.Scrollbar(breakdown_lf, orient="vertical", command=self._mrz_tree.yview)
        self._mrz_tree.configure(yscrollcommand=tree_sb.set)
        tree_sb.pack(side="right", fill="y")
        self._mrz_tree.pack(fill="both", expand=True)

        self._mrz_tree.tag_configure("odd",  background="#f7f9fc")
        self._mrz_tree.tag_configure("even", background="#ffffff")
        self._mrz_tree.tag_configure("err",  background="#fff0f0", foreground="#cc0000")

        # ── pipeline (handles both TD1 and TD3) ──────────────────────────
        self._mrz_universal = default_universal_pipeline()

    # ── format switch ─────────────────────────────────────────────────────────

    def _mrz_on_format_change(self):
        sel = self._mrz_format.get()
        # Extract format key from combo label e.g. "TD1 — ..." → "TD1"
        fmt = sel[:3].strip()

        if fmt == "TD1":
            self._mrz_form_lf.config(text="TD1 — ID Card Fields  (ICAO 9303 Part 5)")
            self._mrz_doc_type_combo.config(values=["I","ID","A","C"])
            self.mrz_doc_type_var.set("ID")
            self._mrz_opt2_lbl.grid()
            self.mrz_opt2.grid()
            self._mrz_out_lf.config(text="MRZ Output  (3 × 30 characters — TD1)")
            self.mrz_output.config(height=3)
            self._mrz_fmt_hint.set(
                "TD1: I / ID / A / C  ·  3 lines × 30 chars  ·  ICAO 9303 Part 5")
            self._mrz_status.set("TD1 ID Card mode — Optional Data 1 (15 chars) + Optional Data 2 (11 chars).")

        elif fmt == "TD2":
            self._mrz_form_lf.config(text="TD2 — Official / Diplomatic ID Fields  (ICAO 9303 Part 6)")
            self._mrz_doc_type_combo.config(values=["A","C","I","AC","AI"])
            self.mrz_doc_type_var.set("A")
            self._mrz_opt2_lbl.grid_remove()
            self.mrz_opt2.grid_remove()
            self._mrz_out_lf.config(text="MRZ Output  (2 × 36 characters — TD2)")
            self.mrz_output.config(height=2)
            self._mrz_fmt_hint.set(
                "TD2: A / C / I  ·  2 lines × 36 chars  ·  ICAO 9303 Part 6  ·  Optional Data up to 7 chars")
            self._mrz_status.set("TD2 Official ID mode — Optional Data up to 7 chars.")

        else:  # TD3
            self._mrz_form_lf.config(text="TD3 — Passport Fields  (ICAO 9303 Part 4)")
            self._mrz_doc_type_combo.config(values=["P","PO","PD","PS","PE","PM"])
            self.mrz_doc_type_var.set("P")
            self._mrz_opt2_lbl.grid_remove()
            self.mrz_opt2.grid_remove()
            self._mrz_out_lf.config(text="MRZ Output  (2 × 44 characters — TD3 Passport)")
            self.mrz_output.config(height=2)
            self._mrz_fmt_hint.set(
                "TD3: P / PO / PD / PS / PE / PM  ·  2 lines × 44 chars  ·  ICAO 9303 Part 4  ·  Optional Data up to 14 chars")
            self._mrz_status.set("TD3 Passport mode — Optional Data up to 14 chars (personal number).")

        self._mrz_clear()

    # ── MRZ actions ──────────────────────────────────────────────────────────

    def _mrz_generate(self):
        sel = self._mrz_format.get()
        fmt = sel[:3].strip()
        try:
            if fmt == "TD3":
                raw = RawTD3Document(
                    document_type   = self.mrz_doc_type_var.get().strip(),
                    issuing_country = self.mrz_country.get().strip().upper(),
                    document_number = self.mrz_doc_num.get().strip().upper(),
                    dob             = self.mrz_dob.get().strip(),
                    gender          = self.mrz_gender_var.get().strip(),
                    expiry          = self.mrz_expiry.get().strip(),
                    nationality     = self.mrz_nationality.get().strip().upper(),
                    surname         = self.mrz_surname.get().strip().upper(),
                    given_names     = self.mrz_given.get().strip().upper(),
                    optional_data   = self.mrz_opt1.get().strip().upper(),
                )
                mrz = self._mrz_universal.process_td3(raw)
                lines = "2 × 44 characters"

            elif fmt == "TD2":
                raw = RawTD2Document(
                    document_type   = self.mrz_doc_type_var.get().strip(),
                    issuing_country = self.mrz_country.get().strip().upper(),
                    document_number = self.mrz_doc_num.get().strip().upper(),
                    dob             = self.mrz_dob.get().strip(),
                    gender          = self.mrz_gender_var.get().strip(),
                    expiry          = self.mrz_expiry.get().strip(),
                    nationality     = self.mrz_nationality.get().strip().upper(),
                    surname         = self.mrz_surname.get().strip().upper(),
                    given_names     = self.mrz_given.get().strip().upper(),
                    optional_data   = self.mrz_opt1.get().strip().upper(),
                )
                mrz = self._mrz_universal.process_td2(raw)
                lines = "2 × 36 characters"

            else:  # TD1
                raw = RawTD1Document(
                    document_type   = self.mrz_doc_type_var.get().strip(),
                    issuing_country = self.mrz_country.get().strip().upper(),
                    document_number = self.mrz_doc_num.get().strip().upper(),
                    dob             = self.mrz_dob.get().strip(),
                    gender          = self.mrz_gender_var.get().strip(),
                    expiry          = self.mrz_expiry.get().strip(),
                    nationality     = self.mrz_nationality.get().strip().upper(),
                    surname         = self.mrz_surname.get().strip().upper(),
                    given_names     = self.mrz_given.get().strip().upper(),
                    optional_data1  = self.mrz_opt1.get().strip().upper(),
                    optional_data2  = self.mrz_opt2.get().strip().upper(),
                )
                mrz = self._mrz_universal.process_td1(raw)
                lines = "3 × 30 characters"

        except MRZError as exc:
            self._mrz_status.set(f"⚠  {exc}")
            messagebox.showerror("MRZ Validation Error", str(exc))
            return
        except Exception as exc:
            self._mrz_status.set(f"✗  {exc}")
            messagebox.showerror("MRZ Error", str(exc))
            return

        self.mrz_output.config(state="normal")
        self.mrz_output.delete("1.0", "end")
        self.mrz_output.insert("1.0", mrz.text)
        self.mrz_output.config(state="disabled")

        self._mrz_status.set(f"✓  {fmt} MRZ generated — {lines}.")
        self._mrz_populate_breakdown(mrz, fmt)

    def _mrz_populate_breakdown(self, mrz, fmt="TD1"):
        for row in self._mrz_tree.get_children():
            self._mrz_tree.delete(row)

        calc = lambda s: str(sum(
            (int(c) if c.isdigit() else (ord(c)-ord('A')+10 if c.isalpha() else 0))
            * [7,3,1][i%3] for i,c in enumerate(s)
        ) % 10)

        if fmt == "TD3":
            l1, l2 = mrz.line1, mrz.line2
            rows = [
                ("L1", "1–2",   "Document Type",          l1[0:2],   ""),
                ("L1", "3–5",   "Issuing Country",         l1[2:5],   ""),
                ("L1", "6–44",  "Name (Surname<<Given)",   l1[5:44],  ""),
                ("L2", "1–9",   "Document Number",         l2[0:9],   ""),
                ("L2", "10",    "Check Digit (Doc No)",    l2[9],     calc(l2[0:9])),
                ("L2", "11–13", "Nationality",             l2[10:13], ""),
                ("L2", "14–19", "Date of Birth",           l2[13:19], ""),
                ("L2", "20",    "Check Digit (DOB)",       l2[19],    calc(l2[13:19])),
                ("L2", "21",    "Gender",                  l2[20],    ""),
                ("L2", "22–27", "Expiry Date",             l2[21:27], ""),
                ("L2", "28",    "Check Digit (Expiry)",    l2[27],    calc(l2[21:27])),
                ("L2", "29–42", "Optional Data",           l2[28:42], ""),
                ("L2", "43",    "Check Digit (Optional)",  l2[42],    calc(l2[28:42])),
                ("L2", "44",    "Composite Check Digit",   l2[43],    ""),
            ]

        elif fmt == "TD2":
            l1, l2 = mrz.line1, mrz.line2
            rows = [
                ("L1", "1–2",   "Document Type",          l1[0:2],   ""),
                ("L1", "3–5",   "Issuing Country",         l1[2:5],   ""),
                ("L1", "6–36",  "Name (Surname<<Given)",   l1[5:36],  ""),
                ("L2", "1–9",   "Document Number",         l2[0:9],   ""),
                ("L2", "10",    "Check Digit (Doc No)",    l2[9],     calc(l2[0:9])),
                ("L2", "11–13", "Nationality",             l2[10:13], ""),
                ("L2", "14–19", "Date of Birth",           l2[13:19], ""),
                ("L2", "20",    "Check Digit (DOB)",       l2[19],    calc(l2[13:19])),
                ("L2", "21",    "Gender",                  l2[20],    ""),
                ("L2", "22–27", "Expiry Date",             l2[21:27], ""),
                ("L2", "28",    "Check Digit (Expiry)",    l2[27],    calc(l2[21:27])),
                ("L2", "29–35", "Optional Data",           l2[28:35], ""),
                ("L2", "36",    "Composite Check Digit",   l2[35],    ""),
            ]

        else:  # TD1
            l1, l2, l3 = mrz.line1, mrz.line2, mrz.line3
            rows = [
                ("L1", "1–2",   "Document Type",        l1[0:2],   ""),
                ("L1", "3–5",   "Issuing Country",       l1[2:5],   ""),
                ("L1", "6–14",  "Document Number",       l1[5:14],  ""),
                ("L1", "15",    "Check Digit (Doc No)",  l1[14],    calc(l1[5:14])),
                ("L1", "16–30", "Optional Data 1",       l1[15:30], ""),
                ("L2", "1–6",   "Date of Birth",         l2[0:6],   ""),
                ("L2", "7",     "Check Digit (DOB)",     l2[6],     calc(l2[0:6])),
                ("L2", "8",     "Gender",                l2[7],     ""),
                ("L2", "9–14",  "Expiry Date",           l2[8:14],  ""),
                ("L2", "15",    "Check Digit (Expiry)",  l2[14],    calc(l2[8:14])),
                ("L2", "16–18", "Nationality",           l2[15:18], ""),
                ("L2", "19–29", "Optional Data 2",       l2[18:29], ""),
                ("L2", "30",    "Composite Check Digit", l2[29],    ""),
                ("L3", "1–30",  "Name (Surname<<Given)", l3,        ""),
            ]

        for i, (line, pos, field, value, chk_val) in enumerate(rows):
            tag = ("odd", "even")[i % 2]
            if chk_val and value != chk_val:
                tag = "err"
            self._mrz_tree.insert("", "end",
                values=(line, pos, field, value.replace("<", "·"), chk_val),
                tags=(tag,))

    def _mrz_copy(self):
        text = self.mrz_output.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Nothing to copy", "Generate an MRZ first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._mrz_status.set("✓  Copied to clipboard.")

    def _mrz_clear(self):
        self.mrz_output.config(state="normal")
        self.mrz_output.delete("1.0", "end")
        self.mrz_output.config(state="disabled")
        for row in self._mrz_tree.get_children():
            self._mrz_tree.delete(row)
        self._mrz_status.set("Cleared.")

    def _mrz_fill_from_info(self):
        def _g(w): return w.get().strip()

        self.mrz_surname.delete(0, "end")
        self.mrz_surname.insert(0, _g(self.last).upper())

        first  = _g(self.first).upper()
        middle = _g(self.middle).upper()
        given  = (first + (" " + middle if middle else "")).strip()
        self.mrz_given.delete(0, "end")
        self.mrz_given.insert(0, given)

        self.mrz_doc_num.delete(0, "end")
        self.mrz_doc_num.insert(0, _g(self.lic).upper())

        state = self.state_var.get()
        if state:
            self.mrz_nationality.delete(0, "end")
            self.mrz_nationality.insert(0, "USA")
            self.mrz_country.delete(0, "end")
            self.mrz_country.insert(0, "USA")

        def _yyyymmdd_to_yymmdd(s):
            s = s.strip()
            return s[2:] if (len(s) == 8 and s.isdigit()) else s

        self.mrz_dob.delete(0, "end")
        self.mrz_dob.insert(0, _yyyymmdd_to_yymmdd(_g(self.birth)))

        self.mrz_expiry.delete(0, "end")
        self.mrz_expiry.insert(0, _yyyymmdd_to_yymmdd(_g(self.exp)))

        sex_raw = self.sex_var.get()
        gender  = {"1 – M": "M", "2 – F": "F", "9 – X": "<"}.get(sex_raw, "<")
        self.mrz_gender_var.set(gender)

        self._mrz_status.set("Fields loaded from Information tab — click Generate MRZ.")