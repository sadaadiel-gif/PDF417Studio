"""
aamva.py
Builds AAMVA-compliant PDF417 barcode payloads.

Wire format (reverse-engineered from real scanner output)
---------------------------------------------------------
Line 0:  @
Line 1:  ANSI <IIN><ver><jur><entries>DL<offset><length>DL<DAQ><value>
Line 2+: <TAG><value>          (one element per line)
Last:    DCF<value>            (no trailing newline)

Key facts confirmed from real scans
-------------------------------------
- Offset  = length of the header line (line 1) including its trailing \n.
            Always computable; for a standard card this is 41 chars.
- Length  = jurisdiction-declared subfile size set at card issuance.
            It is NOT a byte count of the actual data — it is larger
            (padding for future fields). Must be supplied as an input.
- First name tag varies by jurisdiction:
    DAC  — AAMVA standard
    DBC  — used by some states (e.g. Pennsylvania); DBC then also appears
            again for sex, which is valid — scanners handle the repetition.
- DAY = eye colour (not license class; license class = DCA)
- DAB = hair colour (not DAZ)
- Dates = YYYYMMDD
- DAU = height as 3-digit total-inches string e.g. "601" = 6'01"
- DAK = zip, 9 chars space-padded e.g. "78572    "
- DCF (document discriminator) is always the last element, no trailing \n
"""

from dataclasses import dataclass, field


@dataclass
class AAMVAData:
    """One AAMVA DL barcode record."""

    # ── Header fields ────────────────────────────────────────────────────────
    issuer_id:      str = "636000"  # IIN — 6 digits, e.g. "636025"
    version:        str = "01"      # 2-digit spec version
    jurisdiction:   str = "01"      # 2-digit jurisdiction version
    subfile_length: str = "0278"    # declared subfile length (passthrough)

    # ── Name ─────────────────────────────────────────────────────────────────
    last:   str = ""   # DCS
    first:  str = ""   # DAC (standard) or DBC (some states) — see first_tag
    middle: str = ""   # DAD

    # first_tag controls which element tag is used for the first name.
    # Use "DAC" for standard AAMVA. Use "DBC" for PA-style barcodes where
    # DBC encodes the first name AND appears again for sex.
    first_tag: str = "DAC"

    # ── Dates (YYYYMMDD) ─────────────────────────────────────────────────────
    birth_date:  str = ""   # DBB
    expiry_date: str = ""   # DBA
    issue_date:  str = ""   # DBD

    # ── Identity ─────────────────────────────────────────────────────────────
    sex:            str = ""   # DBC  1=M 2=F 9=X
    license_class:  str = ""   # DCA
    license_number: str = ""   # DAQ  (appears on header line)

    # ── Address ──────────────────────────────────────────────────────────────
    address:  str = ""   # DAG
    city:     str = ""   # DAI
    state:    str = ""   # DAJ  2-letter
    zip_code: str = ""   # DAK  padded to 9 chars

    # ── Physical ─────────────────────────────────────────────────────────────
    height: str = ""   # DAU  3-digit total-inches e.g. "601"
    eyes:   str = ""   # DAY  e.g. "HAZ"
    hair:   str = ""   # DAB  e.g. "BRO"
    weight: str = ""   # DAW  lbs as string

    # ── Document ─────────────────────────────────────────────────────────────
    document_discriminator: str = ""   # DCF — always last, no trailing \n

    # ── Optional ─────────────────────────────────────────────────────────────
    country:            str = ""   # DCG  omitted if blank
    compliance_type:    str = ""   # DDA
    donor:              str = ""   # DDK  "1" = yes
    card_revision_date: str = ""   # DDB  MMDDYYYY
    endorsement:        str = ""   # DAT
    inventory:          str = ""   # DCK
    restriction:        str = ""   # DAR
    race_ethnicity:     str = ""   # DCL
    audit_information:  str = ""   # DCJ


