<#
.SYNOPSIS
  Starts SkillSprint AI: Docker, the database, the local LLM, the API and the web app.

.DESCRIPTION
  Safe to run again at any time: anything already running is left alone.
  On a fresh machine it also creates .env, the Python venv, installs the frontend
  packages, applies migrations and loads the demo data.

.EXAMPLE
  .\start.ps1              # everything, local LLM on the GPU if there is one
  .\start.ps1 -NoLLM       # skip the local LLM (plans still work via the other providers)
  .\start.ps1 -NoBrowser   # don't open the browser at the end
#>
param(
    [switch]$NoLLM,
    [switch]$NoBrowser
)

# 'Continue', not 'Stop': Windows PowerShell 5.1 turns any stderr from docker/npm
# (which print progress there) into a fatal error. Failures are checked via $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$ApiUrl = 'http://127.0.0.1:8000/health'
$WebUrl = 'http://localhost:5173'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Note($text) { Write-Host "    $text" -ForegroundColor DarkGray }
function Fail($text) { Write-Host "`n    $text" -ForegroundColor Red; exit 1 }

function Wait-Until([scriptblock]$Test, [int]$Seconds, [string]$What) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Test) { return $true }
        Start-Sleep -Seconds 2
    }
    Fail "Timed out after $Seconds s waiting for $What."
}

function Test-Port([int]$Port) {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-Api {
    try { (Invoke-WebRequest $ApiUrl -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false }
}

# --------------------------------------------------------------- 1. Docker
Step 'Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail 'Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $desktop)) { Fail 'Docker is not running and Docker Desktop was not found. Start Docker yourself, then rerun.' }
    Note 'Starting Docker Desktop (this can take a minute)...'
    Start-Process $desktop
    Wait-Until { docker info *> $null; $LASTEXITCODE -eq 0 } 240 'Docker Desktop' | Out-Null
}
Ok 'Docker is running'

# --------------------------------------------------------------- 2. Config and dependencies
Step 'Configuration and dependencies'
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Ok 'Created .env from .env.example'
}
# The API refuses a missing, short or placeholder SECRET_KEY (it signs every login token),
# so replace one with 48 cryptographically random characters. The key is never printed.
$keyLine = Select-String -Path '.env' -Pattern '^SECRET_KEY=(.*)$' | Select-Object -First 1
$current = if ($keyLine) { $keyLine.Matches[0].Groups[1].Value.Trim() } else { '' }
if ($current.Length -lt 32 -or @('change-me', 'changeme', 'secret') -contains $current.ToLower()) {
    $bytes = New-Object byte[] 36
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
    $lines = Get-Content '.env'
    if ($keyLine) { $lines = $lines -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" } else { $lines += "SECRET_KEY=$secret" }
    [System.IO.File]::WriteAllLines((Join-Path $Root '.env'), $lines)
    Ok 'Set a new random SECRET_KEY in .env (the old one was missing or too weak)'
}
if (-not (Test-Path $Python)) {
    Note 'Creating the Python environment (first run only, several minutes)...'
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $py) { Fail 'Python 3.12 is not installed. Install it from https://www.python.org/downloads/' }
    & $py.Source -m venv .venv
    & $Python -m pip install --quiet --upgrade pip
    & $Python -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Fail 'pip install failed; see the messages above.' }
}
Ok 'Python environment ready'
if (-not (Test-Path 'frontend\node_modules')) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail 'Node.js is not installed. Install it from https://nodejs.org' }
    Note 'Installing frontend packages (first run only)...'
    Push-Location frontend; npm install --no-audit --no-fund; $code = $LASTEXITCODE; Pop-Location
    if ($code -ne 0) { Fail 'npm install failed; see the messages above.' }
}
Ok 'Frontend packages ready'

# --------------------------------------------------------------- 3. Database
Step 'Database (PostgreSQL + pgvector)'
docker compose up -d db 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { docker compose up -d db; Fail 'Could not start the database container.' }
Wait-Until { (docker inspect -f '{{.State.Health.Status}}' skillsprint_db 2>$null) -eq 'healthy' } 120 'the database' | Out-Null
Ok 'Database is healthy'

& $Python -m alembic upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { & $Python -m alembic upgrade head; Fail 'Database migrations failed.' }
Ok 'Migrations applied'

$docs = & $Python -m scripts.count_documents 2>$null
if ($LASTEXITCODE -ne 0) { Fail 'Could not read the database after migrating.' }
if ([int]$docs -eq 0) {
    Note 'Empty database: loading the demo data (documents, requirements, employees, plans; several minutes)...'
    & $Python -m src.database.seed
    & $Python -m scripts.bootstrap_demo --plans
    if ($LASTEXITCODE -ne 0) { Fail 'Loading the demo data failed; see the messages above.' }
    Ok 'Demo data loaded'
} else {
    Ok "Demo data present ($docs documents)"
}

# --------------------------------------------------------------- 4. Local LLM
Step 'Local LLM (Ollama)'
if ($NoLLM) {
    Note 'Skipped (-NoLLM). Plans are written by the other providers in the chain.'
} else {
    $composeFiles = @('-f', 'docker-compose.yml')
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $composeFiles += @('-f', 'docker-compose.gpu.yml'); Note 'NVIDIA GPU found: running on the GPU'
    } else {
        Note 'No NVIDIA GPU found: running on the CPU (slower)'
    }
    docker compose @composeFiles --profile llm up -d ollama 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '    Could not start Ollama; continuing without it.' -ForegroundColor Yellow
    } else {
        Wait-Until { (docker inspect -f '{{.State.Health.Status}}' skillsprint_ollama 2>$null) -eq 'healthy' } 120 'Ollama' | Out-Null
        $model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { 'qwen2.5:3b' }
        if ((docker exec skillsprint_ollama ollama list 2>$null) -match [regex]::Escape($model)) {
            Ok "Ollama is running with $model"
        } else {
            docker compose @composeFiles --profile llm up -d ollama-pull 2>&1 | Out-Null
            Ok "Ollama is running; downloading $model in the background (about 1.9 GB)"
        }
    }
}

# --------------------------------------------------------------- 5. API
Step 'API (http://localhost:8000)'
if (Test-Api) {
    Ok 'Already running'
} elseif (Test-Port 8000) {
    Fail 'Port 8000 is in use by another program. Close it (or run .\stop.ps1) and try again.'
} else {
    Start-Process cmd.exe -ArgumentList '/k', 'title SkillSprint API && scripts\run-api.cmd' -WorkingDirectory $Root
    Note 'Started in a new window; loading the embedding model (about a minute)...'
    Wait-Until { Test-Api } 240 'the API' | Out-Null
    Ok 'API is healthy'
}

# --------------------------------------------------------------- 6. Web app
Step "Web app ($WebUrl)"
if (Test-Port 5173) {
    Ok 'Already running'
} else {
    Start-Process cmd.exe -ArgumentList '/k', 'title SkillSprint Web && scripts\run-web.cmd' -WorkingDirectory $Root
    Wait-Until { Test-Port 5173 } 90 'the web app' | Out-Null
    Ok 'Web app is running'
}

Write-Host "`nSkillSprint is running at $WebUrl" -ForegroundColor Green
Write-Host '    Sign in with a demo account, e.g. Admin (admin@nexoralabs.io / Admin@123).'
Write-Host '    Stop everything with .\stop.ps1 (or stop.cmd).'
if (-not $NoBrowser) { Start-Process $WebUrl }
