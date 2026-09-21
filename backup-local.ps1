$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

$backupDirectory = Join-Path $PSScriptRoot "backups"
[IO.Directory]::CreateDirectory($backupDirectory) | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$output = Join-Path $backupDirectory "garage-plus-$stamp.sql"

$runningServices = @(docker compose ps --status running --services)
if ($LASTEXITCODE -ne 0 -or $runningServices -notcontains "db") {
    throw "La base locale n'est pas démarrée. Lancez d'abord start-garage.cmd."
}

$dump = docker compose exec -T db pg_dump -U ets ets_safouene
if ($LASTEXITCODE -ne 0) { throw "La sauvegarde PostgreSQL a échoué." }
[IO.File]::WriteAllLines($output, $dump, [Text.UTF8Encoding]::new($false))
Write-Host "Sauvegarde créée : $output" -ForegroundColor Green
