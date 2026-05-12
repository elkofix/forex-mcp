# graph.py — Pure LangChain (LCEL)
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from .prompts import SYSTEM_PROMPT


def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0.2,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-1.5-pro"),
            temperature=0.2,
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        streaming=True,
    )


def retrieve_context(inputs: dict) -> str:
    """Recupera contexto desde pgvector (si está disponible)."""
    rag_enabled = os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes", "y"}
    if not rag_enabled:
        return ""

    try:
        from .retriever import get_retriever
        retriever = get_retriever()
        docs = retriever.invoke(inputs["question"])
        context = "\n\n".join(
            [
                f"[category={d.metadata.get('category','unknown')}]\n{d.page_content}"
                for d in docs
                if getattr(d, "page_content", None)
            ]
        )
        return context
    except Exception:
        return ""


def format_history(inputs: dict) -> list:
    """Convierte el historial de diccionarios a objetos Message."""
    messages = []
    for turn in inputs.get("history", []):
        messages.append(HumanMessage(content=turn["human"]))
        messages.append(AIMessage(content=turn["ai"]))
    return messages


def build_graph():
    """Construye y retorna una cadena LangChain (LCEL). 
    Se mantiene el nombre 'build_graph' para no romper app.py"""
    
    llm = _build_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\nContexto (RAG):\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    chain = (
        RunnablePassthrough.assign(
            context=retrieve_context,
            chat_history=format_history
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain
