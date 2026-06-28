"""
mrz_engine.py
ICAO TD1 MRZ generation pipeline.
"""

from datetime import datetime, date
import unicodedata
from typing import Set, Protocol

from exceptions import MRZValidationError, MRZChronologyError
from models import (
    RawTD1Document, NormalizedTD1Document,
    ValidatedTD1Document, TD1MRZ,
)


# ── Protocols ────────────────────────────────────────────────────────────────

class CountryRegistryProtocol(Protocol):
    def validate(self, code: str) -> bool: ...

class PolicyValidatorProtocol(Protocol):
    def enforce_policy(self, dob: date, expiry: date) -> None: ...


# ── Standard implementations ─────────────────────────────────────────────────

class ICAO3166Registry:
    def __init__(self):
        self._codes: Set[str] = {
            "AFG","ALB","DZA","AND","AGO","ATG","ARG","ARM","AUS","AUT",
            "AZE","BHS","BHR","BGD","BRB","BLR","BEL","BLZ","BEN","BTN",
            "BOL","BIH","BWA","BRA","BRN","BGR","BFA","BDI","CPV","KHM",
            "CMR","CAN","CAF","TCD","CHL","CHN","COL","COM","COD","COG",
            "CRI","CIV","HRV","CUB","CYP","CZE","DNK","DJI","DOM","ECU",
            "EGY","SLV","GNQ","ERI","EST","SWZ","ETH","FJI","FIN","FRA",
            "GAB","GMB","GEO","DEU","GHA","GRC","GRD","GTM","GIN","GNB",
            "GUY","HTI","HND","HUN","ISL","IND","IDN","IRN","IRQ","IRL",
            "ISR","ITA","JAM","JPN","JOR","KAZ","KEN","KIR","PRK","KOR",
            "KWT","KGZ","LAO","LVA","LBN","LSO","LBR","LBY","LIE","LTU",
            "LUX","MDG","MWI","MYS","MDV","MLI","MLT","MHL","MRT","MUS",
            "MEX","FSM","MDA","MCO","MNG","MNE","MAR","MOZ","MMR","NAM",
            "NRU","NPL","NLD","NZL","NIC","NER","NGA","MKD","NOR","OMN",
            "PAK","PLW","PAN","PNG","PRY","PER","PHL","POL","PRT","QAT",
            "ROU","RUS","RWA","KNA","LCA","VCT","WSM","SMR","STP","SAU",
            "SEN","SRB","SYC","SLE","SGP","SVK","SVN","SLB","SOM","ZAF",
            "SSD","ESP","LKA","SDN","SUR","SWE","CHE","SYR","TWN","TJK",
            "TZA","THA","TLS","TGO","TON","TTO","TUN","TUR","TKM","TUV",
            "UGA","UKR","ARE","GBR","USA","URY","UZB","VUT","VEN","VNM",
            "YEM","ZMB","ZWE",
            "UTO","XPO","XOM","XXA","XXB","XXC","XXX","D<<",
        }

    def validate(self, code: str) -> bool:
        return code in self._codes


class DefaultIssuerPolicyValidator:
    def enforce_policy(self, dob: date, expiry: date) -> None:
        today = date.today()
        if dob > today:
            raise MRZChronologyError("Date of Birth cannot occur in the future.")
        if expiry <= today:
            raise MRZChronologyError("Document has already physically expired.")


class MRZTransliterator:
    _ALLOWED_SET: Set[str] = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
    _ICAO_MAP = str.maketrans({
        "Ä":"AE","Å":"AA","Æ":"AE","Ö":"OE","Ø":"OE","Ü":"UE","ß":"SS",
        "Ĳ":"IJ","Œ":"OE","Ñ":"N","Ć":"C","Č":"C","Ď":"D","Đ":"D",
        "Ę":"E","Ì":"I","Ł":"L","Ĺ":"L","Ń":"N","Ň":"N","Ŕ":"R",
        "Ř":"R","Ś":"S","Š":"S","Ť":"T","Ů":"U","Ý":"Y","Ź":"Z",
        "Ž":"Z","Þ":"TH","Ð":"DH","Ç":"C",
    })

    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = text.upper().translate(self._ICAO_MAP)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = text.replace(" ", "<")
        for char in text:
            if char not in self._ALLOWED_SET:
                raise MRZValidationError(
                    f"Forbidden character '{char}' in payload.")
        return text


# ── Pipeline stages ───────────────────────────────────────────────────────────

