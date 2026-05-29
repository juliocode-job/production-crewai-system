# app/core/observability.py
import os
import base64
import json
from app.core import config

# Variável de instância global (Singleton) para o CallbackHandler do Langfuse
_langfuse_handler = None

def setup_instrumentation():
    """
    Inicializa a instrumentação da aplicação.
    Para utilizar o Tracing Nativo do Dashboard Enterprise/Platform do CrewAI, 
    nós delegamos o envio de telemetria diretamente ao próprio framework,
    evitando coletores e exportadores customizados de terceiros em rede local.
    Adicionalmente, se rodando em ambiente headless (como Render), configuramos
    as credenciais de login da plataforma CrewAI dinamicamente se fornecidas por envs.
    """
    try:
        print("[Observabilidade] Inicializando instrumentação global...")
        
        # Obter credenciais do CrewAI Platform das variáveis de ambiente
        username = os.getenv("CREWAI_TOOL_REPOSITORY_USERNAME")
        password = os.getenv("CREWAI_TOOL_REPOSITORY_PASSWORD")
        org_uuid = os.getenv("CREWAI_ORG_UUID")
        pat = os.getenv("CREWAI_PAT")  # Personal Access Token para autenticação do tracing no AMP
        
        if username and password:
            config_dir = os.path.expanduser("~/.config/crewai")
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, "settings.json")
            
            config_data = {
                "tool_repository_username": username,
                "tool_repository_password": password,
                "org_name": None,
                "org_uuid": org_uuid,
                "token": pat  # Necessário para autenticar o tracing nativo com o AMP
            }
            
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            
            if pat:
                print(f"[Observabilidade] Tracing Nativo: Credenciais do CrewAI (incluindo PAT) salvas com sucesso em '{config_file}'!")
            else:
                print(f"[Observabilidade] Tracing Nativo: Credenciais salvas em '{config_file}', mas CREWAI_PAT não encontrado — tracing pode falhar na autenticação com o AMP.")
        else:
            print("[Observabilidade] Tracing Nativo: Nenhuma credencial do CrewAI CLI encontrada no ambiente (CREWAI_TOOL_REPOSITORY_USERNAME/PASSWORD).")
            print("[Observabilidade] Certifique-se de executar 'crewai login' no terminal local ou configurar as envs no Render.")
            
        print("[Observabilidade] Utilizando o Tracing Nativo do Dashboard do CrewAI (AMP).")
    except Exception as e:
        print(f"[Observabilidade] Erro ao inicializar instrumentação: {e}")

def get_langfuse_callbacks():
    """
    Instancia de forma Singleton e retorna uma lista contendo o CallbackHandler nativo do Langfuse.
    """
    global _langfuse_handler
    
    if _langfuse_handler is not None:
        return [_langfuse_handler]
        
    callbacks = []
    if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        try:
            try:
                from langfuse.langchain import CallbackHandler
            except ModuleNotFoundError:
                from langfuse.callback import CallbackHandler
            # Garante que as variáveis de ambiente essenciais para o Langfuse estão exportadas para o SDK ler
            if config.LANGFUSE_SECRET_KEY:
                os.environ["LANGFUSE_SECRET_KEY"] = config.LANGFUSE_SECRET_KEY
            if config.LANGFUSE_BASE_URL:
                os.environ["LANGFUSE_HOST"] = config.LANGFUSE_BASE_URL
                
            _langfuse_handler = CallbackHandler(
                public_key=config.LANGFUSE_PUBLIC_KEY
            )
            callbacks.append(_langfuse_handler)
            print("[Observabilidade] Langfuse Callback Handler instanciado com sucesso!")
        except Exception as e:
            print(f"[Observabilidade] Erro ao carregar Langfuse Callback Handler: {e}")
    return callbacks

def flush_langfuse():
    """
    Força a transmissão (flush) imediata de todos os logs e traces acumulados em memória.
    Esta função deve ser executada no encerramento de threads de background para evitar perda de dados.
    """
    global _langfuse_handler
    if _langfuse_handler is not None:
        try:
            # Tenta acessar o cliente do Langfuse subjacente moderno
            if hasattr(_langfuse_handler, "_langfuse_client") and hasattr(_langfuse_handler._langfuse_client, "flush"):
                _langfuse_handler._langfuse_client.flush()
                print("[Observabilidade] Traces do Langfuse transmitidos com sucesso via cliente interno (_langfuse_client)!")
            elif hasattr(_langfuse_handler, "flush"):
                _langfuse_handler.flush()
                print("[Observabilidade] Traces do Langfuse transmitidos (flushed) com sucesso!")
            elif hasattr(_langfuse_handler, "langfuse") and hasattr(_langfuse_handler.langfuse, "flush"):
                _langfuse_handler.langfuse.flush()
                print("[Observabilidade] Traces do Langfuse transmitidos com sucesso via fallback interno (langfuse)!")
            else:
                print("[Observabilidade] Aviso: Nenhum método de transmissão direta (flush) encontrado no Handler.")
        except Exception as e:
            print(f"[Observabilidade] Falha ao tentar forçar a transmissão dos traces: {e}")
