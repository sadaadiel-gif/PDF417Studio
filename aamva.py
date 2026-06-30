from dataclasses import dataclass, field

@dataclass
class AAMVAData:
    issuer_id:      str = "636000"
    version:        str = "01"
    jurisdiction:   str = "01"
    subfile_length: str = "0278"

    last:   str = ""
    first:  str = ""
    middle: str = ""

    first_tag: str = "DAC"

    birth_date:  str = ""
    expiry_date: str = ""
    issue_date:  str = ""

    sex:            str = ""
    license_class:  str = ""
    license_number: str = ""

    address:  str = ""
    city:     str = ""
    state:    str = ""
    zip_code: str = ""

    height: str = ""
    eyes:   str = ""
    hair:   str = ""
    weight: str = ""

    document_discriminator: str = ""

    country:            str = ""
    compliance_type:    str = ""
    donor:              str = ""
    card_revision_date: str = ""
    endorsement:        str = ""
    inventory:          str = ""
    restriction:        str = ""
    race_ethnicity:     str = ""
    audit_information:  str = ""


class AAMVABuilder:
    def build(self, data: AAMVAData) -> str:
        body = self._build_body(data)
        header = self._build_header(data, body)
        # The required AAMVA record terminator: CR LF EOT
        return f"@\n{header}\n{body}\r\n\x04"

    def build_bytes(self, data: AAMVAData) -> bytes:
        return self.build(data).encode("utf-8")

    def _build_header(self, data: AAMVAData, body: str) -> str:
        daq_element = f"DAQ{data.license_number.strip()}"
        prefix_fixed_len = 5 + 6 + 2 + 2 + 4 + 4 + 4 + 2
        offset = prefix_fixed_len + len(daq_element) + 1
        return (
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

    def _build_body(self, data: AAMVAData) -> str:
        def s(val: str) -> str:
            return val.strip() if val else ""

        zip9 = s(data.zip_code).ljust(9)[:9]

        elements: list[tuple[str, str, bool]] = [
            ("DCS", s(data.last),          False),
            (data.first_tag, s(data.first), True),
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
            ("DCG", s(data.country),            True),
            ("DDA", s(data.compliance_type),     True),
            ("DDK", s(data.donor),               True),
            ("DDB", s(data.card_revision_date),  True),
            ("DAT", s(data.endorsement),         True),
            ("DCK", s(data.inventory),           True),
            ("DAR", s(data.restriction),         True),
            ("DCL", s(data.race_ethnicity),      True),
            ("DCJ", s(data.audit_information),   True),
            ("DCF", s(data.document_discriminator), True),
        ]

        lines = []
        for tag, val, omit_blank in elements:
            if omit_blank and not val:
                continue
            lines.append(f"{tag}{val}")
        return "\n".join(lines)


def build_from_dict(fields: dict) -> str:
    data = AAMVAData(**{k: v for k, v in fields.items()
                        if k in AAMVAData.__dataclass_fields__})
    return AAMVABuilder().build(data)