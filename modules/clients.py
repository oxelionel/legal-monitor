"""Módulo B — Gestão de clientes (CRUD completo)."""
from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from database.db import session_scope
from modules import ui
from services import client_service as svc
from services import constants as C
from services.monitoring import run_triage
from services.schemas import ClientIn
from services.text import format_document


def validation_message(exc: ValidationError) -> str:
    msgs = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"]) or "formulário"
        msgs.append(f"• {field}: {err['msg'].removeprefix('Value error, ')}")
    return "Corrija os campos abaixo:\n\n" + "\n".join(msgs)


def _form(prefix: str, initial: dict | None = None) -> dict | None:
    v = initial or {}
    with st.form(f"{prefix}_form", clear_on_submit=initial is None):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nome ou razão social *", v.get("name", ""))
        trade_name = c2.text_input("Nome fantasia", v.get("trade_name") or "")
        c3, c4, c5 = st.columns(3)
        client_type = c3.selectbox("Tipo de cliente *", C.CLIENT_TYPES,
                                   index=C.CLIENT_TYPES.index(v.get("client_type", C.CLIENT_TYPES[0])))
        document = c4.text_input("CPF/CNPJ (opcional)", v.get("document") or "", help="Com ou sem pontuação.")
        status = c5.selectbox("Status de monitoramento", C.CLIENT_STATUS,
                              index=C.CLIENT_STATUS.index(v.get("status", "Ativo")),
                              help="Somente clientes Ativos participam da triagem.")
        c6, c7, c8 = st.columns(3)
        email = c6.text_input("E-mail", v.get("email") or "")
        phone = c7.text_input("Telefone", v.get("phone") or "")
        responsible = c8.text_input("Responsável pelo acompanhamento", v.get("responsible") or "")
        areas = ["—"] + C.LEGAL_AREAS
        legal_area = st.selectbox("Área jurídica de interesse", areas,
                                  index=areas.index(v.get("legal_area") or "—"))
        keywords = st.text_area(
            "Palavras-chave e expressões monitoradas",
            v.get("keywords", ""),
            help="Separe por vírgula, ponto e vírgula ou quebra de linha. Termos com mais de uma palavra são tratados "
                 "como expressões (maior peso). O nome, o nome fantasia e o CPF/CNPJ já são monitorados automaticamente.",
            placeholder="ex.: licenciamento ambiental, pregão eletrônico, FUNRURAL",
        )
        notes = st.text_area("Observações", v.get("notes") or "", height=80)
        label = "Salvar alterações" if initial else "Cadastrar cliente"
        submitted = st.form_submit_button(label, type="primary")
    if not submitted:
        return None
    return dict(name=name, trade_name=trade_name, client_type=client_type, document=document, status=status,
                email=email, phone=phone, responsible=responsible,
                legal_area=None if legal_area == "—" else legal_area, keywords=keywords, notes=notes)


def _list_tab(rows: list[dict]) -> None:
    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("Buscar", placeholder="Nome, CPF/CNPJ, responsável ou palavra-chave",
                          label_visibility="collapsed")
    status = c2.multiselect("Status", C.CLIENT_STATUS, placeholder="Status", label_visibility="collapsed")
    area = c3.multiselect("Área", C.LEGAL_AREAS, placeholder="Área jurídica", label_visibility="collapsed")
    df = pd.DataFrame(rows)
    if df.empty:
        ui.empty_state("Nenhum cliente cadastrado. Utilize a aba “Cadastrar cliente”.")
        return
    if query:
        q = query.lower()
        df = df[df.apply(lambda r: q in " ".join(str(x) for x in r.values).lower(), axis=1)]
    if status:
        df = df[df["Status"].isin(status)]
    if area:
        df = df[df["Área de interesse"].isin(area)]
    st.caption(f"{len(df)} cliente(s) exibido(s)")
    st.dataframe(
        df.drop(columns=["id"]), width="stretch", hide_index=True,
        column_config={
            "Correspondências": st.column_config.NumberColumn(format="%d"),
            "Alta relevância": st.column_config.NumberColumn(format="%d"),
            "Palavras-chave": st.column_config.TextColumn(width="large"),
        },
    )


