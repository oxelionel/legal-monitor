"""Esquemas Pydantic para validação dos dados recebidos pela interface.

Mantidos independentes do Streamlit para que possam ser reutilizados
em uma futura API (FastAPI).
"""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services import constants as C
from services.text import only_digits, parse_keywords

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _cpf_valid(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d[i]) * (size + 1 - i) for i in range(size))
        digit = (total * 10) % 11 % 10
        if digit != int(d[size]):
            return False
    return True


def _cnpj_valid(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for size in (12, 13):
        w = weights[13 - size :]
        total = sum(int(d[i]) * w[i] for i in range(size))
        rest = total % 11
        digit = 0 if rest < 2 else 11 - rest
        if digit != int(d[size]):
            return False
    return True


def validate_document(value: str | None) -> str | None:
    digits = only_digits(value)
    if not digits:
        return None
    if len(digits) == 11 and _cpf_valid(digits):
        return digits
    if len(digits) == 14 and _cnpj_valid(digits):
        return digits
    raise ValueError("CPF/CNPJ inválido (verifique a quantidade de dígitos e os dígitos verificadores).")


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ClientIn(_Base):
    name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    document: str | None = None
    client_type: str = C.CLIENT_TYPES[0]
    email: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    responsible: str | None = Field(default=None, max_length=120)
    legal_area: str | None = None
    keywords: list[str] = Field(default_factory=list)
    notes: str | None = None
    status: str = "Ativo"
    is_demo: bool = False

    _blank = field_validator("trade_name", "email", "phone", "responsible", "legal_area", "notes", mode="before")(
        _blank_to_none
    )

    @field_validator("document", mode="before")
    @classmethod
    def _doc(cls, v):
        return validate_document(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v and not _EMAIL_RE.match(v):
            raise ValueError("E-mail inválido.")
        return v.lower() if v else v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if v and not 8 <= len(only_digits(v)) <= 13:
            raise ValueError("Telefone deve conter entre 8 e 13 dígitos.")
        return v

    @field_validator("client_type")
    @classmethod
    def _type(cls, v):
        if v not in C.CLIENT_TYPES:
            raise ValueError(f"Tipo de cliente inválido: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v not in C.CLIENT_STATUS:
            raise ValueError(f"Status inválido: {v}")
        return v

    @field_validator("legal_area")
    @classmethod
    def _area(cls, v):
        if v and v not in C.LEGAL_AREAS:
            raise ValueError(f"Área jurídica inválida: {v}")
        return v

    @field_validator("keywords", mode="before")
    @classmethod
    def _keywords(cls, v):
        terms = parse_keywords(v)
        too_short = [t for t in terms if len(t) < 3]
        if too_short:
            raise ValueError(f"Palavras-chave devem ter ao menos 3 caracteres: {', '.join(too_short)}")
        return terms

    @model_validator(mode="after")
    def _doc_matches_type(self):
        if self.document and self.client_type == "Pessoa física" and len(self.document) != 11:
            raise ValueError("Pessoa física deve possuir CPF (11 dígitos).")
        return self


class PublicationIn(_Base):
    title: str = Field(min_length=3, max_length=300)
    agency: str = Field(min_length=2, max_length=200)
    source: str = Field(min_length=2, max_length=120)
    number: str | None = Field(default=None, max_length=80)
    publication_date: date
    legal_area: str
    doc_type: str
    content: str = Field(min_length=20)
    url: str | None = None
    is_demo: bool = False

    _blank = field_validator("number", "url", mode="before")(_blank_to_none)

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        if v and not _URL_RE.match(v):
            raise ValueError("URL deve começar com http:// ou https://")
        return v

    @field_validator("legal_area")
    @classmethod
    def _area(cls, v):
        if v not in C.LEGAL_AREAS:
            raise ValueError(f"Área jurídica inválida: {v}")
        return v

    @field_validator("doc_type")
    @classmethod
    def _doc_type(cls, v):
        if v not in C.DOC_TYPES:
            raise ValueError(f"Tipo de documento inválido: {v}")
        return v

    @field_validator("publication_date")
    @classmethod
    def _date(cls, v):
        if v > date.today():
            raise ValueError("A data de publicação não pode estar no futuro.")
        return v


class DeadlineIn(_Base):
    description: str = Field(min_length=3, max_length=300)
    publication_id: int | None = None
    client_id: int | None = None
    date_type: str = C.DATE_TYPES[0]
    reference_date: date | None = None
    due_date: date | None = None
    responsible: str | None = Field(default=None, max_length=120)
    status: str = "Pendente"
    notes: str | None = None
    validated: bool = False
    origin: str = "Manual"
    is_demo: bool = False

    _blank = field_validator("responsible", "notes", mode="before")(_blank_to_none)

    @field_validator("date_type")
    @classmethod
    def _dt(cls, v):
        if v not in C.DATE_TYPES:
            raise ValueError(f"Tipo de data inválido: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v not in C.DEADLINE_STATUS:
            raise ValueError(f"Status inválido: {v}")
        return v

    @field_validator("origin")
    @classmethod
    def _origin(cls, v):
        if v not in C.DEADLINE_ORIGINS:
            raise ValueError(f"Origem inválida: {v}")
        return v

    @model_validator(mode="after")
    def _dates(self):
        if self.reference_date and self.due_date and self.due_date < self.reference_date:
            raise ValueError("A data limite sugerida não pode ser anterior à data de referência.")
        return self
