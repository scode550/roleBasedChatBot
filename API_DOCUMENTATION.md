# API Documentation

This document provides details on the API endpoints for the Multi-Role RAG Chatbot backend.

**Base URL:** `http://127.0.0.1:8000`

---

## 1. Start a New Chat Session

Uploads one or more documents, processes them into a vector knowledge base, and creates a new chat session associated with a specific role.

-   **Endpoint:** `POST /upload`
-   **Method:** `POST`

### Request Format

-   **Content-Type:** `multipart/form-data`
-   **Form Data:**
    -   `role` (string, **required**): The role for the chat session. Must be one of `["Product Lead", "Tech Lead", "Compliance Lead", "Bank Alliance Lead"]`.
    -   `files` (file, **required**): One or more files to be uploaded. Allowed types: `.pdf`, `.txt`, `.csv`.

### Success Response (`200 OK`)

Returns a JSON object containing the new session's metadata.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    {
      "chat_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "filenames": [
        "document1.pdf",
        "notes.txt"
      ],
      "role": "Product Lead"
    }
    ```

### Error Response (`500 Internal Server Error`)

Returns an error detail if the file processing or database insertion fails.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    {
      "detail": "Error message describing the failure."
    }
    ```

---

## 2. Get All Past Chats

Retrieves a list of metadata for all previously created chat sessions, ordered from newest to oldest.

-   **Endpoint:** `GET /chats`
-   **Method:** `GET`

### Request Format

-   No parameters or body required.

### Success Response (`200 OK`)

Returns a JSON array of chat session metadata objects.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    [
      {
        "chat_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "filenames": ["document1.pdf", "notes.txt"],
        "role": "Product Lead"
      },
      {
        "chat_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef1",
        "filenames": ["tech_spec.pdf"],
        "role": "Tech Lead"
      }
    ]
    ```

---

## 3. Send a Message

Sends a new user message to an existing chat session and receives a generated response from the RAG pipeline.

-   **Endpoint:** `POST /chat`
-   **Method:** `POST`

### Request Format

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    {
      "chat_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "message": "What is the monthly limit for secondary users?"
    }
    ```

### Success Response (`200 OK`)

Returns the generated answer and a list of source documents used to create the answer.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    {
      "answer": "The maximum transaction limit per month for secondary users is **₹15,000**.",
      "sources": [
        {
          "source_file": "UPI Circle.pdf",
          "doc_type": "finance",
          "doc_type_score": 0.9876
        }
      ]
    }
    ```

### Error Responses

-   **`404 Not Found`**: If the provided `chat_id` does not exist.
    ```json
    {
      "detail": "Chat session not found."
    }
    ```
-   **`500 Internal Server Error`**: If an error occurs during the RAG pipeline processing.
    ```json
    {
      "detail": "An error occurred while processing your request."
    }
    ```

---

## 4. Get Chat History

Retrieves the full conversation history (all user and assistant messages) for a specific chat session.

-   **Endpoint:** `GET /history/{chat_id}`
-   **Method:** `GET`

### Request Format

-   **Path Parameter:**
    -   `chat_id` (string, **required**): The unique identifier for the chat session.

### Success Response (`200 OK`)

Returns a JSON array of all messages in the conversation.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    [
      {
        "role": "user",
        "content": "What is the monthly limit for secondary users?"
      },
      {
        "role": "assistant",
        "content": "The maximum transaction limit per month for secondary users is **₹15,000**.",
        "sources": [
          {
            "source_file": "UPI Circle.pdf",
            "doc_type": "finance",
            "doc_type_score": 0.9876
          }
        ]
      }
    ]
    ```

### Error Response (`404 Not Found`)

Returns an error if the provided `chat_id` does not exist.

-   **Content-Type:** `application/json`
-   **Body:**
    ```json
    {
      "detail": "Chat history not found."
    }
    ```