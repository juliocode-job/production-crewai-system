# app/api/routes.py
import os
import uuid
from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Request, Response, status
import json
import asyncio
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from langchain_anthropic import ChatAnthropic
from sqlmodel import Session, select

from app.core import config
from app.core.database import get_session, engine
from app.core.models import User, Job, JobLog
from app.core.auth import get_current_user, get_password_hash, verify_password, create_access_token
from app.core.security import sanitize_input
from app.cache.semantic_cache import check_semantic_cache, load_cache, save_cache
from app.jobs.manager import run_crew_job
from app.api.schemas import InquiryRequest, FeedbackRequest, UserAuthRequest

# Criação do roteador para agrupar endpoints
router = APIRouter()

# --- ENDPOINTS DE AUTENTICAÇÃO ---

@router.post("/api/auth/register")
def register_user(req: UserAuthRequest, session: Session = Depends(get_session)):
    """Cadastra um novo usuário no sistema."""
    username = req.username.strip()
    password = req.password.strip()
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário e senha não podem ser vazios."
        )
        
    # Verificar se o usuário já existe
    statement = select(User).where(User.username == username)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já cadastrado. Tente outro."
        )
        
    new_user = User(
        username=username,
        password_hash=get_password_hash(password)
    )
    session.add(new_user)
    session.commit()
    return {"status": "success", "message": "Usuário registrado com sucesso!"}

@router.post("/api/auth/login")
def login_user(req: UserAuthRequest, response: Response, session: Session = Depends(get_session)):
    """Valida as credenciais do usuário e define o Cookie JWT HttpOnly seguro."""
    username = req.username.strip()
    password = req.password.strip()
    
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos."
        )
        
    # Gerar token de acesso
    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Adicionar o token em um Cookie seguro HttpOnly
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Mudar para True se rodando em HTTPS em produção
    )
    
    return {"status": "success", "username": user.username}

@router.post("/api/auth/logout")
def logout_user(response: Response):
    """Limpa o Cookie JWT efetuando o logout do usuário."""
    response.delete_cookie(key="access_token")
    return {"status": "success", "message": "Sessão encerrada com sucesso."}

@router.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário autenticado no momento."""
    return {"username": current_user.username, "id": current_user.id}


# --- ENDPOINTS PROTEGIDOS DA API REST (SUPORTE) ---

@router.get("/api/history")
def get_history(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Retorna o histórico completo de dúvidas enviadas pelo usuário logado."""
    statement = select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    jobs = session.exec(statement).all()
    return [
        {
            "job_id": job.id,
            "inquiry": job.inquiry,
            "status": job.status,
            "cache_hit": job.cache_hit,
            "created_at": job.created_at.isoformat()
        }
        for job in jobs
    ]

