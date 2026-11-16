"""Módulo F — Gestão de possíveis prazos."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from pydantic import ValidationError

import config
from database.db import session_scope
from database.models import Deadline
from modules import ui
from modules.clients import validation_message
from services import constants as C
from services import deadline_service as svc
from services.client_service import list_clients
from services.publication_service import search_publications
from services.schemas import DeadlineIn

URGENCY_STYLE = {"Vencido": "background-color:#FDECEA;color:#C9372C;font-weight:700",
                 "Crítico": "background-color:#FDECEA;color:#C9372C;font-weight:700",
                 "Próximo": "background-color:#FFF2E2;color:#C76A12;font-weight:700",
                 "No prazo": "color:#1E7F55;font-weight:600"}

DATE_TYPE_HELP = {
    "Prazo processual": "Prazo em processo judicial — contagem conforme CPC/CLT/leis específicas (ex.: dias úteis).",
    "Prazo administrativo": "Prazo em processo/ato administrativo — regras da lei do ente (ex.: Lei 9.784/1999).",
    "Data de vigência": "Data em que a norma ou ato passa a produzir efeitos. Não é, por si, um prazo.",
    "Data de publicação": "Data de veiculação do ato. Não é presumida como termo inicial de prazo.",
    "Obrigação contratual": "Obrigação decorrente de contrato, convênio ou termo.",
    "Outra data relevante": "Data de interesse que requer acompanhamento.",
}


def _form(prefix: str, clients: dict, pubs: dict, initial: dict | None = None) -> dict | None:
    v = initial or {}
    with st.form(f"{prefix}_form", clear_on_submit=initial is None):
        desc = st.text_input("Descrição *", v.get("description", ""))
        c1, c2 = st.columns(2)
        client_keys = [None] + list(clients)
        client_id = c1.selectbox("Cliente relacionado", client_keys,
                                 index=client_keys.index(v.get("client_id")) if v.get("client_id") in client_keys else 0,
                                 format_func=lambda k: "—" if k is None else clients[k])
        pub_keys = [None] + list(pubs)
        pub_id = c2.selectbox("Publicação de origem", pub_keys,
                              index=pub_keys.index(v.get("publication_id")) if v.get("publication_id") in pub_keys else 0,
                              format_func=lambda k: "—" if k is None else pubs[k])
        c3, c4, c5, c6 = st.columns(4)
        date_type = c3.selectbox("Natureza da data *", C.DATE_TYPES,
                                 index=C.DATE_TYPES.index(v.get("date_type", C.DATE_TYPES[0])),
                                 help=" | ".join(f"{k}: {t}" for k, t in DATE_TYPE_HELP.items()))
        ref = c4.date_input("Data de referência", v.get("reference_date"), format="DD/MM/YYYY")
        due = c5.date_input("Data limite sugerida", v.get("due_date"), format="DD/MM/YYYY")
        status = c6.selectbox("Status", C.DEADLINE_STATUS, index=C.DEADLINE_STATUS.index(v.get("status", "Pendente")))
        c7, c8 = st.columns(2)
        resp = c7.text_input("Responsável", v.get("responsible") or "")
        validated = c8.checkbox("Validado por profissional responsável", value=bool(v.get("validated")))
        notes = st.text_area("Observações", v.get("notes") or "", height=80)
        submitted = st.form_submit_button("Salvar alterações" if initial else "Registrar possível prazo", type="primary")
    if not submitted:
        return None
    return dict(description=desc, client_id=client_id, publication_id=pub_id, date_type=date_type, reference_date=ref,
                due_date=due, status=status, responsible=resp, validated=validated, notes=notes,
                origin=v.get("origin", "Manual"))


def render() -> None:
    ui.page_header("Possíveis prazos", "Controle de obrigações e datas relevantes identificadas nas publicações.",
                   "Operação")
    ui.callout("<b>Aviso jurídico:</b> os registros desta página são <b>possíveis prazos</b>. O Legal Monitor não "
               "presume que a data de publicação seja o termo inicial e não trata datas extraídas automaticamente como "
               "definitivas. Toda data deve ser validada por profissional responsável, considerando a legislação, "
               "a natureza da data (vigência, publicação, prazo administrativo ou processual) e as regras de contagem.",
               "warn")

    today = date.today()
    with session_scope() as s:
        items = svc.list_deadlines(s)
        rows = []
        for d in items:
            label, days = svc.urgency(d, today)
            rows.append({
                "id": d.id, "Situação": label, "Dias": days, "Descrição": d.description, "Natureza": d.date_type,
                "Cliente": d.client.name if d.client else "—", "Data de referência": d.reference_date,
                "Data limite sugerida": d.due_date, "Status": d.status, "Responsável": d.responsible or "",
                "Validado": "Sim" if d.validated else "Não", "Origem": d.origin,
                "Publicação": d.publication.title if d.publication else "—",
            })
        clients = {c.id: c.name for c in list_clients(s)}
        pubs = {p.id: f"{ui.fmt_date(p.publication_date)} · {p.title[:80]}" for p in search_publications(s)}
    df = pd.DataFrame(rows)

    open_df = df[df["Status"].isin(C.DEADLINE_OPEN_STATUS)] if not df.empty else df
    ui.kpi_grid([
        dict(label="Em aberto", value=len(open_df), hint="pendentes ou em andamento", icon="clock"),
        dict(label=f"Próximos {config.DEADLINE_ALERT_DAYS} dias", value=int(open_df["Situação"].isin(["Crítico", "Próximo"]).sum()) if not open_df.empty else 0,
             hint="exigem atenção", icon="calendar", tone="orange"),
        dict(label="Vencidos", value=int((df["Situação"] == "Vencido").sum()) if not df.empty else 0,
             hint="sem conclusão registrada", icon="alert", tone="red"),
        dict(label="Aguardando validação", value=int((open_df["Validado"] == "Não").sum()) if not open_df.empty else 0,
             hint="não confirmados por profissional", icon="check", tone="blue"),
    ])

    t1, t2, t3 = st.tabs(["Painel de prazos", "Registrar possível prazo", "Editar ou excluir"])
    with t1:
        if df.empty:
            ui.empty_state("Nenhum possível prazo registrado.")
        else:
            f1, f2 = st.columns(2)
            st_filter = f1.multiselect("Status", placeholder="Todos", options=C.DEADLINE_STATUS, default=["Pendente", "Em andamento", "Vencido"])
            nat_filter = f2.multiselect("Natureza da data", placeholder="Todos", options=C.DATE_TYPES)
            view = df[df["Status"].isin(st_filter)] if st_filter else df
            if nat_filter:
                view = view[view["Natureza"].isin(nat_filter)]
            st.dataframe(
                view.drop(columns=["id"]).style.map(lambda v: URGENCY_STYLE.get(v, ""), subset=["Situação"])
                .format({"Dias": lambda v: "—" if pd.isna(v) else f"{int(v)}"}),
                width="stretch", hide_index=True,
                column_config={"Data de referência": st.column_config.DateColumn(format="DD/MM/YYYY"),
                               "Data limite sugerida": st.column_config.DateColumn(format="DD/MM/YYYY"),
                               "Dias": st.column_config.NumberColumn(help="Dias restantes até a data limite sugerida"),
                               "Descrição": st.column_config.TextColumn(width="large")},
            )
            timeline = view.dropna(subset=["Data limite sugerida"])
            timeline = timeline[timeline["Status"].isin(C.DEADLINE_OPEN_STATUS + ("Vencido",))]
            if not timeline.empty:
                timeline = timeline.assign(**{"Data limite": pd.to_datetime(timeline["Data limite sugerida"])})
                fig = px.scatter(timeline, x="Data limite", y="Cliente", color="Situação", symbol="Natureza",
                                 hover_data={"Descrição": True, "Dias": True, "Data limite": "|%d/%m/%Y"},
                                 color_discrete_map={"Vencido": ui.PALETTE["red"], "Crítico": ui.PALETTE["red"],
                                                     "Próximo": ui.PALETTE["orange"], "No prazo": ui.PALETTE["green"]})
                fig.update_traces(marker=dict(size=15, line=dict(width=1.5, color="white")))
                fig.add_vline(x=pd.Timestamp(today).value / 1e6, line_dash="dot", line_color=ui.PALETTE["navy"],
                              annotation_text="Hoje", annotation_position="top")
                fig.update_xaxes(tickformat="%d/%m", range=[pd.Timestamp(today - timedelta(days=10)),
                                                             pd.Timestamp(today + timedelta(days=45))])
                st.plotly_chart(ui.style_fig(fig, height=340, title="Linha do tempo dos possíveis prazos em aberto"),
                                width="stretch", config={"displayModeBar": False})

    with t2:
        data = _form("new_deadline", clients, pubs)
        if data:
            try:
                with session_scope() as s:
                    svc.create_deadline(s, DeadlineIn(**data))
                ui.notify("Possível prazo registrado.")
                st.rerun()
            except ValidationError as exc:
                st.error(validation_message(exc))

    with t3:
        if df.empty:
            ui.empty_state("Nenhum possível prazo para editar.")
            return
        options = {r["id"]: f"{r['Descrição']} ({r['Status']})" for r in rows}
        dl_id = st.selectbox("Selecione", list(options), format_func=options.get)
        with session_scope() as s:
            d = s.get(Deadline, dl_id)
            initial, is_demo = svc.snapshot(d), d.is_demo
        data = _form(f"edit_deadline_{dl_id}", clients, pubs, initial)
        if data:
            try:
                with session_scope() as s:
                    svc.update_deadline(s, dl_id, DeadlineIn(**data, is_demo=is_demo))
                ui.notify("Possível prazo atualizado.")
                st.rerun()
            except ValidationError as exc:
                st.error(validation_message(exc))
            except LookupError as exc:
                st.error(str(exc))
        with st.expander("Excluir possível prazo", icon=":material/delete:"):
            confirm = st.checkbox("Confirmo a exclusão", key=f"del_dl_confirm_{dl_id}")
            if st.button("Excluir", type="primary", disabled=not confirm, key=f"del_dl_{dl_id}"):
                with session_scope() as s:
                    svc.delete_deadline(s, dl_id)
                ui.notify("Possível prazo excluído.")
                st.rerun()
