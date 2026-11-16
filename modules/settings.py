"""Configurações: dados demonstrativos e informações do ambiente."""
from __future__ import annotations

import streamlit as st
from sqlalchemy import func, select

import config
from data.demo_data import has_demo_data, load_demo_data, remove_demo_data
from database.db import session_scope
from database.models import AuditLog, Client, Deadline, Match, Publication
from modules import ui
from services import audit


def render() -> None:
    ui.page_header("Configurações", "Gerencie a base de demonstração e consulte informações do ambiente.", "Sistema")

    with session_scope() as s:
        demo = has_demo_data(s)
        counts = {label: s.scalar(select(func.count()).select_from(model)) or 0
                  for label, model in [("Clientes", Client), ("Publicações", Publication), ("Correspondências", Match),
                                       ("Possíveis prazos", Deadline), ("Registros de auditoria", AuditLog)]}
        demo_counts = {
            "Clientes": s.scalar(select(func.count(Client.id)).where(Client.is_demo)) or 0,
            "Publicações": s.scalar(select(func.count(Publication.id)).where(Publication.is_demo)) or 0,
            "Possíveis prazos": s.scalar(select(func.count(Deadline.id)).where(Deadline.is_demo)) or 0,
        }

    st.markdown("#### Dados demonstrativos")
    ui.callout("A base de demonstração contém <b>apenas registros fictícios</b> (clientes, órgãos, números e textos "
               "inventados), identificados com o selo " + ui.demo_badge(True) + " e com a fonte “Dados de "
               "demonstração”. Ela <b>não representa publicações oficiais reais</b>. As datas são geradas em relação "
               "ao dia da carga.", "demo")
    ui.kpi_grid([dict(label=f"{k} (demo)", value=v, icon="file", tone="orange") for k, v in demo_counts.items()])

    c1, c2 = st.columns(2)
    with c1:
        label = "Restaurar dados demonstrativos" if demo else "Carregar dados demonstrativos"
        st.write("Recria a base fictícia do zero. Registros reais (não demonstrativos) **não** são afetados.")
        if st.button(label, type="primary", icon=":material/restart_alt:"):
            with session_scope() as s:
                result = load_demo_data(s)
            ui.notify(f"Base de demonstração carregada: {result['clients']} clientes, {result['publications']} "
                      f"publicações, {result['matches']} correspondências e {result['deadlines']} possíveis prazos.")
            st.rerun()
    with c2:
        st.write("Remove todos os registros demonstrativos e seu histórico, mantendo os dados reais.")
        confirm = st.checkbox("Confirmo a remoção dos dados demonstrativos", disabled=not demo)
        if st.button("Remover dados demonstrativos", disabled=not (demo and confirm), icon=":material/delete_sweep:"):
            with session_scope() as s:
                remove_demo_data(s)
                audit.log(s, "SISTEMA", "sistema", "Dados demonstrativos removidos.")
            ui.notify("Dados demonstrativos removidos.")
            st.rerun()
    st.caption("Para impedir a carga automática da demonstração em um banco vazio, defina "
               "`LEGAL_MONITOR_AUTO_SEED_DEMO=false` no arquivo `.env`.")

    st.markdown("#### Ambiente")
    db_url = config.DATABASE_URL
    shown = db_url.split("///")[-1] if db_url.startswith("sqlite") else db_url.split("@")[-1]
    ui.kv([("Versão", config.APP_VERSION), ("Banco de dados", ui.esc(shown)),
           ("Usuário das operações", ui.esc(config.DEFAULT_USER)),
           ("Antecedência de alerta", f"{config.DEADLINE_ALERT_DAYS} dias")])
    ui.kv([(k, str(v)) for k, v in counts.items()])
