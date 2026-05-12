# Asesor Financiero AI

Agente de IA experto en asesoramiento financiero y mercados con interfaz de chat, observabilidad completa y soporte multi-proveedor LLM. Todo corre en Docker Compose.

## Funcionalidades principales

- **Asesoramiento Financiero** — Análisis de mercados, finanzas personales y gestión de riesgos.
- **Forex y Trading** — Integración potencial con noticias de mercado (ej. FXStreet) y cotizaciones.
- **Análisis de Datos** — Evaluación técnica y de sentimiento para estrategias de inversión.

## Stack

| Componente | Tecnología |
|---|---|
| Chat UI | Chainlit 1.3.2 |
| Motor del agente | LangGraph 0.2.39 |
| LLM (OpenAI) | gpt-4o-mini via langchain-openai |
| LLM (Groq) | llama-3.3-70b-versatile via langchain-groq |
| Observabilidad | Langfuse v3 |
| RAG (pendiente) | pgvector + PostgreSQL 16 |
| Almacenamiento eventos | ClickHouse 24.3 + MinIO |

## Requisitos

- Docker y Docker Compose
- Una API key de OpenAI **o** Groq (gratuito)

## Inicio rápido

**1. Editar el archivo de entorno `.env` existente:**

Editar `.env` con el proveedor LLM elegido:

```env
# Opción A — OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Opción B — Groq (gratuito, obtener key en console.groq.com)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

**2. Levantar los servicios:**

```bash
docker compose up -d
```

**3. Esperar a que ClickHouse inicialice (~2-3 min):**

```bash
docker compose logs -f langfuse-web
# Esperar el mensaje "Ready"
```

**4. Configurar Langfuse (observabilidad):**

Abrir http://localhost:3000 y seguir estos pasos en orden:

1. Hacer clic en **Sign up** e ingresar cualquier email y contraseña (es local, no se valida)
2. En la pantalla **Create organization**, escribir un nombre (ej. `aws-agent-org`) y confirmar
3. En la pantalla **Create project**, escribir un nombre (ej. `aws-cert-agent`) y confirmar
4. En el panel del proyecto, ir a **Settings** (menú lateral izquierdo, abajo)
5. Ir a la sección **API Keys** y hacer clic en **Create new API key**
6. Copiar el **Public Key** (`pk-lf-...`) y el **Secret Key** (`sk-lf-...`)
7. Pegar las claves en `.env`:
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
8. Reiniciar el agente para que tome las nuevas variables:
   ```bash
   docker compose restart agent
   ```

**5. Abrir el chat:**

```
http://localhost:8000
```

## URLs

| Servicio | URL |
|---|---|
| Chat del agente | http://localhost:8000 |
| Langfuse (observabilidad) | http://localhost:3000 |
| MinIO console (opcional) | http://localhost:9090 |
| PostgreSQL RAG | localhost:5432 |

## Estructura del proyecto

```
aws-cert-agent/
├── docker-compose.yml
├── .env                        # Variables de entorno (no en git)
├── clickhouse/
│   └── config.xml              # ClickHouse Keeper integrado (requerido por Langfuse v3)
└── agent/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                  # Entry point Chainlit
    ├── agent/
    │   ├── graph.py            # LangGraph — nodo LLM + soporte multi-proveedor
    │   ├── retriever.py        # RAG con pgvector (pendiente)
    │   └── prompts.py          # System prompt del agente AWS
    └── ingest/
        └── ingest.py           # Ingestión de documentos (pendiente)
```

## Cambiar proveedor LLM

Editar `.env` y reiniciar:

```bash
# Cambiar a Groq
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile   # opcional, es el valor por defecto