@router.post("/api/inquiry")
def post_inquiry(
    req: InquiryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Recebe a pergunta do cliente, higieniza contra PII, verifica cache semântico
    e dispara a execução dos agentes de forma assíncrona salvando tudo no SQLite.
    """
    original_inquiry = req.inquiry.strip()
    if not original_inquiry:
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")
        
    # Sanitiza a entrada (Segurança - PII Anonymizer)
    sanitized_inquiry = sanitize_input(original_inquiry)
    print(f"Entrada recebida do usuário '{current_user.username}'. Sanitizada: '{sanitized_inquiry}'")
    
    # Verifica o Cache Semântico alimentado por IA (Claude Haiku)
    cached_match = check_semantic_cache(sanitized_inquiry)
    job_id = str(uuid.uuid4())
    
    if cached_match:
        # Cache HIT! Registrar Job concluído no SQLite
        job = Job(
            id=job_id,
            user_id=current_user.id,
            status="concluido",
            inquiry=original_inquiry,
            sanitized_inquiry=sanitized_inquiry,
            draft=cached_match["response"],
            final_response=cached_match["response"],
            cache_hit=True
        )
        session.add(job)
        session.commit()
        
        # Salvar log de sucesso instantâneo no banco
        log_cache_1 = JobLog(job_id=job_id, message="🎯 Cache Hit Semântico encontrado!")
        log_cache_2 = JobLog(job_id=job_id, message="Resposta recuperada instantaneamente do cache local em milissegundos.")
        session.add(log_cache_1)
        session.add(log_cache_2)
        session.commit()
        
        return {"job_id": job_id, "cache_hit": True}
        
    # Cache MISS - Criar Job no SQLite e disparar a Crew em background
    job = Job(
        id=job_id,
        user_id=current_user.id,
        status="triando",
        inquiry=original_inquiry,
        sanitized_inquiry=sanitized_inquiry,
        draft="",
        final_response="",
        cache_hit=False
    )
    session.add(job)
    session.commit()
    
    log_init = JobLog(job_id=job_id, message="Iniciando pipeline de atendimento assíncrono...")
    log_pii = JobLog(job_id=job_id, message="Higienização de dados PII concluída com sucesso!")
    session.add(log_init)
    session.add(log_pii)
    session.commit()
    
    background_tasks.add_task(run_crew_job, job_id, sanitized_inquiry)
    return {"job_id": job_id, "cache_hit": False}

@router.get("/api/status/{job_id}")
def get_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Retorna os dados completos e logs atualizados de um job."""
    statement = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    job = session.exec(statement).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job de atendimento não encontrado.")
    
    # Ordenar logs de execução pelo timestamp ou id
    sorted_logs = sorted(job.logs, key=lambda log: log.timestamp or log.id)
    
    return {
        "status": job.status,
        "inquiry": job.inquiry,
        "sanitized_inquiry": job.sanitized_inquiry,
        "draft": job.draft,
        "final_response": job.final_response,
        "cache_hit": job.cache_hit,
        "logs": [log.message for log in sorted_logs]
    }

@router.get("/api/jobs/{job_id}/stream")
async def stream_job_output(
    job_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Endpoint SSE (Server-Sent Events) para transmitir logs e atualizações de status do Job em tempo real.
    """
    statement = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    job = session.exec(statement).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job de atendimento não encontrado.")

    async def event_generator():
        last_log_id = 0
        last_status = None
        
        while True:
            # Abrimos uma nova sessão curta em cada ciclo para pegar o estado mais recente do SQLite
            with Session(engine) as loop_session:
                j = loop_session.get(Job, job_id)
                if not j:
                    break
                
                # 1. Enviar transição de status se houver alteração
                if j.status != last_status:
                    last_status = j.status
                    yield f"data: {json.dumps({'type': 'status', 'status': j.status}, ensure_ascii=False)}\n\n"
                
                # 2. Buscar novos logs inseridos
                new_logs = loop_session.exec(
                    select(JobLog).where(JobLog.job_id == job_id, JobLog.id > last_log_id).order_by(JobLog.id)
                ).all()
                
                for log in new_logs:
                    last_log_id = log.id
                    sender = "agent" if any(x in log.message for x in ["Pensamento:", "Ferramenta:", "Iniciando", "Buscando"]) else "system"
                    yield f"data: {json.dumps({'type': 'log', 'message': log.message, 'sender': sender}, ensure_ascii=False)}\n\n"
                
                # 3. Finalizar conexão se atingir um estado conclusivo/HITL/erro
                if j.status in ["concluido", "aguardando_aprovacao", "erro"]:
                    yield f"data: {json.dumps({'type': 'finished', 'status': j.status, 'draft': j.draft, 'final_response': j.final_response, 'cache_hit': j.cache_hit}, ensure_ascii=False)}\n\n"
                    break
            
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/api/approve/{job_id}")
def approve_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Aprova a resposta gerada. Ela é movida para concluída e 
    salva no cache semântico local para reaproveitamento.
    """
    statement = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    job = session.exec(statement).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
        
    if not job.draft:
        raise HTTPException(status_code=400, detail="Não há rascunho disponível para aprovação.")
        
    final_resp = job.draft
    job.final_response = final_resp
    job.status = "concluido"
    
    log_approve = JobLog(job_id=job_id, message="✅ Resposta de suporte aprovada pelo operador humano!")
    session.add(log_approve)
    session.add(job)
    session.commit()
    
    # Salva no Cache Semântico local se for uma nova resposta
    if not job.cache_hit:
        cache = load_cache()
        cache.append({
            "query": job.sanitized_inquiry,
            "response": final_resp
        })
        save_cache(cache)
        
        log_cache = JobLog(job_id=job_id, message="💾 Resposta registrada com sucesso no cache semântico local.")
        session.add(log_cache)
        session.commit()
        
    return {"status": "success"}

def re_run_qa_db(job_id: str, feedback_text: str):
    """Função executada em background para o processamento assíncrono do feedback da Crew."""
    try:
        with Session(engine) as session:
            j = session.get(Job, job_id)
            if not j:
                return
            sanitized_inquiry = j.sanitized_inquiry
            draft = j.draft
        
        # Realiza a chamada LLM sem travar a sessão ativa do banco
        prompt = f"""Você é o Analista de Garantia de Qualidade de Suporte.
O operador humano revisou sua sugestão de e-mail e rejeitou pedindo alterações.

DÚVIDA DO CLIENTE: "{sanitized_inquiry}"
RASCUNHO ANTERIOR:
\"\"\"
{draft}
\"\"\"

FEEDBACK DE CORREÇÃO DO OPERADOR: "{feedback_text}"

Por favor, reescreva a resposta de suporte aplicando estritamente as alterações solicitadas pelo operador humano no feedback. Mantenha a precisão técnica e a formatação Markdown profissional.
Responda diretamente com a nova versão do e-mail revisado.

Nova resposta revisada:"""

        llm = ChatAnthropic(model_name="claude-sonnet-4-6", temperature=0.2)
        response = llm.invoke(prompt)
        new_draft = response.content.strip()

        with Session(engine) as session:
            j = session.get(Job, job_id)
            if j:
                j.draft = new_draft
                j.status = "aguardando_aprovacao"
                session.add(j)
                log = JobLog(job_id=job_id, message="Refinamento concluído com sucesso com base no seu feedback! Aguardando nova revisão...")
                session.add(log)
                session.commit()
                
    except Exception as e:
        with Session(engine) as session:
            j = session.get(Job, job_id)
            if j:
                j.status = "erro"
                session.add(j)
                log = JobLog(job_id=job_id, message=f"❌ Erro ao processar feedback de refino: {str(e)}")
                session.add(log)
                session.commit()

@router.post("/api/reject/{job_id}")
def reject_job(
    job_id: str,
    req: FeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Rejeita a resposta e reinicia a etapa de QA do Claude Opus 4.7
    passando o rascunho anterior e as instruções de correção do humano.
    """
    statement = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    job = session.exec(statement).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
        
    feedback_text = req.feedback.strip()
    if not feedback_text:
        raise HTTPException(status_code=400, detail="Por favor, forneça o feedback de correção.")
        
    job.status = "auditando"
    log_reject = JobLog(job_id=job_id, message=f"❌ Resposta rejeitada pelo operador. Feedback: '{feedback_text}'")
    log_re_run = JobLog(job_id=job_id, message="Re-enviando para o Analista de Garantia de Qualidade (Claude Opus 4.7)...")
    
    session.add(job)
    session.add(log_reject)
    session.add(log_re_run)
    session.commit()
    
    # Executa a re-elaboração em background
    background_tasks.add_task(re_run_qa_db, job_id, feedback_text)
    return {"status": "success"}


# --- ENDPOINTS DE GERENCIAMENTO DE CACHE (PROTEGIDOS) ---

@router.get("/api/cache")
def get_all_cache(current_user: User = Depends(get_current_user)):
    """Retorna todos os itens gravados no cache semântico local."""
    return load_cache()

@router.delete("/api/cache/{idx}")
def delete_cache_item(idx: int, current_user: User = Depends(get_current_user)):
    """Deleta um item do cache semântico baseado no índice."""
    cache = load_cache()
    if idx < 0 or idx >= len(cache):
        raise HTTPException(status_code=404, detail="Índice de cache inválido.")
    deleted = cache.pop(idx)
    save_cache(cache)
    return {"status": "success", "deleted": deleted}


# --- RENDERIZADORES FRONTEND (COM VERIFICAÇÃO DE COOKIES) ---

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Renderiza a página principal do Dashboard Web Premium.
    Redireciona para /login se o usuário não possuir um token JWT válido no Cookie.
    """
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        
    if token.startswith("Bearer "):
        token = token[7:]
        
    try:
        # Tenta decodificar o token para validar
        from jose import jwt
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except Exception:
        # Se expirar ou falhar a decodificação, manda pro login
        return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        
    template_file = os.path.join(config.TEMPLATE_DIR, "index.html")
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Servidor Rodando. Dashboard index.html não localizado.</h1>"

@router.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request):
    """
    Renderiza a tela de login.
    Redireciona direto para o Dashboard se o usuário já estiver autenticado.
    """
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            token = token[7:]
        try:
            from jose import jwt
            jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
            return RedirectResponse(url="/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        except Exception:
            pass

    template_file = os.path.join(config.TEMPLATE_DIR, "login.html")
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Servidor Rodando. Página login.html não localizada.</h1>"
