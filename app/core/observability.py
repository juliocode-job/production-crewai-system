# app/core/observability.py
import os
import base64
import json
from app.core import config

# Variável de instância global (Singleton) para o CallbackHandler do Langfuse
_langfuse_handler = None

def setup_instrumentation():
    try:
        print("[Observabilidade] Inicializando instrumentação global com Arize Phoenix...")

        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from openinference.instrumentation.crewai import CrewAIInstrumentor

        phoenix_api_key = os.getenv("PHOENIX_API_KEY")
        phoenix_project = os.getenv("PHOENIX_PROJECT_NAME", "production-crew-support")

        if not phoenix_api_key:
            print("[Observabilidade] PHOENIX_API_KEY não encontrado. Tracing desativado.")
            return

        exporter = OTLPSpanExporter(
            endpoint="https://app.phoenix.arize.com/v1/traces",
            headers={
                "Authorization": f"Bearer {phoenix_api_key}",
                "project_name": phoenix_project,
            }
        )

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))

        CrewAIInstrumentor().instrument(tracer_provider=provider)

        print(f"[Observabilidade] Arize Phoenix ativo! Projeto: {phoenix_project}")

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

