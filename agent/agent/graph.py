import asyncio
import json
import os
from typing import Any, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, create_model

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


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


class MCPStdioClient:
    """Cliente MCP mínimo por stdio (sin dependencias externas)."""

    def __init__(self, command: str, args: list[str], env: dict[str, str]) -> None:
        self.command = command
        self.args = args
        self.env = env
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._proc:
            return

        merged_env = os.environ.copy()
        merged_env.update({k: v for k, v in self.env.items() if v})

        self._proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        await self.request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "forex-mcp-agent", "version": "0.1.0"},
            },
        )
        await self.notify("notifications/initialized", {})

    async def close(self) -> None:
        if not self._proc:
            return
        self._proc.terminate()
        await self._proc.wait()
        self._proc = None

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._write_message(payload)

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        async with self._lock:
            self._request_id += 1
            rid = self._request_id
            payload = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": method,
                "params": params,
            }
            await self._write_message(payload)
            response = await self._read_message()

        if response.get("id") != rid:
            raise RuntimeError("Respuesta MCP fuera de orden")
        if "error" in response:
            raise RuntimeError(f"MCP error {response['error']}")
        return response.get("result")

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list", {})
        return result.get("tools", []) if isinstance(result, dict) else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self.request("tools/call", {"name": name, "arguments": arguments})

    async def _write_message(self, payload: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("Proceso MCP no inicializado")
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self._proc.stdin.write(body + b"\n")
        await self._proc.stdin.drain()

    async def _read_message(self) -> dict[str, Any]:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("Proceso MCP no inicializado")

        line = await self._proc.stdout.readline()
        if not line:
            stderr_content = ""
            if self._proc.stderr:
                try:
                    stderr_bytes = await asyncio.wait_for(self._proc.stderr.read(), timeout=1.0)
                    stderr_content = stderr_bytes.decode("utf-8")
                except Exception as e:
                    stderr_content = f"(No se pudo leer stderr: {e})"
            raise RuntimeError(f"Servidor MCP cerró stdout. Stderr:\n{stderr_content}")
        return json.loads(line.decode("utf-8"))


def retrieve_context(inputs: dict) -> str:
    """Recupera contexto desde pgvector (si está disponible)."""
    rag_enabled = os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes", "y"}
    if not rag_enabled:
        print("DEBUG RAG: RAG está deshabilitado.", flush=True)
        return ""

    try:
        from .retriever import get_retriever
        retriever = get_retriever()
        print(f"DEBUG RAG: Buscando en pgvector con la consulta: '{inputs['question']}'", flush=True)
        docs = retriever.invoke(inputs["question"])
        print(f"DEBUG RAG: Se encontraron {len(docs)} documentos relevantes.", flush=True)
        context = "\n\n".join(
            [
                f"[category={d.metadata.get('category','unknown')}]\n{d.page_content}"
                for d in docs
                if getattr(d, "page_content", None)
            ]
        )
        return context
    except Exception as e:
        import traceback
        print(f"❌ DEBUG RAG: Error al recuperar contexto RAG: {e}", flush=True)
        traceback.print_exc()
        return ""



def format_history(inputs: dict) -> list:
    """Convierte el historial de diccionarios a objetos Message."""
    messages = []
    for turn in inputs.get("history", []):
        messages.append(HumanMessage(content=turn["human"]))
        messages.append(AIMessage(content=turn["ai"]))
    return messages


def _schema_to_model(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
    required = set(input_schema.get("required", [])) if isinstance(input_schema, dict) else set()
    fields: dict[str, tuple[Any, Any]] = {}

    for name, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        description = spec.get("description", "")
        default = ... if name in required else None
        json_type = spec.get("type")
        py_type: Any = Any
        if json_type == "string":
            py_type = str
        elif json_type == "number":
            py_type = float
        elif json_type == "integer":
            py_type = int
        elif json_type == "boolean":
            py_type = bool
        elif json_type == "object":
            py_type = dict[str, Any]
        elif json_type == "array":
            py_type = list[Any]
        fields[name] = (py_type, Field(default=default, description=description))

    if not fields:
        fields = {
            "input": (
                str,
                Field(
                    default="",
                    description="Entrada textual para la herramienta MCP",
                ),
            )
        }

    model_name = f"MCP_{tool_name.replace('-', '_')}"
    return create_model(model_name, **fields)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: str


class FinancialAgent:
    """Agente financiero con RAG transparente y herramientas MCP opcionales."""

    def __init__(self) -> None:
        self.llm = _build_llm()
        self.llm_with_tools = None
        self.base_chain = self._build_base_chain()
        self.react_agent = None
        self.mcp_client: MCPStdioClient | None = None

    def _build_base_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT + "\n\nContexto (RAG):\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])
        return (
            RunnablePassthrough.assign(
                context=retrieve_context,
                chat_history=format_history,
            )
            | prompt
            | self.llm
            | StrOutputParser()
        )

    async def initialize(self) -> None:
        if not _as_bool("MCP_ENABLED", True):
            return

        command = os.getenv("MCP_SERVER_COMMAND", "mcp_massive").strip()
        args = os.getenv("MCP_SERVER_ARGS", "").strip().split()
        env_vars = {
            "POLYGON_API_KEY": os.getenv("POLYGON_API_KEY", ""),
            "MASSIVE_API_KEY": os.getenv("MASSIVE_API_KEY", os.getenv("POLYGON_API_KEY", "")),
        }

        try:
            self.mcp_client = MCPStdioClient(command=command, args=args, env=env_vars)
            await self.mcp_client.start()
            tools_info = await self.mcp_client.list_tools()
            tools = await self._build_mcp_tools(tools_info)
            if tools:
                self.llm_with_tools = self.llm.bind_tools(tools)
                
                # Grafo de decisión personalizado
                workflow = StateGraph(AgentState)
                workflow.add_node("retrieve", self._retrieve_node)
                workflow.add_node("agent", self._call_model_node)
                workflow.add_node("tools", ToolNode(tools))

                workflow.add_edge(START, "retrieve")
                workflow.add_edge("retrieve", "agent")
                workflow.add_conditional_edges(
                    "agent",
                    self._should_continue,
                    {
                        "tools": "tools",
                        END: END,
                    }
                )
                workflow.add_edge("tools", "agent")
                self.react_agent = workflow.compile()
        except Exception as e:
            import traceback
            print(f"❌ Error al inicializar MCP Client: {e}", flush=True)
            traceback.print_exc()
            self.react_agent = None
            self.mcp_client = None

    async def _retrieve_node(self, state: AgentState) -> dict[str, Any]:
        last_human_msg = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_human_msg = msg
                break
        question = last_human_msg.content if last_human_msg else ""
        context = retrieve_context({"question": question})
        return {"context": context}

    async def _call_model_node(self, state: AgentState) -> dict[str, Any]:
        import datetime
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        
        context_str = state.get("context", "")
        system_content = (
            SYSTEM_PROMPT
            + f"\n\nATENCIÓN: La fecha actual es {current_date}. Usa esta fecha como referencia para el día de hoy.\n\n"
            + "\n\nContexto (RAG):\n"
            + (context_str if context_str else "Sin contexto adicional.")
            + "\n\nSi necesitas datos de mercado en tiempo real o historicos, usa herramientas MCP."
        )
        system_message = SystemMessage(content=system_content)
        
        model_messages = [system_message] + list(state["messages"])
        response = await self.llm_with_tools.ainvoke(model_messages)
        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    async def _build_mcp_tools(self, tools_info: list[dict[str, Any]]) -> list[StructuredTool]:
        built_tools: list[StructuredTool] = []
        if not self.mcp_client:
            return built_tools

        for tool_info in tools_info:
            name = tool_info.get("name")
            if not name:
                continue
            description = tool_info.get("description", f"MCP tool: {name}")
            input_schema = tool_info.get("inputSchema", {})
            args_schema = _schema_to_model(name, input_schema)

            async def _call_tool(_name=name, **kwargs):
                result = await self.mcp_client.call_tool(_name, kwargs)
                return json.dumps(result, ensure_ascii=True)

            built_tools.append(
                StructuredTool.from_function(
                    name=name,
                    description=description,
                    args_schema=args_schema,
                    coroutine=_call_tool,
                )
            )

        return built_tools

    async def answer(self, question: str, history: list[dict], config: dict | None = None) -> str:
        if self.react_agent:
            messages = format_history({"history": history}) + [HumanMessage(content=question)]
            result = await self.react_agent.ainvoke(
                {"messages": messages, "context": ""},
                config=config,
            )
            out_messages = result.get("messages", []) if isinstance(result, dict) else []
            for msg in reversed(out_messages):
                if isinstance(msg, AIMessage) and getattr(msg, "content", None):
                    return msg.content
            return "No se obtuvo respuesta del agente con MCP."

        return await self.base_chain.ainvoke(
            {"question": question, "history": history},
            config=config,
        )


def build_graph():
    """Mantiene el nombre para compatibilidad con app.py."""
    return FinancialAgent()
