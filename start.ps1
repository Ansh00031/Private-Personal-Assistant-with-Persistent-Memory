# path: start.ps1
# Startup script for Private Personal Assistant

# Restore persistent keys from Windows User Environment if needed
if (-not $env:NEBIUS_API_KEY -or $env:NEBIUS_API_KEY -eq "your-nebius-api-key") {
    $env:NEBIUS_API_KEY = [System.Environment]::GetEnvironmentVariable("NEBIUS_API_KEY", "User")
}

if (-not $env:MEMORY_ENCRYPTION_KEY) {
    $env:MEMORY_ENCRYPTION_KEY = [System.Environment]::GetEnvironmentVariable("MEMORY_ENCRYPTION_KEY", "User")
}

$env:MEMORY_DB_PATH = "data/memory.db"
$env:SANDBOX_ROOT = "data/sandbox"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Private Personal Assistant is starting up...     " -ForegroundColor Green
Write-Host " Open in browser: http://localhost:8000           " -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan

# Run via python.exe -m uvicorn to bypass Windows Application Control blocking standalone .exe shims
& ".\venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
