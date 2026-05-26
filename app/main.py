# app/main.py
import os
import sys

# Forçar codificação UTF-8 nos fluxos de saída padrão para evitar erros de 'charmap' no terminal do Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core import config
from app.core.observability import setup_instrumentation
from app.api.routes import router

# 1. Inicializa o tracing e instrumentação global do OpenTelemetry/Langfuse
setup_instrumentation()

# 2. Inicialização do servidor FastAPI
app = FastAPI(title="AI Customer Support Dashboard & Crew")

# 3. Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Servir arquivos estáticos (CSS, JS)
if not os.path.exists(config.STATIC_DIR):
    os.makedirs(config.STATIC_DIR)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

# 5. Registrar as rotas REST e o renderizador do dashboard
app.include_router(router)
