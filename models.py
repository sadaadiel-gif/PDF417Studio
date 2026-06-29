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



@dataclass(frozen=True)
class RawTD3Document:
    document_type:  str
    issuing_country:str
    document_number:str
    dob:            str
    gender:         str
    expiry:         str
    nationality:    str
    surname:        str
    given_names:    str
    optional_data:  str = ""

@dataclass(frozen=True)
class TD3MRZ:
    line1: str
    line2: str

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



@dataclass(frozen=True)
class RawTD2Document:
    document_type:   str
    issuing_country: str
    document_number: str
    dob:             str
    gender:          str
    expiry:          str
    nationality:     str
    surname:         str
    given_names:     str
    optional_data:   str = ""

@dataclass(frozen=True)
class TD2MRZ:
    line1: str
    line2: str

    @property
    def text(self) -> str:
        return f"{self.line1}\n{self.line2}"