from sqlalchemy import inspect

from database import db
from database.models import Client
from services.client_service import create_client
from services.schemas import ClientIn


def test_init_creates_all_tables(db_url):
    engine = db.init_db(db_url)
    tables = set(inspect(engine).get_table_names())
    assert {"clients", "client_keywords", "publications", "matches", "deadlines", "audit_log", "settings"} <= tables


def test_init_is_idempotent(db_url):
    db.init_db(db_url)
    db.init_db(db_url)  # não deve falhar nem duplicar


def test_data_persists_across_engines(db_url, client_data):
    db.init_db(db_url)
    with db.session_scope() as s:
        create_client(s, ClientIn(**client_data))
    db.configure(db_url)  # novo engine, mesmo arquivo
    with db.session_scope() as s:
        stored = s.query(Client).one()
        assert stored.name == client_data["name"]
        assert [k.term for k in stored.keywords] == ["licenciamento ambiental", "outorga", "recursos hídricos"]


def test_session_rollback_on_error(db_url, client_data):
    db.init_db(db_url)
    try:
        with db.session_scope() as s:
            create_client(s, ClientIn(**client_data))
            raise RuntimeError("falha simulada")
    except RuntimeError:
        pass
    with db.session_scope() as s:
        assert s.query(Client).count() == 0
