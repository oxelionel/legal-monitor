"""Gestão de possíveis prazos e obrigações.

Todo registro é tratado como **possível prazo**: o campo ``validated`` indica se
um profissional responsável confirmou a data à luz da legislação aplicável.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import config
from database.models import Deadline
from services import audit
from services.constants import DEADLINE_OPEN_STATUS
from services.schemas import DeadlineIn

FIELDS = ("description", "publication_id", "client_id", "date_type", "reference_date", "due_date",
          "responsible", "status", "notes", "validated", "origin")


def snapshot(d: Deadline) -> dict:
    return {f: getattr(d, f) for f in FIELDS}


def create_deadline(session: Session, data: DeadlineIn, user: str | None = None) -> Deadline:
    deadline = Deadline(is_demo=data.is_demo, **{f: getattr(data, f) for f in FIELDS})
    session.add(deadline)
    session.flush()
    when = f" com data limite sugerida {deadline.due_date:%d/%m/%Y}" if deadline.due_date else ""
    audit.log(session, "PRAZO", "prazo", f"Possível prazo registrado: “{deadline.description}”{when}.",
              deadline.id, {"tipo": deadline.date_type, "origem": deadline.origin}, user=user, is_demo=data.is_demo)
    return deadline


def update_deadline(session: Session, deadline_id: int, data: DeadlineIn, user: str | None = None) -> Deadline:
    deadline = session.get(Deadline, deadline_id)
    if deadline is None:
        raise LookupError("Prazo não encontrado.")
    before = snapshot(deadline)
    for f in FIELDS:
        setattr(deadline, f, getattr(data, f))
    session.flush()
    changes = audit.diff(before, snapshot(deadline))
    if changes:
        action = "STATUS" if set(changes) == {"status"} else "ALTERAÇÃO"
        audit.log(session, action, "prazo", f"Possível prazo “{deadline.description}” alterado ({', '.join(changes)}).",
                  deadline.id, changes, user=user, is_demo=deadline.is_demo)
    return deadline


def set_status(session: Session, deadline_id: int, status: str, user: str | None = None) -> Deadline:
    deadline = session.get(Deadline, deadline_id)
    if deadline is None:
        raise LookupError("Prazo não encontrado.")
    data = DeadlineIn(**{**snapshot(deadline), "status": status, "is_demo": deadline.is_demo})
    return update_deadline(session, deadline_id, data, user=user)


def delete_deadline(session: Session, deadline_id: int, user: str | None = None) -> None:
    deadline = session.get(Deadline, deadline_id)
    if deadline is None:
        raise LookupError("Prazo não encontrado.")
    audit.log(session, "EXCLUSÃO", "prazo", f"Possível prazo “{deadline.description}” excluído.", deadline.id,
              user=user, is_demo=deadline.is_demo)
    session.delete(deadline)


def list_deadlines(session: Session) -> list[Deadline]:
    stmt = (
        select(Deadline)
        .options(selectinload(Deadline.client), selectinload(Deadline.publication))
        .order_by(Deadline.due_date.is_(None), Deadline.due_date, Deadline.id)
    )
    return list(session.scalars(stmt))


def refresh_overdue(session: Session, today: date | None = None) -> int:
    """Marca como "Vencido" os prazos em aberto cuja data limite já passou."""
    today = today or date.today()
    stmt = select(Deadline).where(Deadline.status.in_(DEADLINE_OPEN_STATUS), Deadline.due_date < today)
    count = 0
    for d in session.scalars(stmt):
        d.status = "Vencido"
        count += 1
        audit.log(session, "STATUS", "prazo",
                  f"Possível prazo “{d.description}” marcado automaticamente como Vencido "
                  f"(data limite {d.due_date:%d/%m/%Y}).", d.id, user="Sistema", is_demo=d.is_demo)
    return count


def urgency(d: Deadline | dict, today: date | None = None) -> tuple[str, int | None]:
    """Classificação visual: (rótulo, dias restantes)."""
    today = today or date.today()
    status = d["status"] if isinstance(d, dict) else d.status
    due = d["due_date"] if isinstance(d, dict) else d.due_date
    if status in ("Concluído", "Cancelado"):
        return status, None
    if due is None:
        return "Sem data", None
    days = (due - today).days
    if days < 0 or status == "Vencido":
        return "Vencido", days
    if days <= 2:
        return "Crítico", days
    if days <= config.DEADLINE_ALERT_DAYS:
        return "Próximo", days
    return "No prazo", days
