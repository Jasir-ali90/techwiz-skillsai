<#
.SYNOPSIS
  Stops what start.ps1 started: the web app, the API, the local LLM and the database.
.EXAMPLE
  .\stop.ps1            # stop everything (data is kept)
  .\stop.ps1 -KeepDocker  # stop only the API and web app
#>
param([switch]$KeepDocker)

$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

# Only stop the Python (API) and Node (web) processes listening on our ports,
# never some other program that happens to use them.
foreach ($entry in @(@{ Port = 5173; Name = 'node'; Label = 'Web app' }, @{ Port = 8000; Name = 'python'; Label = 'API' })) {
    $owners = Get-NetTCPConnection -LocalPort $entry.Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    $stopped = $false
    foreach ($id in $owners) {
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -like "$($entry.Name)*") {
            Stop-Process -Id $id -Force; $stopped = $true
        } elseif ($proc) {
            Write-Host "    Port $($entry.Port) is used by $($proc.ProcessName), not SkillSprint; left running." -ForegroundColor Yellow
        }
    }
    Write-Host ("{0}: {1}" -f $entry.Label, $(if ($stopped) { 'stopped' } else { 'was not running' }))
}

if (-not $KeepDocker) {
    docker compose --profile llm stop ollama 2>&1 | Out-Null
    Write-Host 'Local LLM: stopped (frees the GPU memory)'
    docker compose stop db 2>&1 | Out-Null
    Write-Host 'Database: stopped (your data is kept)'
}
