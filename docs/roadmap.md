# Roadmap — Legal Monitor

> Itens marcados como **planejado** ou **visão** ainda **não estão implementados**.

## ✅ 1.0 — MVP (atual)
- Gestão de clientes, publicações e possíveis prazos.
- Motor de correspondência por regras transparentes e configuráveis, com simulador.
- Triagem jurídica com histórico de status.
- Dashboard com indicadores calculados do banco.
- Relatórios CSV e PDF.
- Auditoria completa.
- Base demonstrativa fictícia.
- 65 testes automatizados.

## 1.1 — Captura automática (planejado)
- Conector **INLABS** (Imprensa Nacional) para baixar diariamente as seções do DOU em XML.
- Agendamento da captura e da triagem (APScheduler ou cron).
- Notificações por e-mail para alertas de ALTA relevância e prazos próximos.
- Deduplicação por identificador oficial da matéria.

## 1.2 — Processos e calendário (planejado)
- Conector **DataJud (CNJ)** para metadados e movimentações processuais.
- Vínculo entre publicações, processos e clientes.
- Calendário de feriados nacionais, estaduais e forenses para **apoiar** (não substituir) a contagem de prazos.
- Conectores para diários estaduais e municipais prioritários.

## 1.5 — Plataforma (planejado)
- Autenticação (OIDC), perfis de acesso e trilha de auditoria por usuário.
- API REST com **FastAPI** reutilizando a camada `services/`.
- **PostgreSQL** e migrações com Alembic.
- Frontend independente (React/Next.js).
- Criptografia de dados sensíveis e política de retenção.

## 2.0 — Inteligência e SaaS (visão)
- Provedor de **IA** para resumo de publicações e sugestão de classificação, sempre com justificativa auditável e validação humana.
- Aprendizado com as decisões de triagem (confirmadas e descartadas) para recalibrar os pesos.
- SaaS multi-inquilino com planos, painéis por cliente e integrações com sistemas de gestão jurídica.
- Avaliação formal de conformidade com a LGPD e de segurança da informação.
