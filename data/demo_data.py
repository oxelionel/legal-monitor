"""Base de demonstração do Legal Monitor.

TODOS os registros abaixo são FICTÍCIOS e criados exclusivamente para
apresentação do produto. Nomes, órgãos, números e textos não correspondem a
pessoas, empresas ou publicações oficiais reais. Cada registro é gravado com
``is_demo = True`` e exibido com o selo "DEMO" na interface.

O único CNPJ utilizado (11.222.333/0001-81) é um número amplamente usado como
exemplo em documentação técnica.

As datas são relativas à data de carga, para que o painel sempre apresente um
cenário atual.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import AuditLog, Client, ClientKeyword, Deadline, Match, Publication
from services import audit
from services.client_service import create_client
from services.deadline_service import create_deadline, refresh_overdue
from services.monitoring import run_triage, update_match_status
from services.publication_service import create_publication
from services.schemas import ClientIn, DeadlineIn, PublicationIn

DEMO_USER = "Sistema (demonstração)"
DEMO_SOURCE = "Dados de demonstração"
NOTE = "[DEMONSTRAÇÃO] Registro fictício criado para apresentação do Legal Monitor."

CLIENTS = [
    dict(name="Construtora Valeverde Horizonte Ltda", trade_name="Horizonte Obras", document="11.222.333/0001-81",
         client_type="Pessoa jurídica", email="juridico@valeverde-demo.example", phone="(11) 4000-0001",
         responsible="Dra. Ana Ribeiro (fictícia)", legal_area="Licitações e Contratos",
         keywords=["pavimentação urbana", "Pregão Eletrônico", "drenagem pluvial"]),
    dict(name="Lumenara Energia Renovável S.A.", trade_name="Lumenara", client_type="Pessoa jurídica",
         email="regulatorio@lumenara-demo.example", phone="(31) 4000-0002", responsible="Dr. Bruno Costa (fictício)",
         legal_area="Regulatório", keywords=["geração distribuída", "licenciamento ambiental", "fotovoltaica"]),
    dict(name="Farmabrisa Distribuidora de Medicamentos Ltda", trade_name="Farmabrisa", client_type="Pessoa jurídica",
         email="compliance@farmabrisa-demo.example", phone="(41) 4000-0003", responsible="Dra. Carla Mendes (fictícia)",
         legal_area="Consumidor", keywords=["vigilância sanitária", "medicamentos", "boas práticas de distribuição"]),
    dict(name="Transportes Rotaluz Ltda", trade_name="Rotaluz Logística", client_type="Pessoa jurídica",
         email="contencioso@rotaluz-demo.example", phone="(51) 4000-0004", responsible="Dr. Diego Alves (fictício)",
         legal_area="Trabalhista", keywords=["transporte rodoviário de cargas", "jornada de motoristas", "ICMS"]),
    dict(name="Cooperativa Agrícola Serra Clara", trade_name="Coop Serra Clara", client_type="Entidade sem fins lucrativos",
         email="diretoria@serraclara-demo.example", phone="(62) 4000-0005", responsible="Dra. Elisa Prado (fictícia)",
         legal_area="Tributário", keywords=["crédito rural", "FUNRURAL", "armazenagem de grãos"]),
    dict(name="Helena Demonstração Tavares", client_type="Pessoa física", email="helena.tavares@demo.example",
         phone="(21) 94000-0006", responsible="Dr. Bruno Costa (fictício)", legal_area="Previdenciário",
         keywords=["aposentadoria especial"]),
]

# (dias atrás, dados da publicação)
PUBLICATIONS = [
    (2, dict(title="[DEMO] Extrato do Contrato nº DEMO-045/2026 — Obras de drenagem",
             agency="Secretaria Municipal de Obras de Vila Serena (fictícia)", number="DEMO-045/2026",
             legal_area="Licitações e Contratos", doc_type="Extrato de contrato",
             content="EXTRATO DE CONTRATO. Contratante: Município de Vila Serena (fictício). Contratada: CONSTRUTORA "
                     "VALEVERDE HORIZONTE LTDA, CNPJ 11.222.333/0001-81. Objeto: execução de serviços de drenagem "
                     "pluvial e pavimentação urbana no Bairro Jardim Aurora. Valor global: R$ 2.450.000,00. Vigência: "
                     "12 meses a contar da assinatura, ocorrida em {d-13}. A contratada deverá apresentar a garantia "
                     "contratual no prazo de 10 (dez) dias úteis.")),
    (4, dict(title="[DEMO] Auto de Infração Ambiental nº DEMO-AI-778/2026",
             agency="Instituto Estadual de Meio Ambiente de Monte Azul (fictício)", number="DEMO-AI-778/2026",
             legal_area="Ambiental", doc_type="Auto de infração",
             content="NOTIFICAÇÃO DE AUTO DE INFRAÇÃO. Fica notificada a empresa LUMENARA ENERGIA RENOVÁVEL S.A. da "
                     "lavratura do auto de infração por suposta operação de usina fotovoltaica sem a renovação do "
                     "licenciamento ambiental. A autuada poderá apresentar defesa administrativa no prazo de 20 (vinte) "
                     "dias, contados na forma da legislação estadual aplicável.")),
    (6, dict(title="[DEMO] Edital de Pregão Eletrônico nº DEMO-12/2026 — Pavimentação",
             agency="Prefeitura de Rio Claro do Sul (fictícia)", number="DEMO-12/2026",
             legal_area="Licitações e Contratos", doc_type="Edital",
             content="AVISO DE LICITAÇÃO. Pregão Eletrônico para registro de preços visando a contratação de empresa "
                     "especializada em pavimentação urbana e recapeamento asfáltico. Abertura das propostas em "
                     "{d+12}, às 9h. O edital completo está disponível no portal de compras do município.")),
    (8, dict(title="[DEMO] Resolução Normativa nº DEMO-1.050 — Geração distribuída",
             agency="Agência Reguladora de Energia de Exemplo (fictícia)", number="DEMO-1.050/2026",
             legal_area="Regulatório", doc_type="Resolução",
             content="Altera regras de faturamento aplicáveis às unidades consumidoras participantes do sistema de "
                     "geração distribuída. Esta Resolução entra em vigor em {d+46}. Os agentes terão "
                     "prazo de 60 (sessenta) dias para adequação de seus sistemas comerciais.")),
    (11, dict(title="[DEMO] Portaria nº DEMO-310 — Rastreabilidade de medicamentos",
              agency="Departamento de Vigilância em Saúde de Exemplo (fictício)", number="DEMO-310/2026",
              legal_area="Regulatório", doc_type="Portaria",
              content="Estabelece procedimentos de rastreabilidade de medicamentos na cadeia de distribuição, com "
                      "exigências complementares às boas práticas de distribuição e armazenagem.")),
    (13, dict(title="[DEMO] Despacho — Processo sancionador de distribuidora",
              agency="Departamento de Vigilância em Saúde de Exemplo (fictício)", number="DEMO-DESP-88/2026",
              legal_area="Consumidor", doc_type="Despacho",
              content="Processo administrativo sancionador em face de FARMABRIZA DISTRIBUIDORA DE MEDICAMENTOS, "
                      "instaurado pela vigilância sanitária após inspeção de rotina. Fica a interessada notificada "
                      "para apresentar manifestação no prazo de 15 (quinze) dias.")),
    (15, dict(title="[DEMO] Intimação — Reclamação Trabalhista nº 0000000-00.2026.5.99.0001",
              agency="Vara do Trabalho de Exemplo (fictícia)", number="0000000-00.2026.5.99.0001",
              legal_area="Trabalhista", doc_type="Intimação",
              content="Reclamante: J. S. (fictício). Reclamada: TRANSPORTES ROTALUZ LTDA. Fica a reclamada intimada "
                      "para apresentar contestação nos autos, observado o prazo legal, sobre alegações relativas à "
                      "jornada de motoristas no transporte rodoviário de cargas. Audiência designada para {d+23}.")),
    (18, dict(title="[DEMO] Decreto nº DEMO-9.901 — Linhas de crédito rural",
              agency="Governo do Estado de Exemplo (fictício)", number="DEMO-9.901/2026",
              legal_area="Tributário", doc_type="Decreto",
              content="Dispõe sobre linhas especiais de crédito rural para cooperativas. Habilita a Cooperativa "
                      "Agrícola Serra Clara e demais cooperativas cadastradas a apresentarem proposta de adesão até "
                      "{d+29}. O benefício abrange projetos de armazenagem de grãos.")),
    (21, dict(title="[DEMO] Portaria nº DEMO-77 — ICMS no transporte",
              agency="Secretaria da Fazenda de Exemplo (fictícia)", number="DEMO-77/2026",
              legal_area="Tributário", doc_type="Portaria",
              content="Disciplina a emissão de documentos fiscais e o recolhimento do ICMS nas prestações de serviço "
                      "de transporte rodoviário de cargas intermunicipal.")),
    (25, dict(title="[DEMO] Intimação — Processo previdenciário nº 5000000-00.2026.4.99.0002",
              agency="Juizado Especial Federal de Exemplo (fictício)", number="5000000-00.2026.4.99.0002",
              legal_area="Previdenciário", doc_type="Intimação",
              content="Autora: HELENA DEMONSTRAÇÃO TAVARES. Assunto: aposentadoria especial. Intimem-se as partes "
                      "para manifestação sobre o laudo pericial no prazo de 5 (cinco) dias úteis.")),
    (28, dict(title="[DEMO] Aviso — Expediente em dia de ponto facultativo",
              agency="Tribunal de Exemplo (fictício)", number="DEMO-AV-02/2026", legal_area="Administrativo",
              doc_type="Aviso",
              content="Comunica que não haverá expediente presencial nas unidades administrativas em razão de ponto "
                      "facultativo. Os sistemas eletrônicos permanecerão disponíveis.")),
    (33, dict(title="[DEMO] Licença de Operação — Usina solar de exemplo",
              agency="Instituto Estadual de Meio Ambiente de Monte Azul (fictício)", number="DEMO-LO-140/2026",
              legal_area="Ambiental", doc_type="Despacho",
              content="Concede licença de operação a empreendimento de geração de energia solar, condicionada ao "
                      "licenciamento ambiental das linhas de transmissão associadas.")),
    (38, dict(title="[DEMO] Resolução nº DEMO-21 — Jornada de motoristas profissionais",
              agency="Conselho de Trânsito de Exemplo (fictício)", number="DEMO-21/2026", legal_area="Trabalhista",
              doc_type="Resolução",
              content="Regulamenta o controle eletrônico da jornada de motoristas profissionais no transporte "
                      "rodoviário de cargas. Esta Resolução entra em vigor em {d+77}.")),
    (45, dict(title="[DEMO] Edital de Concurso Público nº DEMO-01/2026",
              agency="Câmara Municipal de Vila Serena (fictícia)", number="DEMO-CP-01/2026", legal_area="Administrativo",
              doc_type="Edital",
              content="Torna pública a abertura de inscrições para concurso público destinado ao provimento de cargos "
                      "de analista legislativo.")),
    (52, dict(title="[DEMO] Aviso de Licitação — Horizonte Obras convocada",
              agency="Prefeitura de Rio Claro do Sul (fictícia)", number="DEMO-CONV-07/2026",
              legal_area="Licitações e Contratos", doc_type="Aviso",
              content="Convoca a licitante HORIZONTE OBRAS, primeira colocada, para apresentação dos documentos de "
                      "habilitação no prazo de 2 (dois) dias úteis.")),
    (60, dict(title="[DEMO] Instrução Normativa nº DEMO-5 — FUNRURAL",
              agency="Receita de Exemplo (fictícia)", number="DEMO-IN-5/2026", legal_area="Tributário",
              doc_type="Resolução",
              content="Esclarece procedimentos de declaração da contribuição ao FUNRURAL por cooperativas agrícolas e "
                      "produtores rurais pessoas físicas.")),
    (9, dict(title="[DEMO] Chamada Pública nº DEMO-03/2026 — Eficiência energética",
             agency="Secretaria de Desenvolvimento de Exemplo (fictícia)", number="DEMO-CH-03/2026",
             legal_area="Administrativo", doc_type="Edital",
             content="Torna pública chamada para projetos de eficiência energética em prédios públicos, admitindo "
                     "soluções de iluminação LED e sistemas de energia fotovoltaica de pequeno porte.")),
    (35, dict(title="[DEMO] Aviso de Consulta Pública — Logística hospitalar",
              agency="Secretaria de Saúde de Exemplo (fictícia)", number="DEMO-CP-14/2026",
              legal_area="Administrativo", doc_type="Aviso",
              content="Abre consulta pública sobre a reorganização da logística hospitalar, incluindo a guarda de "
                      "insumos e medicamentos nas unidades de pronto atendimento.")),
    (67, dict(title="[DEMO] Portaria nº DEMO-402 — Inspeção de distribuidoras",
              agency="Departamento de Vigilância em Saúde de Exemplo (fictício)", number="DEMO-402/2026",
              legal_area="Consumidor", doc_type="Portaria",
              content="Aprova o cronograma anual de inspeções da vigilância sanitária em distribuidoras de "
                      "medicamentos da região metropolitana.")),
]


def remove_demo_data(session: Session) -> None:
    demo_pub_ids = select(Publication.id).where(Publication.is_demo)
    demo_client_ids = select(Client.id).where(Client.is_demo)
    session.execute(delete(Deadline).where(Deadline.is_demo))
    session.execute(delete(Match).where(Match.publication_id.in_(demo_pub_ids) | Match.client_id.in_(demo_client_ids)))
    session.execute(delete(Publication).where(Publication.is_demo))
    session.execute(delete(ClientKeyword).where(ClientKeyword.client_id.in_(demo_client_ids)))
    session.execute(delete(Client).where(Client.is_demo))
    session.execute(delete(AuditLog).where(AuditLog.is_demo))
    session.flush()
    # Exclusões em lote não atualizam objetos já carregados: descarta o mapa de identidade.
    session.expunge_all()


def has_demo_data(session: Session) -> bool:
    return session.scalar(select(Client.id).where(Client.is_demo).limit(1)) is not None


def load_demo_data(session: Session, today: date | None = None) -> dict:
    """Carrega (ou restaura) a base de demonstração. Remove a anterior, se houver."""
    today = today or date.today()
    remove_demo_data(session)

    clients = {}
    for data in CLIENTS:
        doc = data.get("document")
        if doc and session.scalar(select(Client.id).where(Client.document == "".join(ch for ch in doc if ch.isdigit()))):
            data = {**data, "document": None}  # documento já usado por um cliente real: não conflita
        c = create_client(session, ClientIn(**data, notes=NOTE, is_demo=True), user=DEMO_USER)
        clients[c.name] = c

    def relative(text: str) -> str:
        return re.sub(r"\{d([+-]\d+)\}", lambda m: (today + timedelta(days=int(m.group(1)))).strftime("%d/%m/%Y"), text)

    pubs = []
    for days_ago, data in PUBLICATIONS:
        data = {**data, "content": relative(data["content"])}
        pubs.append(create_publication(
            session,
            PublicationIn(**data, source=DEMO_SOURCE, publication_date=today - timedelta(days=days_ago), is_demo=True),
            user=DEMO_USER,
        ))

    summary = run_triage(session, [p.id for p in pubs], user=DEMO_USER, is_demo=True)

    # Exemplos de análise humana
    by_title = {p.title: p for p in pubs}

    def match_of(title_prefix: str, client_name: str) -> Match | None:
        pub = next(p for t, p in by_title.items() if t.startswith(title_prefix))
        return session.scalar(select(Match).where(Match.publication_id == pub.id,
                                                  Match.client_id == clients[client_name].id))

    reviews = [
        ("[DEMO] Extrato do Contrato", "Construtora Valeverde Horizonte Ltda", "Confirmada",
         "Contrato assinado; acompanhar garantia contratual."),
        ("[DEMO] Auto de Infração", "Lumenara Energia Renovável S.A.", "Encaminhada ao responsável",
         "Encaminhado ao Dr. Bruno para elaboração de defesa."),
        ("[DEMO] Intimação — Reclamação", "Transportes Rotaluz Ltda", "Em análise", None),
        ("[DEMO] Portaria nº DEMO-402", "Farmabrisa Distribuidora de Medicamentos Ltda", "Descartada",
         "Cronograma genérico; sem impacto direto."),
        ("[DEMO] Aviso de Licitação", "Construtora Valeverde Horizonte Ltda", "Confirmada", "Documentos entregues."),
    ]
    for prefix, client_name, status, notes in reviews:
        m = match_of(prefix, client_name)
        if m:
            update_match_status(session, m.id, status, notes, user=DEMO_USER)

    def pub_id(prefix: str) -> int:
        return next(p.id for t, p in by_title.items() if t.startswith(prefix))

    deadlines = [
        dict(description="Apresentar garantia contratual (contrato DEMO-045/2026)", publication_id=pub_id("[DEMO] Extrato"),
             client_id=clients["Construtora Valeverde Horizonte Ltda"].id, date_type="Obrigação contratual",
             reference_date=today - timedelta(days=13), due_date=today + timedelta(days=1),
             responsible="Dra. Ana Ribeiro (fictícia)", status="Em andamento", validated=True,
             notes="Data limite conferida pela responsável (10 dias úteis da assinatura)."),
        dict(description="Defesa administrativa — Auto de Infração DEMO-AI-778", publication_id=pub_id("[DEMO] Auto de"),
             client_id=clients["Lumenara Energia Renovável S.A."].id, date_type="Prazo administrativo",
             reference_date=today - timedelta(days=4), due_date=today + timedelta(days=5),
             responsible="Dr. Bruno Costa (fictício)", status="Pendente", origin="Sugestão da triagem",
             notes="Sugestão: 20 dias mencionados no auto. Confirmar data de ciência e regra de contagem estadual."),
        dict(description="Contestação — Reclamação Trabalhista (verificar audiência)", publication_id=pub_id("[DEMO] Intimação — Recl"),
             client_id=clients["Transportes Rotaluz Ltda"].id, date_type="Prazo processual",
             reference_date=today + timedelta(days=23), due_date=today + timedelta(days=23),
             responsible="Dr. Diego Alves (fictício)", status="Pendente", origin="Sugestão da triagem",
             notes="Data da audiência mencionada no texto. Prazo processual a ser confirmado pelo advogado."),
        dict(description="Proposta de adesão — crédito rural", publication_id=pub_id("[DEMO] Decreto"),
             client_id=clients["Cooperativa Agrícola Serra Clara"].id, date_type="Prazo administrativo",
             reference_date=today - timedelta(days=18), due_date=today + timedelta(days=29),
             responsible="Dra. Elisa Prado (fictícia)", status="Pendente", validated=True),
        dict(description="Adequação de sistemas — Resolução de geração distribuída", publication_id=pub_id("[DEMO] Resolução Normativa"),
             client_id=clients["Lumenara Energia Renovável S.A."].id, date_type="Data de vigência",
             reference_date=today - timedelta(days=8), due_date=None, responsible="Dr. Bruno Costa (fictício)",
             status="Pendente", origin="Sugestão da triagem",
             notes="Vigência da norma não se confunde com prazo de adequação; definir data após análise."),
        dict(description="Manifestação sobre laudo pericial", publication_id=pub_id("[DEMO] Intimação — Processo prev"),
             client_id=clients["Helena Demonstração Tavares"].id, date_type="Prazo processual",
             reference_date=today - timedelta(days=24), due_date=today - timedelta(days=16),
             responsible="Dr. Bruno Costa (fictício)", status="Concluído", validated=True,
             notes="Manifestação protocolada."),
        dict(description="Entrega de documentos de habilitação", publication_id=pub_id("[DEMO] Aviso de Licitação"),
             client_id=clients["Construtora Valeverde Horizonte Ltda"].id, date_type="Prazo administrativo",
             reference_date=today - timedelta(days=52), due_date=today - timedelta(days=3),
             responsible="Dra. Ana Ribeiro (fictícia)", status="Pendente", validated=False,
             notes="Exemplo de prazo não concluído que passa a constar como vencido."),
    ]
    for d in deadlines:
        create_deadline(session, DeadlineIn(**d, is_demo=True), user=DEMO_USER)
    refresh_overdue(session, today)

    audit.log(session, "SISTEMA", "sistema", "Base de demonstração carregada (todos os registros são fictícios).",
              details={"clientes": len(clients), "publicacoes": len(pubs), "correspondencias": summary.total_matches},
              user=DEMO_USER, is_demo=True)
    session.flush()
    return {"clients": len(clients), "publications": len(pubs), "matches": summary.total_matches,
            "deadlines": len(deadlines)}
