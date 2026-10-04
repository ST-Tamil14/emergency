param([ValidateSet("sumo", "kinematic")][string]$Engine = "sumo")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "CORRIDOR - Local simulation setup" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Install Python 3.12 with the Python launcher, then run this script again." }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required by this launcher. See README for manual Python 3.11 setup." }
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pip install -r research-service\requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed. Check the network and the displayed error." }
if (-not (Test-Path "frontend\dist\index.html")) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "The built UI is missing. Install Node.js 22 to build it." }
    Push-Location frontend
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend package installation failed." }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally { Pop-Location }
}
$env:SIMULATION_MODE = $Engine
$env:AGENT_MODE = "process"
Start-Process -FilePath $python -WorkingDirectory (Join-Path $PSScriptRoot "research-service") -ArgumentList "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"

Write-Host "The simulation service window has opened. Keep it open while using the app." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:8000 . Close the service window to stop."
Write-Host "If SUMO cannot initialize, check its error window and the README; use -Engine kinematic only for a labelled protocol simulation."
$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try { $null = Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 2; $ready = $true; break } catch { Start-Sleep -Milliseconds 500 }
}
if ($ready) { Start-Process "http://127.0.0.1:8000" } else { Write-Warning "Service is not ready. Read the service window for the error before retrying." }
