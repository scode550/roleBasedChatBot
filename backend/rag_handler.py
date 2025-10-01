import torch
import logging
import chromadb
import fitz  
import csv
from sentence_transformers import SentenceTransformer, CrossEncoder
from llama_cpp import Llama
from huggingface_hub import hf_hub_download
import json
import os
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- MODEL AND CLIENT INITIALIZATION ---
llm = None
embedding_model = None
classification_pipeline = None
ner_pipeline = None
chroma_client = None
reranker_model = None

# --- Detailed, one-time role descriptions for the LLM Router ---
ROLE_DESCRIPTIONS = {
    "Product Lead": "Focuses on product features, business strategy, user experience, market requirements, user limits, transaction rules, and delegation of product-related authority. They are concerned with the 'what' and 'why' of the product.",
    "Tech Lead": "Focuses on technical implementation, system architecture, API performance, database queries, code snippets, software bugs, and infrastructure stability. They are concerned with the 'how' of the product's engineering.",
    "Compliance Lead": "Focuses on regulatory adherence, legal standards, risk management, financial compliance (like KYC), audit procedures, and data privacy. They ensure the product operates within legal and ethical boundaries.",
    "Bank Alliance Lead": "Focuses on relationships with partner banks, partnership agreements, Service Level Agreements (SLAs), and the business/technical integration with financial partners."
}

try:
    # Using the Llama 3 8B model from QuantFactory
    logging.info("Initializing Llama 3 8B LLM from QuantFactory. This may trigger a one-time download (~4.7 GB)...")

    model_repo_id = "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
    model_file_name = "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"

    model_path = hf_hub_download(repo_id=model_repo_id, filename=model_file_name)

    llm = Llama(
        model_path=model_path,
        n_gpu_layers=0,      # Force CPU
        n_ctx=8192,          # Context window size
        chat_format="llama-3" # Use the built-in chat format for Llama 3
    )
    logging.info("Llama 3 8B LLM initialized successfully.")
    
    # --- Other models are initialized as before ---
    logging.info("Initializing Reranker model (cross-encoder/ms-marco-MiniLM-L-6-v2)...")
    reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)

    logging.info("Initializing Embedding model (BAAI/bge-base-en-v1.5)...")
    embedding_model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    logging.info("Initializing ChromaDB client...")
    chroma_client = chromadb.PersistentClient(path="./chroma_db")

    logging.info("All supporting models and clients initialized successfully.")

except Exception as e:
    logging.error(f"FATAL: Error during model or client initialization: {e}", exc_info=True)
    exit()


def check_relevance_with_llm(question: str, current_role: str) -> Dict[str, Any]:
    if current_role not in ROLE_DESCRIPTIONS:
        return {"is_relevant": True, "reason": "Role not found."}

    messages = [
        {"role": "system", "content": "You are an expert dispatcher. Your task is to identify the SINGLE most relevant role for the user's question from the list. Respond with only the role title."},
        {"role": "user", "content": f"Role Descriptions:\n- Product Lead: {ROLE_DESCRIPTIONS['Product Lead']}\n- Tech Lead: {ROLE_DESCRIPTIONS['Tech Lead']}\n- Compliance Lead: {ROLE_DESCRIPTIONS['Compliance Lead']}\n- Bank Alliance Lead: {ROLE_DESCRIPTIONS['Bank Alliance Lead']}\n\nUser's Question: \"{question}\"\n\nBased on the question, which role is most relevant?"}
    ]
    
    response = llm.create_chat_completion(messages=messages, max_tokens=20, temperature=0.0)
    predicted_role = response['choices'][0]['message']['content'].strip()
    
    logging.info(f"LLM Router classified question for role: '{predicted_role}'")

    if predicted_role == current_role:
        return {"is_relevant": True}
    else:
        reason = f"This question seems outside the scope of a {current_role}."
        if predicted_role in ROLE_DESCRIPTIONS:
            reason += f" It seems better suited for a **{predicted_role}**."
        return {"is_relevant": False, "reason": reason}

def rewrite_query_for_role(question: str, role: str) -> str:
    logging.info(f"Original query: '{question}'")
    messages = [
        {"role": "system", "content": "You are an expert query rewriter. Your task is to rewrite the user's query to be specific to their professional role, making it ideal for a semantic database search. Respond with ONLY the rewritten query text and nothing else."},
        {"role": "user", "content": f"User's Role: {role}\nOriginal Question: \"{question}\"\n\nRewritten Query:"}
    ]
    
    response = llm.create_chat_completion(messages=messages, max_tokens=100, temperature=0.0)
    rewritten_query = response['choices'][0]['message']['content'].strip().replace('"', '')
    logging.info(f"Rewritten query for retrieval: '{rewritten_query}'")
    return rewritten_query

