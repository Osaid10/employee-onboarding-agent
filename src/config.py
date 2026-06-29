"""Project configuration and environment setup."""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration (Google Gemini)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-flash-latest")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
POLICIES_DIR = os.path.join(DATA_DIR, "policies")
EMPLOYEES_DIR = os.path.join(DATA_DIR, "employees")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
DB_PATH = os.path.join(BASE_DIR, "hris.db")
CHECKPOINT_DB = os.path.join(BASE_DIR, "checkpoint_db.sqlite")

# Thresholds
MAX_REMINDERS_BEFORE_ESCALATION = 2
URGENT_DAYS_THRESHOLD = 3
