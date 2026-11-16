"""Camada planejada de inteligência artificial.

No MVP 1.0 a classificação é feita exclusivamente pelo motor de regras
transparentes (``services/matching.py`` e ``services/classification.py``).
Um provedor de IA poderá, futuramente, sugerir resumos e classificações —
sempre como apoio, nunca substituindo a validação profissional.
"""
from __future__ import annotations

from integrations.base import AIProvider, IntegrationNotAvailableError, SourceInfo

INFO = SourceInfo(
    key="ai",
    name="Assistente de IA (resumo e classificação)",
    description="Resumo automático de publicações e sugestão de classificação com modelos de linguagem.",
    status="Planejado (roadmap 2.0)",
    credentials="Chave de API do provedor escolhido (AI_API_KEY)",
)


class DisabledAIProvider(AIProvider):
    def summarize(self, text: str) -> str:
        raise IntegrationNotAvailableError("Provedor de IA não configurado no MVP 1.0.")

    def suggest_classification(self, text: str, client_context: str) -> dict:
        raise IntegrationNotAvailableError("Provedor de IA não configurado no MVP 1.0.")