class AAMVABuilder:
    """
    Produces a barcode payload byte-compatible with real scanner output.

    Output structure
    ----------------
        @\\n
        ANSI <IIN><ver><jur>02DL<offset><length>DL<DAQ><lic_num>\\n
        DCS<last>\\n
        <first_tag><first>\\n        ← DAC or DBC depending on first_tag
        DAD<middle>\\n               ← omitted if blank
        DBB<birth_date>\\n
        DBC<sex>\\n
        DBD<issue_date>\\n
        DBA<expiry_date>\\n
        DAG<address>\\n
        DAI<city>\\n
        DAJ<state>\\n
        DAK<zip9>\\n
        DAU<height>\\n               ← omitted if blank
        DAY<eyes>\\n                 ← omitted if blank
        DAB<hair>\\n                 ← omitted if blank
        DCA<license_class>\\n        ← omitted if blank
        DAW<weight>\\n               ← omitted if blank
        [optional fields]\\n
        DCF<document_discriminator>  ← no trailing newline
    """

    def build(self, data: AAMVAData) -> str:
        body_lines = self._body_lines(data)   # list of "TAG+value" strings

        # The header line contains: fixed prefix + "DL" + first body element (DAQ)
        daq_element = f"DAQ{data.license_number.strip()}"

        # offset = len of header line including its \n
        # "ANSI " + IIN(6) + ver(2) + jur(2) + "02DL" + offset(4) + length(4) + "DL" + daq + "\n"
        #  5      +  6     +  2     +  2     +   4   +    4       +    4       +  2   + len(daq) + 1
        prefix_fixed_len = 5 + 6 + 2 + 2 + 4 + 4 + 4 + 2   # = 29
        offset = prefix_fixed_len + len(daq_element) + 1      # +1 for \n

        header_line = (
            f"ANSI "
            f"{data.issuer_id}"
            f"{data.version}"
            f"{data.jurisdiction}"
            f"02"
            f"DL"
            f"{offset:04d}"
            f"{data.subfile_length}"
            f"DL"
            f"{daq_element}"
        )

        body = "\n".join(body_lines)   # last line (DCF) has no trailing \n

        return f"@\n{header_line}\n{body}"

    # ── private ──────────────────────────────────────────────────────────────

    def _body_lines(self, data: AAMVAData) -> list[str]:
        """
        Return body element strings in wire order.
        Blank optional values are omitted.
        DCF is always last.
        """
        s = lambda val: val.strip() if val else ""

        zip9 = s(data.zip_code).ljust(9)[:9]

        # Fixed-order mandatory/common elements
        elements: list[tuple[str, str, bool]] = [
            # (tag, value, omit_if_blank)
            ("DCS", s(data.last),          False),
            (data.first_tag, s(data.first), True),   # DAC or DBC
            ("DAD", s(data.middle),         True),
            ("DBB", s(data.birth_date),     False),
            ("DBC", s(data.sex),            False),
            ("DBD", s(data.issue_date),     False),
            ("DBA", s(data.expiry_date),    False),
            ("DAG", s(data.address),        False),
            ("DAI", s(data.city),           False),
            ("DAJ", s(data.state),          False),
            ("DAK", zip9,                   True),
            ("DAU", s(data.height),         True),
            ("DAY", s(data.eyes),           True),
            ("DAB", s(data.hair),           True),
            ("DCA", s(data.license_class),  True),
            ("DAW", s(data.weight),         True),
            # Optional
            ("DCG", s(data.country),            True),
            ("DDA", s(data.compliance_type),     True),
            ("DDK", s(data.donor),               True),
            ("DDB", s(data.card_revision_date),  True),
            ("DAT", s(data.endorsement),         True),
            ("DCK", s(data.inventory),           True),
            ("DAR", s(data.restriction),         True),
            ("DCL", s(data.race_ethnicity),      True),
            ("DCJ", s(data.audit_information),   True),
            # Always last
            ("DCF", s(data.document_discriminator), True),
        ]

        lines = []
        for tag, val, omit_blank in elements:
            if omit_blank and not val:
                continue
            lines.append(f"{tag}{val}")
        return lines


def build_from_dict(fields: dict) -> str:
    """Shortcut: build an AAMVA string from a plain dict."""
    data = AAMVAData(**{k: v for k, v in fields.items()
                        if k in AAMVAData.__dataclass_fields__})
    return AAMVABuilder().build(data)