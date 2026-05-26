# app/core/database.py
import os
from sqlmodel import SQLModel, create_engine, Session
from app.core import config

# O SQLite exige check_same_thread=False quando rodamos em múltiplas threads
# Adicionamos "timeout": 30 para esperar liberar locks concorrentes de escrita
connect_args = {
    "check_same_thread": False,
    "timeout": 30
}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args)

# Ativar o modo WAL (Write-Ahead Logging) e sincronização otimizada para concorrência
if config.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

def create_db_and_tables():
    # Garantir que a pasta data exista
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    # Importar os modelos para registrá-los no metadata do SQLModel
    from app.core.models import User, Job, JobLog
    SQLModel.metadata.create_all(engine)
    
    # Criar usuário padrão (admin/admin123) se a base de dados estiver vazia
    with Session(engine) as session:
        from sqlmodel import select
        from app.core.auth import get_password_hash
        
        statement = select(User)
        existing = session.exec(statement).first()
        if not existing:
            print("=== Inicializando Banco de Dados: Criando usuário administrador padrão (admin / admin123) ===")
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123")
            )
            session.add(admin_user)
            session.commit()
            print("=== Usuário administrador criado com sucesso! ===")

def get_session():
    with Session(engine) as session:
        yield session
