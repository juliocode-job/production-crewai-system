# app/jobs/manager.py
from typing import Dict, Any
from app.crew.orchestrator import CustomerSupportCrew
from app.core.observability import flush_langfuse

# Banco de dados em memória para acompanhar as execuções (Jobs)
# Estados de status: "triando", "resolvendo", "auditando", "aguardando_aprovacao", "concluido", "erro"
ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}

def run_crew_job(job_id: str, sanitized_inquiry: str):
    """
    Executa a Crew em uma thread separada para não travar a API FastAPI.
    Atualiza dinamicamente o status e logs intermediários do job usando callbacks.
    Garante o envio da telemetria ao Langfuse (flush) ao fim do processo.
    """
    try:
        try:
            ACTIVE_JOBS[job_id]["status"] = "triando"
            ACTIVE_JOBS[job_id]["logs"].append("Iniciando triagem com Claude Haiku 4.5...")
            
            # Cria a função de callback dinamicamente vinculada ao job_id
            def job_step_callback(step_output):
                log_msg = "Agente realizando processamento intermediário..."
                if hasattr(step_output, 'thought') and step_output.thought:
                    log_msg = f"Pensamento: {step_output.thought}"
                elif hasattr(step_output, 'tool') and step_output.tool:
                    log_msg = f"Ferramenta: '{step_output.tool}' acionada com entrada: '{step_output.tool_input}'"
                
                ACTIVE_JOBS[job_id]["logs"].append(log_msg)
                
                # Atualiza o status visual com base no agente atual
                if "Router" in log_msg or "Triagem" in log_msg:
                    ACTIVE_JOBS[job_id]["status"] = "triando"
                elif "Support" in log_msg or "Docs" in log_msg:
                    ACTIVE_JOBS[job_id]["status"] = "resolvendo"
                elif "QA" in log_msg or "Qualidade" in log_msg:
                    ACTIVE_JOBS[job_id]["status"] = "auditando"

            # Inicializa a Crew com o nosso middleware (step_callback)
            support_crew_orchestrator = CustomerSupportCrew(step_callback=job_step_callback)
            crew_instance = support_crew_orchestrator.get_crew(customer_inquiry=sanitized_inquiry)
            
            # Inicia a execução da Crew de agentes
            ACTIVE_JOBS[job_id]["logs"].append("Buscando documentação de suporte e rascunhando resposta...")
            
            inputs = {"customer_inquiry": sanitized_inquiry}
            result = crew_instance.kickoff(inputs=inputs)
            
            # Extrai metadados gerados (opcionalmente)
            # O resultado do QA task (último) é o rascunho de resposta final revisado
            draft_response = result.raw if hasattr(result, 'raw') else str(result)
            
            ACTIVE_JOBS[job_id]["draft"] = draft_response
            ACTIVE_JOBS[job_id]["status"] = "aguardando_aprovacao"
            ACTIVE_JOBS[job_id]["logs"].append("Resposta de suporte gerada e revisada pelo Claude Opus 4.7! Aguardando aprovação humana...")
            
        except Exception as e:
            ACTIVE_JOBS[job_id]["status"] = "erro"
            ACTIVE_JOBS[job_id]["logs"].append(f"❌ Erro fatal na execução dos agentes: {str(e)}")
    finally:
        # Garante a transmissão imediata dos traces ao Langfuse Cloud ao encerrar a thread
        flush_langfuse()
