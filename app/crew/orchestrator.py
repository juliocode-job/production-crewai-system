# app/crew/orchestrator.py
import os
import yaml
from crewai import Agent, Crew, Process, Task, LLM
from app.core import config
from app.core.observability import get_langfuse_callbacks
from app.crew.tools import search_docs

class CustomerSupportCrew:
    """
    Orquestrador da Crew de Suporte ao Cliente.
    Carrega as configurações YAML, inicializa os modelos Claude e monta a Crew.
    """
    
    def __init__(self, step_callback=None):
        self.step_callback = step_callback
        
        # Carregar explicitamente as configurações de agentes e tarefas dos arquivos YAML na raiz
        agents_path = os.path.join(config.CONFIG_DIR, 'agents.yaml')
        with open(agents_path, 'r', encoding='utf-8') as f:
            self.agents_config = yaml.safe_load(f)
            
        tasks_path = os.path.join(config.CONFIG_DIR, 'tasks.yaml')
        with open(tasks_path, 'r', encoding='utf-8') as f:
            self.tasks_config = yaml.safe_load(f)
            
        # Configurar os modelos de LLM usando o LiteLLM nativo do CrewAI com Prompt Caching ativado
        # Adiciona o Callback Handler nativo do Langfuse obtido do módulo de observabilidade
        callbacks = get_langfuse_callbacks()

        self.haiku_llm = LLM(
            model="anthropic/claude-haiku-4-5",
            callbacks=callbacks,
            extra_headers={
                "anthropic-beta": "prompt-caching-2024-07-31"
            },
            model_kwargs={
                "cache_control": {"type": "ephemeral"}
            }
        )
        self.sonnet_llm = LLM(
            model="anthropic/claude-sonnet-4-6",
            callbacks=callbacks,
            extra_headers={
                "anthropic-beta": "prompt-caching-2024-07-31"
            },
            model_kwargs={
                "cache_control": {"type": "ephemeral"}
            }
        )
        self.opus_llm = LLM(
            model="anthropic/claude-opus-4-7",
            callbacks=callbacks,
            extra_headers={
                "anthropic-beta": "prompt-caching-2024-07-31"
            },
            model_kwargs={
                "cache_control": {"type": "ephemeral"}
            }
        )
        
    def inquiry_router(self) -> Agent:
        return Agent(
            config=self.agents_config['inquiry_router'],
            llm=self.haiku_llm,
            verbose=True,
            step_callback=self.step_callback
        )
        
    def support_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['support_agent'],
            llm=self.sonnet_llm,
            tools=[search_docs],
            verbose=True,
            step_callback=self.step_callback
        )
        
    def qa_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['qa_agent'],
            llm=self.opus_llm,
            verbose=True,
            step_callback=self.step_callback
        )
        
    def get_full_crew(self, customer_inquiry: str) -> Crew:
        """
        Monta e retorna a versão completa e robusta da Crew de suporte (Router + Support + QA Auditor).
        Ideal para dúvidas complexas, financeiras ou reclamações.
        """
        # 1. Tarefa de Triagem e Classificação
        routing_task = Task(
            config=self.tasks_config['routing_task'],
            agent=self.inquiry_router()
        )
        
        # 2. Tarefa de Resolução e busca na base de conhecimento
        resolution_task = Task(
            config=self.tasks_config['resolution_task'],
            agent=self.support_agent()
        )
        
        # 3. Tarefa de Auditoria de Qualidade e Segurança contra Prompt Injection
        qa_task = Task(
            config=self.tasks_config['qa_task'],
            agent=self.qa_agent()
        )
        
        return Crew(
            agents=[
                self.inquiry_router(),
                self.support_agent(),
                self.qa_agent()
            ],
            tasks=[
                routing_task,
                resolution_task,
                qa_task
            ],
            process=Process.sequential,
            verbose=True,
            memory=True,  # Ativa a memória semântica local
            tracing=True
        )

    def get_express_crew(self, customer_inquiry: str) -> Crew:
        """
        Monta e retorna uma versão expressa e rápida da Crew de suporte (Apenas Support Agent).
        Focada em velocidade extrema para dúvidas rotineiras e simples.
        """
        resolution_task = Task(
            config=self.tasks_config['resolution_task'],
            agent=self.support_agent()
        )
        
        return Crew(
            agents=[
                self.support_agent()
            ],
            tasks=[
                resolution_task
            ],
            process=Process.sequential,
            verbose=True,
            memory=True,  # Ativa a memória semântica local
            tracing=True
        )
        
    def get_crew(self, customer_inquiry: str) -> Crew:
        """
        Mantido para compatibilidade reversa com chamadas legadas do get_crew.
        """
        return self.get_full_crew(customer_inquiry)
