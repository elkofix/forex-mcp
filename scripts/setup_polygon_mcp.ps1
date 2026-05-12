param(
    [string]$RepoDir = "mcp_polygon",
    [string]$RepoUrl = "https://github.com/polygon-io/mcp_polygon.git"
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "No se encontro el comando requerido: $Name"
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $false)][string[]]$Args = @()
    )

    & $Command @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el comando: $Command $($Args -join ' ')"
    }
}

Assert-Command git

$root = Get-Location
$target = Join-Path $root $RepoDir

if (-not (Test-Path $target)) {
    Write-Host "Clonando $RepoUrl en $target ..."
    git clone $RepoUrl $target
} else {
    Write-Host "Repositorio existente detectado en $target. Actualizando..."
    Push-Location $target
    try {
        git pull --ff-only
    } finally {
        Pop-Location
    }
}

Push-Location $target
try {
    if (Test-Path "package.json") {
        Assert-Command node
        if (Test-Path "pnpm-lock.yaml") {
            Assert-Command pnpm
            Write-Host "Instalando dependencias MCP con pnpm..."
            Invoke-CheckedCommand -Command "pnpm" -Args @("install")
            Invoke-CheckedCommand -Command "pnpm" -Args @("run", "build")
        } else {
            Assert-Command npm
            Write-Host "Instalando dependencias MCP con npm..."
            Invoke-CheckedCommand -Command "npm" -Args @("install")
            Invoke-CheckedCommand -Command "npm" -Args @("run", "build")
        }
    } elseif (Test-Path "pyproject.toml") {
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-Host "Configurando MCP Python con uv sync..."
            Invoke-CheckedCommand -Command "uv" -Args @("sync")
        } else {
            Assert-Command python
            Write-Host "uv no esta instalado. Configurando MCP Python con pip editable..."
            Invoke-CheckedCommand -Command "python" -Args @("-m", "pip", "install", "-e", ".")
        }
    } else {
        throw "No se detecto estructura MCP compatible (sin package.json ni pyproject.toml)."
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Preparacion finalizada."
Write-Host '1) Configura tu API key: $env:POLYGON_API_KEY="tu_api_key"'
Write-Host "2) Ejecuta el servidor: ./scripts/run_polygon_mcp.ps1"
