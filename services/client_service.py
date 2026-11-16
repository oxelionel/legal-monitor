"""Regras de negócio e persistência de clientes."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import Client, ClientKeyword
from services import audit
from services.schemas import ClientIn
from services.text import format_document, normalize


class DuplicateClientError(ValueError):
    pass


def _check_duplicates(session: Session, data: ClientIn, exclude_id: int | None = None) -> None:
    if data.document:
        stmt = select(Client).where(Client.document == data.document)
        if exclude_id:
            stmt = stmt.where(Client.id != exclude_id)
        if session.scalars(stmt).first():
            raise DuplicateClientError(f"Já existe cliente com o CPF/CNPJ {format_document(data.document)}.")
    stmt = select(Client).where(Client.name_normalized == normalize(data.name))
    if exclude_id:
        stmt = stmt.where(Client.id != exclude_id)
    existing = session.scalars(stmt).first()
    if existing and (not data.document or not existing.document or existing.document == data.document):
        raise DuplicateClientError(f"Já existe cliente cadastrado com o nome “{existing.name}”.")


def snapshot(client: Client) -> dict:
    return {
        "name": client.name,
        "trade_name": client.trade_name,
        "document": client.document,
        "client_type": client.client_type,
        "email": client.email,
        "phone": client.phone,
        "responsible": client.responsible,
        "legal_area": client.legal_area,
        "keywords": [k.term for k in client.keywords],
        "notes": client.notes,
        "status": client.status,
    }


def _apply(client: Client, data: ClientIn) -> None:
    client.name = data.name
    client.name_normalized = normalize(data.name)
    client.trade_name = data.trade_name
    client.document = data.document
    client.client_type = data.client_type
    client.email = data.email
    client.phone = data.phone
    client.responsible = data.responsible
    client.legal_area = data.legal_area
    client.notes = data.notes
    client.status = data.status
    wanted = {normalize(t): t for t in data.keywords}
    client.keywords[:] = [k for k in client.keywords if k.term_normalized in wanted]
    current = {k.term_normalized for k in client.keywords}
    for norm, term in wanted.items():
        if norm not in current:
            client.keywords.append(ClientKeyword(term=term, term_normalized=norm))


def create_client(session: Session, data: ClientIn, user: str | None = None) -> Client:
    _check_duplicates(session, data)
    client = Client(is_demo=data.is_demo)
    _apply(client, data)
    session.add(client)
    session.flush()
    audit.log(session, "CRIAÇÃO", "cliente", f"Cliente “{client.name}” cadastrado.", client.id,
              {"palavras_chave": data.keywords}, user=user, is_demo=data.is_demo)
    return client


def update_client(session: Session, client_id: int, data: ClientIn, user: str | None = None) -> Client:
    client = get_client(session, client_id)
    if client is None:
        raise LookupError("Cliente não encontrado.")
    _check_duplicates(session, data, exclude_id=client_id)
    before = snapshot(client)
    _apply(client, data)
    session.flush()
    changes = audit.diff(before, snapshot(client))
    if changes:
        audit.log(session, "ALTERAÇÃO", "cliente", f"Cliente “{client.name}” alterado ({', '.join(changes)}).",
                  client.id, changes, user=user, is_demo=client.is_demo)
    return client


def delete_client(session: Session, client_id: int, user: str | None = None) -> None:
    client = get_client(session, client_id)
    if client is None:
        raise LookupError("Cliente não encontrado.")
    n_matches = len(client.matches)
    audit.log(session, "EXCLUSÃO", "cliente",
              f"Cliente “{client.name}” excluído (com {n_matches} correspondência(s) vinculada(s)).",
              client.id, snapshot(client), user=user, is_demo=client.is_demo)
    session.delete(client)


def get_client(session: Session, client_id: int) -> Client | None:
    stmt = select(Client).options(selectinload(Client.keywords), selectinload(Client.matches)).where(Client.id == client_id)
    return session.scalars(stmt).first()


def list_clients(session: Session, only_active: bool = False) -> list[Client]:
    stmt = select(Client).options(selectinload(Client.keywords)).order_by(Client.name)
    if only_active:
        stmt = stmt.where(Client.status == "Ativo")
    return list(session.scalars(stmt))


def to_form(client: Client) -> dict:
    data = snapshot(client)
    data["document"] = format_document(client.document) if client.document else ""
    data["keywords"] = ", ".join(data["keywords"])
    return data
