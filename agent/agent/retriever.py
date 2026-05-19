# retriever.py — RAG con pgvector
# ══════════════════════════════════════════════════════════════
# ESTADO: PENDIENTE DE IMPLEMENTACIÓN
#
# Este módulo se encargará de:
# 1. Conectarse a PostgreSQL con pgvector (postgres-rag)
# 2. Recibir una query del usuario
# 3. Generar el embedding de la query con OpenAI
# 4. Buscar los chunks más similares en la base de datos
# 5. Retornar el contexto relevante al agente
#
# Se integrará con graph.py reemplazando el nodo "retrieve"
# que actualmente está comentado.
# ══════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return value


def get_vectorstore() -> PGVector:
    """Crea un vectorstore PGVector apuntando a postgres-rag."""

    connection_string = _env("DATABASE_URL")
    collection_name = os.getenv("RAG_COLLECTION", "financial_reports")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()

    if embedding_provider == "openai":
        _env("OPENAI_API_KEY")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        embeddings = OpenAIEmbeddings(model=embedding_model)
    else:
        # Google por defecto
        _env("GOOGLE_API_KEY")
        embedding_model = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-2-preview")
        embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)

    return PGVector(
        connection_string=connection_string,
        embedding_function=embeddings,
        collection_name=collection_name,
    )


def get_retriever(k: int | None = None):
    """Retorna un retriever conectado a pgvector con filtro de score threshold.

    Requiere que antes se haya corrido la ingesta en `agent/ingest/ingest.py`.
    """

    k_final = k or int(os.getenv("RAG_K", "5"))
    threshold = float(os.getenv("RAG_SCORE_THRESHOLD", "0.65"))
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "score_threshold": threshold,
            "k": k_final
        }
    )

