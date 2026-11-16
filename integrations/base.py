"""Contratos (interfaces) para conectores de fontes oficiais e provedores de IA.

O MVP 1.0 **não** realiza consultas externas. Estes contratos definem como os
conectores futuros devem se integrar ao fluxo existente: cada conector produz
objetos ``PublicationIn`` que seguem o mesmo caminho do cadastro manual
(validação → persistência → triagem → auditoria).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from services.schemas import PublicationIn


class IntegrationNotAvailableError(NotImplementedError):
    """Lançada por conectores ainda não implementados."""


@dataclass(frozen=True)
class SourceInfo:
    key: str
    name: str
    description: str
    status: str
    credentials: str


class OfficialSource(ABC):
    info: SourceInfo

    @abstractmethod
    def fetch(self, start: date, end: date | None = None) -> list[PublicationIn]:
        """Retorna publicações do período, já normalizadas para o modelo interno."""


class AIProvider(ABC):
    """Provedor opcional de IA para resumo e classificação assistida."""

    @abstractmethod
    def summarize(self, text: str) -> str: ...

    @abstractmethod
    def suggest_classification(self, text: str, client_context: str) -> dict: ...