class TD1Normalizer:
    def __init__(self, transliterator: MRZTransliterator):
        self.tx = transliterator

    def process(self, doc: RawTD1Document) -> NormalizedTD1Document:
        return NormalizedTD1Document(
            document_type  = self.tx.clean(doc.document_type),
            issuing_country= self.tx.clean(doc.issuing_country),
            document_number= self.tx.clean(doc.document_number),
            dob            = self.tx.clean(doc.dob),
            gender         = self.tx.clean(doc.gender),
            expiry         = self.tx.clean(doc.expiry),
            nationality    = self.tx.clean(doc.nationality),
            surname        = self.tx.clean(doc.surname),
            given_names    = self.tx.clean(doc.given_names),
            optional_data1 = self.tx.clean(doc.optional_data1),
            optional_data2 = self.tx.clean(doc.optional_data2),
        )


class TD1Validator:
    def __init__(self, registry: CountryRegistryProtocol,
                 issuer_policy: PolicyValidatorProtocol):
        self.registry = registry
        self.policy   = issuer_policy
        self._valid_types = {"I", "ID", "A", "C"}

    def process(self, doc: NormalizedTD1Document) -> ValidatedTD1Document:
        if doc.document_type not in self._valid_types:
            raise MRZValidationError(
                f"Unsupported document type: '{doc.document_type}'")
        if not self.registry.validate(doc.issuing_country):
            raise MRZValidationError(
                f"Unrecognised issuing country: '{doc.issuing_country}'")
        if not self.registry.validate(doc.nationality):
            raise MRZValidationError(
                f"Unrecognised nationality: '{doc.nationality}'")
        if len(doc.document_number) > 9:
            raise MRZValidationError("Document number exceeds 9 characters.")
        if len(doc.optional_data1) > 15:
            raise MRZValidationError("Optional data 1 exceeds 15 characters.")
        if len(doc.optional_data2) > 11:
            raise MRZValidationError("Optional data 2 exceeds 11 characters.")

        try:
            dob_dt = datetime.strptime(doc.dob, "%y%m%d").date()
            exp_dt = datetime.strptime(doc.expiry, "%y%m%d").date()
        except ValueError:
            raise MRZValidationError("Dates must be in YYMMDD format (e.g. 900905).")

        if exp_dt <= dob_dt:
            raise MRZChronologyError(
                "Expiry date cannot be on or before date of birth.")

        self.policy.enforce_policy(dob_dt, exp_dt)

        return ValidatedTD1Document(
            document_type   = doc.document_type,
            issuing_country = doc.issuing_country,
            document_number = doc.document_number,
            dob             = doc.dob,
            gender          = doc.gender,
            expiry          = doc.expiry,
            nationality     = doc.nationality,
            surname         = doc.surname,
            given_names     = doc.given_names,
            optional_data1  = doc.optional_data1,
            optional_data2  = doc.optional_data2,
            dob_date        = dob_dt,
            expiry_date     = exp_dt,
        )


class CheckDigitCalculator:
    @staticmethod
    def calculate(data_str: str) -> str:
        weights = [7, 3, 1]
        total = 0
        for i, char in enumerate(data_str):
            if char.isdigit():
                val = int(char)
            elif char.isalpha():
                val = ord(char) - ord('A') + 10
            else:
                val = 0
            total += val * weights[i % 3]
        return str(total % 10)


class TD1Serializer:
    def __init__(self):
        self.calc = CheckDigitCalculator()

    def serialize(self, doc: ValidatedTD1Document) -> TD1MRZ:
        doc_padded  = doc.document_number.ljust(9, "<")
        doc_chk     = self.calc.calculate(doc_padded)
        opt1_padded = doc.optional_data1.ljust(15, "<")
        opt2_padded = doc.optional_data2.ljust(11, "<")
        dob_chk     = self.calc.calculate(doc.dob)
        exp_chk     = self.calc.calculate(doc.expiry)
        gender_char = doc.gender if doc.gender in ("M", "F") else "<"

        composite = (
            f"{doc_padded}{doc_chk}{opt1_padded}"
            f"{doc.dob}{dob_chk}{doc.expiry}{exp_chk}{opt2_padded}"
        )
        composite_chk = self.calc.calculate(composite)

        line1 = (f"{doc.document_type.ljust(2,'<')}{doc.issuing_country}"
                 f"{doc_padded}{doc_chk}{opt1_padded}")
        line2 = (f"{doc.dob}{dob_chk}{gender_char}{doc.expiry}{exp_chk}"
                 f"{doc.nationality}{opt2_padded}{composite_chk}")
        name_block = (f"{doc.surname}<<{doc.given_names}"
                      if doc.surname else f"<<{doc.given_names}")
        line3 = name_block.ljust(30, "<")[:30]

        for ln, label in ((line1,"Line 1"),(line2,"Line 2"),(line3,"Line 3")):
            if len(ln) != 30:
                raise RuntimeError(
                    f"MRZ {label} length is {len(ln)}, expected 30.")

        return TD1MRZ(line1=line1, line2=line2, line3=line3)


