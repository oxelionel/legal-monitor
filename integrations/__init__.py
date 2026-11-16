"""Registro de integrações externas (todas planejadas; nenhuma ativa no MVP 1.0)."""
from integrations.base import SourceInfo

MANUAL = SourceInfo(
    key="manual",
    name="Cadastro manual",
    description="Inclusão manual de publicações pela interface, com validação e triagem automática.",
    status="Disponível",
    credentials="Nenhuma",
)


def _load() -> list[SourceInfo]:
    from integrations.ai import INFO as AI
    from integrations.datajud import INFO as DATAJUD
    from integrations.inlabs import INFO as INLABS

    return [MANUAL, INLABS, DATAJUD, AI]


SOURCES = _load()
