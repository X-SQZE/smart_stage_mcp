from dotenv import load_dotenv
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
BRANCH = "main"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
LLM_MODEL_NAME = "models/gemini-3-flash-preview"
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
REQUIRED_EXTS = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".md", ".txt"]
EXCLUDE_DIRS = ["node_modules", ".git", "venv", "__pycache__", "llamaindex_pipeline"]
CHROMA_COLLECTION_NAME = "CodeX_Repo"