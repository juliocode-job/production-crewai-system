# app/core/models.py
from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
import uuid

class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamento de Jobs do usuário
    jobs: List["Job"] = Relationship(back_populates="user", cascade_delete=True)

class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    status: str  # "triando", "resolvendo", "auditando", "aguardando_aprovacao", "concluido", "erro"
    inquiry: str
    sanitized_inquiry: str
    draft: str = Field(default="")
    final_response: str = Field(default="")
    cache_hit: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamentos
    user: Optional[User] = Relationship(back_populates="jobs")
    logs: List["JobLog"] = Relationship(back_populates="job", cascade_delete=True)

class JobLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(foreign_key="job.id", index=True)
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamento
    job: Optional[Job] = Relationship(back_populates="logs")
