"""
incremental_update.py — Met à jour SEULEMENT les fichiers modifiés dans Chroma,
au lieu de tout réindexer. Appelé par la GitHub Action à chaque push.

Usage: python incremental_update.py changed_files.txt

changed_files.txt contient des lignes du type (sortie de `git diff --name-status`) :
    M	src/auth.py
    A	src/new_file.py
    D	src/old_file.py
"""

import sys
import os
import base64
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import configu

from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core import Document, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

Settings.embed_model = HuggingFaceEmbedding(model_name=configu.EMBED_MODEL_NAME)

EXT_TO_LANG = {".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java"}
TEXT_EXTS = [".md", ".txt"]


def get_ext(path: str) -> str:
    return "." + path.split(".")[-1]


def char_idx_to_line(text: str, char_idx: int) -> int:
    return text[:char_idx].count("\n") + 1


def fetch_file_content(path: str) -> str | None:
    """Récupère le contenu d'un fichier via l'API GitHub (contenu à jour, branche main)."""
    token = os.getenv("GITHUB_TOKEN_RAG") or configu.GITHUB_TOKEN
    url = f"https://api.github.com/repos/{configu.REPO_OWNER}/{configu.REPO_NAME}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params={"ref": configu.BRANCH}, timeout=20)
    if not resp.ok:
        print(f"  -> impossible de récupérer {path} ({resp.status_code})")
        return None
    data = resp.json()
    if data.get("encoding") != "base64":
        return None
    return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")


def chunk_file(path: str, text: str):
    """Découpe un seul fichier en nodes, avec start_line/end_line dans les métadonnées."""
    ext = get_ext(path)
    doc = Document(text=text, metadata={"file_path": path, "file_name": path})

    if ext in EXT_TO_LANG:
        splitter = CodeSplitter(language=EXT_TO_LANG[ext], chunk_lines=40, chunk_lines_overlap=15)
    elif ext in TEXT_EXTS:
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    else:
        print(f"  -> extension {ext} non gérée, ignorée")
        return []

    nodes = splitter.get_nodes_from_documents([doc])
    for node in nodes:
        if node.start_char_idx is not None:
            node.metadata["start_line"] = char_idx_to_line(text, node.start_char_idx)
        if node.end_char_idx is not None:
            node.metadata["end_line"] = char_idx_to_line(text, node.end_char_idx)
    return nodes


def main():
    changed_files_txt = sys.argv[1]
    with open(changed_files_txt, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    chroma_client = chromadb.PersistentClient(path=configu.STORAGE_DIR)
    collection = chroma_client.get_or_create_collection(configu.CHROMA_COLLECTION_NAME)

    for line in lines:
        status, path = line.split("\t", 1)
        print(f"[{status}] {path}")

        collection.delete(where={"file_path": path})

        if status == "D":
            print(f"  -> fichier supprimé, chunks retirés de Chroma")
            continue

        text = fetch_file_content(path)
        if not text:
            continue

        nodes = chunk_file(path, text)
        if not nodes:
            continue

        embeddings = [Settings.embed_model.get_text_embedding(n.text) for n in nodes]
        collection.add(
            ids=[f"{path}::{i}" for i in range(len(nodes))],
            embeddings=embeddings,
            documents=[n.text for n in nodes],
            metadatas=[n.metadata for n in nodes],
        )
        print(f"  -> {len(nodes)} chunks mis à jour")

    print("Réindexation incrémentale terminée.")


if __name__ == "__main__":
    main()