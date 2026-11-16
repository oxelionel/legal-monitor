"""Utilitários de normalização de texto usados pelo motor de correspondência."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(value: str | None) -> str:
    """Minúsculas, sem acentos, pontuação convertida em espaço e espaços colapsados."""
    if not value:
        return ""
    text = strip_accents(value).lower()
    text = _NON_ALNUM.sub(" ", text)
    return _WS.sub(" ", text).strip()


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def tokens(value: str) -> list[str]:
    return normalize(value).split()


def format_document(digits: str | None) -> str:
    """Formata CPF (11) ou CNPJ (14) para exibição."""
    d = only_digits(digits)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return d


def parse_keywords(raw: str | list[str] | None) -> list[str]:
    """Aceita texto separado por vírgula, ponto e vírgula ou quebra de linha."""
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else re.split(r"[,;\n]", raw)
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        term = _WS.sub(" ", str(item)).strip()
        key = normalize(term)
        if term and key and key not in seen:
            seen.add(key)
            result.append(term)
    return result
