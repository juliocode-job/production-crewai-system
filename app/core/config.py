# app/core/config.py
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env na raiz do projeto
load_dotenv()

# Anthropic API Config
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Langfuse API Config
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

# Base Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_FILE = os.path.join(DATA_DIR, "semantic_cache.json")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Database and Security Config
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'customer_support.db')}"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "customer-support-crew-super-secret-key-123456789")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day