# ── High-level coordinator ────────────────────────────────────────────────────

class TD1ProcessorPipeline:
    def __init__(
        self,
        registry: CountryRegistryProtocol,
        policy: PolicyValidatorProtocol,
        transliterator: MRZTransliterator,
    ):
        self.normalizer = TD1Normalizer(transliterator)
        self.validator  = TD1Validator(registry, policy)
        self.serializer = TD1Serializer()

    def run(self, raw: RawTD1Document) -> TD1MRZ:
        normalized = self.normalizer.process(raw)
        validated  = self.validator.process(normalized)
        return self.serializer.serialize(validated)


def default_pipeline() -> TD1ProcessorPipeline:
    return TD1ProcessorPipeline(
        registry       = ICAO3166Registry(),
        policy         = DefaultIssuerPolicyValidator(),
        transliterator = MRZTransliterator(),
    )


# ── TD3 Pipeline ─────────────────────────────────────────────────────────────

from models import RawTD3Document, TD3MRZ


class TD3Serializer:
    """
    Produces a 2 × 44 char TD3 MRZ (passport).

    Line 1:  doc_type(2) + issuing_country(3) + name_field(39)
    Line 2:  doc_number(9) + chk(1) + nationality(3) + dob(6) + chk(1) +
             gender(1) + expiry(6) + chk(1) + optional(14) + chk(1)
    """

    def __init__(self):
        self.calc = CheckDigitCalculator()

    def serialize(self, raw: RawTD3Document,
                  transliterator: "MRZTransliterator") -> TD3MRZ:
        tx = transliterator.clean

        doc_type    = tx(raw.document_type).ljust(2, "<")[:2]
        country     = tx(raw.issuing_country)[:3]
        doc_num     = tx(raw.document_number).ljust(9, "<")[:9]
        dob         = tx(raw.dob)[:6]
        gender      = raw.gender if raw.gender in ("M", "F") else "<"
        expiry      = tx(raw.expiry)[:6]
        nationality = tx(raw.nationality)[:3]
        optional    = tx(raw.optional_data).ljust(14, "<")[:14]
        surname     = tx(raw.surname)
        given       = tx(raw.given_names)

        doc_chk    = self.calc.calculate(doc_num)
        dob_chk    = self.calc.calculate(dob)
        exp_chk    = self.calc.calculate(expiry)
        opt_chk    = self.calc.calculate(optional)

        # Composite check: positions 1-10 + 14-20 + 22-43 of line 2
        composite_str = doc_num + doc_chk + dob + dob_chk + gender + expiry + exp_chk + optional
        comp_chk = self.calc.calculate(composite_str)

        # Line 1 — name field is 39 chars
        name_field = f"{surname}<<{given}".ljust(39, "<")[:39]
        line1 = f"{doc_type}{country}{name_field}"

        # Line 2
        line2 = (
            f"{doc_num}{doc_chk}"
            f"{nationality}"
            f"{dob}{dob_chk}"
            f"{gender}"
            f"{expiry}{exp_chk}"
            f"{optional}{comp_chk}"
        )

        if len(line1) != 44 or len(line2) != 44:
            raise RuntimeError(
                f"TD3 line length error: L1={len(line1)} L2={len(line2)} (expected 44)"
            )

        return TD3MRZ(line1=line1, line2=line2)


class TD3ProcessorPipeline:
    def __init__(self, transliterator: MRZTransliterator):
        self.tx = transliterator
        self.serializer = TD3Serializer()

    def run(self, raw: RawTD3Document) -> TD3MRZ:
        return self.serializer.serialize(raw, self.tx)


def default_td3_pipeline() -> TD3ProcessorPipeline:
    return TD3ProcessorPipeline(MRZTransliterator())


# ── Universal Pipeline (TD1 + TD3) ───────────────────────────────────────────

from models import ValidatedTD3Document, NormalizedTD1Document


