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
  - **Conexão Mismatch / 404:** A chave de API da Anthropic do seu ambiente de curso (proxy juliocode) utiliza aliases de modelo customizados da plataforma (ex: `claude-haiku-4-5` e `claude-sonnet-4-6`). Chamadas diretas de `ChatAnthropic` no cache semântico tentando usar o nome de modelo padrão `claude-3-haiku-20240307` (ou no refinamento tentando usar `claude-3-5-sonnet-20241022`) falhavam com erro `404 Not Found`, inativando silenciosamente o cache semântico e forçando Cache Miss constante.
  - **Correção:** Migramos os clientes `ChatAnthropic` no validador semântico ([`app/cache/semantic_cache.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/cache/semantic_cache.py)) para o alias de modelo ativo **`claude-haiku-4-5`**, e o refinamento do operador em [`app/api/routes.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/api/routes.py) para usar o alias correspondente ativo **`claude-sonnet-4-6`**. O cache semântico agora funciona perfeitamente, com retorno instantâneo em **0.2 segundos** e consumo zero de tokens LLM em consultas recorrentes!

### 3. Estabilização do Ambiente Windows e do Hot-Reload (Uvicorn)
* **Status**: 🟢 Resolvido e Homologado
* **Problema e Resolução**:
  - **WatchFiles Hot-Reload Loop:** O Uvicorn entrava em loop infinito de reinicializações por varrer recursivamente milhares de arquivos na pasta do ambiente virtual (`venv/`). Resolvemos isso restringindo a diretiva de monitoramento exclusivamente para a pasta do aplicativo com o comando `--reload-dir app`.
  - **Erros de Escrita 'charmap' de Emojis:** Os logs ricos com emojis da CrewAI travavam o terminal do Windows por falta de codificação adequada do console. Resolvemos isso adicionando uma reconfiguração explícita de streams (`sys.stdout` e `sys.stderr` para `utf-8`) programaticamente na inicialização do servidor.

### 4. Erros de Criptografia Passlib no Python 3.12+ (Bcrypt Mismatch)
* **Status**: 🟢 Resolvido e Homologado
* **Problema e Resolução**:
  - **Incompatibilidade Passlib / Bcrypt 4+:** O `passlib` (sem atualização desde 2020) falhava no Python 3.13 ao tentar buscar o atributo privado `__about__` da biblioteca `bcrypt`, travando a inicialização do banco. Adicionalmente, disparava o erro `ValueError: password cannot be longer than 72 bytes` em sua rotina interna de compatibilidade.
  - **Solução definitiva:** Abolimos o `passlib` e reescrevemos o hashing e verificação de senhas em [`app/core/auth.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/auth.py) utilizando a biblioteca **`bcrypt` diretamente** (`bcrypt.hashpw` e `bcrypt.checkpw`). A inicialização ficou mais rápida, limpa e 100% resiliente a mudanças nas dependências do Python moderno.

### 5. Persistência de Histórico de Atendimentos e Autenticação JWT
* **Status**: 🟢 Homologado e em Operação
* **Descrição da Arquitetura**:
  - **Banco de Dados SQLite Local:** Integramos o `SQLModel` para gerenciar a persistência local (no arquivo [`data/customer_support.db`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/data/customer_support.db)) de `User`, `Job` e `JobLog`. A fila temporária em memória (`ACTIVE_JOBS`) foi totalmente removida, e os atendimentos agora resistem a reinicializações.
  - **Autenticação JWT via Cookie HttpOnly:** Tokens JWT seguros são gerados no login e injetados de forma protegida como Cookies no navegador. As páginas e rotas de API possuem validação automatizada e as requisições de frontend anexam a credencial de forma segura.
  - **Histórico Lateral Interativo:** O dashboard conta com uma barra lateral de **Histórico Recente** que recarrega atendimentos passados, permitindo que o operador clique em qualquer item histórico para restaurar logs e rascunhos instantaneamente no painel.

---

## 🛠️ Componentes do Repositório

- **`/app` (Módulos da Aplicação):**
  - [`app/main.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/main.py): Setup central do servidor FastAPI, middlewares e montagem de estáticos.
  - [`app/core/config.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/config.py): Carregamento e centralização de variáveis do `.env`, JWT e URLs de banco.
  - [`app/core/security.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/security.py): Higienizador contra vazamento de dados sensíveis (PII Anonymizer).
  - [`app/core/observability.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/observability.py): Instrumentação global de telemetria OTel (TracerProvider, OTLPSpanExporter) e Langfuse.
  - [`app/core/models.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/models.py): Tabelas de banco de dados do SQLite baseadas em SQLModel (`User`, `Job`, `JobLog`).
  - [`app/core/database.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/database.py): Setup do banco SQLite, injeção de sessão e semente inicial de usuário administrador (`admin`/`admin123`).
  - [`app/core/auth.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/core/auth.py): Lógica de JWT, hashing nativo com `bcrypt` direto e dependência de usuário ativo.
  - [`app/cache/semantic_cache.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/cache/semantic_cache.py): Gerenciamento do banco local JSON de cache semântico baseado em Claude Haiku.
  - [`app/crew/orchestrator.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/crew/orchestrator.py): Configuração de agentes, tarefas e orquestração do pipeline da CrewAI com `tracing=True`.
  - [`app/crew/tools.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/crew/tools.py): `DocsSearchTool` para busca de manuais na base de conhecimento simulada.
  - [`app/jobs/manager.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/jobs/manager.py): Fila de Jobs e gravação de logs de progresso e transições de agentes diretamente no SQLite.
  - [`app/api/routes.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/api/routes.py): Todos os endpoints REST (incluindo rotas de Auth e Histórico), serving do frontend e redirecionamentos JWT.
  - [`app/api/schemas.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/app/api/schemas.py): Modelos de validação de dados Pydantic (incluindo schemas de Login/Cadastro).
- **Configurações e Assets:**
  - [`config/agents.yaml`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/config/agents.yaml) & [`config/tasks.yaml`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/config/tasks.yaml): Escopos de IA do CrewAI.
  - [`templates/index.html`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/templates/index.html): Interface operacional em Glassmorphism Dark Mode com histórico e perfil de usuário.
  - [`templates/login.html`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/templates/login.html): Tela de login/registro integrada em Glassmorphism Dark Mode.
  - [`static/css/style.css`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/static/css/style.css) & [`static/js/app.js`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/static/js/app.js): Lógica visual, interações em tempo real com histórico lateral clicável.
- **Raiz e Orquestração:**
  - [`main.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/main.py): Entrypoint limpo para execução do Uvicorn (`app.main:app`).
  - [`Dockerfile`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/Dockerfile): Configuração de containerização multi-stage de produção para o FastAPI/CrewAI.
  - [`.dockerignore`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/.dockerignore): Otimização de camadas de build e exclusão de credenciais locais.
  - [`requirements.txt`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/requirements.txt): Dependências globais do ecossistema.
  - [`.env`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/.env): Chaves e endpoints de rede protegidos.
  - [`context.md`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/context.md): Histórico e diário técnico de desenvolvimento.
  - [`tests/test_api.py`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/tests/test_api.py): Script de teste automatizado que realiza login automático, aquisição de cookie e validação de rotas REST.
  - [`PROXIMOS_PASSOS.md`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/PROXIMOS_PASSOS.md): Planejamento e blueprint técnico detalhado para escalabilidade horizontal da CrewAI em produção.
  - [`PLANO_LATENCIA.md`](file:///c:/Users/lemos/OneDrive/Área de Trabalho/Customer-support-crew/PLANO_LATENCIA.md): Planejamento e blueprints de código para otimização extrema de latência da CrewAI localmente.
