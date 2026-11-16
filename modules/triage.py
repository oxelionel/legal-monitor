"""Módulo E — Triagem jurídica."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from sqlalchemy import select

from database.db import session_scope
from database.models import AuditLog, Match
from modules import ui
from modules.clients import validation_message
from services import constants as C
from services.classification import EVIDENCE_LABELS
from services.client_service import list_clients
from services.date_extraction import extract_mentions
from services.deadline_service import create_deadline
from services.monitoring import list_matches, update_match_status
from services.schemas import DeadlineIn
from services.text import format_document


def _load_detail(match_id: int) -> dict | None:
    with session_scope() as s:
        m = s.get(Match, match_id)
        if m is None:
            return None
        p, c = m.publication, m.client
        hist = [(a.timestamp, a.description, a.user) for a in s.scalars(
            select(AuditLog).where(AuditLog.entity == "correspondencia", AuditLog.entity_id == match_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()))]
        return dict(
            id=m.id, status=m.status, relevance=m.relevance, score=m.score, terms=m.matched_terms,
            justification=m.justification, notes=m.analyst_notes, pub_id=p.id, title=p.title, agency=p.agency,
            source=p.source, number=p.number, pub_date=p.publication_date, area=p.legal_area, doc_type=p.doc_type,
            content=p.content, url=p.url, demo=p.is_demo, client_id=c.id, client=c.name, responsible=c.responsible,
            client_area=c.legal_area, history=hist,
        )


def _detail(d: dict) -> None:
    st.markdown(f"### {ui.esc(d['title'])} {ui.demo_badge(d['demo'])}", unsafe_allow_html=True)
    st.markdown(f"{ui.badge(d['relevance'])} {ui.badge(d['status'])} &nbsp; Pontuação **{d['score']:.0f}/100**",
                unsafe_allow_html=True)
    ui.kv([
        ("Cliente relacionado", ui.esc(d["client"])), ("Responsável", ui.esc(d["responsible"] or "—")),
        ("Área jurídica", ui.esc(d["area"])), ("Data de publicação", ui.fmt_date(d["pub_date"])),
        ("Órgão", ui.esc(d["agency"])), ("Tipo / número", ui.esc(f"{d['doc_type']} · {d['number'] or 's/n'}")),
    ])

    col_doc, col_side = st.columns([1.5, 1])
    with col_doc:
        st.markdown("##### Publicação original")
        terms = []
        for t in d["terms"]:
            if t["type"] == "documento":
                terms.append(format_document(t["term"]))
            elif t["type"] == "aproximada" and t.get("excerpt"):
                continue
            elif t["type"] != "area":
                terms.append(t["term"])
        st.markdown(f'<div class="lm-doc">{ui.highlight(d["content"], terms)}</div>', unsafe_allow_html=True)
        if d["url"]:
            st.markdown(f"[Abrir fonte original ↗]({d['url']})")
    with col_side:
        st.markdown("##### Justificativa da correspondência")
        st.markdown(f'<div class="lm-justification">{ui.esc(d["justification"])}</div>', unsafe_allow_html=True)
        st.markdown("##### Palavras-chave encontradas")
        st.dataframe(pd.DataFrame([{
            "Tipo": EVIDENCE_LABELS.get(t["type"], t["type"]),
            "Termo": format_document(t["term"]) if t["type"] == "documento" else t["term"],
            "Ocorr.": t["occurrences"], "Pontos": round(t["points"], 1),
        } for t in d["terms"]]), hide_index=True, width="stretch")

    st.markdown("##### Análise do profissional")
    with st.form(f"status_{d['id']}"):
        c1, c2 = st.columns([1, 2])
        status = c1.selectbox("Status da análise", C.TRIAGE_STATUS, index=C.TRIAGE_STATUS.index(d["status"]))
        notes = c2.text_area("Observações da análise", d["notes"] or "", height=90)
        if st.form_submit_button("Salvar análise", type="primary"):
            with session_scope() as s:
                update_match_status(s, d["id"], status, notes)
            ui.notify(f"Status atualizado para “{status}”.")
            st.rerun()

    _deadline_form(d)

    with st.expander("Histórico desta correspondência", icon=":material/history:"):
        if not d["history"]:
            st.caption("Sem registros.")
        for ts, desc, user in d["history"]:
            st.markdown(f"- **{ui.fmt_date(ts, True)}** · {desc} · _{user}_")


def _deadline_form(d: dict) -> None:
    mentions = extract_mentions(d["content"])
    with st.expander("Registrar possível prazo a partir desta publicação", icon=":material/event_upcoming:"):
        ui.callout("<b>Atenção:</b> as datas e períodos abaixo são <b>indícios extraídos automaticamente</b>. "
                   "O sistema não presume que a data de publicação seja o termo inicial de contagem nem trata "
                   "sugestões como prazos definitivos. Valide a natureza da data, o termo inicial e a regra de "
                   "contagem (dias úteis/corridos, feriados, suspensões) conforme a legislação aplicável.", "warn")
        if mentions:
            st.dataframe(pd.DataFrame([{"Indício": m.summary, "Trecho": m.snippet} for m in mentions]),
                         hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma menção a data ou prazo identificada no texto.")
        first_date = next((m for m in mentions if m.kind == "data"), None)
        with st.form(f"deadline_{d['id']}", clear_on_submit=True):
            desc = st.text_input("Descrição *", f"Verificar obrigação — {d['title'][:120]}")
            c1, c2, c3 = st.columns(3)
            suggested = first_date.suggested_type if first_date else C.DATE_TYPES[1]
            date_type = c1.selectbox("Natureza da data *", C.DATE_TYPES, index=C.DATE_TYPES.index(suggested))
            ref = c2.date_input("Data de referência", None, format="DD/MM/YYYY",
                                help="Termo inicial ou data-base informada pelo profissional.")
            due = c3.date_input("Data limite sugerida", first_date.value if first_date else None, format="DD/MM/YYYY")
            c4, c5 = st.columns([1, 1])
            resp = c4.text_input("Responsável", d["responsible"] or "")
            validated = c5.checkbox("Data validada por profissional responsável")
            notes = st.text_area("Observações", height=70)
            if st.form_submit_button("Registrar possível prazo", type="primary"):
                try:
                    payload = DeadlineIn(description=desc, publication_id=d["pub_id"], client_id=d["client_id"],
                                         date_type=date_type, reference_date=ref, due_date=due, responsible=resp,
                                         notes=notes, validated=validated, origin="Sugestão da triagem",
                                         is_demo=d["demo"])
                    with session_scope() as s:
                        create_deadline(s, payload)
                    ui.notify("Possível prazo registrado. Acompanhe em “Possíveis prazos”.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(validation_message(exc))


def render() -> None:
    ui.page_header("Triagem jurídica", "Analise as correspondências identificadas pelo motor e registre a decisão "
                   "profissional.", "Operação")
    with session_scope() as s:
        clients = {c.id: c.name for c in list_clients(s)}

    c1, c2, c3 = st.columns(3)
    relevance = c1.multiselect("Relevância", placeholder="Todos", options=C.RELEVANCE_LEVELS)
    status = c2.multiselect("Status da análise", placeholder="Todos", options=C.TRIAGE_STATUS, default=["Pendente", "Em análise"])
    client_ids = c3.multiselect("Cliente", placeholder="Todos", options=list(clients), format_func=clients.get)

    with session_scope() as s:
        matches = list_matches(s, relevance or None, status or None, client_ids or None)
        rows = [{
            "id": m.id, "Relevância": m.relevance, "Pontuação": round(m.score), "Cliente": m.client.name,
            "Publicação": m.publication.title, "Data": m.publication.publication_date, "Área": m.publication.legal_area,
            "Status": m.status,
            "Termos": ", ".join(dict.fromkeys(format_document(t["term"]) if t["type"] == "documento" else t["term"]
                                              for t in m.matched_terms if t["type"] != "area")),
        } for m in matches]
    df = pd.DataFrame(rows)

    counts = df["Relevância"].value_counts().to_dict() if not df.empty else {}
    ui.kpi_grid([
        dict(label="Itens na fila", value=len(df), hint="conforme filtros", icon="check"),
        dict(label="Alta relevância", value=counts.get("ALTA", 0), icon="alert", tone="red"),
        dict(label="Média relevância", value=counts.get("MÉDIA", 0), icon="link", tone="orange"),
        dict(label="Baixa relevância", value=counts.get("BAIXA", 0), icon="file", tone="blue"),
    ])

    if df.empty:
        ui.empty_state("Nenhuma correspondência para os filtros selecionados.")
        return

    def _color(v):
        return {"ALTA": "color:#C9372C;font-weight:700", "MÉDIA": "color:#C76A12;font-weight:700",
                "BAIXA": "color:#2F6FC4;font-weight:700"}.get(v, "")

    st.caption("Selecione uma linha para abrir a análise detalhada.")
    event = st.dataframe(
        df.drop(columns=["id"]).style.map(_color, subset=["Relevância"]), width="stretch", hide_index=True,
        on_select="rerun", selection_mode="single-row", key="triage_table",
        column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                       "Pontuação": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                       "Publicação": st.column_config.TextColumn(width="large")},
    )
    selected = event.selection.rows if event and event.selection else []
    if not selected:
        ui.callout(f"Dica: comece pelos itens de <b>ALTA</b> relevância. Hoje é {date.today():%d/%m/%Y}.", "info")
        return
    st.divider()
    detail = _load_detail(int(df.iloc[selected[0]]["id"]))
    if detail:
        _detail(detail)