class UniversalMRZPipeline:
    """
    Single pipeline that handles both TD1 (ID cards) and TD3 (passports).
    Shared normalization and validation; format-specific serialization.
    """

    def __init__(
        self,
        registry:      CountryRegistryProtocol,
        policy:        PolicyValidatorProtocol,
        transliterator: MRZTransliterator,
    ):
        self.tx            = transliterator
        self.td1_validator = TD1Validator(registry, policy)
        self.td1_serial    = TD1Serializer()
        self.td3_serial    = TD3Serializer()

    # ── TD1 ──────────────────────────────────────────────────────────────────

    def process_td1(self, raw: "RawTD1Document") -> "TD1MRZ":
        normalizer = TD1Normalizer(self.tx)
        normalized = normalizer.process(raw)
        validated  = self.td1_validator.process(normalized)
        return self.td1_serial.serialize(validated)

    # ── TD3 ──────────────────────────────────────────────────────────────────

    def process_td3(self, raw: "RawTD3Document") -> "TD3MRZ":
        tx = self.tx.clean

        # 1. Normalize — reuse the shared transliterator
        normalized = NormalizedTD1Document(
            document_type   = tx(raw.document_type),
            issuing_country = tx(raw.issuing_country),
            document_number = tx(raw.document_number),
            dob             = tx(raw.dob),
            gender          = raw.gender if raw.gender in ("M", "F") else "<",
            expiry          = tx(raw.expiry),
            nationality     = tx(raw.nationality),
            surname         = tx(raw.surname),
            given_names     = tx(raw.given_names),
            optional_data1  = tx(raw.optional_data),
            optional_data2  = "",
        )

        # 2. Validate — reuse shared TD1Validator (structural + chronology checks)
        validated_td1 = self.td1_validator.process(normalized)

        # 3. Map to ValidatedTD3Document
        validated = ValidatedTD3Document(
            document_type   = validated_td1.document_type,
            issuing_country = validated_td1.issuing_country,
            document_number = validated_td1.document_number,
            dob             = validated_td1.dob,
            gender          = validated_td1.gender,
            expiry          = validated_td1.expiry,
            nationality     = validated_td1.nationality,
            surname         = validated_td1.surname,
            given_names     = validated_td1.given_names,
            optional_data   = validated_td1.optional_data1,
            dob_date        = validated_td1.dob_date,
            expiry_date     = validated_td1.expiry_date,
        )

        # 4. Serialize into 2 × 44
        return self.td3_serial.serialize(validated, self.tx)


def default_universal_pipeline() -> UniversalMRZPipeline:
    return UniversalMRZPipeline(
        registry      = ICAO3166Registry(),
        policy        = DefaultIssuerPolicyValidator(),
        transliterator= MRZTransliterator(),
    )


# ── TD2 Serializer (2 × 36) ───────────────────────────────────────────────────

from models import RawTD2Document, TD2MRZ


class TD2Serializer:
    """
    Produces a 2 × 36 character TD2 MRZ (official/diplomatic ID cards).

    Line 1:  doc_type(2) + country(3) + name(31)
    Line 2:  doc_number(9) + chk(1) + nationality(3) + dob(6) + chk(1) +
             gender(1) + expiry(6) + chk(1) + optional(7) + composite_chk(1)
    """

    def __init__(self):
        self.calc = CheckDigitCalculator()

    def serialize(self, raw: RawTD2Document,
                  transliterator: "MRZTransliterator") -> TD2MRZ:
        tx = transliterator.clean

        doc_type    = tx(raw.document_type).ljust(2, "<")[:2]
        country     = tx(raw.issuing_country)[:3]
        doc_num     = tx(raw.document_number).ljust(9, "<")[:9]
        dob         = tx(raw.dob)[:6]
        gender      = raw.gender if raw.gender in ("M", "F") else "<"
        expiry      = tx(raw.expiry)[:6]
        nationality = tx(raw.nationality)[:3]
        optional    = tx(raw.optional_data).ljust(7, "<")[:7]
        surname     = tx(raw.surname)
        given       = tx(raw.given_names)

        doc_chk  = self.calc.calculate(doc_num)
        dob_chk  = self.calc.calculate(dob)
        exp_chk  = self.calc.calculate(expiry)

        # Composite: doc_num+chk + dob+chk + gender + expiry+chk + optional
        composite_str = doc_num + doc_chk + dob + dob_chk + gender + expiry + exp_chk + optional
        comp_chk = self.calc.calculate(composite_str)

        # Line 1 — name field is 31 chars (36 - 2 type - 3 country)
        name_field = f"{surname}<<{given}".ljust(31, "<")[:31]
        line1 = f"{doc_type}{country}{name_field}"

        # Line 2 — 36 chars
        line2 = (
            f"{doc_num}{doc_chk}"
            f"{nationality}"
            f"{dob}{dob_chk}"
            f"{gender}"
            f"{expiry}{exp_chk}"
            f"{optional}"
            f"{comp_chk}"
        )

        if len(line1) != 36 or len(line2) != 36:
            raise RuntimeError(
                f"TD2 line length error: L1={len(line1)} L2={len(line2)} (expected 36)"
            )

        return TD2MRZ(line1=line1, line2=line2)


# ── Extend UniversalMRZPipeline with TD2 ─────────────────────────────────────

# Patch process_td2 onto UniversalMRZPipeline dynamically so we don't rewrite it

def _process_td2(self, raw: RawTD2Document) -> TD2MRZ:
    serializer = TD2Serializer()
    return serializer.serialize(raw, self.tx)

UniversalMRZPipeline.process_td2 = _process_td2