# app.py — Entry point Chainlit
import chainlit as cl
from agent.graph import build_graph
from langfuse.callback import CallbackHandler
import os

graph = build_graph()


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])
    provider = os.getenv("LLM_PROVIDER", "openai").upper()
    await cl.Message(
        content=(
            f"👋 ¡Hola! Soy tu asistente experto Analista Financiero. *(usando {provider})*\n\n"
            "Puedo ayudarte con:\n"
            "- 📈 **Análisis de Mercados** (Acciones, tendencias macroeconómicas)\n"
            "- 📑 **Reportes Financieros** (Métricas corporativas, balances, 10-K)\n"
            "- 💼 **Estrategia y Portafolio** (Diversificación, ETFs)\n\n"
            "¿Qué datos o activos quieres analizar hoy?"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("history", [])

    # Soporta tanto LANGFUSE_HOST como LANGFUSE_BASE_URL
    langfuse_host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")

    langfuse_handler = CallbackHandler(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=langfuse_host,
    )

    response_message = cl.Message(content="")
    await response_message.send()

    full_response = ""

    async for chunk in graph.astream(
        {"question": message.content, "history": history},
        config={"callbacks": [langfuse_handler]},
    ):
        # En la versión pura de LangChain (LCEL) enviamos un string stream (o un chunk)
        # por lo que no es necesario el chequeo ["llm"]["answer"]
        if isinstance(chunk, str):
            await response_message.stream_token(chunk)
            full_response += chunk
        elif hasattr(chunk, "content"):
            # A veces langchain retorna Message chunks
            await response_message.stream_token(chunk.content)
            full_response += chunk.content

    await response_message.update()

    history.append({"human": message.content, "ai": full_response})
    cl.user_session.set("history", history)
