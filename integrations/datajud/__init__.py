"""Conector planejado para a API Pública do DataJud (CNJ).

Planejamento: consulta de metadados e movimentações de processos por número
CNJ, permitindo vincular publicações a processos monitorados. Exige chave de
API pública (variável ``DATAJUD_API_KEY``). Não implementado no MVP 1.0.
"""
from __future__ import annotations

from datetime import date

from integrations.base import IntegrationNotAvailableError, OfficialSource, SourceInfo

INFO = SourceInfo(
    key="datajud",
    name="DataJud — API Pública (CNJ)",
    description="Metadados e movimentações processuais dos tribunais brasileiros.",
    status="Planejado (roadmap 1.2)",
    credentials="Chave pública de API do DataJud",
)


class DatajudSource(OfficialSource):
    info = INFO

    def fetch(self, start: date, end: date | None = None):
        raise IntegrationNotAvailableError("Integração com o DataJud ainda não implementada no MVP 1.0.")