def render() -> None:
    ui.page_header("Gestão de clientes", "Cadastre os clientes e os termos que devem ser monitorados nas publicações.",
                   "Operação")

    with session_scope() as s:
        clients = svc.list_clients(s)
        rows = [{
            "id": c.id, "Nome / razão social": c.name, "Nome fantasia": c.trade_name or "",
            "CPF/CNPJ": format_document(c.document) if c.document else "", "Tipo": c.client_type,
            "Área de interesse": c.legal_area or "", "Responsável": c.responsible or "",
            "Palavras-chave": ", ".join(k.term for k in c.keywords), "Status": c.status,
            "Correspondências": len(c.matches), "Alta relevância": sum(m.relevance == "ALTA" for m in c.matches),
            "Demonstração": "Sim" if c.is_demo else "",
        } for c in clients]
        options = {c.id: f"{c.name}{' (DEMO)' if c.is_demo else ''}" for c in clients}

    active = sum(r["Status"] == "Ativo" for r in rows)
    ui.kpi_grid([
        dict(label="Clientes cadastrados", value=len(rows), hint=f"{active} com monitoramento ativo", icon="users"),
        dict(label="Termos monitorados", value=sum(len(r["Palavras-chave"].split(", ")) for r in rows if r["Palavras-chave"]),
             hint="além de nome e documento", icon="link", tone="blue"),
        dict(label="Clientes com alerta alto", value=sum(r["Alta relevância"] > 0 for r in rows),
             hint="possuem correspondência ALTA", icon="alert", tone="red"),
    ])

    tab_list, tab_new, tab_edit = st.tabs(["Clientes cadastrados", "Cadastrar cliente", "Editar ou excluir"])
    with tab_list:
        _list_tab(rows)

    with tab_new:
        data = _form("new")
        if data:
            try:
                payload = ClientIn(**data)
                with session_scope() as s:
                    client = svc.create_client(s, payload)
                    summary = run_triage(s, log_run=False) if payload.status == "Ativo" else None
                msg = f"Cliente “{payload.name}” cadastrado."
                if summary:
                    msg += f" Triagem atualizada: {summary.created} nova(s) correspondência(s)."
                ui.notify(msg)
                st.rerun()
            except ValidationError as exc:
                st.error(validation_message(exc))
            except svc.DuplicateClientError as exc:
                st.error(str(exc))

    with tab_edit:
        if not options:
            ui.empty_state("Nenhum cliente para editar.")
            return
        client_id = st.selectbox("Selecione o cliente", list(options), format_func=options.get)
        with session_scope() as s:
            client = svc.get_client(s, client_id)
            initial = svc.to_form(client) if client else None
            is_demo = client.is_demo if client else False
        if initial is None:
            st.warning("Cliente não encontrado.")
            return
        if is_demo:
            ui.callout("Este é um cliente <b>fictício de demonstração</b>.", "demo")
        data = _form(f"edit_{client_id}", initial)
        if data:
            try:
                payload = ClientIn(**data, is_demo=is_demo)
                with session_scope() as s:
                    svc.update_client(s, client_id, payload)
                    run_triage(s, log_run=False)
                ui.notify("Cliente atualizado e triagem recalculada.")
                st.rerun()
            except ValidationError as exc:
                st.error(validation_message(exc))
            except (svc.DuplicateClientError, LookupError) as exc:
                st.error(str(exc))

        with st.expander("Excluir cliente", icon=":material/delete:"):
            st.write("A exclusão remove o cliente, suas palavras-chave e as correspondências vinculadas. "
                     "O registro permanece no histórico de auditoria.")
            confirm = st.checkbox("Confirmo a exclusão definitiva deste cliente", key=f"del_confirm_{client_id}")
            if st.button("Excluir cliente", type="primary", disabled=not confirm, key=f"del_{client_id}"):
                with session_scope() as s:
                    svc.delete_client(s, client_id)
                ui.notify("Cliente excluído.")
                st.rerun()
