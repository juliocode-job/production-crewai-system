# app/core/observability.py
import os
import base64
from app.core import config

# Variável de instância global (Singleton) para o CallbackHandler do Langfuse
_langfuse_handler = None

def setup_instrumentation():
    """
    Inicializa a instrumentação da aplicação.
    Para utilizar o Tracing Nativo do Dashboard Enterprise/Platform do CrewAI, 
    nós delegamos o envio de telemetria diretamente ao próprio framework,
    evitando coletores e exportadores customizados de terceiros em rede local.
    """
    try:
        print("[Observabilidade] Utilizando o Tracing Nativo do Dashboard do CrewAI (AMP).")
        print("[Observabilidade] Certifique-se de executar 'crewai login' no terminal local para autenticar.")
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

