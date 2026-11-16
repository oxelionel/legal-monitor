from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from database.models import AuditLog, Deadline
from services import deadline_service as svc
from services.date_extraction import extract_mentions
from services.schemas import DeadlineIn

TODAY = date(2026, 11, 16)


def test_register_deadline(session):
    d = svc.create_deadline(session, DeadlineIn(description="Apresentar defesa", date_type="Prazo administrativo",
                                                reference_date=TODAY, due_date=TODAY + timedelta(days=10)))
    assert d.id and d.status == "Pendente" and d.validated is False
    assert session.query(AuditLog).filter_by(action="PRAZO").count() == 1


def test_due_before_reference_rejected():
    with pytest.raises(ValidationError):
        DeadlineIn(description="Teste", reference_date=TODAY, due_date=TODAY - timedelta(days=1))


def test_refresh_overdue_marks_only_open(session):
    late = svc.create_deadline(session, DeadlineIn(description="Atrasado", due_date=TODAY - timedelta(days=1)))
    done = svc.create_deadline(session, DeadlineIn(description="Feito", due_date=TODAY - timedelta(days=1),
                                                   status="Concluído"))
    assert svc.refresh_overdue(session, TODAY) == 1
    assert session.get(Deadline, late.id).status == "Vencido"
    assert session.get(Deadline, done.id).status == "Concluído"


def test_set_status_logs_history(session):
    d = svc.create_deadline(session, DeadlineIn(description="Status", due_date=TODAY))
    svc.set_status(session, d.id, "Em andamento")
    assert session.query(AuditLog).filter_by(action="STATUS", entity="prazo").count() == 1


@pytest.mark.parametrize("days,label", [(-1, "Vencido"), (1, "Crítico"), (5, "Próximo"), (30, "No prazo")])
def test_urgency(days, label):
    assert svc.urgency({"status": "Pendente", "due_date": TODAY + timedelta(days=days)}, TODAY)[0] == label


def test_urgency_without_date_and_closed():
    assert svc.urgency({"status": "Pendente", "due_date": None}, TODAY)[0] == "Sem data"
    assert svc.urgency({"status": "Concluído", "due_date": TODAY}, TODAY)[0] == "Concluído"


def test_extract_mentions_distinguishes_types():
    text = ("Esta Resolução entra em vigor em 1º de janeiro de 2027. A autuada poderá apresentar defesa "
            "no prazo de 20 (vinte) dias. Audiência nos autos em 09/12/2026.")
    mentions = extract_mentions(text)
    by_kind = {(m.kind, m.value or m.amount): m.suggested_type for m in mentions}
    assert by_kind[("data", date(2027, 1, 1))] == "Data de vigência"
    assert by_kind[("período", 20)] == "Prazo administrativo"
    assert ("data", date(2026, 12, 9)) in by_kind


def test_extract_ignores_invalid_dates():
    assert extract_mentions("Data impossível 31/02/2026.") == []
