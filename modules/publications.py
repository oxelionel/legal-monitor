"""Módulo C — Publicações."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from sqlalchemy import select

from database.db import session_scope
from database.models import AuditLog
from integrations import SOURCES
from modules import ui
from modules.clients import validation_message
from services import constants as C
from services import publication_service as svc
from services.monitoring import run_triage
from services.schemas import PublicationIn


def _form(prefix: str, initial: dict | None = None) -> dict | None:
    v = initial or {}
    with st.form(f"{prefix}_form", clear_on_submit=initial is None):
        title = st.text_input("Título *", v.get("title", ""))
        c1, c2 = st.columns(2)
        agency = c1.text_input("Órgão responsável *", v.get("agency", ""))
        sources = C.PUBLICATION_SOURCES
        source = c2.selectbox("Fonte *", sources, index=sources.index(v.get("source", "Cadastro manual"))
                              if v.get("source", "Cadastro manual") in sources else 0)
        c3, c4, c5, c6 = st.columns(4)
        number = c3.text_input("Número da publicação", v.get("number") or "")
        pub_date = c4.date_input("Data de publicação *", v.get("publication_date", date.today()),
                                 max_value=date.today(), format="DD/MM/YYYY")
        legal_area = c5.selectbox("Área jurídica *", C.LEGAL_AREAS,
                                  index=C.LEGAL_AREAS.index(v.get("legal_area", C.LEGAL_AREAS[0])))
        doc_type = c6.selectbox("Tipo de documento *", C.DOC_TYPES,
                                index=C.DOC_TYPES.index(v.get("doc_type", C.DOC_TYPES[0])))
        url = st.text_input("URL de origem (quando disponível)", v.get("url") or "", placeholder="https://")
        content = st.text_area("Conteúdo integral *", v.get("content", ""), height=220,
                               help="Cole o texto integral da publicação. Mínimo de 20 caracteres.")
        triage = st.checkbox("Executar triagem automaticamente após salvar", value=True)
        submitted = st.form_submit_button("Salvar alterações" if initial else "Cadastrar publicação", type="primary")
    if not submitted:
        return None
    return dict(title=title, agency=agency, source=source, number=number, publication_date=pub_date,
                legal_area=legal_area, doc_type=doc_type, url=url, content=content, _triage=triage)


def _detail(pub_id: int) -> None:
    with session_scope() as s:
        p = svc.get_publication(s, pub_id)
        if p is None:
            return
        matches = [(m.client.name, m.relevance, m.score, m.status, [t["term"] for t in m.matched_terms])
                   for m in sorted(p.matches, key=lambda m: -m.score)]
        hist = list(s.scalars(select(AuditLog).where(AuditLog.entity == "publicacao", AuditLog.entity_id == pub_id)
                              .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())))
        data = dict(title=p.title, agency=p.agency, source=p.source, number=p.number, date=p.publication_date,
                    area=p.legal_area, doc_type=p.doc_type, url=p.url, content=p.content, demo=p.is_demo,
                    triaged=p.last_triaged_at)

    st.markdown(f"#### {ui.esc(data['title'])} {ui.demo_badge(data['demo'])}", unsafe_allow_html=True)
    ui.kv([
        ("Órgão", ui.esc(data["agency"])), ("Fonte", ui.esc(data["source"])), ("Número", ui.esc(data["number"] or "—")),
        ("Data de publicação", ui.fmt_date(data["date"])), ("Área jurídica", ui.esc(data["area"])),
        ("Tipo", ui.esc(data["doc_type"])), ("Última triagem", ui.fmt_date(data["triaged"], True)),
    ])
    if data["url"]:
        st.markdown(f"[Abrir fonte original ↗]({data['url']})")
    terms = [t for *_, ts in matches for t in ts]
    st.markdown(f'<div class="lm-doc">{ui.highlight(data["content"], terms)}</div>', unsafe_allow_html=True)

    st.markdown("##### Correspondências identificadas")
    if matches:
        st.markdown("".join(
            f'<div class="lm-list-item"><span class="lm-item-title">{ui.esc(c)}</span> {ui.badge(r)} '
            f'{ui.badge(st_, None)}<div class="lm-item-meta">Pontuação {sc:.0f} · termos: '
            f'{ui.esc(", ".join(dict.fromkeys(ts)))}</div></div>'
            for c, r, sc, st_, ts in matches), unsafe_allow_html=True)
    else:
        st.caption("Nenhuma correspondência com clientes ativos.")

    with st.expander("Histórico desta publicação", icon=":material/history:"):
        for a in hist:
            st.markdown(f"- **{ui.fmt_date(a.timestamp, True)}** · {a.action} · {a.description} · _{a.user}_")


def render() -> None:
    ui.page_header("Publicações", "Cadastre, pesquise e consulte publicações oficiais monitoradas.", "Operação")

    tab_search, tab_new, tab_edit, tab_sources = st.tabs(
        ["Consultar", "Cadastrar publicação", "Editar ou excluir", "Fontes oficiais"])

    with tab_search:
        c1, c2, c3 = st.columns([2, 1.2, 1])
        text = c1.text_input("Pesquisar", placeholder="Título, órgão, número ou conteúdo (ignora acentos)")
        period = c2.date_input("Período", (date.today() - timedelta(days=120), date.today()), format="DD/MM/YYYY")
        areas = c3.multiselect("Área jurídica", placeholder="Todos", options=C.LEGAL_AREAS)
        c4, c5 = st.columns(2)
        sources = c4.multiselect("Fonte", placeholder="Todos", options=C.PUBLICATION_SOURCES)
        doc_types = c5.multiselect("Tipo de documento", placeholder="Todos", options=C.DOC_TYPES)
        start, end = (period if isinstance(period, tuple) and len(period) == 2 else (None, None))
        with session_scope() as s:
            pubs = svc.search_publications(s, text, start, end, areas, sources, doc_types)
            rows = [{
                "id": p.id, "Data": p.publication_date, "Título": p.title, "Órgão": p.agency, "Tipo": p.doc_type,
                "Área": p.legal_area, "Fonte": p.source, "Correspondências": len(p.matches),
                "Maior relevância": next((r for r in ("ALTA", "MÉDIA", "BAIXA") if any(m.relevance == r for m in p.matches)), "—"),
            } for p in pubs]
        df = pd.DataFrame(rows)
        st.caption(f"{len(df)} publicação(ões) encontrada(s). Selecione uma linha para ver o conteúdo integral.")
        if df.empty:
            ui.empty_state("Nenhuma publicação encontrada para os filtros informados.")
        else:
            event = st.dataframe(
                df.drop(columns=["id"]), width="stretch", hide_index=True, on_select="rerun",
                selection_mode="single-row", key="pub_table",
                column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                               "Título": st.column_config.TextColumn(width="large")},
            )
            selected = event.selection.rows if event and event.selection else []
            if selected:
                st.divider()
                _detail(int(df.iloc[selected[0]]["id"]))

    with tab_new:
        ui.callout("Cadastre aqui publicações obtidas manualmente. A captura automática de fontes oficiais ainda "
                   "não está implementada — veja a aba <b>Fontes oficiais</b>.", "info")
        data = _form("new_pub")
        if data:
            do_triage = data.pop("_triage")
            try:
                payload = PublicationIn(**data)
                with session_scope() as s:
                    pub = svc.create_publication(s, payload)
                    summary = run_triage(s, [pub.id]) if do_triage else None
                msg = "Publicação cadastrada."
                if summary:
                    msg += (f" Triagem: {summary.total_matches} correspondência(s) — "
                            f"{summary.by_relevance['ALTA']} alta, {summary.by_relevance['MÉDIA']} média, "
                            f"{summary.by_relevance['BAIXA']} baixa.")
                ui.notify(msg)
                st.rerun()
            except ValidationError as exc:
                st.error(validation_message(exc))
            except svc.DuplicatePublicationError as exc:
                st.error(str(exc))

    with tab_edit:
        with session_scope() as s:
            options = {p.id: f"{ui.fmt_date(p.publication_date)} · {p.title}"
                       for p in svc.search_publications(s)}
        if not options:
            ui.empty_state("Nenhuma publicação cadastrada.")
        else:
            pub_id = st.selectbox("Selecione a publicação", list(options), format_func=options.get)
            with session_scope() as s:
                p = svc.get_publication(s, pub_id)
                initial = svc.snapshot(p)
                is_demo = p.is_demo
            data = _form(f"edit_pub_{pub_id}", initial)
            if data:
                do_triage = data.pop("_triage")
                try:
                    payload = PublicationIn(**data, is_demo=is_demo)
                    with session_scope() as s:
                        svc.update_publication(s, pub_id, payload)
                        if do_triage:
                            run_triage(s, [pub_id])
                    ui.notify("Publicação atualizada.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(validation_message(exc))
                except (svc.DuplicatePublicationError, LookupError) as exc:
                    st.error(str(exc))
            with st.expander("Excluir publicação", icon=":material/delete:"):
                st.write("A exclusão remove a publicação e suas correspondências. Possíveis prazos vinculados são "
                         "mantidos, sem a referência de origem.")
                confirm = st.checkbox("Confirmo a exclusão definitiva", key=f"del_pub_confirm_{pub_id}")
                if st.button("Excluir publicação", type="primary", disabled=not confirm, key=f"del_pub_{pub_id}"):
                    with session_scope() as s:
                        svc.delete_publication(s, pub_id)
                    ui.notify("Publicação excluída.")
                    st.rerun()

    with tab_sources:
        ui.callout("A arquitetura já prevê conectores para fontes oficiais (pasta <code>integrations/</code>). "
                   "<b>Nenhuma consulta externa é realizada no MVP 1.0</b>; os conectores abaixo estão planejados.",
                   "warn")
        st.dataframe(pd.DataFrame([{"Fonte": src.name, "Descrição": src.description, "Situação": src.status,
                                    "Credenciais necessárias": src.credentials} for src in SOURCES]),
                     width="stretch", hide_index=True)
