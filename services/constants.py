"""Vocabulários controlados do domínio."""

CLIENT_TYPES = ["Pessoa jurídica", "Pessoa física", "Órgão público", "Entidade sem fins lucrativos"]
CLIENT_STATUS = ["Ativo", "Pausado", "Inativo"]

LEGAL_AREAS = [
    "Administrativo",
    "Ambiental",
    "Cível",
    "Consumidor",
    "Empresarial",
    "Licitações e Contratos",
    "Previdenciário",
    "Regulatório",
    "Trabalhista",
    "Tributário",
    "Outra",
]

PUBLICATION_SOURCES = [
    "Diário Oficial da União (DOU)",
    "Diário Oficial do Estado",
    "Diário Oficial do Município",
    "Diário de Justiça Eletrônico",
    "Portal de agência reguladora",
    "Cadastro manual",
    "Dados de demonstração",
]

DOC_TYPES = [
    "Portaria",
    "Resolução",
    "Decreto",
    "Edital",
    "Extrato de contrato",
    "Despacho",
    "Intimação",
    "Auto de infração",
    "Decisão",
    "Aviso",
    "Outro",
]

RELEVANCE_LEVELS = ["ALTA", "MÉDIA", "BAIXA"]

TRIAGE_STATUS = ["Pendente", "Em análise", "Confirmada", "Descartada", "Encaminhada ao responsável"]

DEADLINE_STATUS = ["Pendente", "Em andamento", "Concluído", "Vencido", "Cancelado"]
DEADLINE_OPEN_STATUS = ("Pendente", "Em andamento")

# Natureza da data — o sistema diferencia explicitamente cada tipo
DATE_TYPES = [
    "Prazo processual",
    "Prazo administrativo",
    "Data de vigência",
    "Data de publicação",
    "Obrigação contratual",
    "Outra data relevante",
]

DEADLINE_ORIGINS = ["Manual", "Sugestão da triagem"]
