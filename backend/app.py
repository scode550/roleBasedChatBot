import streamlit as st
import requests
import json
from typing import List, Dict

# --- Configuration ---
FASTAPI_URL = "http://127.0.0.1:8000"
ROLES = ["Product Lead", "Tech Lead", "Compliance Lead", "Bank Alliance Lead"]

# --- State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_id" not in st.session_state:
    st.session_state.chat_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "past_chats" not in st.session_state:
    st.session_state.past_chats = []

# --- API Functions ---
def get_past_chats():
    try:
        response = requests.get(f"{FASTAPI_URL}/chats")
        response.raise_for_status()
        st.session_state.past_chats = response.json()
    except requests.exceptions.RequestException:
        st.sidebar.error("Failed to connect to backend.")
        st.session_state.past_chats = []

def load_chat_history(chat_id: str):
    try:
        response = requests.get(f"{FASTAPI_URL}/history/{chat_id}")
        response.raise_for_status()
        st.session_state.messages = response.json()
        st.session_state.chat_id = chat_id
        for chat in st.session_state.past_chats:
            if chat['chat_id'] == chat_id:
                st.session_state.role = chat['role']
                break
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to load history: {e}")

# --- UI Helper Functions ---
def display_assistant_message(message: Dict):
    st.markdown(message["content"])

    if message.get("sources"):
        with st.expander("Sources", expanded=False):
            for s in message["sources"]:
                score_info = ""
                if s.get("doc_type_score") is not None:
                    score_info = f" (Type: *{s.get('doc_type', 'N/A')}* - Confidence: {s['doc_type_score']:.2%})"
                st.markdown(f"- **{s['source_file']}**{score_info}")

# --- Sidebar UI ---
with st.sidebar:
    st.header("Chatbot Setup")

    def reset_chat():
        st.session_state.messages = []
        st.session_state.chat_id = None
        st.session_state.role = None
        if 'file_uploader_key' not in st.session_state:
            st.session_state.file_uploader_key = 0
        st.session_state.file_uploader_key += 1

    st.button("➕ New Chat", on_click=reset_chat, use_container_width=True)

    is_chat_active = st.session_state.chat_id is not None
    selected_role = st.radio("Choose your role:", options=ROLES, key="role_selection", disabled=is_chat_active)

    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["pdf", "txt", "csv"],
        accept_multiple_files=True,
        disabled=is_chat_active,
        key=f"file_uploader_{st.session_state.get('file_uploader_key', 0)}"
    )

    if st.button("Upload & Start Chat", use_container_width=True, disabled=(not uploaded_files or is_chat_active)):
        with st.spinner("Processing documents... This may take a moment."):
            try:
                files_for_upload = [("files", (file.name, file.getvalue(), file.type)) for file in uploaded_files]
                response = requests.post(
                    f"{FASTAPI_URL}/upload",
                    data={"role": selected_role},
                    files=files_for_upload,
                    timeout=600
                )
                response.raise_for_status()
                result = response.json()
                reset_chat()
                st.session_state.chat_id = result['chat_id']
                st.session_state.role = result['role']
                get_past_chats()
                st.rerun()
            except requests.exceptions.RequestException as e:
                error_detail = "Could not connect to the backend."
                if e.response:
                    error_detail = e.response.json().get('detail', 'Unknown error from server.')
                st.error(f"Upload failed: {error_detail}")

    st.divider()
    st.subheader("Past Chats")
    if not st.session_state.past_chats: get_past_chats()
    for chat in st.session_state.past_chats:
        filenames_str = ", ".join(chat['filenames'])
        if len(filenames_str) > 40:
            filenames_str = filenames_str[:37] + "..."
        label = f"**{chat['role']}**: {filenames_str}"
        if st.button(label, key=chat['chat_id'], use_container_width=True):
            load_chat_history(chat['chat_id'])

# --- Main Chat Interface ---
st.title(f"Multi-Stakeholder RAG Chatbot")
if st.session_state.role: st.caption(f"Chatting as: **{st.session_state.role}**")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            display_assistant_message(message)

if prompt := st.chat_input("Ask a question..."):
    if not st.session_state.chat_id:
        st.error("Please start a new chat by uploading documents first.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(
                        f"{FASTAPI_URL}/chat",
                        json={"chat_id": st.session_state.chat_id, "message": prompt}
                    )
                    response.raise_for_status()
                    assistant_response = response.json()

                    message_data = {
                        "role": "assistant",
                        "content": assistant_response["answer"],
                        "sources": assistant_response["sources"],
                    }
                    st.session_state.messages.append(message_data)

                    display_assistant_message(message_data)

                except requests.exceptions.RequestException as e:
                    error_detail = "Could not connect to the backend."
                    if e.response:
                         error_detail = e.response.json().get('detail', 'Unknown error from server.')
                    st.error(f"Failed to get response: {error_detail}")