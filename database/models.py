"""Modelos ORM (SQLAlchemy 2.x) do Legal Monitor.

O modelo foi desenhado para ser portável para PostgreSQL: não utiliza recursos
exclusivos do SQLite e armazena listas/estruturas em colunas JSON.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now().replace(microsecond=0)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    trade_name: Mapped[str | None] = mapped_column(String(200))
    document: Mapped[str | None] = mapped_column(String(14), unique=True)  # apenas dígitos
    client_type: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    responsible: Mapped[str | None] = mapped_column(String(120))
    legal_area: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Ativo", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    keywords: Mapped[list[ClientKeyword]] = relationship(
        back_populates="client", cascade="all, delete-orphan", order_by="ClientKeyword.id"
    )
    matches: Mapped[list[Match]] = relationship(back_populates="client", cascade="all, delete-orphan")


class ClientKeyword(Base):
    __tablename__ = "client_keywords"
    __table_args__ = (UniqueConstraint("client_id", "term_normalized", name="uq_client_keyword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    term: Mapped[str] = mapped_column(String(200), nullable=False)
    term_normalized: Mapped[str] = mapped_column(String(200), nullable=False)

    client: Mapped[Client] = relationship(back_populates="keywords")


class Publication(TimestampMixin, Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    agency: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    number: Mapped[str | None] = mapped_column(String(80))
    publication_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    legal_area: Mapped[str] = mapped_column(String(80), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_triaged_at: Mapped[datetime | None] = mapped_column(DateTime)

    matches: Mapped[list[Match]] = relationship(back_populates="publication", cascade="all, delete-orphan")


class Match(TimestampMixin, Base):
    """Resultado da triagem: correspondência entre uma publicação e um cliente."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("publication_id", "client_id", name="uq_match_pub_client"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    relevance: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    matched_terms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="Pendente", nullable=False, index=True)
    analyst_notes: Mapped[str | None] = mapped_column(Text)

    publication: Mapped[Publication] = relationship(back_populates="matches")
    client: Mapped[Client] = relationship(back_populates="matches")


class Deadline(TimestampMixin, Base):
    """Possível prazo/obrigação. Sempre depende de validação profissional."""

    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    publication_id: Mapped[int | None] = mapped_column(ForeignKey("publications.id", ondelete="SET NULL"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"))
    date_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    responsible: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="Pendente", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    origin: Mapped[str] = mapped_column(String(30), default="Manual", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    publication: Mapped[Publication | None] = relationship()
    client: Mapped[Client | None] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    user: Mapped[str] = mapped_column("actor", String(120), nullable=False)  # "user" é reservado no PostgreSQL
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
