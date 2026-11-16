"""Identificação de menções a datas e prazos no texto das publicações.

ATENÇÃO: este módulo produz apenas **indícios** para apoiar o profissional.
Nenhuma data identificada é tratada como prazo definitivo, e a data de
publicação não é presumida como termo inicial de contagem. A natureza da
data (vigência, prazo administrativo, prazo processual etc.) é sugerida por
heurística de contexto e deve ser confirmada pelo responsável.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from services.text import strip_accents

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_WRITTEN_DATE = re.compile(
    r"\b(\d{1,2})(?:º|o)?\s+de\s+(" + "|".join(MONTHS) + r")\s+de\s+(\d{4})\b", re.IGNORECASE
)
_PERIOD = re.compile(
    r"\bprazo\s+(?:de\s+|maximo\s+de\s+|improrrogavel\s+de\s+)?(?:ate\s+)?(\d{1,3})\s*(?:\([^)]{1,40}\)\s*)?"
    r"(dias?\s+uteis|dias?\s+corridos|dias?|horas?|meses|mes)\b",
    re.IGNORECASE,
)

_CONTEXT_RULES = [
    ("Data de vigência", ("vigor", "vigencia", "vigorar", "produz efeitos", "produzira efeitos")),
    ("Prazo processual", ("intimad", "intimacao", "contestacao", "recurso", "manifestacao nos autos",
                          "processo n", "autos", "embargos", "apelacao", "cumprimento de sentenca")),
    ("Prazo administrativo", ("defesa", "impugnacao", "processo administrativo", "auto de infracao",
                              "notifica", "regularizacao", "apresentar", "proposta", "habilitacao")),
    ("Obrigação contratual", ("contrato", "vigencia contratual", "aditivo", "entrega")),
]


@dataclass
class DateMention:
    kind: str  # "data" ou "período"
    snippet: str
    suggested_type: str
    value: date | None = None
    amount: int | None = None
    unit: str | None = None

    @property
    def summary(self) -> str:
        if self.kind == "data" and self.value:
            return f"{self.value:%d/%m/%Y} — {self.suggested_type} (sugestão)"
        return f"{self.amount} {self.unit} — {self.suggested_type} (sugestão)"


def _context(text: str, start: int, end: int, width: int = 90) -> str:
    return text[max(0, start - width) : min(len(text), end + width)].replace("\n", " ").strip()


def _typing_window(text: str, start: int, end: int) -> str:
    """Contexto usado para sugerir a natureza: privilegia o texto que antecede a menção."""
    return text[max(0, start - 80) : min(len(text), end + 15)]


def _suggest_type(snippet: str, is_period: bool = False) -> str:
    low = strip_accents(snippet).lower()
    for label, keys in _CONTEXT_RULES:
        if is_period and label == "Data de vigência":
            continue  # um período ("prazo de N dias") não é, em si, uma data de vigência
        if any(k in low for k in keys):
            return label
    return "Outra data relevante"


def extract_mentions(text: str) -> list[DateMention]:
    plain = strip_accents(text)
    mentions: list[DateMention] = []
    seen: set[tuple] = set()

    def _add_date(d: int, m: int, y: int, start: int, end: int) -> None:
        try:
            value = date(y, m, d)
        except ValueError:
            return
        key = ("data", value)
        if key in seen:
            return
        seen.add(key)
        snippet = _context(text, start, end)
        mentions.append(DateMention("data", snippet, _suggest_type(_typing_window(text, start, end)), value=value))

    for m in _NUMERIC_DATE.finditer(plain):
        _add_date(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.start(), m.end())
    for m in _WRITTEN_DATE.finditer(plain):
        _add_date(int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3)), m.start(), m.end())
    for m in _PERIOD.finditer(plain):
        amount, unit = int(m.group(1)), m.group(2).lower()
        key = ("periodo", amount, unit)
        if key in seen:
            continue
        seen.add(key)
        snippet = _context(text, m.start(), m.end())
        mentions.append(DateMention("período", snippet, _suggest_type(_typing_window(text, m.start(), m.end()), is_period=True), amount=amount, unit=unit))
    return mentions
