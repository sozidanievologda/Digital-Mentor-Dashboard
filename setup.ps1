# Настройка и запуск дашборда на Windows.
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -NoStart
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Local
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Docker

param(
    [switch]$NoStart,
    [switch]$Docker,
    [switch]$Local,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Windows PowerShell 5.1 reads scripts without a BOM as ANSI; this file is
# stored as UTF-8 with BOM. Also switch the console to UTF-8 for Cyrillic.
try {
    & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch { }

function Find-Python {
    foreach ($candidate in @("py", "python", "python3")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) { continue }

        foreach ($prefix in @(@(), @("-3"))) {
            if ($candidate -ne "py" -and $prefix.Count -gt 0) { continue }
            try {
                $version = & $command.Source @prefix -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])" 2>$null
                if ([int]$version -ge 311) {
                    return @{ Exe = $command.Source; Prefix = $prefix }
                }
            } catch { }
        }
    }
    return $null
}

function Test-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    docker compose version *> $null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "== Настройка Digital Mentor Dashboard ==" -ForegroundColor Cyan

$python = Find-Python
if ($python) {
    & $python.Exe @($python.Prefix + @("backend\scripts\setup_env.py") + $Rest)
} elseif (Test-Docker) {
    Write-Host "Python не найден — настраиваю .env через контейнер python:3.12-slim"
    docker run --rm -it -v "${PWD}\backend:/app" -w /app python:3.12-slim python scripts/setup_env.py @Rest
} else {
    Write-Host "Нужен Python 3.11+ (https://www.python.org/downloads/windows/) или запущенный Docker Desktop." -ForegroundColor Red
    exit 1
}

if ($NoStart) {
    Write-Host ""
    Write-Host "Готово. Запуск:"
    Write-Host "  Docker:   docker compose up -d --build"
    Write-Host "  Локально: cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
    exit 0
}

if (-not $Local -and (Test-Docker)) {
    Write-Host ""
    Write-Host "== Запуск через Docker ==" -ForegroundColor Cyan
    docker compose up -d --build
    Write-Host ""
    Write-Host "Дашборд: http://localhost:8080"
    Write-Host "Логи:    docker compose logs -f backend"
    Start-Process "http://localhost:8080"
    exit 0
}

if ($Docker) {
    Write-Host "Docker Desktop не запущен или нет плагина compose. Запустите Docker Desktop и повторите." -ForegroundColor Red
    exit 1
}

if (-not $python) {
    Write-Host "Для локального запуска нужен Python 3.11+." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "== Локальный запуск ==" -ForegroundColor Cyan
$venvPython = Join-Path $PSScriptRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python.Exe @($python.Prefix + @("-m", "venv", "backend\.venv"))
}
& $venvPython -m pip install -q --disable-pip-version-check -r backend\requirements.txt

Write-Host "API:  http://localhost:8000"
Write-Host "UI:   $PSScriptRoot\frontend\index.html"
Write-Host "Вход: логин и пароль, заданные при настройке."
Write-Host ""
Start-Process (Join-Path $PSScriptRoot "frontend\index.html")

Push-Location backend
try {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
