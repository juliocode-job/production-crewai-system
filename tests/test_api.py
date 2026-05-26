# test_api.py
import urllib.request
import urllib.parse
import json
import time
import sys

def safe_print(text):
    if not text:
        return
    # Determina o encoding correto do terminal ou cai para utf-8
    encoding = sys.stdout.encoding or "utf-8"
    try:
        # Codifica e decodifica ignorando/substituindo caracteres incompatíveis
        encoded = text.encode(encoding, errors="replace").decode(encoding)
        sys.stdout.write(encoded + "\n")
    except Exception:
        # Fallback supremo para ASCII puro caso tudo falhe
        sys.stdout.write(text.encode("ascii", errors="replace").decode("ascii") + "\n")
    sys.stdout.flush()

def main():
    url_inquiry = "http://127.0.0.1:8000/api/inquiry"
    
    # Pergunta nova para evitar cache e forçar processamento dos agentes
    inquiry_text = (
        "Olá! Gostaria de saber se o SDK de suporte possui compatibilidade com Python 3.8. "
        "Como realizo a configuração inicial do SDK? Meu e-mail é novo_teste_otel@dominio.com."
    )
    
    data = json.dumps({"inquiry": inquiry_text}).encode("utf-8")
    req = urllib.request.Request(
        url_inquiry, 
        data=data, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    safe_print("=== Enviando Inquiry para a API ===")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            safe_print(f"Resposta da API: {res_json}")
            job_id = res_json.get("job_id")
            cache_hit = res_json.get("cache_hit")
    except Exception as e:
        safe_print(f"Erro ao enviar pergunta para a API: {e}")
        sys.exit(1)
        
    if cache_hit:
        safe_print("=== Cache Hit! O resultado foi retornado imediatamente. ===")
        get_status(job_id)
        return
        
    safe_print(f"=== Cache Miss! Executando a Crew (Job ID: {job_id}) ===")
    
    printed_logs = set()
    last_status = None
    
    while True:
        status_data = get_status_data(job_id)
        if not status_data:
            safe_print("Não foi possível obter dados do status.")
            time.sleep(3)
            continue
            
        status = status_data.get("status")
        logs = status_data.get("logs", [])
        
        # Print new logs
        for log in logs:
            if log not in printed_logs:
                safe_print(f"[LOG] {log}")
                printed_logs.add(log)
                
        if status != last_status:
            safe_print(f"[STATUS] Transição de estado: {last_status} -> {status}")
            last_status = status
            
        if status in ["aguardando_aprovacao", "concluido", "erro"]:
            safe_print(f"\n=== Job Finalizado com status: {status} ===")
            if status == "aguardando_aprovacao":
                safe_print("Rascunho de resposta gerado com sucesso!")
                safe_print("\n--- RASCUNHO GERADO ---")
                safe_print(status_data.get("draft"))
                safe_print("-----------------------\n")
                
                # Vamos aprovar o job automaticamente para simular a ação humana
                approve_job(job_id)
            elif status == "erro":
                safe_print("Erro na execução:")
                safe_print(status_data.get("final_response") or "Erro sem detalhes adicionais.")
            break
            
        time.sleep(3)

def get_status_data(job_id):
    url_status = f"http://127.0.0.1:8000/api/status/{job_id}"
    try:
        with urllib.request.urlopen(url_status) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except Exception as e:
        safe_print(f"Erro ao obter status: {e}")
        return None

def get_status(job_id):
    data = get_status_data(job_id)
    if data:
        safe_print(f"Status atual: {data.get('status')}")
        safe_print(f"Logs: {data.get('logs')}")
        safe_print(f"Resposta Final: {data.get('final_response')}")

def approve_job(job_id):
    url_approve = f"http://127.0.0.1:8000/api/approve/{job_id}"
    req = urllib.request.Request(url_approve, method="POST")
    safe_print(f"=== Aprovando o Job {job_id} (Human-in-the-Loop) ===")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            safe_print(f"Resposta da Aprovação: {json.loads(res_body)}")
    except Exception as e:
        safe_print(f"Erro ao aprovar o job: {e}")

if __name__ == "__main__":
    main()
