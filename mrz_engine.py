from datetime import datetime, date
import unicodedata
from typing import Set, Protocol

from exceptions import MRZValidationError, MRZChronologyError
from models import (
    RawTD1Document, NormalizedTD1Document,
    ValidatedTD1Document, TD1MRZ,
    RawTD3Document, TD3MRZ,
    RawTD2Document, TD2MRZ,
    ValidatedTD3Document,
)

class CountryRegistryProtocol(Protocol):
    def validate(self, code: str) -> bool: ...

class PolicyValidatorProtocol(Protocol):
    def enforce_policy(self, dob: date, expiry: date) -> None: ...

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
                 policy: PolicyValidatorProtocol):
        self.registry = registry
        self.policy   = policy
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

class TD3Validator:
    def __init__(self, registry: CountryRegistryProtocol,
                 policy: PolicyValidatorProtocol):
        self.registry = registry
        self.policy   = policy
        self._valid_types = {"P", "PO", "PD", "PS", "PE", "PM", "P<"}

    def process(self, doc: NormalizedTD1Document) -> ValidatedTD3Document:
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
        if len(doc.optional_data1) > 14:
            raise MRZValidationError("Optional data (personal number) exceeds 14 characters.")

        try:
            dob_dt = datetime.strptime(doc.dob, "%y%m%d").date()
            exp_dt = datetime.strptime(doc.expiry, "%y%m%d").date()
        except ValueError:
            raise MRZValidationError("Dates must be in YYMMDD format (e.g. 900905).")

        if exp_dt <= dob_dt:
            raise MRZChronologyError(
                "Expiry date cannot be on or before date of birth.")

        self.policy.enforce_policy(dob_dt, exp_dt)

        return ValidatedTD3Document(
            document_type   = doc.document_type,
            issuing_country = doc.issuing_country,
            document_number = doc.document_number,
            dob             = doc.dob,
            gender          = doc.gender if doc.gender in ("M", "F") else "<",
            expiry          = doc.expiry,
            nationality     = doc.nationality,
            surname         = doc.surname,
            given_names     = doc.given_names,
            optional_data   = doc.optional_data1,
            dob_date        = dob_dt,
            expiry_date     = exp_dt,
        )

class TD3Serializer:
    def __init__(self):
        self.calc = CheckDigitCalculator()

    def serialize(self, doc: ValidatedTD3Document) -> TD3MRZ:
        doc_type    = doc.document_type.ljust(2, "<")[:2]
        country     = doc.issuing_country[:3].ljust(3, "<")
        doc_num     = doc.document_number.ljust(9, "<")[:9]
        dob         = doc.dob.ljust(6, "<")[:6]
        expiry      = doc.expiry.ljust(6, "<")[:6]
        nationality = doc.nationality[:3].ljust(3, "<")
        optional    = doc.optional_data.ljust(14, "<")[:14]
        gender      = doc.gender if doc.gender in ("M", "F") else "<"

        doc_chk = self.calc.calculate(doc_num)
        dob_chk = self.calc.calculate(dob)
        exp_chk = self.calc.calculate(expiry)
        opt_chk = self.calc.calculate(optional)

        # Composite check digit – ICAO 9303 excludes nationality and gender
        composite_str = (
            f"{doc_num}{doc_chk}"
            f"{dob}{dob_chk}"
            f"{expiry}{exp_chk}"
            f"{optional}{opt_chk}"
        )
        comp_chk = self.calc.calculate(composite_str)

        name_field = f"{doc.surname}<<{doc.given_names}".ljust(39, "<")[:39]
        line1 = f"{doc_type}{country}{name_field}"
        line2 = (
            f"{doc_num}{doc_chk}"
            f"{nationality}"
            f"{dob}{dob_chk}"
            f"{gender}"
            f"{expiry}{exp_chk}"
            f"{optional}{opt_chk}"
            f"{comp_chk}"
        )

        if len(line1) != 44:
            raise RuntimeError(f"TD3 line1 length is {len(line1)}, expected 44.")
        if len(line2) != 44:
            raise RuntimeError(f"TD3 line2 length is {len(line2)}, expected 44.")

        return TD3MRZ(line1=line1, line2=line2)

