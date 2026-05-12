# Integracion MCP de Polygon

Este documento especifica el procedimiento recomendado para integrar el servidor MCP oficial de Polygon en entornos locales de desarrollo.

Nota: aunque la integracion se denomina Polygon, el repositorio oficial actual publica el servidor como `mcp_massive` (compatibilidad mantenida con `POLYGON_API_KEY`).

## 1. Preparacion del servidor MCP

En PowerShell (desde la raiz del proyecto):

```powershell
./scripts/setup_polygon_mcp.ps1
```

El proceso clona o actualiza el repositorio oficial y prepara dependencias.

## 2. Variables de entorno

Definir la clave API de Polygon en la sesion activa:

```powershell
$env:POLYGON_API_KEY="tu_api_key"
```

## 3. Ejecucion local para validacion

```powershell
./scripts/run_polygon_mcp.ps1
```

## 4. Integracion con Claude Desktop (Windows)

Archivo objetivo:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

Configuracion sugerida:

```json
{
  "mcpServers": {
    "polygon": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/ruta/absoluta/forex-mcp/mcp_polygon",
        "run",
        "mcp_massive"
      ],
      "env": {
        "POLYGON_API_KEY": "tu_api_key",
        "MASSIVE_API_KEY": "tu_api_key"
      }
    }
  }
}
```

Tras guardar cambios, reiniciar Claude Desktop.

## 5. Integracion con Cursor

Usar la plantilla incluida:

1. copiar `.cursor/mcp.json.example` a `.cursor/mcp.json`
2. ajustar la API key
3. verificar la ruta de `dist/index.js`

Configuracion base:

```json
{
  "mcpServers": {
    "polygon": {
      "command": "uv",
      "args": ["--directory", "./mcp_polygon", "run", "mcp_massive"],
      "env": {
        "POLYGON_API_KEY": "tu_api_key",
        "MASSIVE_API_KEY": "tu_api_key"
      }
    }
  }
}
```

## 6. Prompts de verificacion

- Precio actual de BTCUSD
- Velas de 1h de EURUSD de los ultimos 3 dias
- Noticias recientes de NVIDIA
- Tendencia SPY con EMA 20 y RSI
