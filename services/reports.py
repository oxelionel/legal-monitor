"""Relatórios tabulares com filtros e exportação CSV/PDF."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import config
from database.models import AuditLog, Client, Deadline, Match, Publication
from services.deadline_service import urgency
from services.text import format_document

REPORT_TYPES = {
    "publicacoes": "Relatório de publicações",
    "clientes": "Relatório de clientes",
    "correspondencias": "Relatório de correspondências",
    "alertas": "Relatório de alertas (alta relevância)",
    "prazos": "Relatório de possíveis prazos",
}


@dataclass
class ReportFilters:
    start: date | None = None
    end: date | None = None
    client_ids: list[int] = field(default_factory=list)
    relevance: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = []
        if self.start or self.end:
            s = self.start.strftime("%d/%m/%Y") if self.start else "início"
            e = self.end.strftime("%d/%m/%Y") if self.end else "hoje"
            parts.append(f"Período: {s} a {e}")
        if self.client_ids:
            parts.append(f"Clientes selecionados: {len(self.client_ids)}")
        if self.relevance:
            parts.append(f"Relevância: {', '.join(self.relevance)}")
        if self.status:
            parts.append(f"Status: {', '.join(self.status)}")
        return " | ".join(parts) or "Sem filtros"


def _in_period(d: date | None, f: ReportFilters) -> bool:
    if d is None:
        return not (f.start or f.end)
    return (not f.start or d >= f.start) and (not f.end or d <= f.end)


def _yes(v: bool) -> str:
    return "Sim" if v else "Não"


def publications_report(session: Session, f: ReportFilters) -> pd.DataFrame:
    pubs = session.scalars(select(Publication).options(selectinload(Publication.matches))
                           .order_by(Publication.publication_date.desc())).all()
    rows = []
    for p in pubs:
        if not _in_period(p.publication_date, f):
            continue
        matches = [m for m in p.matches if (not f.client_ids or m.client_id in f.client_ids)
                   and (not f.relevance or m.relevance in f.relevance)]
        if (f.client_ids or f.relevance) and not matches:
            continue
        rows.append({
            "ID": p.id, "Data de publicação": p.publication_date, "Título": p.title, "Órgão": p.agency,
            "Fonte": p.source, "Número": p.number or "", "Tipo": p.doc_type, "Área jurídica": p.legal_area,
            "Correspondências": len(matches),
            "Maior relevância": next((r for r in ("ALTA", "MÉDIA", "BAIXA") if any(m.relevance == r for m in matches)), "—"),
            "Triada": _yes(p.last_triaged_at is not None), "URL": p.url or "", "Demonstração": _yes(p.is_demo),
        })
    return pd.DataFrame(rows)


def clients_report(session: Session, f: ReportFilters) -> pd.DataFrame:
    clients = session.scalars(select(Client).options(selectinload(Client.keywords), selectinload(Client.matches))
                              .order_by(Client.name)).all()
    rows = []
    for c in clients:
        if f.client_ids and c.id not in f.client_ids:
            continue
        if f.status and c.status not in f.status:
            continue
        matches = [m for m in c.matches if not f.relevance or m.relevance in f.relevance]
        rows.append({
            "ID": c.id, "Nome / razão social": c.name, "Nome fantasia": c.trade_name or "",
            "CPF/CNPJ": format_document(c.document) if c.document else "", "Tipo": c.client_type,
            "Responsável": c.responsible or "", "Área de interesse": c.legal_area or "",
            "Palavras-chave": ", ".join(k.term for k in c.keywords), "Status": c.status,
            "Correspondências": len(matches), "Alta relevância": sum(m.relevance == "ALTA" for m in c.matches),
            "E-mail": c.email or "", "Telefone": c.phone or "", "Demonstração": _yes(c.is_demo),
        })
    return pd.DataFrame(rows)


def matches_report(session: Session, f: ReportFilters, only_high: bool = False) -> pd.DataFrame:
    stmt = select(Match).options(selectinload(Match.publication), selectinload(Match.client))
    rows = []
    for m in session.scalars(stmt):
        p = m.publication
        if not _in_period(p.publication_date, f):
            continue
        if f.client_ids and m.client_id not in f.client_ids:
            continue
        if only_high and m.relevance != "ALTA":
            continue
        if f.relevance and m.relevance not in f.relevance:
            continue
        if f.status and m.status not in f.status:
            continue
        rows.append({
            "ID": m.id, "Data de publicação": p.publication_date, "Publicação": p.title, "Cliente": m.client.name,
            "Relevância": m.relevance, "Pontuação": round(m.score), "Status da análise": m.status,
            "Termos encontrados": ", ".join(dict.fromkeys(t["term"] for t in m.matched_terms)),
            "Justificativa": m.justification.replace("\n", " "), "Área jurídica": p.legal_area,
            "Responsável": m.client.responsible or "", "Demonstração": _yes(p.is_demo),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Data de publicação", "Pontuação"], ascending=[False, False])
    return df


def deadlines_report(session: Session, f: ReportFilters) -> pd.DataFrame:
    stmt = select(Deadline).options(selectinload(Deadline.client), selectinload(Deadline.publication))
    rows = []
    for d in session.scalars(stmt):
        if not _in_period(d.due_date or d.reference_date, f):
            continue
        if f.client_ids and d.client_id not in f.client_ids:
            continue
        if f.status and d.status not in f.status:
            continue
        label, days = urgency(d)
        rows.append({
            "ID": d.id, "Descrição": d.description, "Tipo de data": d.date_type, "Cliente": d.client.name if d.client else "",
            "Publicação de origem": d.publication.title if d.publication else "",
            "Data de referência": d.reference_date, "Data limite sugerida": d.due_date, "Dias restantes": days,
            "Situação": label, "Status": d.status, "Responsável": d.responsible or "",
            "Validado por profissional": _yes(d.validated), "Origem": d.origin, "Observações": d.notes or "",
            "Demonstração": _yes(d.is_demo),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Data limite sugerida", na_position="last")
    return df


def audit_report(session: Session, f: ReportFilters) -> pd.DataFrame:
    rows = []
    for a in session.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())):
        if not _in_period(a.timestamp.date(), f):
            continue
        rows.append({"Data/hora": a.timestamp, "Ação": a.action, "Entidade": a.entity, "ID": a.entity_id,
                     "Descrição": a.description, "Usuário": a.user, "Demonstração": _yes(a.is_demo)})
    return pd.DataFrame(rows)


def build_report(session: Session, kind: str, f: ReportFilters) -> pd.DataFrame:
    if kind == "publicacoes":
        return publications_report(session, f)
    if kind == "clientes":
        return clients_report(session, f)
    if kind == "correspondencias":
        return matches_report(session, f)
    if kind == "alertas":
        return matches_report(session, f, only_high=True)
    if kind == "prazos":
        return deadlines_report(session, f)
    raise ValueError(f"Tipo de relatório desconhecido: {kind}")


# --------------------------------------------------------------------------- exportação

def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return str(v)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV com separador ';' e BOM UTF-8 — abre corretamente no Excel em português."""
    out = df.copy()
    for col in out.columns:
        if out[col].map(lambda x: isinstance(x, (date, datetime))).any():
            out[col] = out[col].map(_fmt)
    return out.to_csv(index=False, sep=";").encode("utf-8-sig")


