# app/api/routes.py
import os
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from langchain_anthropic import ChatAnthropic

from app.core import config
from app.core.security import sanitize_input
from app.cache.semantic_cache import check_semantic_cache, load_cache, save_cache
from app.jobs.manager import ACTIVE_JOBS, run_crew_job
from app.api.schemas import InquiryRequest, FeedbackRequest

# Criação do roteador para agrupar endpoints
router = APIRouter()

# --- ENDPOINTS DA API REST ---

@router.post("/api/inquiry")
def post_inquiry(req: InquiryRequest, background_tasks: BackgroundTasks):
    """
    Recebe a pergunta do cliente, higieniza contra PII, verifica cache semântico
    e dispara a execução dos agentes de forma assíncrona.
    """
    original_inquiry = req.inquiry.strip()
    if not original_inquiry:
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")
        
    # Sanitiza a entrada (Segurança - PII Anonymizer)
    sanitized_inquiry = sanitize_input(original_inquiry)
    print(f"Entrada recebida. Sanitizada: '{sanitized_inquiry}'")
    
    # Verifica o Cache Semântico alimentado por IA (Claude Haiku)
    cached_match = check_semantic_cache(sanitized_inquiry)
    if cached_match:
        # Cache HIT!
        job_id = str(uuid.uuid4())
        ACTIVE_JOBS[job_id] = {
            "status": "concluido",
            "inquiry": original_inquiry,
            "sanitized_inquiry": sanitized_inquiry,
            "draft": cached_match["response"],
            "final_response": cached_match["response"],
            "cache_hit": True,
            "logs": ["🎯 Cache Hit Semântico encontrado!", "Resposta recuperada instantaneamente do cache local em milissegundos."]
        }
        return {"job_id": job_id, "cache_hit": True}
        
    # Cache MISS - Disparar a Crew em background
    job_id = str(uuid.uuid4())
    ACTIVE_JOBS[job_id] = {
        "status": "triando",
        "inquiry": original_inquiry,
        "sanitized_inquiry": sanitized_inquiry,
        "draft": "",
        "final_response": "",
        "cache_hit": False,
        "logs": ["Iniciando pipeline de atendimento assíncrono...", "Higienização de dados PII concluída com sucesso!"]
    }
    
    background_tasks.add_task(run_crew_job, job_id, sanitized_inquiry)
    return {"job_id": job_id, "cache_hit": False}

@router.get("/api/status/{job_id}")
def get_status(job_id: str):
    """Retorna os dados completos e logs atualizados de um job."""
    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail="Job de atendimento não encontrado.")
    return ACTIVE_JOBS[job_id]

@router.post("/api/approve/{job_id}")
def approve_job(job_id: str):
    """
    Aprova a resposta gerada. Ela é movida para concluída e 
    salva no cache semântico local para reaproveitamento.
    """
    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
        
    job = ACTIVE_JOBS[job_id]
    if not job["draft"]:
        raise HTTPException(status_code=400, detail="Não há rascunho disponível para aprovação.")
        
    final_resp = job["draft"]
    job["final_response"] = final_resp
    job["status"] = "concluido"
    job["logs"].append("✅ Resposta de suporte aprovada pelo operador humano!")
    
    # Salva no Cache Semântico local se for uma nova resposta
    if not job.get("cache_hit", False):
        cache = load_cache()
        cache.append({
            "query": job["sanitized_inquiry"],
            "response": final_resp
        })
        save_cache(cache)
        job["logs"].append("💾 Resposta registrada com sucesso no cache semântico local.")
        
    return {"status": "success"}

@router.post("/api/reject/{job_id}")
def reject_job(job_id: str, req: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Rejeita a resposta e reinicia a etapa de QA do Claude Opus 4.7
    passando o rascunho anterior e as instruções de correção do humano.
    """
    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
        
    job = ACTIVE_JOBS[job_id]
    feedback_text = req.feedback.strip()
    if not feedback_text:
        raise HTTPException(status_code=400, detail="Por favor, forneça o feedback de correção.")
        
    job["logs"].append(f"❌ Resposta rejeitada pelo operador. Feedback: '{feedback_text}'")
    job["status"] = "auditando"
    
    # Lógica rápida de re-execução (Web-friendly HITL):
    # Rodamos o Claude Opus novamente de forma assíncrona para aplicar o feedback do usuário
    def re_run_qa():
        try:
            job["logs"].append("Re-enviando para o Analista de Garantia de Qualidade (Claude Opus 4.7)...")
            
            prompt = f"""Você é o Analista de Garantia de Qualidade de Suporte.
O operador humano revisou sua sugestão de e-mail e rejeitou pedindo alterações.

DÚVIDA DO CLIENTE: "{job['sanitized_inquiry']}"
RASCUNHO ANTERIOR:
\"\"\"
{job['draft']}
\"\"\"

FEEDBACK DE CORREÇÃO DO OPERADOR: "{feedback_text}"

Por favor, reescreva a resposta de suporte aplicando estritamente as alterações solicitadas pelo operador humano no feedback. Mantenha a precisão técnica e a formatação Markdown profissional.
Responda diretamente com a nova versão do e-mail revisado.

Nova resposta revisada:"""

            llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022", temperature=0.2) # or claude-opus-4-7
            response = llm.invoke(prompt)
            new_draft = response.content.strip()
            
            job["draft"] = new_draft
            job["status"] = "aguardando_aprovacao"
            job["logs"].append("Refinamento concluído com sucesso com base no seu feedback! Aguardando nova revisão...")
        except Exception as e:
            job["status"] = "erro"
            job["logs"].append(f"❌ Erro ao processar feedback de refino: {str(e)}")

    background_tasks.add_task(re_run_qa)
    return {"status": "success"}

# --- ENDPOINTS DE GERENCIAMENTO DE CACHE ---

@router.get("/api/cache")
def get_all_cache():
    """Retorna todos os itens gravados no cache semântico local."""
    return load_cache()

@router.delete("/api/cache/{idx}")
def delete_cache_item(idx: int):
    """Deleta um item do cache semântico baseado no índice."""
    cache = load_cache()
    if idx < 0 or idx >= len(cache):
        raise HTTPException(status_code=404, detail="Índice de cache inválido.")
    deleted = cache.pop(idx)
    save_cache(cache)
    return {"status": "success", "deleted": deleted}

# --- RENDERIZADOR FRONTEND (HTML PRINCIPAL) ---

@router.get("/", response_class=HTMLResponse)
def index():
    """Renderiza a página principal do Dashboard Web Premium."""
    template_file = os.path.join(config.TEMPLATE_DIR, "index.html")
    if os.path.exists(template_file):
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Servidor Rodando. Dashboard em desenvolvimento.</h1>"
