from dotenv import load_dotenv
import os

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

REPO_OWNER = "slmxx"
REPO_NAME = "EverGreenfinal"
BRANCH = "main"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
LLM_MODEL_NAME = "models/gemini-3-flash-preview"
STORAGE_DIR = "./llamaindex_pipeline/storage"
REQUIRED_EXTS = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".md", ".txt"]
EXCLUDE_DIRS = ["node_modules", ".git", "venv", "__pycache__"]
