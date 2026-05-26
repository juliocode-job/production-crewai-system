# app/core/auth.py
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from jose import JWTError, jwt
import bcrypt
from sqlmodel import Session, select

from app.core import config
from app.core.database import get_session
from app.core.models import User

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano bate com o hash criptografado."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Gera o hash criptografado a partir da senha em texto plano usando bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Gera um token de acesso JWT assinado."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """
    Dependência FastAPI que lê o token JWT a partir do Cookie seguro 'access_token',
    valida a expiração e assinatura, e retorna o usuário autenticado.
    Retorna HTTP 401 se não autenticado.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Por favor, faça login."
        )
    
    # Suporte a Bearer no Cookie (caso inserido com o prefixo)
    if token.startswith("Bearer "):
        token = token[7:]
        
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido. Faça login novamente."
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Faça login novamente."
        )
        
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não cadastrado."
        )
    return user
