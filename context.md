# Contexto de Desenvolvimento: Customer Support Crew

Este documento serve como o diário de bordo e registro técnico de todas as decisões de arquitetura, componentes implementados, testes realizados e o histórico de resoluções de problemas.

---

## 🏗️ Arquitetura do Sistema

Desenvolvemos um sistema de atendimento ao cliente multicanal de alto nível composto por:
1. **Multi-Agent Pipeline (CrewAI)**:
   - **Router (Claude Haiku 4.5)**: Classifica as dúvidas entre suporte técnico, reembolso e geral.
   - **Support Agent (Claude Sonnet 4.6)**: Integrado à ferramenta `DocsSearchTool` para busca em manuais internos.
   - **QA Analyst (Claude Opus 4.7)**: Realiza auditoria técnica, formatação de Markdown e blindagem de segurança.
2. **FastAPI Backend**:
   - Execução assíncrona da Crew em Threads separadas para evitar bloqueio de requisições.
   - Higienizador de dados pessoais sensíveis (PII Anonymizer) com regex.
   - Máquina de estados para suporte a **Human-in-the-Loop (HITL)** na web.
3. **Web Dashboard Premium**:
   - Interface Glassmorphic Dark Mode.
   - Terminal de streaming de logs em tempo real dos agentes.
   - Timeline interativa do pipeline de processamento.
   - Gerenciador de Banco de Cache Semântico Local.

---

## 🟢 Bugs e Gargalos Técnicos Resolvidos

Durante o ciclo de transição modular e testes de produção, identificamos e resolvemos com precisão cirúrgica todos os problemas que bloqueavam a aplicação:

### 1. Transição para o Tracing Nativo do CrewAI Platform (AMP)
* **Status**: 🟢 Homologado via Tracing Nativo do CrewAI
* **Descobertas e Transição Aplicada**:
  - **Gargalos e Erros OTel HTTP (404/Langfuse):** A exportação de telemetria OpenTelemetry (OTel) OTLP HTTP para nuvens públicas do Langfuse frequentemente resultava em erros HTTP 404 (retornando páginas HTML do Next.js) devido a conflitos de rotas de endpoint, diferenças de subpaths regionais e cabeçalhos de Basic Auth. Isso gerava desperdício desnecessário de tokens de rede e logs poluídos.
  - **Adoção da Observabilidade Nativa:** Para uma integração resiliente e imediata com o painel oficial do **CrewAI Enterprise/Platform (AMP)**, desativamos o provedor customizado OTel em [`app/core/observability.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/observability.py).
  - **Como Ativar o Tracing Nativo**:
    1. Mantenha `CREWAI_TRACING_ENABLED=true` no [`.env`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/.env) e `tracing=True` na criação da `Crew` em `orchestrator.py` (já configurados).
    2. Execute o comando **`crewai login`** no terminal local. Ele abrirá o navegador e autenticará sua máquina diretamente com a plataforma CrewAI.
    3. Todos os traces de agentes, chamadas LLM e etapas serão transmitidos automaticamente de forma nativa e segura para a aba **"Traces"** do seu painel CrewAI.

### 2. Cache Semântico Hit não sendo atingido (Erro 404 Anthropic)
* **Status**: 🟢 Resolvido e Homologado
* **Descobertas e Correções Aplicadas**:
  - **Conexão Mismatch / 404:** O motor de cache tentava usar o modelo `claude-3-5-haiku-20241022` que retorna erro 404 em contas abaixo de Tier 1. Isso quebrava silenciosamente a validação semântica local do JSON.
  - **Correção:** Alteramos o modelo em [`app/cache/semantic_cache.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/cache/semantic_cache.py) para o modelo oficial **`claude-3-haiku-20240307`** (Claude 3 Haiku), que é rápido, super econômico, extremamente assertivo na avaliação semântica e 100% disponível para qualquer nível de conta Anthropic.

---

## 🛠️ Componentes do Repositório

- **`/app` (Módulos da Aplicação):**
  - [`app/main.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/main.py): Setup central do servidor FastAPI, middlewares e montagem de estáticos.
  - [`app/core/config.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/config.py): Carregamento e centralização de variáveis do `.env`.
  - [`app/core/security.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/security.py): Higienizador contra vazamento de dados sensíveis (PII Anonymizer).
  - [`app/core/observability.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/observability.py): Instrumentação global de telemetria OTel (TracerProvider, OTLPSpanExporter) e Langfuse.
  - [`app/cache/semantic_cache.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/cache/semantic_cache.py): Gerenciamento do banco local JSON de cache semântico baseado em Claude Haiku.
  - [`app/crew/orchestrator.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/crew/orchestrator.py): Configuração de agentes, tarefas e orquestração do pipeline da CrewAI com `tracing=True`.
  - [`app/crew/tools.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/crew/tools.py): `DocsSearchTool` para busca de manuais na base de conhecimento simulada.
  - [`app/jobs/manager.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/jobs/manager.py): Fila de Jobs em memória e threads assíncronas de processamento em background.
  - [`app/api/routes.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/api/routes.py): Todos os endpoints REST e renderização do index HTML.
  - [`app/api/schemas.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/api/schemas.py): Modelos de validação de dados Pydantic.
- **Configurações e Assets:**
  - [`config/agents.yaml`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/config/agents.yaml) & [`config/tasks.yaml`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/config/tasks.yaml): Escopos de IA do CrewAI.
  - [`templates/index.html`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/templates/index.html): Interface operacional em Glassmorphism Dark Mode.
  - [`static/css/style.css`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/static/css/style.css) & [`static/js/app.js`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/static/js/app.js): Lógica visual e interações dinâmicas via SSE/polling.
- **Raiz e Orquestração:**
  - [`main.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/main.py): Entrypoint limpo para execução do Uvicorn (`app.main:app`).
  - [`requirements.txt`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/requirements.txt): Dependências globais do ecossistema.
  - [`.env`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/.env): Chaves e endpoints de rede protegidos.
  - [`context.md`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/context.md): Histórico e diário técnico de desenvolvimento.
  - [`tests/test_api.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/tests/test_api.py): Script de teste automatizado de endpoints REST e HITL em background.
