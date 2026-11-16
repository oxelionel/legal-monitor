"""Módulo D — Motor de monitoramento e correspondência (execução, regras e simulador)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from database.db import session_scope
from modules import ui
from services import audit
from services import classification as cls
from services.client_service import list_clients
from services.constants import LEGAL_AREAS
from services.matching import PublicationText, evaluate
from services.monitoring import profile_of, run_triage
from services.publication_service import search_publications

PIPELINE = [
    ("1", "Recepção", "A publicação é cadastrada (manual hoje; conectores oficiais no roadmap)."),
    ("2", "Normalização", "Texto em minúsculas, sem acentos e pontuação, para comparação robusta."),
    ("3", "Comparação", "CPF/CNPJ, nome, nome fantasia, expressões e palavras-chave de cada cliente ativo."),
    ("4", "Aproximação", "Similaridade de sequência tolera erros de digitação/OCR em nomes e expressões."),
    ("5", "Pontuação", "Pesos configuráveis por tipo de evidência + bônus por repetição e área jurídica."),
    ("6", "Classificação", "ALTA, MÉDIA ou BAIXA com justificativa e termos registrados."),
    ("7", "Triagem humana", "O profissional confirma, descarta ou encaminha — e registra possíveis prazos."),
]


def _pipeline() -> None:
    steps = "".join(
        f'<div class="lm-kpi" style="padding:.8rem .9rem"><div class="lm-kpi-label">Etapa {n}</div>'
        f'<div style="font-weight:700;color:#0B2545;margin:.2rem 0">{t}</div>'
        f'<div class="lm-kpi-hint">{d}</div></div>' for n, t, d in PIPELINE)
    st.markdown(f'<div class="lm-kpi-grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr))">{steps}</div>',
                unsafe_allow_html=True)


def _run_tab() -> None:
    with session_scope() as s:
        pubs = {p.id: f"{ui.fmt_date(p.publication_date)} · {p.title}" for p in search_publications(s)}
        n_active = len(list_clients(s, only_active=True))
    st.write(f"**{len(pubs)}** publicação(ões) cadastrada(s) · **{n_active}** cliente(s) com monitoramento ativo.")
    scope = st.radio("Escopo da triagem", ["Todas as publicações", "Publicações selecionadas"], horizontal=True)
    selected = []
    if scope == "Publicações selecionadas":
        selected = st.multiselect("Publicações", placeholder="Todos", options=list(pubs), format_func=pubs.get)
    st.caption("A triagem é idempotente: não gera duplicidades, atualiza pontuações e preserva o status definido "
               "manualmente pelos analistas.")
    if st.button("Executar triagem agora", type="primary", icon=":material/play_arrow:",
                 disabled=scope == "Publicações selecionadas" and not selected):
        with st.spinner("Comparando publicações com os clientes monitorados..."):
            with session_scope() as s:
                summary = run_triage(s, selected or None)
        st.session_state["last_triage"] = summary
    summary = st.session_state.get("last_triage")
    if summary:
        st.success("Triagem concluída.")
        ui.kpi_grid([
            dict(label="Publicações processadas", value=summary.publications, icon="file"),
            dict(label="Novas correspondências", value=summary.created, icon="link", tone="blue"),
            dict(label="Atualizadas", value=summary.updated, hint=f"{summary.unchanged} sem alteração", icon="check",
                 tone="green"),
            dict(label="Removidas / preservadas", value=f"{summary.removed} / {summary.kept_reviewed}",
                 hint="preservadas: já revisadas por analista", icon="clock", tone="orange"),
            dict(label="Alta relevância", value=summary.by_relevance["ALTA"],
                 hint=f"Média {summary.by_relevance['MÉDIA']} · Baixa {summary.by_relevance['BAIXA']}", icon="alert",
                 tone="red"),
        ])


def _rules_tab() -> None:
    with session_scope() as s:
        rules = cls.get_rules(s)
    ui.callout("As regras são <b>transparentes e configuráveis</b>. Cada correspondência registra os termos "
               "encontrados e os pontos atribuídos, permitindo auditar a classificação.", "info")
    with st.form("rules_form"):
        st.markdown("**Pesos por tipo de evidência (pontos da primeira ocorrência)**")
        cols = st.columns(4)
        weights = {}
        for i, (key, label) in enumerate(cls.EVIDENCE_LABELS.items()):
            weights[key] = cols[i % 4].number_input(label, 0, 100, int(rules["weights"][key]), key=f"w_{key}")
        st.markdown("**Limites de classificação (pontuação mínima)**")
        c1, c2, c3 = st.columns(3)
        alta = c1.number_input("ALTA", 1, 100, int(rules["thresholds"]["ALTA"]))
        media = c2.number_input("MÉDIA", 1, 100, int(rules["thresholds"]["MÉDIA"]))
        baixa = c3.number_input("BAIXA", 1, 100, int(rules["thresholds"]["BAIXA"]))
        st.markdown("**Parâmetros adicionais**")
        c4, c5, c6 = st.columns(3)
        bonus = c4.number_input("Bônus por ocorrência repetida", 0, 20, int(rules["repeat_bonus"]))
        cap = c5.number_input("Teto do bônus por termo", 0, 50, int(rules["repeat_bonus_cap"]))
        fuzzy = c6.slider("Similaridade mínima (aproximada)", 0.70, 0.99, float(rules["fuzzy_threshold"]), 0.01)
        strong = st.multiselect("Evidências que caracterizam ALTA relevância isoladamente",
                                list(cls.EVIDENCE_LABELS), default=rules["strong_types"], placeholder="Nenhuma",
                                format_func=cls.EVIDENCE_LABELS.get)
        area_only = st.checkbox("Considerar coincidência de área jurídica isolada como correspondência (BAIXA)",
                                value=bool(rules["area_only_counts"]),
                                help="Desativado por padrão para evitar ruído: todos os clientes da área seriam alertados.")
        c7, c8 = st.columns(2)
        save = c7.form_submit_button("Salvar regras e reprocessar", type="primary")
        reset = c8.form_submit_button("Restaurar padrões")
    if save or reset:
        try:
            with session_scope() as s:
                if reset:
                    new_rules = cls.reset_rules(s)
                else:
                    new_rules = {**rules, "weights": weights, "thresholds": {"ALTA": alta, "MÉDIA": media, "BAIXA": baixa},
                                 "repeat_bonus": bonus, "repeat_bonus_cap": cap, "fuzzy_threshold": fuzzy,
                                 "strong_types": strong, "area_only_counts": area_only}
                    cls.save_rules(s, new_rules)
                audit.log(s, "ALTERAÇÃO", "configuracao",
                          "Regras de classificação restauradas ao padrão." if reset else "Regras de classificação alteradas.",
                          details=new_rules)
                s.flush()
                summary = run_triage(s)
            ui.notify(f"Regras salvas. Triagem reprocessada: {summary.total_matches} correspondência(s).")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def _simulator_tab() -> None:
    st.write("Teste o motor com qualquer texto, **sem gravar nada** no banco. Útil para demonstrar o funcionamento "
             "e calibrar palavras-chave.")
    text = st.text_area("Texto da publicação", height=170,
                        placeholder="Cole um trecho, por exemplo: “Fica notificada a TRANSPORTES ROTALUZ LTDA ...”")
    area = st.selectbox("Área jurídica do texto (opcional)", ["—"] + LEGAL_AREAS)
    if st.button("Simular correspondências", icon=":material/science:") and text.strip():
        with session_scope() as s:
            rules = cls.get_rules(s)
            profiles = [profile_of(c) for c in list_clients(s, only_active=True)]
        pub = PublicationText(id=None, title="", content=text, legal_area=None if area == "—" else area)
        results = [(p, evaluate(pub, p, rules)) for p in profiles]
        results = sorted([r for r in results if r[1]], key=lambda r: -r[1].score)
        if not results:
            ui.empty_state("Nenhuma correspondência com os clientes ativos.")
        for profile, r in results:
            st.markdown(f"**{ui.esc(profile.name)}** {ui.badge(r.relevance)} · pontuação {r.score:.0f}",
                        unsafe_allow_html=True)
            st.markdown(f'<div class="lm-justification">{ui.esc(r.justification)}</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{"Tipo": e.label, "Termo": e.term, "Ocorrências": e.occurrences,
                                        "Pontos": e.points, "Similaridade": e.similarity} for e in r.evidences]),
                         hide_index=True, width="stretch")


def render() -> None:
    ui.page_header("Motor de monitoramento", "Execute a triagem automatizada, ajuste as regras de relevância e "
                   "teste o motor de correspondência.", "Operação")
    _pipeline()
    t1, t2, t3 = st.tabs(["Executar triagem", "Regras de classificação", "Simulador"])
    with t1:
        _run_tab()
    with t2:
        _rules_tab()
    with t3:
        _simulator_tab()
