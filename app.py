"""Streamlit interface for the Compass RAG chatbot."""

import os
from uuid import uuid4

import streamlit as st
from langchain_core.messages import HumanMessage

from rag_chatbot.config import get_settings
from rag_chatbot.graph import build_graph

st.set_page_config(page_title="Compass", page_icon="🧭", layout="centered")

st.markdown(
    """
    <style>
    :root { --ink:#111827; --muted:#667085; --line:#e4e7ec; --accent:#2563eb; }
    .stApp { background:#f8fafc; }
    .block-container { max-width:820px; padding-top:2.25rem; }
    [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] .block-container { padding-top:1.6rem; }
    .brand { display:flex; align-items:center; gap:.7rem; margin-bottom:1.75rem; }
    .brand-mark { display:grid; place-items:center; width:2.25rem; height:2.25rem;
        border-radius:.7rem; color:#fff; background:#111827; font-size:1.15rem; }
    .brand-name { color:var(--ink); font-size:1.05rem; font-weight:750; }
    .brand-subtitle { color:var(--muted); font-size:.76rem; }
    .status-row { display:flex; justify-content:space-between; align-items:center;
        padding:.7rem 0; color:#344054; font-size:.84rem; border-bottom:1px solid #f2f4f7; }
    .status-dot { display:inline-block; width:.48rem; height:.48rem; margin-right:.4rem;
        border-radius:50%; background:#12b76a; }
    [data-testid="stSidebar"] .stButton>button { min-height:2.6rem; color:#fff;
        background:#111827; border:0; border-radius:.65rem; font-weight:650; }
    [data-testid="stSidebar"] .stButton>button:hover { color:#fff; background:#344054; }
    .page-header { margin:.2rem 0 2rem; }
    .page-kicker { color:var(--accent); font-size:.76rem; font-weight:750;
        letter-spacing:.08em; text-transform:uppercase; margin-bottom:.55rem; }
    .page-header h1 { color:var(--ink); font-size:2rem; line-height:1.2;
        letter-spacing:-.035em; margin:0; }
    .page-header p { color:var(--muted); font-size:1rem; line-height:1.6;
        margin:.65rem 0 0; }
    .section-label { color:#344054; font-size:.8rem; font-weight:650; margin:0 0 .55rem; }
    [data-testid="stHorizontalBlock"] .stButton>button { min-height:5.2rem;
        padding:.9rem 1rem; color:#344054; background:#fff; border:1px solid var(--line);
        border-radius:.8rem; font-weight:550; text-align:left;
        box-shadow:0 1px 2px rgba(16,24,40,.03); }
    [data-testid="stHorizontalBlock"] .stButton>button:hover { color:var(--accent);
        border-color:#b2ccff; background:#f9fbff; transform:translateY(-1px); }
    [data-testid="stChatMessage"] { padding:.85rem 1rem; margin-bottom:.75rem;
        background:#fff; border:1px solid var(--line); border-radius:.85rem;
        box-shadow:0 1px 2px rgba(16,24,40,.025); }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background:#eff6ff; border-color:#dbeafe; }
    [data-testid="stChatInput"] { background:#fff; border:1px solid #d0d5dd;
        border-radius:.8rem; box-shadow:0 4px 16px rgba(16,24,40,.08); }
    [data-testid="stExpander"] { margin-top:.65rem; background:#fcfcfd;
        border:1px solid var(--line); border-radius:.7rem; }
    .route-label { display:inline-flex; align-items:center; margin-top:.35rem;
        padding:.22rem .55rem; color:#175cd3; background:#eff8ff;
        border-radius:999px; font-size:.72rem; font-weight:650; }
    .footer { padding:2.4rem 0 .5rem; color:#98a2b3; text-align:center; font-size:.74rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_graph():
    """Build one graph instance while Streamlit is running."""
    return build_graph(get_settings())


def reset_chat() -> None:
    st.session_state.thread_id = str(uuid4())
    st.session_state.chat_history = []


def source_details(document) -> dict[str, str | int | None]:
    return {
        "source": document.metadata.get("source", "Unknown source"),
        "page": document.metadata.get("page"),
        "namespace": document.metadata.get("namespace", "Unknown"),
        "content": document.page_content,
    }


def render_route(namespaces: list[str]) -> None:
    st.markdown(
        f'<span class="route-label">Searched&nbsp;·&nbsp;{", ".join(namespaces)}</span>',
        unsafe_allow_html=True,
    )


def render_sources(sources: list[dict]) -> None:
    with st.expander(f"View {len(sources)} retrieved sources"):
        for number, source in enumerate(sources, start=1):
            page = f" · page {source['page']}" if source["page"] else ""
            st.markdown(
                f"**{number}. {source['source']}{page}**  \n"
                f"Collection: `{source['namespace']}`"
            )
            st.caption(source["content"])
            if number < len(sources):
                st.divider()


if "thread_id" not in st.session_state:
    reset_chat()

settings = get_settings()

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">◈</div>
            <div><div class="brand-name">Compass</div>
            <div class="brand-subtitle">Knowledge assistant</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("＋  New conversation", use_container_width=True):
        reset_chat()
        st.rerun()
    st.markdown("##### Workspace")
    st.markdown(
        """
        <div class="status-row"><span>HR policies</span><span><i class="status-dot"></i>Ready</span></div>
        <div class="status-row"><span>Technical docs</span><span><i class="status-dot"></i>Ready</span></div>
        <div class="status-row"><span>Compliance</span><span><i class="status-dot"></i>Ready</span></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("&nbsp;", unsafe_allow_html=True)
    st.caption(f"Model · {settings.chat_model}")
    st.caption(f"Retrieval · {settings.retrieval_k} results per collection")
    credentials_ready = bool(os.getenv("GROQ_API_KEY") and os.getenv("PINECONE_API_KEY"))
    st.caption("● Services online" if credentials_ready else "○ Setup required")

st.markdown(
    """
    <header class="page-header">
        <div class="page-kicker">Company knowledge</div>
        <h1>How can I help?</h1>
        <p>Ask a question and Compass will find the most relevant information across your
        company policies and documentation.</p>
    </header>
    """,
    unsafe_allow_html=True,
)

suggested_question = None
if not st.session_state.chat_history:
    st.markdown('<div class="section-label">Try asking</div>', unsafe_allow_html=True)
    columns = st.columns(3)
    suggestions = (
        ("HR", "What is the parental leave policy?"),
        ("Technical", "How does API authentication work?"),
        ("Compliance", "What are the audit requirements?"),
    )
    for column, (label, prompt) in zip(columns, suggestions, strict=True):
        with column:
            if st.button(f"{label}\n\n{prompt}", key=f"suggestion-{label}"):
                suggested_question = prompt

for item in st.session_state.chat_history:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
        if item.get("namespaces"):
            render_route(item["namespaces"])
        if item.get("sources"):
            render_sources(item["sources"])

question = st.chat_input("Ask about HR, technical, or compliance...") or suggested_question
if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"), st.spinner("Finding the best sources..."):
        try:
            result = get_graph().invoke(
                {"messages": [HumanMessage(content=question)]},
                config={"configurable": {"thread_id": st.session_state.thread_id}},
            )
        except Exception as error:  # noqa: BLE001 - display backend failures in the UI
            st.error(f"Compass could not answer this question: {error}")
        else:
            answer = str(result["messages"][-1].content)
            namespaces = result["selected_namespaces"]
            sources = [source_details(document) for document in result["context"]]
            st.markdown(answer)
            render_route(namespaces)
            render_sources(sources)
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "namespaces": namespaces,
                    "sources": sources,
                }
            )

st.markdown(
    '<div class="footer">Answers are generated from your indexed company documents.</div>',
    unsafe_allow_html=True,
)
