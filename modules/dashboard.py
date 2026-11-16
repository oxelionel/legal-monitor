"""Módulo A — Dashboard executivo."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from database.db import session_scope
from modules import ui
from services import analytics
from services.audit import ACTIONS
from services.deadline_service import list_deadlines, urgency

ACTION_DOT = {"CRIAÇÃO": "green", "ALTERAÇÃO": "blue", "EXCLUSÃO": "red", "TRIAGEM": "blue",
              "CORRESPONDÊNCIA": "orange", "STATUS": "blue", "PRAZO": "orange", "SISTEMA": "gray"}


def render() -> None:
    ui.page_header("Painel de monitoramento", "Visão consolidada das publicações, correspondências e possíveis prazos "
                   "da carteira monitorada.", "Visão geral")

    with session_scope() as s:
        k = analytics.kpis(s, soon_days=config.DEADLINE_ALERT_DAYS)
        pubs_df = analytics.publications_frame(s)
        matches_df = analytics.matches_frame(s)
        recent_pubs = [(p.title, p.agency, p.publication_date, p.legal_area, p.is_demo,
                        max((m.relevance for m in p.matches), key=["BAIXA", "MÉDIA", "ALTA"].index, default=None))
                       for p in analytics.recent_publications(s)]
        activity = [(a.timestamp, a.action, a.description, a.user, a.is_demo) for a in analytics.recent_activity(s)]
        upcoming = [(d.description, d.due_date, d.status, d.client.name if d.client else "—", d.date_type,
                     d.validated, urgency(d)) for d in list_deadlines(s) if d.status in ("Pendente", "Em andamento", "Vencido")]

    if k.demo_records:
        ui.callout("<b>Base de demonstração ativa.</b> Os indicadores abaixo são calculados em tempo real a partir do "
                   "banco de dados, que contém registros <b>fictícios</b> identificados com o selo "
                   + ui.demo_badge(True) + ". Gerencie-os em <i>Configurações</i>.", "demo")

    analyzed_pct = f"{k.publications_analyzed / k.publications_total:.0%} do total" if k.publications_total else "—"
    ui.kpi_grid([
        dict(label="Clientes monitorados", value=k.clients_active, hint=f"{k.clients_total} cadastrados",
             icon="users"),
        dict(label="Publicações cadastradas", value=k.publications_total, hint="em todas as fontes", icon="file",
             tone="blue"),
        dict(label="Publicações analisadas", value=k.publications_analyzed, hint=analyzed_pct, icon="check",
             tone="green"),
        dict(label="Correspondências", value=k.matches_total, hint="publicação × cliente", icon="link", tone="blue"),
        dict(label="Alertas de alta relevância", value=k.high_alerts, hint=f"{k.high_alerts_pending} aguardando análise",
             icon="alert", tone="red"),
        dict(label="Possíveis prazos pendentes", value=k.deadlines_open,
             hint=f"{k.deadlines_soon} nos próximos {config.DEADLINE_ALERT_DAYS} dias · {k.deadlines_overdue} vencido(s)",
             icon="clock", tone="orange"),
    ])

    c1, c2 = st.columns([1.35, 1])
    with c1:
        series = analytics.publications_by_period(pubs_df)
        fig = px.bar(series, x="periodo", y="publicacoes", labels={"periodo": "Semana", "publicacoes": "Publicações"})
        fig.update_traces(marker_color=ui.PALETTE["primary"], marker_line_width=0,
                          hovertemplate="Semana de %{x|%d/%m}<br>%{y} publicação(ões)<extra></extra>")
        fig.update_xaxes(tickformat="%d/%m")
        st.plotly_chart(ui.style_fig(fig, title="Publicações por período (semanal)", legend=False),
                        width="stretch", config={"displayModeBar": False})
    with c2:
        rel = analytics.distribution(matches_df, "relevance", ["ALTA", "MÉDIA", "BAIXA"])
        fig = go.Figure(go.Pie(labels=rel.get("relevance", []), values=rel.get("total", []), hole=0.62, sort=False,
                               marker=dict(colors=[ui.RELEVANCE_COLORS.get(str(r)) for r in rel.get("relevance", [])],
                                           line=dict(color="white", width=2)),
                               textinfo="value", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
        fig.add_annotation(text=f"<b>{k.matches_total}</b><br><span style='font-size:11px'>correspondências</span>",
                           showarrow=False, font=dict(size=20, color=ui.PALETTE["navy"]))
        st.plotly_chart(ui.style_fig(fig, title="Distribuição por relevância"), width="stretch",
                        config={"displayModeBar": False})

    c3, c4 = st.columns([1, 1.35])
    with c3:
        areas = analytics.distribution(pubs_df, "legal_area").sort_values("total") if not pubs_df.empty else pubs_df
        fig = px.bar(areas, x="total", y="legal_area", orientation="h", labels={"total": "Publicações", "legal_area": ""})
        fig.update_traces(marker_color=ui.PALETTE["blue"], hovertemplate="%{y}: %{x}<extra></extra>")
        st.plotly_chart(ui.style_fig(fig, title="Distribuição por área jurídica", legend=False), width="stretch",
                        config={"displayModeBar": False})
    with c4:
        evo = analytics.matches_evolution(matches_df)
        fig = px.line(evo, x="periodo", y="acumulado", color="relevance", markers=True,
                      color_discrete_map=ui.RELEVANCE_COLORS, category_orders={"relevance": ["ALTA", "MÉDIA", "BAIXA"]},
                      labels={"periodo": "Semana da publicação", "acumulado": "Acumulado", "relevance": "Relevância"})
        fig.update_traces(line=dict(width=2.5), hovertemplate="%{x|%d/%m}: %{y}<extra></extra>")
        fig.update_xaxes(tickformat="%d/%m")
        st.plotly_chart(ui.style_fig(fig, title="Evolução das correspondências identificadas (acumulado)"),
                        width="stretch", config={"displayModeBar": False})

    c5, c6, c7 = st.columns([1.1, 1, 1])
    with c5:
        items = "".join(
            f'<div class="lm-list-item"><div class="lm-item-title">{ui.esc(t)} {ui.demo_badge(demo)}</div>'
            f'<div class="lm-item-meta">{ui.fmt_date(d)} · {ui.esc(ag)} · {ui.esc(area)} '
            f'{ui.badge(rel) if rel else ui.badge("Sem correspondência", "gray")}</div></div>'
            for t, ag, d, area, demo, rel in recent_pubs
        )
        ui.card("Publicações recentes", items or "<span class='lm-item-meta'>Nenhuma publicação cadastrada.</span>")
    with c6:
        open_items = sorted(upcoming, key=lambda x: (x[1] is None, x[1]))[:6]
        items = "".join(
            f'<div class="lm-list-item"><div class="lm-item-title">{ui.esc(desc)}</div>'
            f'<div class="lm-item-meta">{ui.esc(client)} · {ui.esc(dtype)}<br>'
            f'Limite sugerido: <b>{ui.fmt_date(due)}</b> {ui.badge(urg[0])}'
            f'{"" if validated else " " + ui.badge("Não validado", "gray")}</div></div>'
            for desc, due, status, client, dtype, validated, urg in open_items
        )
        ui.card("Próximos possíveis prazos", items or "<span class='lm-item-meta'>Nenhum prazo em aberto.</span>")
    with c7:
        items = "".join(
            f'<div class="lm-timeline-item"><span class="lm-dot {ACTION_DOT.get(action, "blue")}"></span><div>'
            f'<div class="lm-item-title" style="font-weight:500">{ui.esc(desc)}</div>'
            f'<div class="lm-item-meta">{ui.fmt_date(ts, True)} · {ui.esc(ACTIONS.get(action, action))}</div></div></div>'
            for ts, action, desc, user, demo in activity
        )
        ui.card("Atividades recentes", items or "<span class='lm-item-meta'>Sem atividades registradas.</span>")
