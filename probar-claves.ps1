# Comprueba todas las claves de CIENCIA Y DIOS (Supabase, Gemini, OpenAlex, repositorios y API).
# Uso, desde cualquier carpeta:
#   powershell -ExecutionPolicy Bypass -File C:\Users\martin\Desktop\VSC\BestS\cidios-app\probar-claves.ps1
$ErrorActionPreference = "Stop"
$api = Join-Path $PSScriptRoot "apps\api"
$py = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "No existe $py. Crea el entorno: cd $api ; python -m venv .venv ; .\.venv\Scripts\pip install -e '.[dev]'" -ForegroundColor Red
  exit 1
}
Push-Location $api
try { & $py -m cdd.check_keys; $code = $LASTEXITCODE } finally { Pop-Location }
exit $code

