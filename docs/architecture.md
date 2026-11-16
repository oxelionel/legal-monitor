# Arquitetura — Legal Monitor MVP 1.0

## Visão geral

A aplicação segue uma arquitetura em camadas, simples o bastante para rodar localmente com Streamlit e SQLite, mas organizada para permitir a migração para **FastAPI + PostgreSQL + frontend independente** sem reescrever as regras de negócio.

```
Interface (modules/)  →  Serviços (services/)  →  Persistência (database/)
                                   ↘
                          Integrações (integrations/) — contratos para fontes externas
```

| Camada | Responsabilidade | Depende de |
|---|---|---|
| `app.py` | Configuração da página, inicialização do banco, navegação | `modules`, `database` |
| `modules/` | Páginas Streamlit, formulários, gráficos e componentes visuais | `services`, `database.db` (sessões) |
| `services/` | Regras de negócio, validação, motor de correspondência, relatórios, auditoria | `database.models` |
| `database/` | Modelos ORM, engine, sessões transacionais e DDL de referência | SQLAlchemy |
| `integrations/` | Interfaces (`OfficialSource`, `AIProvider`) e conectores planejados | `services.schemas` |
| `data/` | Base demonstrativa fictícia | `services` |

## Decisões técnicas

| Decisão | Justificativa |
|---|---|
| **Streamlit com `st.navigation`** | Entrega rápida de uma interface multipágina com navegação lateral e ícones, sem frontend separado |
| **SQLAlchemy 2 (ORM)** | Consultas parametrizadas (evita SQL injection), portabilidade para PostgreSQL e migrações futuras (Alembic) |
| **Pydantic nos dados de entrada** | Validação única reutilizável pela UI hoje e por uma API amanhã |
| **Motor de correspondência em funções puras** | Testável sem banco, reutilizável em workers assíncronos e em processamento em lote |
| **Regras de classificação no banco (`settings`)** | Ajuste pela interface, sem novo deploy; a classificação continua transparente |
| **Restrição única `(publicação, cliente)`** | Impede correspondências duplicadas, mesmo em reprocessamentos |
| **`difflib` para correspondência aproximada** | Biblioteca padrão; evita dependências extras no MVP |
| **Auditoria como tabela de eventos** | Linha do tempo única para todas as entidades, com diferenças (`details` JSON) |
| **Flag `is_demo` em todas as entidades** | Separa dados fictícios dos reais; permite restaurar/remover a demonstração com segurança |
| **CSS próprio + tema em `.streamlit/config.toml`** | Identidade visual consistente (azul-marinho, superfícies claras, alertas em vermelho/laranja) |
| **Escape de HTML (`ui.esc`)** | Todo conteúdo do usuário inserido em HTML é escapado, prevenindo injeção de script |

## Modelo de dados

```
clients 1──* client_keywords
clients 1──* matches *──1 publications
deadlines *──0..1 clients
deadlines *──0..1 publications
audit_log (eventos de todas as entidades)
settings (regras de classificação em JSON)
```

| Tabela | Destaques |
|---|---|
| `clients` | `document` único (somente dígitos), `name_normalized` para detectar duplicidade, `status` controla a participação na triagem |
| `client_keywords` | termo original + normalizado, único por cliente |
| `publications` | metadados, conteúdo integral, `last_triaged_at` |
| `matches` | `score`, `relevance`, `matched_terms` (JSON com tipo, termo, ocorrências, pontos, similaridade e trecho), `justification`, `status`, `analyst_notes` |
| `deadlines` | `date_type` (natureza da data), `reference_date`, `due_date`, `validated`, `origin` |
| `audit_log` | `action`, `entity`, `entity_id`, `description`, `details`, `actor` |

O DDL completo está em [`database/schema.sql`](../database/schema.sql), gerado a partir de `database/models.py`.

## Fluxo de triagem

1. `services/monitoring.run_triage()` carrega as regras (`classification.get_rules`), os clientes **ativos** e as publicações do escopo.
2. Para cada par, `matching.evaluate()` normaliza o texto, coleta evidências, soma pontos e classifica.
3. As correspondências novas são inseridas e as existentes são atualizadas (pontuação, termos e justificativa). O **status definido pelo analista nunca é sobrescrito**.
4. As correspondências que deixaram de existir são removidas apenas se ainda estiverem *Pendente*.
5. Cada correspondência nova e cada execução geram eventos de auditoria.

## Segurança no MVP

- Consultas via ORM, sempre parametrizadas.
- Validação de entrada (Pydantic): CPF/CNPJ com dígitos verificadores, e-mail, URL `http(s)`, datas e vocabulários controlados.
- Escape de HTML em todo conteúdo dinâmico renderizado.
- Configuração por variáveis de ambiente; `.env` e bancos `*.db` estão no `.gitignore`.
- Erros de validação exibidos de forma amigável, sem stack traces na interface.
- **Limitações:** não há autenticação, autorização, criptografia em repouso nem trilha assinada. Não houve auditoria de conformidade com a LGPD.

## Caminho de evolução

| Hoje | Próximo passo |
|---|---|
| Streamlit chama `services/` | FastAPI expõe os mesmos `services/` e um frontend (React/Next.js) consome a API |
| SQLite | PostgreSQL (`LEGAL_MONITOR_DATABASE_URL`) + Alembic para migrações |
| Triagem disparada na interface | Worker agendado (Celery/RQ/APScheduler) consumindo conectores de `integrations/` |
| Regras determinísticas | `AIProvider` opcional para resumo e sugestão, mantendo a justificativa auditável |
| Usuário por variável de ambiente | Autenticação (OIDC), perfis e multi-inquilino |
