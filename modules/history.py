"""Módulo H — Histórico e auditoria."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from database.db import session_scope
from modules import ui
from modules.dashboard import ACTION_DOT
from services import audit
from services.reports import to_csv_bytes
from services.text import normalize


def render() -> None:
    ui.page_header("Histórico e auditoria", "Registro cronológico de cadastros, alterações, exclusões, triagens, "
                   "correspondências, mudanças de status e prazos.", "Gestão")

    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.4])
    period = c1.date_input("Período", (date.today() - timedelta(days=30), date.today()), format="DD/MM/YYYY")
    actions = c2.multiselect("Ação", placeholder="Todos", options=list(audit.ACTIONS), format_func=audit.ACTIONS.get)
    entities = c3.multiselect("Entidade", placeholder="Todos", options=list(audit.ENTITY_LABELS), format_func=audit.ENTITY_LABELS.get)
    text = c4.text_input("Buscar na descrição")
    order = st.radio("Ordem", ["Mais recentes primeiro", "Mais antigos primeiro"], horizontal=True,
                     label_visibility="collapsed")

    with session_scope() as s:
        entries = [(a.timestamp, a.action, a.entity, a.entity_id, a.description, a.user, a.is_demo)
                   for a in audit.list_entries(s)]
    start, end = period if isinstance(period, tuple) and len(period) == 2 else (None, None)
    needle = normalize(text)
    filtered = [e for e in entries
                if (not start or e[0].date() >= start) and (not end or e[0].date() <= end)
                and (not actions or e[1] in actions) and (not entities or e[2] in entities)
                and (not needle or needle in normalize(e[4]))]
    if order == "Mais antigos primeiro":
        filtered.reverse()

    st.caption(f"{len(filtered)} registro(s) de {len(entries)}")
    df = pd.DataFrame([{"Data/hora": ts, "Ação": audit.ACTIONS.get(act, act), "Entidade": audit.ENTITY_LABELS.get(ent, ent),
                        "ID": eid, "Descrição": desc, "Usuário": user, "Demonstração": "Sim" if demo else ""}
                       for ts, act, ent, eid, desc, user, demo in filtered])

    tab_tl, tab_table = st.tabs(["Linha do tempo", "Tabela"])
    with tab_tl:
        if not filtered:
            ui.empty_state("Nenhum registro no período.")
        page_size = 40
        pages = max(1, -(-len(filtered) // page_size))
        page = st.number_input("Página", 1, pages, 1) if pages > 1 else 1
        chunk = filtered[(page - 1) * page_size: page * page_size]
        last_day = None
        html_parts = []
        for ts, act, ent, eid, desc, user, demo in chunk:
            day = ts.strftime("%d/%m/%Y")
            if day != last_day:
                html_parts.append(f'<div class="lm-eyebrow" style="margin-top:.8rem">{day}</div>')
                last_day = day
            html_parts.append(
                f'<div class="lm-timeline-item"><span class="lm-dot {ACTION_DOT.get(act, "blue")}"></span><div>'
                f'<div class="lm-item-title" style="font-weight:500">{ui.esc(desc)} {ui.demo_badge(demo)}</div>'
                f'<div class="lm-item-meta">{ts:%H:%M:%S} · {ui.badge(audit.ACTIONS.get(act, act), "blue")} '
                f'{ui.esc(audit.ENTITY_LABELS.get(ent, ent))}{f" #{eid}" if eid else ""} · {ui.esc(user)}</div>'
                f'</div></div>')
        if html_parts:
            st.markdown(f'<div class="lm-card">{"".join(html_parts)}</div>', unsafe_allow_html=True)
    with tab_table:
        st.dataframe(df, width="stretch", hide_index=True,
                     column_config={"Data/hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm:ss"),
                                    "Descrição": st.column_config.TextColumn(width="large")})
        st.download_button("Exportar histórico (CSV)", to_csv_bytes(df), icon=":material/download:",
                           file_name=f"legal_monitor_historico_{datetime.now():%Y%m%d_%H%M}.csv", mime="text/csv",
                           disabled=df.empty)
