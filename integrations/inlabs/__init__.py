"""Conector planejado para o INLABS (Imprensa Nacional) — Diário Oficial da União.

Planejamento:
1. Autenticar com e-mail/senha do INLABS (variáveis ``INLABS_EMAIL`` e ``INLABS_PASSWORD``).
2. Baixar os arquivos XML/ZIP das seções do DOU do dia.
3. Converter cada matéria em ``PublicationIn`` (título, órgão, número, data, conteúdo, URL).
4. Entregar ao fluxo padrão de cadastro e triagem.

Não implementado no MVP 1.0 — nenhuma requisição externa é feita.
"""
from __future__ import annotations

from datetime import date

from integrations.base import IntegrationNotAvailableError, OfficialSource, SourceInfo

INFO = SourceInfo(
    key="inlabs",
    name="Diário Oficial da União (INLABS)",
    description="Download diário das seções do DOU em XML pela plataforma INLABS da Imprensa Nacional.",
    status="Planejado (roadmap 1.1)",
    credentials="Cadastro gratuito no INLABS (e-mail e senha)",
)


class InlabsSource(OfficialSource):
    info = INFO

    def fetch(self, start: date, end: date | None = None):
        raise IntegrationNotAvailableError("Integração com o INLABS ainda não implementada no MVP 1.0.")
