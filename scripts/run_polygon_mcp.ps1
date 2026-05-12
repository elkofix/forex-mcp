param(
    [string]$RepoDir = "mcp_polygon",
    [string]$ApiKey = ""
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "No se encontro el comando requerido: $Name"
    }
}

$root = Get-Location
$target = Join-Path $root $RepoDir
$entrypoint = Join-Path $target "dist/index.js"
$pyproject = Join-Path $target "pyproject.toml"

if (-not (Test-Path $target)) {
    throw "No existe el directorio '$RepoDir'. Ejecuta primero ./scripts/setup_polygon_mcp.ps1"
}

if ($ApiKey) {
    $env:POLYGON_API_KEY = $ApiKey
}

if (-not $env:POLYGON_API_KEY) {
    throw "La variable POLYGON_API_KEY no esta definida. Usa -ApiKey o exportala en el entorno."
}

if (-not $env:MASSIVE_API_KEY) {
    $env:MASSIVE_API_KEY = $env:POLYGON_API_KEY
}

if (Test-Path $entrypoint) {
    Assert-Command node
    Write-Host "Iniciando Polygon MCP server (Node/STDIO)..."
    Write-Host "Repositorio: $target"
    node $entrypoint
    return
}

if (Test-Path $pyproject) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Host "Iniciando Polygon MCP server (Python/uv/STDIO)..."
        Write-Host "Repositorio: $target"
        uv --directory $target run mcp_massive
        return
    }

    Assert-Command mcp_massive
    Write-Host "Iniciando Polygon MCP server (Python script/STDIO)..."
    Write-Host "Repositorio: $target"
    mcp_massive
    return
}

throw "No se encontro ni dist/index.js ni pyproject.toml en $target. Revisa el repositorio MCP clonado."