class TD3ProcessorPipeline:
    def __init__(self, registry: CountryRegistryProtocol,
                 policy: PolicyValidatorProtocol,
                 transliterator: MRZTransliterator):
        self.validator = TD3Validator(registry, policy)
        self.serializer = TD3Serializer()
        self.tx = transliterator

    def run(self, raw: RawTD3Document) -> TD3MRZ:
        normalizer = TD1Normalizer(self.tx)
        normalized = NormalizedTD1Document(
            document_type   = self.tx.clean(raw.document_type),
            issuing_country = self.tx.clean(raw.issuing_country),
            document_number = self.tx.clean(raw.document_number),
            dob             = self.tx.clean(raw.dob),
            gender          = raw.gender,
            expiry          = self.tx.clean(raw.expiry),
            nationality     = self.tx.clean(raw.nationality),
            surname         = self.tx.clean(raw.surname),
            given_names     = self.tx.clean(raw.given_names),
            optional_data1  = self.tx.clean(raw.optional_data),
            optional_data2  = "",
        )
        validated = self.validator.process(normalized)
        return self.serializer.serialize(validated)

def default_td3_pipeline() -> TD3ProcessorPipeline:
    return TD3ProcessorPipeline(
        registry       = ICAO3166Registry(),
        policy         = DefaultIssuerPolicyValidator(),
        transliterator = MRZTransliterator(),
    )

class TD2Validator:
    def __init__(self, registry: CountryRegistryProtocol,
                 policy: PolicyValidatorProtocol):
        self.registry = registry
        self.policy   = policy
        self._valid_types = {"A", "C", "I", "AC", "AI", "A<", "C<", "I<"}

    def process(self, doc: NormalizedTD1Document) -> ValidatedTD2Document:
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
        if len(doc.optional_data1) > 7:
            raise MRZValidationError("Optional data exceeds 7 characters.")

        try:
            dob_dt = datetime.strptime(doc.dob, "%y%m%d").date()
            exp_dt = datetime.strptime(doc.expiry, "%y%m%d").date()
        except ValueError:
            raise MRZValidationError("Dates must be in YYMMDD format (e.g. 900905).")

        if exp_dt <= dob_dt:
            raise MRZChronologyError(
                "Expiry date cannot be on or before date of birth.")

        self.policy.enforce_policy(dob_dt, exp_dt)

        return ValidatedTD2Document(
            document_type   = doc.document_type,
            issuing_country = doc.issuing_country,
            document_number = doc.document_number,
            dob             = doc.dob,
            gender          = doc.gender if doc.gender in ("M", "F") else "<",
            expiry          = doc.expiry,
            nationality     = doc.nationality,
            surname         = doc.surname,
            given_names     = doc.given_names,
            optional_data   = doc.optional_data1,
            dob_date        = dob_dt,
            expiry_date     = exp_dt,
        )

