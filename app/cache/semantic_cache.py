# app/cache/semantic_cache.py
import os
import json
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from app.core import config

def load_cache() -> List[Dict[str, Any]]:
    """Carrega o cache local em formato JSON."""
    if not os.path.exists(os.path.dirname(config.CACHE_FILE)):
        os.makedirs(os.path.dirname(config.CACHE_FILE))
    if os.path.exists(config.CACHE_FILE):
        try:
            with open(config.CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_cache(cache_data: List[Dict[str, Any]]):
    """Salva a lista de cache no arquivo local."""
    with open(config.CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def check_semantic_cache(inquiry: str) -> Dict[str, Any] | None:
    """
    Verifica de forma semântica se uma pergunta semelhante já existe no cache local.
    Usa o Claude Haiku para comparar significados com altíssima velocidade e baixo custo.
    """
    cache = load_cache()
    if not cache:
        return None
        
    # Prepara a lista de perguntas atualmente salvas no cache
    cache_list = "\n".join([f"{idx}. {item['query']}" for idx, item in enumerate(cache)])
    
    prompt = f"""Você é um validador de cache semântico de alta precisão para suporte ao cliente.
Dada a nova pergunta do cliente: "{inquiry}"

E a lista de perguntas respondidas anteriormente no cache (com seus respectivos números de índice):
{cache_list}

Determine se a nova pergunta possui EXATAMENTE o mesmo significado, intenção e assunto de alguma pergunta da lista do cache (mesmo se estiver escrita de forma ligeiramente diferente ou refraseada com sinônimos).
- Se houver uma correspondência semântica clara e 100% segura, responda APENAS com o número correspondente do índice (ex: se corresponder ao item 0, responda apenas "0").
- Se não houver nenhuma correspondência segura ou se o assunto for diferente, responda APENAS "MISS".

Resposta final:"""

    try:
        # Usamos o Claude Haiku que é extremamente barato, veloz e ideal para classificação semântica
        llm = ChatAnthropic(model_name="claude-3-haiku-20240307", temperature=0.0)
        response = llm.invoke(prompt)
        ans = response.content.strip()
        if ans.isdigit():
            idx = int(ans)
            if 0 <= idx < len(cache):
                print(f"[Cache] Cache Hit Semantico encontrado no indice {idx}!")
                return cache[idx]
    except Exception as e:
        print(f"[Cache] Erro ao verificar cache semantico: {e}")
    return None
