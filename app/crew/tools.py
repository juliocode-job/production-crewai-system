# app/crew/tools.py
from crewai.tools import tool

# Base de dados simulada contendo as políticas reais da empresa
KNOWLEDGE_BASE = {
    "reembolso": """
=== POLÍTICA OFICIAL DE REEMBOLSO E DEVOLUÇÃO ===
- Prazo de Desistência: O cliente tem o direito de solicitar o reembolso total do valor pago em até 7 dias corridos após a data de compra, conforme o Código de Defesa do Consumidor.
- Processamento: Uma vez aprovado o reembolso pela equipe financeira, o estorno na fatura do cartão de crédito ou o PIX de devolução será processado em até 5 dias úteis.
- Compras após 7 dias: Não são permitidos reembolsos para compras efetuadas há mais de 7 dias. Nesses casos, o suporte pode oferecer uma extensão gratuita de 30 dias na assinatura atual ou um cupom de 20% de desconto para novos produtos como cortesia de satisfação.
- Assinaturas Anuais: O cancelamento de planos anuais após 7 dias interrompe a renovação automática para o próximo ano, mas não dá direito a reembolso proporcional do período restante.
""",
    "instalacao": """
=== GUIA DE INSTALAÇÃO DO CUSTOMER SUPPORT SDK (PYTHON/NODE) ===
- Requisitos: Python 3.8+ ou Node.js 16+.
- Passo 1 (Instalação): Execute o comando no seu terminal:
  `pip install customer-support-sdk`
- Passo 2 (Configuração): Crie um arquivo `.env` na raiz do seu projeto e configure sua chave de API:
  `CUSTOMER_SUPPORT_API_KEY=sua_chave_aqui`
- Passo 3 (Código de Inicialização):
  ```python
  from support_sdk import CustomerSupportSDK
  
  # Inicialização do SDK
  sdk = CustomerSupportSDK(api_key="CUSTOMER_SUPPORT_API_KEY")
  sdk.start()
  ```
- Solução de Problemas Comuns:
  - Erro 403 (Forbidden / ConnectionError): Significa que a chave de API configurada no arquivo `.env` é inválida, está expirada ou foi bloqueada por falta de pagamento. Verifique se não há espaços adicionais ou aspas ao redor da chave no arquivo `.env`.
  - Erro de Conexão no Worker: Verifique se sua rede permite conexões outbound na porta 443 para o domínio `api.support-sdk.com`.
""",
    "geral": """
=== INFORMAÇÕES GERAIS E HORÁRIOS DE ATENDIMENTO ===
- Horário de Funcionamento: Segunda a Sexta-feira, das 09:00 às 18:00 (Horário de Brasília).
- Clientes Enterprise: Possuem SLA de atendimento de 24/7 com suporte dedicado via canal Slack exclusivo e telefone de emergência.
- Clientes Standard/Pro: Tempo médio de primeira resposta é de até 4 horas úteis.
- Contato Oficial: suporte@suaempresa.com.br ou portal help.suaempresa.com.br.
"""
}

@tool("DocsSearchTool")
def search_docs(query: str) -> str:
    """Busca informações oficiais na base de conhecimento interna para responder a dúvidas de suporte técnico, reembolsos e informações gerais da empresa."""
    query_lower = query.lower()
    
    results = []
    
    # Busca por correspondência de palavras-chave
    if any(word in query_lower for word in ["reembolso", "devolução", "dinheiro", "cancelar", "cancelamento", "estorno", "compra", "pagamento"]):
        results.append(KNOWLEDGE_BASE["reembolso"])
        
    if any(word in query_lower for word in ["instalar", "instalacao", "sdk", "python", "node", "configurar", "configuracao", "erro", "403", "forbidden", "connection", "setup"]):
        results.append(KNOWLEDGE_BASE["instalacao"])
        
    # Se não houver correspondências específicas ou para enriquecer o contexto, traz informações gerais
    if not results or any(word in query_lower for word in ["suporte", "horas", "horario", "empresa", "ajuda", "contato", "atendimento"]):
        results.append(KNOWLEDGE_BASE["geral"])
        
    return "\n\n".join(results) if results else "Nenhum documento específico encontrado para essa busca. Por favor, tente termos como 'reembolso' ou 'instalação'."
