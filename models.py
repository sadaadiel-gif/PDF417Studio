from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class RawTD1Document:
    document_type: str
    issuing_country: str
    document_number: str
    dob: str
    gender: str
    expiry: str
    nationality: str
    surname: str
    given_names: str
    optional_data1: str = ""
    optional_data2: str = ""

@dataclass(frozen=True)
class NormalizedTD1Document:
    document_type: str
    issuing_country: str
    document_number: str
    dob: str
    gender: str
    expiry: str
    nationality: str
    surname: str
    given_names: str
    optional_data1: str
    optional_data2: str

@dataclass(frozen=True)
class ValidatedTD1Document:
    document_type: str
    issuing_country: str
    document_number: str
    dob: str
    gender: str
    expiry: str
    nationality: str
    surname: str
    given_names: str
    optional_data1: str
    optional_data2: str
    dob_date: date
    expiry_date: date

@dataclass(frozen=True)
class TD1MRZ:
    line1: str
    line2: str
    line3: str

    @property
    def text(self) -> str:
        return f"{self.line1}\n{self.line2}\n{self.line3}"


# ── TD3 (Passport — 2 × 44 chars) ────────────────────────────────────────────

@dataclass(frozen=True)
class RawTD3Document:
    document_type:  str          # P, PO, PD, PS, PE, PM
    issuing_country:str          # 3-letter ICAO code
    document_number:str          # up to 9 chars
    dob:            str          # YYMMDD
    gender:         str          # M, F, or <
    expiry:         str          # YYMMDD
    nationality:    str          # 3-letter ICAO code
    surname:        str
    given_names:    str
    optional_data:  str = ""     # up to 14 chars (line 2 positions 29–42)

@dataclass(frozen=True)
class TD3MRZ:
    line1: str   # 44 chars
    line2: str   # 44 chars

    @property
    def text(self) -> str:
        return f"{self.line1}\n{self.line2}"


@dataclass(frozen=True)
class ValidatedTD3Document:
    document_type:   str
    issuing_country: str
    document_number: str
    dob:             str
    gender:          str
    expiry:          str
    nationality:     str
    surname:         str
    given_names:     str
    optional_data:   str
    dob_date:        "date"
    expiry_date:     "date"


# ── TD2 (Official / Diplomatic ID — 2 × 36 chars) ────────────────────────────

@dataclass(frozen=True)
class RawTD2Document:
    document_type:   str   # A, C, I, or any 2-char type
    issuing_country: str   # 3-letter ICAO code
    document_number: str   # up to 9 chars
    dob:             str   # YYMMDD
    gender:          str   # M, F, or <
    expiry:          str   # YYMMDD
    nationality:     str   # 3-letter ICAO code
    surname:         str
    given_names:     str
    optional_data:   str = ""  # up to 7 chars

@dataclass(frozen=True)
class TD2MRZ:
    line1: str   # 36 chars
    line2: str   # 36 chars

    @property
    def text(self) -> str:
        return f"{self.line1}\n{self.line2}"