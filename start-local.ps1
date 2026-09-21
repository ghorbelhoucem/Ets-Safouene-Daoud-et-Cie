$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

function New-RandomHex([int] $Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return ([System.BitConverter]::ToString($buffer)).Replace("-", "").ToLowerInvariant()
}

function Read-Pin([string] $Label) {
    while ($true) {
        $secure = Read-Host "$Label (exactement 4 chiffres)" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $pin = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
        if ($pin -match '^\d{4}$') { return $pin }
        Write-Host "Le code doit contenir exactement 4 chiffres." -ForegroundColor Yellow
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop n'est pas installé. Installez-le, démarrez-le, puis relancez start-garage.cmd."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop n'est pas démarré. Ouvrez Docker Desktop puis réessayez."
}

if (-not (Test-Path ".env")) {
    Write-Host "Première installation de Garage Plus" -ForegroundColor Cyan
    $managementPin = Read-Pin "Code PIN Management"
    $majdiPin = Read-Pin "Code PIN Majdi"
    while ($majdiPin -eq $managementPin) {
        Write-Host "Les deux profils doivent avoir des codes différents." -ForegroundColor Yellow
        $majdiPin = Read-Pin "Nouveau code PIN Majdi"
    }

    $lines = @(
        "POSTGRES_PASSWORD=$(New-RandomHex 24)",
        "JWT_SECRET=$(New-RandomHex 48)",
        "JWT_EXPIRE_MINUTES=480",
        "ETS_ADMIN_PIN=$managementPin",
        "ETS_STOREKEEPER_PIN=$majdiPin",
        "CORS_ORIGINS=http://localhost:61938,http://127.0.0.1:61938",
        "SHEET_SYNC_INTERVAL_MINUTES=10",
        "LEGACY_WEBAPP_URL="
    )
    [IO.File]::WriteAllLines((Join-Path $PSScriptRoot ".env"), $lines, [Text.UTF8Encoding]::new($false))
    Write-Host "Configuration locale sécurisée créée." -ForegroundColor Green
}

Write-Host "Démarrage de Garage Plus..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "Le démarrage Docker a échoué." }

$ready = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:61938/health" -TimeoutSec 2
        if ($health.ok -eq $true) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) {
    docker compose logs --tail 80 app
    throw "Garage Plus n'a pas répondu après deux minutes. Les journaux sont affichés ci-dessus."
}

Write-Host "Garage Plus est prêt : http://localhost:61938" -ForegroundColor Green
Start-Process "http://localhost:61938"
