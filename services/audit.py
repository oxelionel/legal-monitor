"""Registro de histórico e auditoria."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import config
from database.models import AuditLog

ACTIONS = {
    "CRIAÇÃO": "Cadastro",
    "ALTERAÇÃO": "Alteração",
    "EXCLUSÃO": "Exclusão",
    "TRIAGEM": "Triagem executada",
    "CORRESPONDÊNCIA": "Correspondência identificada",
    "STATUS": "Alteração de status",
    "PRAZO": "Possível prazo",
    "SISTEMA": "Sistema",
}

ENTITY_LABELS = {
    "cliente": "Cliente",
    "publicacao": "Publicação",
    "correspondencia": "Correspondência",
    "prazo": "Possível prazo",
    "configuracao": "Configuração",
    "sistema": "Sistema",
}


def log(
    session: Session,
    action: str,
    entity: str,
    description: str,
    entity_id: int | None = None,
    details: dict | None = None,
    user: str | None = None,
    is_demo: bool = False,
) -> AuditLog:
    if action not in ACTIONS:
        raise ValueError(f"Ação de auditoria desconhecida: {action}")
    entry = AuditLog(
        action=action,
        entity=entity,
        entity_id=entity_id,
        description=description,
        details=details,
        user=user or config.DEFAULT_USER,
        is_demo=is_demo,
    )
    session.add(entry)
    return entry


def diff(before: dict, after: dict) -> dict:
    """Retorna apenas os campos alterados: {campo: [antes, depois]}."""
    changes = {}
    for key, new in after.items():
        old = before.get(key)
        if old != new:
            changes[key] = [_jsonable(old), _jsonable(new)]
    return changes


def _jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def list_entries(session: Session, limit: int | None = None) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))
