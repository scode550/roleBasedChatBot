import os
import uuid
import sqlite3
import json
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from rag_handler import (
    process_documents_and_create_collection,
    query_rag_pipeline,
    chroma_client
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.makedirs("documents", exist_ok=True)
os.makedirs("chroma_db", exist_ok=True)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_histories (
            chat_id TEXT PRIMARY KEY,
            filenames TEXT,
            role TEXT,
            history TEXT
        )
    """)
    conn.commit()
    conn.close()
    logging.info("SQLite database initialized.")

init_db()

class ChatMessage(BaseModel):
    chat_id: str; message: str

class ChatSessionMetadata(BaseModel):
    chat_id: str; filenames: List[str]; role: str

class SourceDetail(BaseModel):
    source_file: str
    doc_type: str
    doc_type_score: Optional[float] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceDetail]

@app.post("/upload")
async def upload_documents(role: str = Form(...), files: List[UploadFile] = File(...)):
    saved_files, filenames = [], []
    chat_id = str(uuid.uuid4())
    try:
        for file in files:
            unique_filename = f"{chat_id}_{file.filename}"
            file_path = os.path.join("documents", unique_filename)
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            saved_files.append(file_path)
            filenames.append(file.filename)

        process_documents_and_create_collection(files=saved_files, collection_name=chat_id)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_histories (chat_id, filenames, role, history) VALUES (?, ?, ?, ?)",
            (chat_id, json.dumps(filenames), role, json.dumps([]))
        )
        conn.commit()
        conn.close()
        return {"chat_id": chat_id, "filenames": filenames, "role": role}
    except Exception as e:
        logging.error(f"Upload failed: {e}", exc_info=True)
        for file_path in saved_files:
            if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chats", response_model=List[ChatSessionMetadata])
async def get_all_chat_sessions():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, filenames, role FROM chat_histories ORDER BY rowid DESC")
    results = cursor.fetchall()
    conn.close()
    return [{"chat_id": cid, "filenames": json.loads(fnames or '[]'), "role": r} for cid, fnames, r in results if r]

@app.post("/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatMessage):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT history, role FROM chat_histories WHERE chat_id = ?", (request.chat_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Chat session not found.")
    current_history, role = json.loads(result[0]), result[1]

    try:
        response_data = query_rag_pipeline(
            question=request.message,
            collection_name=request.chat_id,
            role=role,
            chat_history=current_history
        )

        history_entry = {
            "role": "assistant",
            "content": response_data["answer"],
            "sources": response_data["sources"],
        }

        current_history.append({"role": "user", "content": request.message})
        current_history.append(history_entry)

        cursor.execute("UPDATE chat_histories SET history = ? WHERE chat_id = ?", (json.dumps(current_history), request.chat_id))
        conn.commit()

        return ChatResponse(**response_data)

    except Exception as e:
        logging.error(f"Chat processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing your request.")
    finally:
        conn.close()

@app.get("/history/{chat_id}", response_model=List[dict])
async def get_chat_history(chat_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT history FROM chat_histories WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    if not result: raise HTTPException(status_code=404, detail="Chat history not found.")
    return json.loads(result[0])