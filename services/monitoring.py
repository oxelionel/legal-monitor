"""Orquestração da triagem: executa o motor de correspondência sobre o banco.

- Idempotente: a restrição única (publicação, cliente) impede resultados duplicados;
  reexecuções atualizam pontuação/justificativa das correspondências existentes.
- Preserva a análise humana: o status definido manualmente nunca é sobrescrito.
- Correspondências que deixaram de existir (ex.: palavra-chave removida) são
  removidas apenas se ainda estiverem "Pendente"; as demais são mantidas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import Client, Match, Publication
from services import audit
from services.classification import get_rules
from services.constants import TRIAGE_STATUS
from services.matching import ClientProfile, PublicationText, evaluate


@dataclass
class TriageSummary:
    publications: int = 0
    clients: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    kept_reviewed: int = 0
    by_relevance: dict = field(default_factory=lambda: {"ALTA": 0, "MÉDIA": 0, "BAIXA": 0})

    @property
    def total_matches(self) -> int:
        return self.created + self.updated + self.unchanged


def profile_of(client: Client) -> ClientProfile:
    return ClientProfile(
        id=client.id,
        name=client.name,
        trade_name=client.trade_name,
        document=client.document,
        legal_area=client.legal_area,
        keywords=[k.term for k in client.keywords],
    )


def text_of(pub: Publication) -> PublicationText:
    return PublicationText(id=pub.id, title=pub.title, content=pub.content, legal_area=pub.legal_area)


def run_triage(
    session: Session,
    publication_ids: list[int] | None = None,
    user: str | None = None,
    log_run: bool = True,
    is_demo: bool = False,
) -> TriageSummary:
    rules = get_rules(session)
    clients = list(
        session.scalars(select(Client).options(selectinload(Client.keywords)).where(Client.status == "Ativo"))
    )
    stmt = select(Publication)
    if publication_ids:
        stmt = stmt.where(Publication.id.in_(publication_ids))
    publications = list(session.scalars(stmt))
    profiles = [profile_of(c) for c in clients]
    active_ids = {c.id for c in clients}
    summary = TriageSummary(publications=len(publications), clients=len(clients))
    now = datetime.now().replace(microsecond=0)

    for pub in publications:
        # Consulta direta (e não a coleção em memória) para refletir o estado atual da sessão.
        existing = {m.client_id: m for m in session.scalars(select(Match).where(Match.publication_id == pub.id))}
        found: set[int] = set()
        pub_text = text_of(pub)
        for profile in profiles:
            result = evaluate(pub_text, profile, rules)
            if result is None:
                continue
            found.add(profile.id)
            summary.by_relevance[result.relevance] += 1
            terms = result.terms_as_json()
            match = existing.get(profile.id)
            if match is None:
                match = Match(
                    publication_id=pub.id, client_id=profile.id, score=result.score, relevance=result.relevance,
                    matched_terms=terms, justification=result.justification, status="Pendente",
                )
                session.add(match)
                session.flush()
                summary.created += 1
                audit.log(
                    session, "CORRESPONDÊNCIA", "correspondencia",
                    f"Correspondência {result.relevance} entre “{pub.title}” e “{profile.name}” "
                    f"(pontuação {result.score:.0f}).",
                    match.id, {"termos": [e.term for e in result.evidences]}, user=user, is_demo=pub.is_demo,
                )
            elif (match.score, match.relevance, match.matched_terms) != (result.score, result.relevance, terms):
                match.score, match.relevance = result.score, result.relevance
                match.matched_terms, match.justification = terms, result.justification
                summary.updated += 1
            else:
                summary.unchanged += 1

        for client_id, match in existing.items():
            # Correspondências de clientes inativos são preservadas, pois o cliente não foi avaliado.
            if client_id in found or client_id not in active_ids:
                continue
            if match.status == "Pendente":
                session.delete(match)
                summary.removed += 1
            else:
                summary.kept_reviewed += 1
        pub.last_triaged_at = now

    if log_run:
        audit.log(
            session, "TRIAGEM", "sistema",
            f"Triagem executada: {summary.publications} publicação(ões) × {summary.clients} cliente(s) ativo(s); "
            f"{summary.created} nova(s), {summary.updated} atualizada(s), {summary.removed} removida(s).",
            details={"alta": summary.by_relevance["ALTA"], "media": summary.by_relevance["MÉDIA"],
                     "baixa": summary.by_relevance["BAIXA"]},
            user=user,
            is_demo=is_demo,
        )
    session.flush()
    return summary


def update_match_status(
    session: Session, match_id: int, status: str, notes: str | None = None, user: str | None = None
) -> Match:
    if status not in TRIAGE_STATUS:
        raise ValueError(f"Status de triagem inválido: {status}")
    match = session.get(Match, match_id)
    if match is None:
        raise LookupError("Correspondência não encontrada.")
    old_status, old_notes = match.status, match.analyst_notes
    match.status = status
    if notes is not None:
        match.analyst_notes = notes.strip() or None
    if old_status != status:
        audit.log(
            session, "STATUS", "correspondencia",
            f"Triagem de “{match.publication.title}” × “{match.client.name}”: {old_status} → {status}.",
            match.id, {"de": old_status, "para": status, "observacao": match.analyst_notes}, user=user,
            is_demo=match.publication.is_demo,
        )
    elif old_notes != match.analyst_notes:
        audit.log(session, "ALTERAÇÃO", "correspondencia", f"Observação da análise #{match.id} atualizada.",
                  match.id, user=user, is_demo=match.publication.is_demo)
    return match


def list_matches(
    session: Session,
    relevance: list[str] | None = None,
    status: list[str] | None = None,
    client_ids: list[int] | None = None,
) -> list[Match]:
    stmt = (
        select(Match)
        .options(selectinload(Match.publication), selectinload(Match.client))
        .join(Publication)
        .order_by(Publication.publication_date.desc(), Match.score.desc())
    )
    if relevance:
        stmt = stmt.where(Match.relevance.in_(relevance))
    if status:
        stmt = stmt.where(Match.status.in_(status))
    if client_ids:
        stmt = stmt.where(Match.client_id.in_(client_ids))
    return list(session.scalars(stmt))
