import csv
import io

from data.demo_data import CLIENTS, PUBLICATIONS, has_demo_data, load_demo_data, remove_demo_data
from database.models import AuditLog, Client, Deadline, Match, Publication
from services import analytics
from services import reports as R
from services.client_service import create_client
from services.schemas import ClientIn


def test_demo_data_loads_consistently(session):
    result = load_demo_data(session)
    assert result["clients"] >= 5 and result["publications"] >= 15
    assert session.query(Client).filter_by(is_demo=True).count() == len(CLIENTS)
    assert session.query(Publication).filter_by(is_demo=True).count() == len(PUBLICATIONS)
    assert {m.relevance for m in session.query(Match)} == {"ALTA", "MÉDIA", "BAIXA"}
    assert session.query(Deadline).count() >= 5
    assert all(p.source == "Dados de demonstração" and p.title.startswith("[DEMO]") for p in session.query(Publication))
    assert session.query(AuditLog).count() > 0


def test_demo_restore_is_idempotent_and_keeps_real_data(session, client_data):
    real = create_client(session, ClientIn(**client_data))  # mesmo CNPJ de um cliente demo
    load_demo_data(session)
    first = session.query(Match).count()
    load_demo_data(session)
    assert session.query(Match).count() >= first - 1  # sem duplicação
    assert session.query(Client).filter_by(is_demo=True).count() == len(CLIENTS)
    remove_demo_data(session)
    assert not has_demo_data(session)
    assert session.get(Client, real.id) is not None


def test_kpis_are_computed_from_database(session):
    load_demo_data(session)
    k = analytics.kpis(session)
    assert k.clients_total == session.query(Client).count()
    assert k.publications_total == session.query(Publication).count()
    assert k.matches_total == session.query(Match).count()
    assert k.high_alerts == session.query(Match).filter(Match.relevance == "ALTA", Match.status != "Descartada").count()


def test_csv_export(session):
    load_demo_data(session)
    for kind in R.REPORT_TYPES:
        df = R.build_report(session, kind, R.ReportFilters())
        data = R.to_csv_bytes(df)
        assert data.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 para Excel
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))
        assert len(rows) == len(df) + 1
        assert rows[0] == list(df.columns)


def test_report_filters(session):
    load_demo_data(session)
    high = R.build_report(session, "correspondencias", R.ReportFilters(relevance=["ALTA"]))
    assert not high.empty and set(high["Relevância"]) == {"ALTA"}
    alerts = R.build_report(session, "alertas", R.ReportFilters())
    assert len(alerts) == len(high)
    client = session.query(Client).first()
    by_client = R.build_report(session, "correspondencias", R.ReportFilters(client_ids=[client.id]))
    assert set(by_client["Cliente"]) <= {client.name}


def test_pdf_export(session):
    load_demo_data(session)
    df = R.build_report(session, "prazos", R.ReportFilters())
    pdf = R.to_pdf_bytes(df, "Relatório de possíveis prazos", R.ReportFilters(), R.PDF_COLUMNS["prazos"])
    assert pdf.startswith(b"%PDF")


def test_empty_csv_export():
    import pandas as pd

    assert R.to_csv_bytes(pd.DataFrame()).decode("utf-8-sig").strip() == ""
