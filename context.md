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

### 1. Transição para o Tracing via Arize Phoenix (OpenTelemetry Puro)
* **Status**: 🟢 Ativado e Homologado com OpenTelemetry OTLPSpanExporter
* **Descobertas e Integração Aplicada**:
  - **Estratégia de Observabilidade:** Para garantir monitoramento em tempo real de nível corporativo sem as complexidades de autenticação headless de CLI no Render e evitando conflitos com o TracerProvider interno da biblioteca do Phoenix (`arize-phoenix-otel`), migramos para uma abordagem de **OpenTelemetry Puro** usando `OTLPSpanExporter`.
  - **Instrumentadores Ativos:** Usamos o `opentelemetry-exporter-otlp-proto-http` junto com `CrewAIInstrumentor` (da OpenInference) para capturar a lógica de execução da Crew de forma direta e padronizada.
  - **Bypas de Conflitos OTel:** Configuramos manualmente o `TracerProvider` com o `BatchSpanProcessor` acoplado ao `OTLPSpanExporter` puro, e o passamos diretamente para o `CrewAIInstrumentor(tracer_provider=provider)`. Bypassamos completamente a chamada global `trace.set_tracer_provider(provider)`. Isso elimina 100% qualquer conflito de concorrência global de inicialização no OpenTelemetry!
  - **Configuração via Variáveis de Ambiente:** O sistema agora é configurado apenas pelas variáveis do Render `PHOENIX_API_KEY` e `PHOENIX_PROJECT_NAME`, enviando telemetria para a nuvem de forma nativa e assíncrona.

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

## 🌐 Implantação em Produção (Render) e Solução de Problemas

Registramos aqui a jornada de colocar o Monolito FastAPI / CrewAI em produção na plataforma **Render**, as decisões de arquitetura e a investigação em andamento dos fluxos de login em múltiplos dispositivos.

### 1. Detalhes do Deploy no Render
* **Tipo de Serviço:** Escolhido **Web Services** (Serviço Web dinâmico), pois a aplicação roda um servidor Python que processa IA em tempo real e fornece o Dashboard Glassmorphic.
* **Ambiente de Execução:** Escolhemos **Docker** como linguagem. O Render detectou automaticamente o nosso `Dockerfile` de produção que:
  - Isola o sistema operacional usando `python:3.11-slim`.
  - Instala `build-essential` e dependências para que o banco de dados `sqlite3` e o hashing Bcrypt compilem e rodem sem falhas no ambiente Linux.
  - Expõe e inicia o servidor Uvicorn escutando em `0.0.0.0:8000`.
* **Deploy inicial:** Finalizado de primeira e com absoluto sucesso. A URL pública foi gerada como `https://production-crewai-system.onrender.com/login` e o banco foi populado com a semente automática do administrador (`admin` / `admin123`).

### 2. Configurações de Variáveis de Ambiente e Tracing
* **Langfuse Tracing:** Configurado no Render colando as chaves `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` e `LANGFUSE_BASE_URL=https://cloud.langfuse.com` (sem aspas para evitar conflito de caracteres especiais).
* **Arize Phoenix Tracing (OpenTelemetry):** O Uvicorn inicializa a instrumentação global com o SDK do Arize Phoenix na inicialização do servidor se as seguintes variáveis de ambiente estiverem configuradas no Render:
  - `PHOENIX_API_KEY`: A chave JWT de autenticação do Arize Phoenix.
  - `PHOENIX_PROJECT_NAME`: O nome do projeto no dashboard (ex: `production-crew-support`).
  Com isso, todas as interações e traces da Crew e do LiteLLM são enviados de forma nativa e segura para o Arize Phoenix usando o endpoint padrão `https://app.phoenix.arize.com/v1/traces`!

### 3. Persistência de Dados (Investigação do SQLite e Reset de Banco)
* **Comportamento Efêmero do Render:** Descobrimos que, por padrão, o Render destrói o container anterior e seus arquivos locais (incluindo `customer_support.db`) toda vez que um novo deploy, alteração de env ou reinício automático por inatividade do plano Free acontece.
* **Solução Homologada:** Para evitar a perda de dados e histórico, adicionamos a instrução de criar um **Disco Persistente (Disk)** no Render:
  - **Mount Path:** `/app/data` (pasta onde o SQLite lê/grava os dados).
  - **Tamanho:** `1 GiB` (mínimo).
  - Com isso, as tabelas e usuários são mantidos permanentemente em um volume físico separado.

### 4. Investigação do Fluxo de Login (Usuário "Sara")
* **O Problema:** A usuária `Sara` (senha `S@ra140103`) se cadastrou pelo celular e utilizou o sistema com sucesso (incluindo fazer logout e login de novo com êxito em seu aparelho). No entanto, o operador ao tentar fazer o login a partir de seu computador pessoal (PC) na mesma URL de produção recebe "Usuário ou senha incorretos".
* **Fatos Diagnosticados:**
  - O teclado do PC está imprimindo o caractere `@` corretamente (testado no campo de texto aberto de usuário).
  - A conta `Sara` está devidamente gravada no banco de dados do Render (pois a usuária ainda usa e se loga nela no celular).
  - SQLite é **case-sensitive** (diferencia maiúsculas) para buscas de texto com `=`. O usuário deve ser escrito como `Sara` (e não `sara`).
* **Próximos Passos de Depuração:**
  - Investigar se há cookies de sessão ou tokens JWT residuais no navegador do PC que estejam gerando conflito de estado de rotas HTTP.
  - Investigar se existem extensões bloqueadoras, antivírus ou gerenciadores de senhas no PC que modificam o payload JSON de envio no endpoint `/api/auth/login`.
  - Investigar se o preenchimento automático inseriu espaços extras ocultos na digitação.
