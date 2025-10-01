# 🤖 Multi-Role RAG Chatbot

This project is an advanced, multi-stakeholder Retrieval-Augmented Generation (RAG) chatbot designed to answer role-specific questions based on uploaded documents. It features a sophisticated pipeline that ensures answers are contextually relevant, factually grounded, and reasoned, catering to four distinct professional roles: Product Lead, Tech Lead, Compliance Lead, and Bank Alliance Lead.

The system is built with a FastAPI backend for the AI logic and a Streamlit frontend for the user interface. All models, including the LLM, run locally on a CPU, ensuring data privacy and no reliance on external APIs.

---

## ✨ Features

-   **Multi-Role Context:** The chatbot understands the distinct context and semantics of four different professional roles.
-   **Intelligent Guardrail:** Uses a powerful LLM (**Llama 3 8B**) to act as an intelligent "router," ensuring questions are relevant to the selected role before processing.
-   **Semantic Query Transformation:** Rewrites user queries based on their role to perform highly contextual and accurate searches in the document knowledge base.
-   **Advanced RAG Pipeline:** Implements a full retrieve-and-rerank architecture for high-quality, fact-based answer generation.
-   **Reasoning Capabilities:** Capable of answering hypothetical "what if" questions by reasoning with the facts extracted from the documents.
-   **Local & Private:** All models are designed to run locally on a CPU, with no external API calls for the core logic.

---

## 🏛️ Architecture Overview

The pipeline processes each user query through a series of steps to ensure accuracy and relevance.

> **User Query** → **[1. Guardrail]** → **[2. Query Rewrite]** → **[3. Retrieval]** → **[4. Reranking]** → **[5. Generation]** → **Final Answer**

1.  **Guardrail (Role Relevance Check):** The **Llama 3 8B** model first checks if the user's question is relevant to their selected role by comparing it against detailed role descriptions.
2.  **Query Transformation:** The **Llama 3 8B** model rewrites the query to be specific to the role's context (e.g., "delegation" for a Product Lead becomes "delegation of financial authority").
3.  **Retrieval:** The rewritten query is converted into a vector embedding (**`bge-base-en-v1.5`**) and used to find the top 10 potentially relevant document chunks from the **ChromaDB** vector store.
4.  **Reranking:** A more powerful Cross-Encoder model (**`ms-marco-MiniLM-L-6-v2`**) re-evaluates the top 10 chunks and sorts them for true relevance, selecting the top 4.
5.  **Answer Generation:** The **Llama 3 8B** model receives the top 4 chunks and the original question. It then synthesizes a concise, formatted, and reasoned answer based *only* on the provided context.

---

## 🚀 Setup and Installation (Local)

Follow these steps to set up and run the project on your local machine.

### Prerequisites

-   Python 3.10+
-   An internet connection (for downloading models on the first run).

### Installation

1.  **Clone the repository and navigate into the `backend` directory:**
    ```bash
    git clone https://github.com/scode550/roleBasedChatBot.git
    cd roleBasedChatBot/backend
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use: venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

---

## 🏃 How to Run

You need to run the backend and frontend in **two separate terminals**.

1.  **Run the Backend (FastAPI):**
    Open a terminal in the `backend/` directory and run:
    ```bash
    uvicorn main:app --reload
    ```
    The API server will start on `http://127.0.0.1:8000`. Wait for the console to log that the Llama 3 8B model has been initialized. **This may take several minutes on the first run as the model (~4.7 GB) is downloaded.**

2.  **Run the Frontend (Streamlit):**
    Open a second terminal in the `backend/` directory and run:
    ```bash
    streamlit run app.py
    ```
    A new tab will open in your browser at `http://localhost:8501` with the chatbot interface.

---

## 🐳 Docker Setup (Backend Only)

You can also run the FastAPI backend as a Docker container.

### Build the Docker Image

From the `backend/` directory, run the build command:
```bash
docker build -t roleBasedChatBot .
```

Run the Docker Container
Run the container, mapping the port to your host machine:

```bash

docker run -p 8000:8000 roleBasedChatBot
```
The API will be accessible at http://127.0.0.1:8000. You can then run the Streamlit frontend locally (as described in the "How to Run" section) to connect to it.
