"""Legal Monitor — ponto de entrada da aplicação Streamlit.

Execução:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import config
from database import db
from modules import (
    about,
    clients,
    dashboard,
    deadlines,
    history,
    monitoring,
    publications,
    reports,
    settings,
    triage,
    ui,
)

st.set_page_config(
    page_title=f"{config.APP_NAME} · {config.APP_SLOGAN}",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="auto",
)


@st.cache_resource(show_spinner=False)
def _bootstrap() -> bool:
    """Inicializa o banco uma única vez por processo e carrega a demonstração se estiver vazio."""
    db.init_db()
    if config.AUTO_SEED_DEMO:
        from sqlalchemy import func, select

        from data.demo_data import load_demo_data
        from database.models import Client, Publication

        with db.session_scope() as s:
            empty = not (s.scalar(select(func.count(Client.id))) or s.scalar(select(func.count(Publication.id))))
            if empty:
                load_demo_data(s)
    return True


def _refresh_deadlines() -> None:
    """Atualiza prazos vencidos uma vez por sessão do navegador."""
    if st.session_state.get("_overdue_checked"):
        return
    from services.deadline_service import refresh_overdue

    with db.session_scope() as s:
        refresh_overdue(s)
    st.session_state["_overdue_checked"] = True


def main() -> None:
    try:
        _bootstrap()
        _refresh_deadlines()
    except Exception as exc:  # pragma: no cover - falha de infraestrutura
        st.error(f"Não foi possível inicializar o banco de dados: {exc}")
        st.stop()

    ui.inject_css()
    ui.sidebar_brand()

    pages = {
        "Visão geral": [
            st.Page(dashboard.render, title="Dashboard", icon=":material/space_dashboard:", default=True),
        ],
        "Operação": [
            st.Page(clients.render, title="Clientes", icon=":material/groups:", url_path="clientes"),
            st.Page(publications.render, title="Publicações", icon=":material/article:", url_path="publicacoes"),
            st.Page(monitoring.render, title="Monitoramento", icon=":material/radar:", url_path="monitoramento"),
            st.Page(triage.render, title="Triagem jurídica", icon=":material/fact_check:", url_path="triagem"),
            st.Page(deadlines.render, title="Possíveis prazos", icon=":material/event_upcoming:", url_path="prazos"),
        ],
        "Gestão": [
            st.Page(reports.render, title="Relatórios", icon=":material/summarize:", url_path="relatorios"),
            st.Page(history.render, title="Histórico e auditoria", icon=":material/history:", url_path="historico"),
        ],
        "Sistema": [
            st.Page(settings.render, title="Configurações", icon=":material/settings:", url_path="configuracoes"),
            st.Page(about.render, title="Sobre o projeto", icon=":material/info:", url_path="sobre"),
        ],
    }
    nav = st.navigation(pages)

    from data.demo_data import has_demo_data

    with db.session_scope() as s:
        demo = has_demo_data(s)
    ui.sidebar_footer(demo)
    ui.flash()
    nav.run()


main()
