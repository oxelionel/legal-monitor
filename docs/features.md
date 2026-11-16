# Funcionalidades — Legal Monitor MVP 1.0

Este documento descreve o comportamento de cada módulo **conforme implementado**.

## A. Dashboard
- Indicadores calculados em tempo real a partir do banco: clientes ativos/cadastrados, publicações cadastradas e analisadas (já triadas), correspondências, alertas de alta relevância (exceto descartados) e possíveis prazos em aberto, próximos e vencidos.
- Gráficos (Plotly): publicações por semana, distribuição por relevância, por área jurídica e evolução acumulada das correspondências por nível.
- Listas: publicações recentes (com maior relevância encontrada), próximos possíveis prazos e atividades recentes.
- Aviso explícito quando há dados demonstrativos no banco.

## B. Clientes
- Campos: nome/razão social, nome fantasia, CPF/CNPJ (opcional), tipo, e-mail, telefone, responsável, área jurídica, palavras-chave, observações e status (Ativo, Pausado ou Inativo).
- Palavras-chave separadas por vírgula, ponto e vírgula ou quebra de linha; duplicatas são removidas, ignorando acentos e maiúsculas; mínimo de 3 caracteres.
- Validações: CPF/CNPJ com dígitos verificadores; pessoa física exige CPF; formato de e-mail; telefone com 8 a 13 dígitos.
- Duplicidade: mesmo CPF/CNPJ, ou mesmo nome normalizado quando não há documentos diferentes que distingam os clientes.
- Ao cadastrar ou editar, a triagem é recalculada automaticamente.

## C. Publicações
- Campos: título, órgão, fonte, número, data (não pode ser futura), área jurídica, tipo de documento, conteúdo integral e URL (`http/https`).
- Duplicidade: mesma fonte e data com o mesmo título ou número.
- Pesquisa sem diferenciar acentos e maiúsculas em título, órgão, número e conteúdo, com filtros por período, área, fonte e tipo.
- Visualização do texto integral com destaque dos termos, das correspondências e do histórico da publicação.
- Aba **Fontes oficiais** lista os conectores planejados. Nenhuma consulta externa é realizada.

## D. Motor de monitoramento e correspondência

### Etapas
1. **Normalização:** minúsculas, remoção de acentos e pontuação.
2. **Documento:** sequências numéricas formatadas no texto são comparadas, apenas pelos dígitos, com o CPF/CNPJ do cliente.
3. **Nome:** razão social completa ou sem sufixo societário (Ltda, S.A., EIRELI, ME, EPP...).
4. **Nome fantasia.**
5. **Expressões** (2 ou mais palavras) e **palavras-chave** (1 palavra), sempre respeitando limites de palavra (`drenagem` não casa com `subdrenagem`).
6. **Correspondência aproximada:** para nomes e expressões não encontrados exatamente (e palavras com 8 ou mais letras), calcula a similaridade com janelas de mesmo tamanho do texto. Aceita a partir de 0,86 por padrão.
7. **Contexto:** área jurídica igual à do cliente soma pontos apenas como complemento.

### Regras padrão (configuráveis)

| Parâmetro | Padrão |
|---|---|
| Peso CPF/CNPJ | 60 |
| Peso nome / razão social | 50 |
| Peso nome fantasia | 40 |
| Peso expressão | 30 |
| Peso aproximada | 20 × similaridade |
| Peso palavra-chave | 15 |
| Peso área coincidente | 10 |
| Bônus por repetição | +2 por ocorrência extra, até +10 por termo |
| Limites | ALTA ≥ 50 · MÉDIA ≥ 25 · BAIXA ≥ 10 |
| Evidências fortes (ALTA direta) | CPF/CNPJ, nome |
| Área isolada gera alerta | Não |
| Pontuação máxima | 100 |

### Garantias
- Cada correspondência guarda os termos, o tipo de evidência, as ocorrências, os pontos, a similaridade e um trecho do texto.
- A justificativa é gerada em linguagem natural a partir das evidências.
- **Sem duplicidade:** existe restrição única por publicação e cliente.
- **Reexecução segura:** atualiza a pontuação sem alterar o status definido pelo analista.
- **Simulador:** testa qualquer texto contra os clientes ativos sem gravar nada no banco.

## E. Triagem jurídica
- Fila com filtros por relevância, status e cliente; pontuação exibida em barra de progresso.
- Detalhe: publicação original com destaques, cliente e responsável, justificativa, termos e pontos, área, data e status.
- Status: Pendente, Em análise, Confirmada, Descartada e Encaminhada ao responsável, com observações. Cada mudança vai para o histórico.
- Registro de possível prazo diretamente a partir da publicação, mostrando os indícios de datas e períodos encontrados no texto.

## F. Possíveis prazos
- Campos: descrição, publicação de origem, cliente, natureza da data, data de referência, data limite sugerida, responsável, status, observações, validação profissional e origem (manual ou sugestão da triagem).
- Natureza da data: prazo processual, prazo administrativo, data de vigência, data de publicação, obrigação contratual ou outra data relevante.
- Situação visual: Vencido, Crítico (até 2 dias), Próximo (até `LEGAL_MONITOR_DEADLINE_ALERT_DAYS`), No prazo ou Sem data.
- Prazos em aberto com data limite passada são marcados automaticamente como **Vencido**, com registro no histórico.
- **Salvaguardas jurídicas:** a data de publicação nunca é presumida como termo inicial; datas extraídas são apenas indícios; nenhuma data é calculada automaticamente; o campo "validado por profissional" é explícito.

## G. Relatórios
- Tipos: publicações, clientes, correspondências, alertas (somente ALTA) e possíveis prazos.
- Filtros: período, clientes, relevância e status (conforme o tipo de relatório).
- Exportação CSV com separador `;` e BOM UTF-8, para abrir corretamente no Excel em português, e PDF em paisagem com cabeçalho, filtros aplicados e aviso jurídico.

## H. Histórico e auditoria
- Ações registradas: CRIAÇÃO, ALTERAÇÃO (com diferenças campo a campo), EXCLUSÃO, TRIAGEM, CORRESPONDÊNCIA, STATUS, PRAZO e SISTEMA.
- Linha do tempo agrupada por dia (paginada), tabela completa, filtros por período, ação, entidade e texto, e exportação CSV.

## Configurações
- Carregar, restaurar ou remover a base demonstrativa sem afetar dados reais.
- Informações do ambiente (banco, versão, usuário e contagens).
