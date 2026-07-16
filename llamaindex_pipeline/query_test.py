from llama_index.core import StorageContext, load_index_from_storage, Settings
import config
import sys
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.google_genai import GoogleGenAI
Settings.embed_model = HuggingFaceEmbedding(model_name=config.EMBED_MODEL_NAME)
Settings.llm = GoogleGenAI(model=config.LLM_MODEL_NAME, api_key=config.GEMINI_API_KEY)

storage_context = StorageContext.from_defaults(persist_dir=config.STORAGE_DIR)
index = load_index_from_storage(storage_context)

question = sys.argv[1] if len(sys.argv) > 1 else "Que fait ce projet ?"

query_engine = index.as_query_engine(similarity_top_k=4)
response = query_engine.query(question)

print("\n=== Réponse ===")
print(response)

print("\n=== Chunks utilisés ===")
for i, node in enumerate(response.source_nodes):
    content = node.node.get_content()
    print(f"\n--- Chunk {i+1} (score={node.score:.3f}) ---")
    print(f"Fichier : {node.node.metadata.get('file_path')}")
    print(f"Nombre de lignes : {len(content.splitlines())}")
    print(f"Contenu :\n{content}")