def query_rag_pipeline(question: str, collection_name: str, role: str, chat_history: List[Dict]) -> Dict[str, Any]:
    if not all([llm, embedding_model, chroma_client, reranker_model]):
        raise ConnectionError("Core models not initialized.")

    relevance_check = check_relevance_with_llm(question, role)
    if not relevance_check["is_relevant"]:
        return {"answer": relevance_check["reason"], "sources": []}

    enhanced_query = rewrite_query_for_role(question, role)

    collection = chroma_client.get_collection(name=collection_name)
    question_embedding = embedding_model.encode(enhanced_query).tolist()
    
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=10,
        include=['documents', 'metadatas']
    )
    
    retrieved_docs = results['documents'][0] if results['documents'] else []
    if not retrieved_docs:
        return {"answer": "I could not find relevant information in the uploaded documents to answer your question.", "sources": []}

    rerank_pairs = [[enhanced_query, doc] for doc in retrieved_docs]
    rerank_scores = reranker_model.predict(rerank_pairs)
    reranked_results = sorted(zip(rerank_scores, results['metadatas'][0], retrieved_docs), reverse=True)
    final_metadatas = [meta for score, meta, doc in reranked_results[:4]]
    final_docs = [doc for score, meta, doc in reranked_results[:4]]

    context_parts = []
    for meta, doc in zip(final_metadatas, final_docs):
        context_parts.append(f"Source Document: '{meta['source_file']}'\nContent Snippet: {doc}")
    context = "\n---\n".join(context_parts)

    system_prompt = f"""You are a precise, factual assistant acting as a {role}. Your task is to answer the user's question based *only* on the provided context. Follow these rules strictly:
1.  **Reasoning for 'What If':** If the user asks a hypothetical 'what if' question, use the facts from the context to reason about the scenario and provide a step-by-step explanation for your conclusion.
2.  **Be Direct:** For factual questions, directly answer the question. Do not provide long explanations or summarize the entire source document.
3.  **Use Formatting:** Structure your answer with bullet points (*) and bold text (**) to highlight key information.
4.  **Stay in Context:** If the answer is not in the provided context, you must respond with "Based on the provided documents, I cannot answer that question."
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"CONTEXT SNIPPETS:\n---\n{context}\n---\n\nQUESTION: \"{question}\"\n\nANSWER:"}
    ]
    
    response = llm.create_chat_completion(messages=messages, max_tokens=512, temperature=0.1)
    answer = response['choices'][0]['message']['content']

    used_sources = []
    seen_files = set()
    for source in final_metadatas:
        if source['source_file'] not in seen_files:
            used_sources.append({
                'source_file': source['source_file'],
                'doc_type': source.get('doc_type', 'N/A'),
                'doc_type_score': source.get('doc_type_score')
            })
            seen_files.add(source['source_file'])

    return {"answer": answer, "sources": used_sources}


def classify_document(text: str) -> Dict[str, Any]:
    global classification_pipeline
    if classification_pipeline is None:
        from transformers import pipeline
        classification_pipeline = pipeline("text-classification", model="ProsusAI/finbert")
    result = classification_pipeline(text[:512], top_k=1)[0]
    return {"label": result['label'], "score": float(result['score'])}

def process_documents_and_create_collection(files: list, collection_name: str):
    if not all([chroma_client, embedding_model]): raise ConnectionError("Core services not initialized.")
    all_chunks, all_metadatas, all_ids = [], [], []
    doc_id_counter = 0
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    for file_path in files:
        original_filename = os.path.basename(file_path).split(f"{collection_name}_", 1)[1]
        doc_id_counter += 1
        text = ""
        try:
            file_extension = os.path.splitext(original_filename)[1].lower()
            if file_extension == ".pdf":
                with fitz.open(file_path) as doc: text = "".join(page.get_text("text") for page in doc)
            elif file_extension == ".txt":
                with open(file_path, 'r', encoding='utf-8') as f: text = f.read()
            elif file_extension == ".csv":
                with open(file_path, 'r', encoding='utf-8', newline='') as f: text = "\n".join([", ".join(row) for row in csv.reader(f)])
            else: continue
        except Exception as e: raise ValueError(f"Could not read file {original_filename}. Error: {e}")
        if not text.strip(): continue

        classification_result = classify_document(text)
        chunks = text_splitter.split_text(text)
        for chunk_idx, chunk in enumerate(chunks, start=1):
            chunk_id = f"doc{doc_id_counter}_chunk{chunk_idx}"
            all_chunks.append(chunk)
            all_metadatas.append({
                'doc_type': classification_result['label'],
                'doc_type_score': classification_result['score'],
                'source_file': original_filename
            })
            all_ids.append(chunk_id)

    if not all_chunks: raise ValueError("No text could be extracted from the provided documents.")
    collection = chroma_client.get_or_create_collection(name=collection_name)
    if collection.count() > 0: collection.delete(ids=collection.get(include=[])['ids'])
    embeddings = embedding_model.encode(all_chunks, show_progress_bar=True).tolist()
    collection.add(embeddings=embeddings, documents=all_chunks, metadatas=all_metadatas, ids=all_ids)