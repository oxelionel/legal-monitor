"""Módulo G — Relatórios com exportação CSV e PDF."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from database.db import session_scope
from modules import ui
from services import constants as C
from services import reports as R
from services.client_service import list_clients

STATUS_OPTIONS = {
    "publicacoes": [],
    "clientes": C.CLIENT_STATUS,
    "correspondencias": C.TRIAGE_STATUS,
    "alertas": C.TRIAGE_STATUS,
    "prazos": C.DEADLINE_STATUS,
}


def render() -> None:
    ui.page_header("Relatórios", "Gere relatórios filtrados e exporte em CSV (compatível com Excel) ou PDF.", "Gestão")

    with session_scope() as s:
        clients = {c.id: c.name for c in list_clients(s)}

    kind = st.segmented_control("Tipo de relatório", list(R.REPORT_TYPES), format_func=R.REPORT_TYPES.get,
                                default="correspondencias", selection_mode="single") or "correspondencias"
    c1, c2, c3, c4 = st.columns([1.3, 1.3, 1, 1.2])
    use_period = kind != "clientes"
    period = c1.date_input("Período", (date.today() - timedelta(days=90), date.today() + timedelta(days=60)),
                           format="DD/MM/YYYY", disabled=not use_period,
                           help="Publicações: data de publicação · Prazos: data limite (ou de referência).")
    client_ids = c2.multiselect("Clientes", placeholder="Todos", options=list(clients), format_func=clients.get)
    relevance = c3.multiselect("Relevância", placeholder="Todos", options=C.RELEVANCE_LEVELS, disabled=kind in ("prazos", "alertas"))
    status = c4.multiselect("Status", placeholder="Todos", options=STATUS_OPTIONS[kind], disabled=not STATUS_OPTIONS[kind])

    start, end = (period if use_period and isinstance(period, tuple) and len(period) == 2 else (None, None))
    filters = R.ReportFilters(start=start, end=end, client_ids=client_ids,
                              relevance=[] if kind in ("prazos", "alertas") else relevance, status=status)
    with session_scope() as s:
        df = R.build_report(s, kind, filters)

    title = R.REPORT_TYPES[kind]
    st.markdown(f"#### {title}")
    st.caption(f"{len(df)} registro(s) · {filters.describe()}")
    if df.empty:
        ui.empty_state("Nenhum registro para os filtros selecionados.")
    else:
        date_cols = {c: st.column_config.DateColumn(format="DD/MM/YYYY") for c in df.columns if c.startswith("Data")}
        st.dataframe(df, width="stretch", hide_index=True, column_config=date_cols)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button("Exportar CSV", R.to_csv_bytes(df), file_name=f"legal_monitor_{kind}_{stamp}.csv",
                       mime="text/csv", type="primary", icon=":material/download:", disabled=df.empty)
    try:
        pdf = R.to_pdf_bytes(df, title, filters, R.PDF_COLUMNS.get(kind))
        d2.download_button("Exportar PDF", pdf, file_name=f"legal_monitor_{kind}_{stamp}.pdf",
                           mime="application/pdf", icon=":material/picture_as_pdf:", disabled=df.empty)
    except Exception as exc:  # pragma: no cover - dependência opcional
        d2.caption(f"PDF indisponível: {exc}")
