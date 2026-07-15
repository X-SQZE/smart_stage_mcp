from llama_index.readers.github import GithubRepositoryReader, GithubClient
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core import VectorStoreIndex, Settings
import config
import os
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

os.environ["GOOGLE_API_KEY"] = config.GEMINI_API_KEY
Settings.embed_model = HuggingFaceEmbedding(model_name=config.EMBED_MODEL_NAME)
Settings.llm = GoogleGenAI(model=config.LLM_MODEL_NAME, api_key=config.GEMINI_API_KEY)

github_client = GithubClient(github_token=config.GITHUB_TOKEN)

reader = GithubRepositoryReader(
    github_client=github_client,
    owner=config.REPO_OWNER,
    repo=config.REPO_NAME,
    filter_file_extensions=(config.REQUIRED_EXTS, GithubRepositoryReader.FilterType.INCLUDE),
    filter_directories=(config.EXCLUDE_DIRS, GithubRepositoryReader.FilterType.EXCLUDE),
)

documents = reader.load_data(branch=config.BRANCH)
print(f"{len(documents)} fichiers récupérés")

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
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

import time
index = VectorStoreIndex(all_nodes)

index.storage_context.persist(persist_dir=config.STORAGE_DIR)
print("Index sauvegardé dans", config.STORAGE_DIR)



#--------------------------------
for i, node in enumerate(response.source_nodes):
    content = node.node.get_content()
    print(f"Chunk {i+1}: {len(content.splitlines())} lignes")