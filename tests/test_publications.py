from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from services import publication_service as svc
from services.schemas import PublicationIn


def test_create_and_search_publication(session, pub_data):
    p = svc.create_publication(session, PublicationIn(**pub_data))
    assert p.id
    assert svc.search_publications(session, text="licenciamento AMBIENTAL")[0].id == p.id
    assert svc.search_publications(session, text="orgao de teste")  # sem acento encontra "Órgão"
    assert svc.search_publications(session, text="inexistente") == []
    assert svc.search_publications(session, areas=["Tributário"]) == []
    assert svc.search_publications(session, start=date.today(), end=date.today()) == []


def test_duplicate_publication_rejected(session, pub_data):
    svc.create_publication(session, PublicationIn(**pub_data))
    with pytest.raises(svc.DuplicatePublicationError):
        svc.create_publication(session, PublicationIn(**{**pub_data, "title": "Outro título"}))  # mesmo número


def test_future_date_rejected(pub_data):
    with pytest.raises(ValidationError):
        PublicationIn(**{**pub_data, "publication_date": date.today() + timedelta(days=1)})


def test_invalid_url_rejected(pub_data):
    with pytest.raises(ValidationError):
        PublicationIn(**{**pub_data, "url": "javascript:alert(1)"})


def test_update_and_delete_publication(session, pub_data):
    p = svc.create_publication(session, PublicationIn(**pub_data))
    svc.update_publication(session, p.id, PublicationIn(**{**pub_data, "title": "Título alterado"}))
    assert svc.get_publication(session, p.id).title == "Título alterado"
    svc.delete_publication(session, p.id)
    session.flush()
    assert svc.get_publication(session, p.id) is None
