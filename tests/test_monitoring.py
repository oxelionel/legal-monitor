import pytest

from database.models import AuditLog, Match
from services import classification as cls
from services.client_service import create_client, update_client
from services.monitoring import run_triage, update_match_status
from services.publication_service import create_publication
from services.schemas import ClientIn, PublicationIn


@pytest.fixture()
def seeded(session, client_data, pub_data):
    c = create_client(session, ClientIn(**client_data))
    other = create_client(session, ClientIn(name="Sem Relação Nenhuma SA", client_type="Pessoa jurídica",
                                            keywords="mineração"))
    p = create_publication(session, PublicationIn(**pub_data))
    return session, c, other, p


def test_triage_creates_match_with_terms(seeded):
    session, c, other, p = seeded
    summary = run_triage(session)
    assert summary.created == 1
    m = session.query(Match).one()
    assert (m.client_id, m.publication_id, m.relevance, m.status) == (c.id, p.id, "ALTA", "Pendente")
    terms = {t["term"] for t in m.matched_terms}
    assert {"11222333000181", "Empresa Teste Alfa Ltda", "licenciamento ambiental"} <= terms
    assert session.query(AuditLog).filter_by(action="CORRESPONDÊNCIA").count() == 1
    assert session.query(AuditLog).filter_by(action="TRIAGEM").count() == 1


def test_triage_rerun_does_not_duplicate(seeded):
    session = seeded[0]
    run_triage(session)
    summary = run_triage(session)
    assert summary.created == 0 and summary.unchanged == 1
    assert session.query(Match).count() == 1


def test_rerun_preserves_manual_status(seeded):
    session, c, _, p = seeded
    run_triage(session)
    m = session.query(Match).one()
    update_match_status(session, m.id, "Confirmada", "Ok")
    run_triage(session)
    assert session.get(Match, m.id).status == "Confirmada"
    assert session.query(AuditLog).filter_by(action="STATUS").count() == 1


def test_stale_pending_match_removed_after_keyword_change(session, pub_data):
    c = create_client(session, ClientIn(name="Cliente Palavra Unica", client_type="Pessoa jurídica",
                                        keywords="outorga"))
    create_publication(session, PublicationIn(**{**pub_data, "content": pub_data["content"] + " Outorga de uso."}))
    run_triage(session)
    assert session.query(Match).count() == 1
    update_client(session, c.id, ClientIn(name="Cliente Palavra Unica", client_type="Pessoa jurídica",
                                          keywords="mineração"))
    summary = run_triage(session)
    assert summary.removed == 1 and session.query(Match).count() == 0


def test_inactive_clients_are_not_triaged(session, client_data, pub_data):
    create_client(session, ClientIn(**{**client_data, "status": "Pausado"}))
    create_publication(session, PublicationIn(**pub_data))
    assert run_triage(session).created == 0


def test_custom_rules_change_classification(session, pub_data):
    create_client(session, ClientIn(name="Cliente Regras", client_type="Pessoa jurídica",
                                    keywords="licenciamento ambiental"))
    create_publication(session, PublicationIn(**pub_data))
    run_triage(session)
    assert session.query(Match).one().relevance == "MÉDIA"
    rules = cls.get_rules(session)
    rules["thresholds"] = {"ALTA": 30, "MÉDIA": 20, "BAIXA": 10}
    cls.save_rules(session, rules)
    run_triage(session)
    assert session.query(Match).one().relevance == "ALTA"


def test_invalid_rules_rejected(session):
    rules = cls.get_rules(session)
    rules["thresholds"] = {"ALTA": 10, "MÉDIA": 20, "BAIXA": 5}
    with pytest.raises(ValueError):
        cls.save_rules(session, rules)


def test_invalid_triage_status(seeded):
    session = seeded[0]
    run_triage(session)
    with pytest.raises(ValueError):
        update_match_status(session, session.query(Match).one().id, "Inexistente")