docker compose restart agent
```

El mensaje de bienvenida del chat indica el proveedor activo.

## Integracion MCP de Polygon

Se incorpora una integracion formal para consumir datos de mercado mediante el servidor MCP oficial de Polygon, ejecutado localmente por STDIO y conectable desde clientes como Claude Desktop o Cursor.

Nota de compatibilidad: el repositorio oficial mantiene compatibilidad con `POLYGON_API_KEY`, pero actualmente el servidor se distribuye como `mcp_massive` (Python).

### Objetivo

Esta integracion habilita consultas de mercado en tiempo real e historicas (acciones, forex, crypto, noticias e indicadores) desde prompts de lenguaje natural, delegando la obtencion de datos al servidor MCP de Polygon.

### Requisitos

- API key valida de Polygon
- Node.js 18+ (solo para variantes Node)
- Python 3.12+ y `uv` (ruta recomendada del repo oficial actual)
- Un cliente MCP (Claude Desktop, Cursor u otro compatible)

### Preparacion automatizada (Windows PowerShell)

El repositorio incluye un script de preparacion:

```powershell
./scripts/setup_polygon_mcp.ps1
```

El script:
- clona o actualiza el repositorio oficial en `./mcp_polygon`
- detecta automaticamente si el servidor MCP es Node o Python
- instala dependencias segun el tipo detectado (`npm`/`pnpm`, o `uv`/`pip`)

### Ejecucion local del servidor MCP

Con el proyecto ya preparado:

```powershell
$env:POLYGON_API_KEY="tu_api_key"
./scripts/run_polygon_mcp.ps1
```

Nota: el servidor MCP en STDIO debe ejecutarse como proceso hijo del cliente MCP. El script de ejecucion se provee para validacion local y depuracion.

El script `run_polygon_mcp.ps1` soporta dos escenarios:
- `dist/index.js` (repos Node)
- `pyproject.toml` con `mcp_massive` (repos Python actuales)

### Configuracion de Cursor

Se incluye plantilla en `.cursor/mcp.json.example`. Para uso local:

1. copiar `.cursor/mcp.json.example` a `.cursor/mcp.json`
2. reemplazar `tu_api_key` por la clave real
3. ajustar la ruta de `dist/index.js` si se utiliza una ubicacion distinta

### Configuracion de Claude Desktop (Windows)

Usar la estructura documentada en `docs/mcp/polygon.md` y registrar el servidor en:

```txt
%APPDATA%\Claude\claude_desktop_config.json
```

### Variables de entorno

- `POLYGON_API_KEY`: credencial de acceso a Polygon
- `MASSIVE_API_KEY`: variable principal usada por versiones actuales de `mcp_massive` (recomendado definir ambas con el mismo valor)
- `POLYGON_MCP_PATH`: ruta local del repositorio `mcp_polygon`

### Integracion directa en el agente LangChain

El agente de `agent/agent/graph.py` ya integra MCP por STDIO y expone herramientas del servidor al modelo (con fallback automatico al modo LCEL base si MCP no inicia).

Variables recomendadas en `.env`:

```env
MCP_ENABLED=true
MCP_SERVER_COMMAND=mcp_massive
MCP_SERVER_ARGS=
POLYGON_API_KEY=tu_api_key
MASSIVE_API_KEY=tu_api_key
```

Con esto, al iniciar Chainlit, el agente intentara levantar el proceso MCP y utilizar tools de mercado durante la inferencia.

## RAG — Implementado (pgvector)

El RAG ya está implementado con **PostgreSQL + pgvector**. Flujo:
1) pones tus documentos en `agent/docs/` → 2) corres la ingesta → 3) el agente recupera chunks y los inyecta como contexto.

### 1) ¿Dónde pongo mis 3 documentos?

Colócalos dentro de `agent/docs/` en la carpeta que corresponda a la certificación:

```
agent/docs/cloud-practitioner/
agent/docs/security-specialty/
agent/docs/ml-specialty/
```

Se soportan `.pdf`, `.txt` y `.md`.

### 2) Ejecutar ingesta

Recomendado (borra y recrea la colección para evitar duplicados):

```bash
docker compose exec agent python ingest/ingest.py --reset
```

### 3) Variables útiles

- `RAG_ENABLED` (default: `true`) — si lo pones en `false`, el agente responde sin RAG.
- `RAG_COLLECTION` (default: `aws_certifications`) — nombre de colección.
- `RAG_K` (default: `5`) — cantidad de chunks recuperados por pregunta.
- `EMBEDDING_MODEL` (default: `text-embedding-3-small`).

Nota: **los embeddings del RAG usan OpenAI**, así que aunque uses `LLM_PROVIDER=groq`, para la ingesta/búsqueda necesitas `OPENAI_API_KEY`.

## Comandos útiles

```bash
# Ver estado de todos los contenedores
docker compose ps

# Logs del agente
docker compose logs -f agent

# Reiniciar solo el agente (tras cambios en .env)
docker compose restart agent

# Detener todo
docker compose down

# Detener y eliminar volúmenes (reset completo)
docker compose down -v
```

## Notas técnicas

- `sqlalchemy==2.0.35` — langchain-community 0.3.7 es incompatible con 2.0.36
- `pydantic>=2.6.0,<2.10.0` — chainlit 1.3.2 es incompatible con pydantic 2.10+
- `clickhouse/config.xml` monta ClickHouse Keeper integrado, requerido por las migraciones de Langfuse v3 (`ReplicatedMergeTree ON CLUSTER default`)
- `CLICKHOUSE_MIGRATION_URL` usa el protocolo nativo (`clickhouse://`) no HTTP
