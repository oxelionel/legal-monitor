import pytest
from pydantic import ValidationError

from database.models import AuditLog, Client
from services import client_service as svc
from services.schemas import ClientIn


def test_create_client_normalizes_fields(session, client_data):
    c = svc.create_client(session, ClientIn(**client_data))
    assert c.id
    assert c.document == "11222333000181"
    assert c.email == "contato@alfa.example"
    assert len(c.keywords) == 3
    assert session.query(AuditLog).filter_by(action="CRIAÇÃO", entity="cliente").count() == 1


def test_duplicate_document_rejected(session, client_data):
    svc.create_client(session, ClientIn(**client_data))
    with pytest.raises(svc.DuplicateClientError):
        svc.create_client(session, ClientIn(**{**client_data, "name": "Outro Nome"}))


def test_duplicate_name_rejected_ignoring_accents_and_case(session, client_data):
    svc.create_client(session, ClientIn(**{**client_data, "document": None}))
    with pytest.raises(svc.DuplicateClientError):
        svc.create_client(session, ClientIn(**{**client_data, "document": None, "name": "EMPRESA TÉSTE ALFA LTDA"}))


@pytest.mark.parametrize("field,value", [
    ("document", "11.222.333/0001-00"),  # dígito verificador inválido
    ("email", "email-invalido"),
    ("name", "A"),
    ("keywords", "ok termo, ab"),
    ("phone", "123"),
])
def test_validation_errors(client_data, field, value):
    with pytest.raises(ValidationError):
        ClientIn(**{**client_data, field: value})


def test_cpf_required_for_individual(client_data):
    with pytest.raises(ValidationError):
        ClientIn(**{**client_data, "client_type": "Pessoa física"})  # CNPJ em pessoa física


def test_keywords_deduplicated():
    c = ClientIn(name="Fulano Teste", client_type="Pessoa física", keywords="Termo Um; termo um\nTermo Dois")
    assert c.keywords == ["Termo Um", "Termo Dois"]


def test_update_client_and_keywords(session, client_data):
    c = svc.create_client(session, ClientIn(**client_data))
    updated = svc.update_client(session, c.id, ClientIn(**{**client_data, "responsible": "Nova Pessoa",
                                                           "keywords": "outorga, saneamento"}))
    assert updated.responsible == "Nova Pessoa"
    assert sorted(k.term for k in updated.keywords) == ["outorga", "saneamento"]
    log = session.query(AuditLog).filter_by(action="ALTERAÇÃO").one()
    assert "responsible" in log.details and "keywords" in log.details


def test_update_without_changes_does_not_log(session, client_data):
    c = svc.create_client(session, ClientIn(**client_data))
    svc.update_client(session, c.id, ClientIn(**client_data))
    assert session.query(AuditLog).filter_by(action="ALTERAÇÃO").count() == 0


def test_delete_client(session, client_data):
    c = svc.create_client(session, ClientIn(**client_data))
    svc.delete_client(session, c.id)
    session.flush()
    assert session.query(Client).count() == 0
    assert session.query(AuditLog).filter_by(action="EXCLUSÃO").count() == 1


def test_update_missing_client_raises(session, client_data):
    with pytest.raises(LookupError):
        svc.update_client(session, 999, ClientIn(**client_data))
