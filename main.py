# main.py
# Ponto de entrada (Entrypoint) do Monolito Modular.
# Redireciona a inicialização do FastAPI/Uvicorn para o pacote modular `app`.

from app.main import app
