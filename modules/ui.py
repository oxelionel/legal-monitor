"""Componentes visuais compartilhados por todas as páginas."""
from __future__ import annotations

import html
import re
from datetime import date, datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

import config

ASSETS = Path(__file__).resolve().parent.parent / "assets"

PALETTE = {
    "navy": "#0B2545", "primary": "#12376B", "blue": "#2F6FC4", "sky": "#7FA7DC", "pale": "#C9D8EE",
    "red": "#C9372C", "orange": "#D9822B", "green": "#1E7F55", "gray": "#8A99AE",
}
RELEVANCE_COLORS = {"ALTA": PALETTE["red"], "MÉDIA": PALETTE["orange"], "BAIXA": PALETTE["blue"]}
SEQUENCE = [PALETTE["primary"], PALETTE["blue"], PALETTE["sky"], "#4F5D75", "#A3B8D6", "#2B4C7E", "#6C8EBF",
            "#9FB1C8", "#1D3557", "#C9D8EE", "#5C7AA8"]

_SVG = {
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4 12 14.01l-3-3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
}


def icon(name: str, size: int = 18) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{_SVG[name]}</svg>')


def esc(value) -> str:
    """Escapa conteúdo do usuário antes de inseri-lo em HTML (evita injeção de HTML/JS)."""
    return html.escape("" if value is None else str(value))


def inject_css() -> None:
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def sidebar_brand() -> None:
    st.sidebar.markdown(
        f'<div class="lm-brand"><div class="lm-brand-mark">{icon("scale", 22)}</div>'
        f'<div><div class="lm-brand-name">{config.APP_NAME}</div>'
        f'<div class="lm-brand-slogan">{config.APP_SLOGAN}</div></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_footer(demo: bool) -> None:
    demo_line = "<br>⚠ Base de demonstração ativa (dados fictícios)" if demo else ""
    st.sidebar.markdown(
        f'<div class="lm-sidebar-foot">MVP {config.APP_VERSION} · execução local{demo_line}</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    meta = datetime.now().strftime("%d/%m/%Y")
    st.markdown(
        f'<div class="lm-header"><div>'
        f'{f"<div class=lm-eyebrow>{esc(eyebrow)}</div>" if eyebrow else ""}'
        f'<h1 class="lm-title">{esc(title)}</h1>'
        f'{f"<div class=lm-subtitle>{esc(subtitle)}</div>" if subtitle else ""}'
        f'</div><div class="lm-header-meta">{meta}<br>{esc(config.DEFAULT_USER)}</div></div>',
        unsafe_allow_html=True,
    )


def kpi_grid(items: list[dict]) -> None:
    cards = []
    for it in items:
        cards.append(
            f'<div class="lm-kpi tone-{it.get("tone", "navy")}"><div class="lm-kpi-top">'
            f'<span class="lm-kpi-label">{esc(it["label"])}</span>'
            f'<span class="lm-kpi-icon">{icon(it.get("icon", "file"), 17)}</span></div>'
            f'<div class="lm-kpi-value">{esc(it["value"])}</div>'
            f'<div class="lm-kpi-hint">{esc(it.get("hint", ""))}</div></div>'
        )
    st.markdown(f'<div class="lm-kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


TONES = {
    "ALTA": "red", "MÉDIA": "orange", "BAIXA": "blue",
    "Pendente": "gray", "Em análise": "blue", "Confirmada": "green", "Descartada": "gray",
    "Encaminhada ao responsável": "navy", "Em andamento": "blue", "Concluído": "green", "Vencido": "red",
    "Cancelado": "gray", "Crítico": "red", "Próximo": "orange", "No prazo": "green", "Sem data": "gray",
    "Ativo": "green", "Pausado": "orange", "Inativo": "gray",
}


def badge(text: str, tone: str | None = None) -> str:
    return f'<span class="lm-badge {tone or TONES.get(text, "blue")}">{esc(text)}</span>'


def demo_badge(is_demo: bool) -> str:
    return '<span class="lm-badge demo" title="Registro fictício de demonstração">DEMO</span>' if is_demo else ""


def callout(text: str, kind: str = "info") -> None:
    st.markdown(f'<div class="lm-callout {kind}">{text}</div>', unsafe_allow_html=True)


def card(title: str, body_html: str) -> None:
    st.markdown(f'<div class="lm-card"><div class="lm-card-title">{esc(title)}</div>{body_html}</div>',
                unsafe_allow_html=True)


def kv(items: list[tuple[str, str]]) -> None:
    cells = "".join(f"<div><small>{esc(k)}</small><span>{v}</span></div>" for k, v in items)
    st.markdown(f'<div class="lm-kv">{cells}</div>', unsafe_allow_html=True)


def flash() -> None:
    """Exibe mensagens registradas antes de um st.rerun()."""
    for kind, msg in st.session_state.pop("_flash", []):
        getattr(st, kind)(msg)


def notify(msg: str, kind: str = "success") -> None:
    st.session_state.setdefault("_flash", []).append((kind, msg))


def fmt_date(d: date | datetime | None, with_time: bool = False) -> str:
    if d is None:
        return "—"
    if with_time and isinstance(d, datetime):
        return d.strftime("%d/%m/%Y %H:%M")
    return d.strftime("%d/%m/%Y")


def style_fig(fig: go.Figure, height: int = 320, title: str | None = None, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=48 if title else 16, b=10),
        title=dict(text=title, font=dict(size=15, color=PALETTE["navy"], family="Inter"), x=0.01) if title else None,
        font=dict(family="Inter, sans-serif", size=12, color="#3A4A60"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter"),
        colorway=SEQUENCE,
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E7EF")
    fig.update_yaxes(gridcolor="#EEF1F5", zeroline=False)
    return fig


def empty_state(message: str) -> None:
    st.markdown(f'<div class="lm-card" style="text-align:center;color:#5B6B82;padding:1.6rem">{esc(message)}</div>',
                unsafe_allow_html=True)


# ----------------------------------------------------------------- destaque de termos

_ACCENTS = {"a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö", "u": "uúùûü", "c": "cç", "n": "nñ"}


def _accent_insensitive(term: str) -> str:
    parts = []
    for ch in term:
        low = ch.lower()
        if low in _ACCENTS:
            parts.append(f"[{_ACCENTS[low]}{_ACCENTS[low].upper()}]")
        elif ch.isspace():
            parts.append(r"[\W_]+")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def highlight(text: str, terms: list[str]) -> str:
    """Retorna HTML seguro com os termos destacados (sem diferenciar acentos/maiúsculas)."""
    from services.text import strip_accents

    clean = [strip_accents(t).strip() for t in terms if t and len(t.strip()) >= 3]
    if not clean:
        return esc(text)
    pattern = re.compile("|".join(_accent_insensitive(t) for t in sorted(set(clean), key=len, reverse=True)),
                         re.IGNORECASE)
    out, pos = [], 0
    for m in pattern.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f"<mark>{esc(m.group(0))}</mark>")
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)
