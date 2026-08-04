from llama_index.readers.github import GithubRepositoryReader, GithubClient
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb
import os
import configu

os.environ["GOOGLE_API_KEY"] = configu.GEMINI_API_KEY
Settings.embed_model = HuggingFaceEmbedding(model_name=configu.EMBED_MODEL_NAME)
Settings.llm = GoogleGenAI(model=configu.LLM_MODEL_NAME, api_key=configu.GEMINI_API_KEY)

github_client = GithubClient(github_token=configu.GITHUB_TOKEN)

reader = GithubRepositoryReader(
    github_client=github_client,
    owner=configu.REPO_OWNER,
    repo=configu.REPO_NAME,
    filter_file_extensions=(configu.REQUIRED_EXTS, GithubRepositoryReader.FilterType.INCLUDE),
    filter_directories=(configu.EXCLUDE_DIRS, GithubRepositoryReader.FilterType.EXCLUDE),
)

documents = reader.load_data(branch=configu.BRANCH)
print(f"{len(documents)} fichiers récupérés")

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",        # C++
    ".c": "c",            # C
    ".go": "go",          # Go
    ".rs": "rust",        # Rust
    ".php": "php",        # PHP
    ".rb": "ruby",        # Ruby
}
TEXT_EXTS = [".md", ".txt"]

def get_ext(doc):
    return "." + doc.metadata.get("file_path", "").split(".")[-1]

all_nodes = []

for ext, lang in EXT_TO_LANG.items():
    docs_for_lang = [d for d in documents if get_ext(d) == ext]
    if not docs_for_lang:
        continue
    splitter = CodeSplitter(language=lang, chunk_lines=40, chunk_lines_overlap=15)
    nodes = splitter.get_nodes_from_documents(docs_for_lang)
    all_nodes.extend(nodes)
    print(f"{len(docs_for_lang)} fichiers .{ext.strip('.')} -> {len(nodes)} chunks")

text_docs = [d for d in documents if get_ext(d) in TEXT_EXTS]
if text_docs:
    text_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    text_nodes = text_splitter.get_nodes_from_documents(text_docs)
    all_nodes.extend(text_nodes)
    print(f"{len(text_docs)} fichiers texte -> {len(text_nodes)} chunks")

print(f"{len(all_nodes)} chunks créés au total")


# Assigner des IDs cohérents avec incremental_update.py : "chemin::index_dans_le_fichier"
nodes_by_file: dict[str, list] = {}
for node in all_nodes:
    file_path = node.metadata.get("file_path", "unknown")
    nodes_by_file.setdefault(file_path, []).append(node)

for file_path, nodes in nodes_by_file.items():
    for i, node in enumerate(nodes):
        node.node_id = f"{file_path}::{i}"

# Écriture dans ChromaDB (cohérent avec incremental_update.py et mon_serveur.py)
chroma_client = chromadb.PersistentClient(path=configu.STORAGE_DIR)
chroma_collection = chroma_client.get_or_create_collection(configu.CHROMA_COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

chroma_client = chromadb.PersistentClient(path=configu.STORAGE_DIR)

# Supprime l'ancienne collection si elle existe, pour repartir propre
try:
    chroma_client.delete_collection(configu.CHROMA_COLLECTION_NAME)
    print(f"Ancienne collection '{configu.CHROMA_COLLECTION_NAME}' supprimée.")
except Exception:
    print("Aucune collection existante à supprimer (premier run).")

chroma_collection = chroma_client.get_or_create_collection(configu.CHROMA_COLLECTION_NAME)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex(all_nodes, storage_context=storage_context)
print("Index sauvegardé dans ChromaDB :", configu.STORAGE_DIR)