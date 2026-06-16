# Arranca el servidor de desarrollo de Villavo Rutas.
#   PS> ./run.ps1
$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No existe el entorno virtual. Crealo con:" -ForegroundColor Yellow
    Write-Host "  py -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt"
    exit 1
}
& $py -m uvicorn app.server:app --reload --port 8000
