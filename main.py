# main.py
# Ponto de entrada (Entrypoint) do Monolito Modular.
# Redireciona a inicialização do FastAPI/Uvicorn para o pacote modular `app`.

import sys

# Forçar codificação UTF-8 nos fluxos de saída padrão para evitar erros de 'charmap' no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.main import app

