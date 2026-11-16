import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database import db  # noqa: E402


@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture()
def session(db_url):
    db.init_db(db_url)
    with db.session_scope() as s:
        yield s


@pytest.fixture()
def client_data():
    return dict(
        name="Empresa Teste Alfa Ltda",
        trade_name="Alfa Teste",
        document="11.222.333/0001-81",
        client_type="Pessoa jurídica",
        email="contato@alfa.example",
        phone="(11) 4000-1234",
        responsible="Responsável Teste",
        legal_area="Ambiental",
        keywords="licenciamento ambiental, outorga, recursos hídricos",
    )


@pytest.fixture()
def pub_data():
    from datetime import date, timedelta

    return dict(
        title="Portaria de teste nº 1",
        agency="Órgão de Teste",
        source="Cadastro manual",
        number="T-1/2026",
        publication_date=date.today() - timedelta(days=1),
        legal_area="Ambiental",
        doc_type="Portaria",
        content="Fica notificada a EMPRESA TESTE ALFA LTDA, CNPJ 11.222.333/0001-81, sobre o licenciamento "
                "ambiental. Prazo de 15 (quinze) dias para apresentar defesa.",
    )
