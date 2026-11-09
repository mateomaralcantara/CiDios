# Recrea la base local (Windows / PowerShell) usando el contenedor de docker-compose.yml.
# Alternativa: python -m cdd.dbreset (desde apps/api). Uso (desde la raíz del repo):  .\scripts\db_reset_local.ps1            -> base "cdd"
#                                .\scripts\db_reset_local.ps1 cdd_test   -> base de pruebas
param([string]$DbName = "cdd")
$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)   # el SQL lleva tildes
$Root = Split-Path -Parent $PSScriptRoot

function Invoke-Psql([string]$Db, [string]$File = $null, [string[]]$Commands = @()) {
  $args = @("compose", "exec", "-T", "db", "psql", "-U", "postgres", "-d", $Db, "-v", "ON_ERROR_STOP=1", "-q")
  foreach ($c in $Commands) { $args += @("-c", $c) }
  if ($File) { Get-Content -Raw -Encoding UTF8 $File | docker @args } else { docker @args }
  if ($LASTEXITCODE -ne 0) { throw "psql falló ($Db $File)" }
}

Push-Location $Root
try {
  Invoke-Psql "postgres" -Commands @("drop database if exists `"$DbName`" with (force)", "create database `"$DbName`"")
  Invoke-Psql $DbName -File "supabase/tests/00_local_supabase_shim.sql"
  Get-ChildItem "supabase/migrations/*.sql" | Sort-Object Name | ForEach-Object {
    Write-Host "-> $($_.Name)"
    Invoke-Psql $DbName -File $_.FullName
  }
  Write-Host "Base $DbName lista."
} finally { Pop-Location }
