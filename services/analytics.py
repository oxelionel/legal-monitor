"""Indicadores e séries para o dashboard — sempre calculados a partir do banco."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AuditLog, Client, Deadline, Match, Publication
from services.constants import DEADLINE_OPEN_STATUS


@dataclass
class Kpis:
    clients_total: int
    clients_active: int
    publications_total: int
    publications_analyzed: int
    matches_total: int
    high_alerts: int
    high_alerts_pending: int
    deadlines_open: int
    deadlines_soon: int
    deadlines_overdue: int
    demo_records: int


def kpis(session: Session, soon_days: int = 7, today: date | None = None) -> Kpis:
    today = today or date.today()
    count = lambda stmt: session.scalar(stmt) or 0  # noqa: E731
    open_deadlines = select(func.count(Deadline.id)).where(Deadline.status.in_(DEADLINE_OPEN_STATUS))
    return Kpis(
        clients_total=count(select(func.count(Client.id))),
        clients_active=count(select(func.count(Client.id)).where(Client.status == "Ativo")),
        publications_total=count(select(func.count(Publication.id))),
        publications_analyzed=count(select(func.count(Publication.id)).where(Publication.last_triaged_at.is_not(None))),
        matches_total=count(select(func.count(Match.id))),
        high_alerts=count(select(func.count(Match.id)).where(Match.relevance == "ALTA",
                                                             Match.status != "Descartada")),
        high_alerts_pending=count(select(func.count(Match.id)).where(Match.relevance == "ALTA",
                                                                     Match.status.in_(["Pendente", "Em análise"]))),
        deadlines_open=count(open_deadlines),
        deadlines_soon=count(open_deadlines.where(Deadline.due_date >= today,
                                                  Deadline.due_date <= today + timedelta(days=soon_days))),
        deadlines_overdue=count(select(func.count(Deadline.id)).where(
            (Deadline.status == "Vencido") | (Deadline.status.in_(DEADLINE_OPEN_STATUS) & (Deadline.due_date < today))
        )),
        demo_records=count(select(func.count(Client.id)).where(Client.is_demo))
        + count(select(func.count(Publication.id)).where(Publication.is_demo)),
    )


def publications_frame(session: Session) -> pd.DataFrame:
    rows = session.execute(
        select(Publication.id, Publication.publication_date, Publication.legal_area, Publication.source,
               Publication.doc_type)
    ).all()
    df = pd.DataFrame(rows, columns=["id", "publication_date", "legal_area", "source", "doc_type"])
    if not df.empty:
        df["publication_date"] = pd.to_datetime(df["publication_date"])
    return df


def matches_frame(session: Session) -> pd.DataFrame:
    rows = session.execute(
        select(Match.id, Match.relevance, Match.status, Match.score, Match.created_at, Publication.publication_date,
               Publication.legal_area, Client.name)
        .join(Publication, Match.publication_id == Publication.id)
        .join(Client, Match.client_id == Client.id)
    ).all()
    df = pd.DataFrame(rows, columns=["id", "relevance", "status", "score", "created_at", "publication_date",
                                     "legal_area", "client"])
    if not df.empty:
        df["publication_date"] = pd.to_datetime(df["publication_date"])
    return df


def publications_by_period(df: pd.DataFrame, freq: str = "W-MON") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["periodo", "publicacoes"])
    s = df.set_index("publication_date").resample(freq, label="left", closed="left")["id"].count()
    return s.rename("publicacoes").reset_index().rename(columns={"publication_date": "periodo"})


def distribution(df: pd.DataFrame, column: str, order: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[column, "total"])
    out = df[column].value_counts().rename_axis(column).reset_index(name="total")
    if order:
        out[column] = pd.Categorical(out[column], categories=order, ordered=True)
        out = out.sort_values(column)
    return out


def matches_evolution(df: pd.DataFrame, freq: str = "W-MON") -> pd.DataFrame:
    """Correspondências por período da publicação, por nível, com acumulado."""
    if df.empty:
        return pd.DataFrame(columns=["periodo", "relevance", "total", "acumulado"])
    grouped = (
        df.set_index("publication_date").groupby("relevance").resample(freq, label="left", closed="left")["id"].count()
        .rename("total").reset_index().rename(columns={"publication_date": "periodo"})
    )
    grouped = grouped.sort_values("periodo")
    grouped["acumulado"] = grouped.groupby("relevance")["total"].cumsum()
    return grouped


def recent_publications(session: Session, limit: int = 6) -> list[Publication]:
    stmt = select(Publication).order_by(Publication.publication_date.desc(), Publication.id.desc()).limit(limit)
    return list(session.scalars(stmt))


def recent_activity(session: Session, limit: int = 8) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit)
    return list(session.scalars(stmt))