class TD2Serializer:
    def __init__(self):
        self.calc = CheckDigitCalculator()

    def serialize(self, doc: ValidatedTD2Document) -> TD2MRZ:
        doc_type    = doc.document_type.ljust(2, "<")[:2]
        country     = doc.issuing_country[:3].ljust(3, "<")
        doc_num     = doc.document_number.ljust(9, "<")[:9]
        dob         = doc.dob.ljust(6, "<")[:6]
        expiry      = doc.expiry.ljust(6, "<")[:6]
        nationality = doc.nationality[:3].ljust(3, "<")
        optional    = doc.optional_data.ljust(7, "<")[:7]
        gender      = doc.gender if doc.gender in ("M", "F") else "<"

        doc_chk = self.calc.calculate(doc_num)
        dob_chk = self.calc.calculate(dob)
        exp_chk = self.calc.calculate(expiry)
        opt_chk = self.calc.calculate(optional)

        # Composite check digit – ICAO excludes nationality and gender
        composite_str = (
            f"{doc_num}{doc_chk}"
            f"{dob}{dob_chk}"
            f"{expiry}{exp_chk}"
            f"{optional}{opt_chk}"
        )
        comp_chk = self.calc.calculate(composite_str)

        name_field = f"{doc.surname}<<{doc.given_names}".ljust(31, "<")[:31]
        line1 = f"{doc_type}{country}{name_field}"
        line2 = (
            f"{doc_num}{doc_chk}"
            f"{nationality}"
            f"{dob}{dob_chk}"
            f"{gender}"
            f"{expiry}{exp_chk}"
            f"{optional}{opt_chk}"
            f"{comp_chk}"
        )

        if len(line1) != 36:
            raise RuntimeError(f"TD2 line1 length is {len(line1)}, expected 36.")
        if len(line2) != 36:
            raise RuntimeError(f"TD2 line2 length is {len(line2)}, expected 36.")

        return TD2MRZ(line1=line1, line2=line2)

class UniversalMRZPipeline:
    def __init__(
        self,
        registry:      CountryRegistryProtocol,
        policy:        PolicyValidatorProtocol,
        transliterator: MRZTransliterator,
    ):
        self.tx            = transliterator
        self.td1_validator = TD1Validator(registry, policy)
        self.td2_validator = TD2Validator(registry, policy)
        self.td3_validator = TD3Validator(registry, policy)
        self.td1_serial    = TD1Serializer()
        self.td2_serial    = TD2Serializer()
        self.td3_serial    = TD3Serializer()

    def process_td1(self, raw: RawTD1Document) -> TD1MRZ:
        normalizer = TD1Normalizer(self.tx)
        normalized = normalizer.process(raw)
        validated  = self.td1_validator.process(normalized)
        return self.td1_serial.serialize(validated)

    def process_td2(self, raw: RawTD2Document) -> TD2MRZ:
        normalized = NormalizedTD1Document(
            document_type   = self.tx.clean(raw.document_type),
            issuing_country = self.tx.clean(raw.issuing_country),
            document_number = self.tx.clean(raw.document_number),
            dob             = self.tx.clean(raw.dob),
            gender          = raw.gender,
            expiry          = self.tx.clean(raw.expiry),
            nationality     = self.tx.clean(raw.nationality),
            surname         = self.tx.clean(raw.surname),
            given_names     = self.tx.clean(raw.given_names),
            optional_data1  = self.tx.clean(raw.optional_data),
            optional_data2  = "",
        )
        validated = self.td2_validator.process(normalized)
        return self.td2_serial.serialize(validated)

    def process_td3(self, raw: RawTD3Document) -> TD3MRZ:
        normalized = NormalizedTD1Document(
            document_type   = self.tx.clean(raw.document_type),
            issuing_country = self.tx.clean(raw.issuing_country),
            document_number = self.tx.clean(raw.document_number),
            dob             = self.tx.clean(raw.dob),
            gender          = raw.gender,
            expiry          = self.tx.clean(raw.expiry),
            nationality     = self.tx.clean(raw.nationality),
            surname         = self.tx.clean(raw.surname),
            given_names     = self.tx.clean(raw.given_names),
            optional_data1  = self.tx.clean(raw.optional_data),
            optional_data2  = "",
        )
        validated = self.td3_validator.process(normalized)
        return self.td3_serial.serialize(validated)

def default_universal_pipeline() -> UniversalMRZPipeline:
    return UniversalMRZPipeline(
        registry      = ICAO3166Registry(),
        policy        = DefaultIssuerPolicyValidator(),
        transliterator= MRZTransliterator(),
    )