_PDF_REPLACEMENTS = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "→": "->", "•": "-",
                     "≤": "<=", "≥": ">="}


def _latin1(text: str) -> str:
    for k, v in _PDF_REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def to_pdf_bytes(df: pd.DataFrame, title: str, filters: ReportFilters, columns: list[str] | None = None) -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    cols = [c for c in (columns or list(df.columns)) if c in df.columns]
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_fill_color(11, 37, 69)
    pdf.rect(0, 0, 297, 22, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_xy(10, 5)
    pdf.cell(0, 7, _latin1(f"{config.APP_NAME} - {title}"))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(10, 13)
    pdf.cell(0, 5, _latin1(f"{config.APP_SLOGAN}   |   Gerado em {datetime.now():%d/%m/%Y %H:%M}"))
    pdf.set_text_color(14, 26, 43)
    pdf.set_xy(10, 26)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4, _latin1(f"Filtros: {filters.describe()}   |   Registros: {len(df)}"))
    pdf.ln(2)
    if df.empty:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "Nenhum registro encontrado para os filtros selecionados.")
    else:
        pdf.set_font("Helvetica", "", 7)
        heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(18, 55, 107))
        with pdf.table(headings_style=heading, line_height=4, cell_fill_color=(242, 245, 250),
                       cell_fill_mode="ROWS", text_align="LEFT") as table:
            table.row([_latin1(c) for c in cols])
            for _, r in df[cols].iterrows():
                table.row([_latin1(_fmt(r[c]))[:300] for c in cols])
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(0, 3.5, _latin1(
        "Aviso: possíveis prazos e classificações são sugestões automatizadas e devem ser validados por "
        "profissional responsável, considerando a legislação e as regras aplicáveis. Registros marcados como "
        "demonstração são fictícios."))
    return bytes(pdf.output())


PDF_COLUMNS = {
    "publicacoes": ["Data de publicação", "Título", "Órgão", "Tipo", "Área jurídica", "Correspondências", "Maior relevância"],
    "clientes": ["Nome / razão social", "CPF/CNPJ", "Tipo", "Responsável", "Área de interesse", "Status",
                 "Correspondências", "Alta relevância"],
    "correspondencias": ["Data de publicação", "Publicação", "Cliente", "Relevância", "Pontuação", "Status da análise",
                         "Termos encontrados"],
    "alertas": ["Data de publicação", "Publicação", "Cliente", "Pontuação", "Status da análise", "Termos encontrados",
                "Responsável"],
    "prazos": ["Descrição", "Tipo de data", "Cliente", "Data limite sugerida", "Situação", "Status", "Responsável",
               "Validado por profissional"],
}
