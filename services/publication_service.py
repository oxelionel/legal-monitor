"""Regras de negócio e persistência de publicações."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import Publication
from services import audit
from services.schemas import PublicationIn
from services.text import normalize

FIELDS = ("title", "agency", "source", "number", "publication_date", "legal_area", "doc_type", "content", "url")


class DuplicatePublicationError(ValueError):
    pass


def snapshot(pub: Publication) -> dict:
    return {f: getattr(pub, f) for f in FIELDS}


def _check_duplicate(session: Session, data: PublicationIn, exclude_id: int | None = None) -> None:
    """Mesma fonte + número + data, ou mesmo título + data, indicam duplicidade."""
    conditions = [func.lower(Publication.title) == data.title.lower()]
    if data.number:
        conditions.append(func.lower(Publication.number) == data.number.lower())
    stmt = select(Publication).where(Publication.publication_date == data.publication_date,
                                     Publication.source == data.source, or_(*conditions))
    if exclude_id:
        stmt = stmt.where(Publication.id != exclude_id)
    if session.scalars(stmt).first():
        raise DuplicatePublicationError("Já existe publicação com o mesmo título/número, fonte e data.")


def create_publication(session: Session, data: PublicationIn, user: str | None = None) -> Publication:
    _check_duplicate(session, data)
    pub = Publication(is_demo=data.is_demo, **{f: getattr(data, f) for f in FIELDS})
    session.add(pub)
    session.flush()
    audit.log(session, "CRIAÇÃO", "publicacao", f"Publicação “{pub.title}” cadastrada.", pub.id,
              {"fonte": pub.source, "data": pub.publication_date.isoformat()}, user=user, is_demo=pub.is_demo)
    return pub


def update_publication(session: Session, pub_id: int, data: PublicationIn, user: str | None = None) -> Publication:
    pub = session.get(Publication, pub_id)
    if pub is None:
        raise LookupError("Publicação não encontrada.")
    _check_duplicate(session, data, exclude_id=pub_id)
    before = snapshot(pub)
    for f in FIELDS:
        setattr(pub, f, getattr(data, f))
    session.flush()
    changes = audit.diff(before, snapshot(pub))
    if "content" in changes:
        changes["content"] = ["(texto anterior)", "(texto atualizado)"]
    if changes:
        audit.log(session, "ALTERAÇÃO", "publicacao", f"Publicação “{pub.title}” alterada ({', '.join(changes)}).",
                  pub.id, changes, user=user, is_demo=pub.is_demo)
    return pub


def delete_publication(session: Session, pub_id: int, user: str | None = None) -> None:
    pub = session.get(Publication, pub_id)
    if pub is None:
        raise LookupError("Publicação não encontrada.")
    audit.log(session, "EXCLUSÃO", "publicacao", f"Publicação “{pub.title}” excluída.", pub.id,
              {"fonte": pub.source, "data": pub.publication_date.isoformat()}, user=user, is_demo=pub.is_demo)
    session.delete(pub)


def get_publication(session: Session, pub_id: int) -> Publication | None:
    return session.get(Publication, pub_id)


def search_publications(
    session: Session,
    text: str | None = None,
    start: date | None = None,
    end: date | None = None,
    areas: list[str] | None = None,
    sources: list[str] | None = None,
    doc_types: list[str] | None = None,
) -> list[Publication]:
    stmt = select(Publication).order_by(Publication.publication_date.desc(), Publication.id.desc())
    if start:
        stmt = stmt.where(Publication.publication_date >= start)
    if end:
        stmt = stmt.where(Publication.publication_date <= end)
    if areas:
        stmt = stmt.where(Publication.legal_area.in_(areas))
    if sources:
        stmt = stmt.where(Publication.source.in_(sources))
    if doc_types:
        stmt = stmt.where(Publication.doc_type.in_(doc_types))
    results = list(session.scalars(stmt))
    if text:
        # Busca sem acentos e sem diferenciar maiúsculas em título, órgão, número e conteúdo.
        needle = normalize(text)
        results = [
            p for p in results
            if needle in normalize(f"{p.title} {p.agency} {p.number or ''} {p.content}")
        ]
    return results
