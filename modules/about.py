"""Página institucional: problema, solução, funcionamento e evolução do produto."""
from __future__ import annotations

import streamlit as st

import config
from modules import ui

PROBLEM = [
    ("Volume", "Diários oficiais publicam milhares de atos por dia, em diversas fontes e formatos."),
    ("Risco", "Uma publicação não identificada pode significar multa, perda de prazo ou oportunidade perdida."),
    ("Custo", "A leitura manual é lenta, repetitiva e sujeita a falhas humanas."),
    ("Rastreabilidade", "Planilhas e e-mails não registram por que algo foi considerado relevante."),
]

FLOW = [
    ("Clientes", "Cadastro de clientes, documentos e termos monitorados."),
    ("Publicações", "Cadastro manual hoje; conectores oficiais (DOU/INLABS, DataJud) no roadmap."),
    ("Motor", "Comparação exata, por expressões, palavras-chave e aproximada, com pontuação transparente."),
    ("Triagem", "Fila priorizada por relevância para decisão do profissional."),
    ("Prazos", "Registro de possíveis prazos com natureza da data e validação obrigatória."),
    ("Relatórios", "Exportação CSV/PDF e trilha de auditoria completa."),
]

ROADMAP = [
    ("MVP 1.0 — atual", "Disponível", "Cadastros, motor de correspondência por regras, triagem, possíveis prazos, "
     "relatórios CSV/PDF, auditoria e base demonstrativa."),
    ("1.1", "Planejado", "Captura automática do DOU via INLABS; agendamento diário; notificações por e-mail."),
    ("1.2", "Planejado", "Integração DataJud (CNJ); vínculo de publicações a processos; calendário de feriados."),
    ("1.5", "Planejado", "Autenticação, perfis de acesso e multiusuário; API REST (FastAPI) e PostgreSQL."),
    ("2.0", "Visão", "IA para resumo e classificação assistida; SaaS multi-inquilino; painéis por cliente."),
]


def render() -> None:
    ui.page_header(config.APP_NAME, config.APP_SLOGAN, "Sobre o projeto")
    ui.callout("O <b>Legal Monitor</b> automatiza a identificação, classificação e acompanhamento de publicações "
               "oficiais relevantes para clientes, empresas e departamentos jurídicos — com regras auditáveis e a "
               "decisão final sempre nas mãos do profissional.", "info")

    st.markdown("#### O problema")
    problems = "".join(
        f'<div class="lm-kpi tone-red"><div style="font-weight:700;color:#0B2545;margin-bottom:.25rem">{t}</div>'
        f'<div class="lm-kpi-hint">{d}</div></div>' for t, d in PROBLEM)
    st.markdown(f'<div class="lm-kpi-grid">{problems}</div>', unsafe_allow_html=True)

    st.markdown("#### Como a solução funciona")
    steps = "".join(
        f'<div class="lm-kpi tone-blue"><div class="lm-kpi-label">Etapa {i}</div>'
        f'<div style="font-weight:700;color:#0B2545;margin:.25rem 0">{t}</div><div class="lm-kpi-hint">{d}</div></div>'
        for i, (t, d) in enumerate(FLOW, 1))
    st.markdown(f'<div class="lm-kpi-grid">{steps}</div>', unsafe_allow_html=True)

    st.markdown("#### Diferenciais")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.card("Transparência", "<span class='lm-item-meta'>Cada alerta mostra os termos encontrados, os pontos "
                "atribuídos e a justificativa. As regras são configuráveis.</span>")
    with c2:
        ui.card("Segurança jurídica", "<span class='lm-item-meta'>Datas são tratadas como <b>possíveis prazos</b>, "
                "diferenciando vigência, publicação, prazo administrativo e processual.</span>")
    with c3:
        ui.card("Pronto para evoluir", "<span class='lm-item-meta'>Arquitetura em camadas (interface, serviços, "
                "dados e integrações) preparada para API, PostgreSQL e IA.</span>")

    st.markdown("#### Roadmap")
    for version, status, desc in ROADMAP:
        tone = "green" if status == "Disponível" else ("blue" if status == "Planejado" else "gray")
        st.markdown(f'<div class="lm-card"><div class="lm-card-title">{version} {ui.badge(status, tone)}</div>'
                    f'<div class="lm-item-meta">{desc}</div></div>', unsafe_allow_html=True)

    st.markdown("#### Limitações conhecidas do MVP")
    st.markdown(
        "- Sem autenticação de usuários: indicado para uso local e demonstrações.\n"
        "- Sem captura automática de fontes oficiais; publicações são cadastradas manualmente.\n"
        "- Classificação por regras (sem IA); a correspondência aproximada é heurística.\n"
        "- Extração de datas é indicativa e não calcula prazos legais (feriados, dias úteis, suspensões).\n"
        "- O MVP não foi auditado quanto à conformidade com a LGPD; não utilize dados pessoais reais sem avaliação."
    )
