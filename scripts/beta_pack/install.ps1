#Requires -Version 5.1
<#
    Machia beta installer.
    Run from anywhere; it locates the repo root by walking up from this file.
#>

[CmdletBinding()]
param(
    [string]$Workspace = "$env:USERPROFILE\machia-workspace",
    [string]$ModelPath = "",
    [switch]$SkipInstall,
    [switch]$SkipModelCheck,
    [switch]$SkipServerLaunch
)

$ErrorActionPreference = "Stop"

function Write-Section($text) {
    Write-Host ""
    Write-Host "-- $text " -ForegroundColor Cyan -NoNewline
    Write-Host ("-" * (70 - $text.Length)) -ForegroundColor DarkCyan
}
function Write-Ok($text)   { Write-Host "  OK  " -ForegroundColor Green -NoNewline; Write-Host $text }
function Write-Warn($text) { Write-Host "  !   " -ForegroundColor Yellow -NoNewline; Write-Host $text }
function Write-Err($text)  { Write-Host "  X   " -ForegroundColor Red -NoNewline;    Write-Host $text }
function Write-Info($text) { Write-Host "  .   " -ForegroundColor DarkGray -NoNewline; Write-Host $text }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path

Write-Host ""
Write-Host "  Machia -- installer" -ForegroundColor Magenta
Write-Host "  repo: $RepoRoot" -ForegroundColor DarkGray

# 1. Python check
Write-Section "Checking Python"
$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $version = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 11) {
                $pythonCmd = $candidate
                Write-Ok "$candidate $version"
                break
            } else {
                Write-Warn "$candidate $version is too old (need 3.11+)"
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Err "Python 3.11+ not found."
    Write-Host "  Install from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# 2. Install package
if (-not $SkipInstall) {
    Write-Section "Installing machia package"
    Push-Location $RepoRoot
    try {
        & $pythonCmd -m pip install -e . --quiet --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            Write-Err "pip install failed."
            exit 1
        }
        Write-Ok "machia installed (editable)"
    } finally { Pop-Location }
} else {
    Write-Section "Skipping package install"
}

# 3. Model check
$foundModel = $null
if (-not $SkipModelCheck) {
    Write-Section "Checking model file"
    $candidates = @()
    if ($ModelPath) { $candidates += $ModelPath }
    $candidates += (Join-Path $RepoRoot "models\ggml-model-Q4_K_M.gguf")
    $candidates += "C:\dev\models\ggml-model-Q4_K_M.gguf"
    foreach ($c in $candidates) {
        if (Test-Path $c) { $foundModel = (Resolve-Path $c).Path; break }
    }
    if ($foundModel) {
        Write-Ok "Model: $foundModel"
    } else {
        Write-Warn "Model file not found."
        Write-Host "  Download with:" -ForegroundColor Yellow
        Write-Host "    pip install -U `"huggingface_hub[cli]`"" -ForegroundColor White
        Write-Host "    hf download inuwamobarak/N-ATLaS-8B-GGUF-Q4_K_M ggml-model-Q4_K_M.gguf --local-dir C:\dev\models" -ForegroundColor White
        $SkipServerLaunch = $true
    }
} else {
    Write-Section "Skipping model check"
}

# 4. Workspace
Write-Section "Preparing workspace"
if (-not (Test-Path $Workspace)) {
    New-Item -ItemType Directory -Path $Workspace | Out-Null
    Write-Ok "Created: $Workspace"
    "Hello from Machia." | Out-File -FilePath (Join-Path $Workspace "notes.txt") -Encoding utf8
    "jollof rice recipe" | Out-File -FilePath (Join-Path $Workspace "recipe.txt") -Encoding utf8
    "a fake pdf"         | Out-File -FilePath (Join-Path $Workspace "report.pdf") -Encoding utf8
    "a fake image"       | Out-File -FilePath (Join-Path $Workspace "banner.png") -Encoding utf8
    "a fake exe"         | Out-File -FilePath (Join-Path $Workspace "installer.exe") -Encoding utf8
    Write-Ok "Seeded 5 sample files"
} else {
    Write-Ok "Already exists: $Workspace"
}

# 5. Server
$serverUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $serverUp = $true }
} catch { }

if (-not $SkipServerLaunch) {
    Write-Section "Model server"
    if ($serverUp) {
        Write-Ok "Server already running on http://127.0.0.1:8080"
    } else {
        $llamaServer = $null
        $cands = @(
            (Get-Command llama-server.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
            "C:\Users\$env:USERNAME\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
        ) | Where-Object { $_ -and (Test-Path $_) }
        if ($cands.Count -gt 0) { $llamaServer = $cands[0] }

        if (-not $llamaServer) {
            Write-Err "llama-server.exe not found."
            Write-Host "  Install with:  winget install ggml.llamacpp" -ForegroundColor Yellow
            exit 1
        }

        Write-Info "Starting server in a new window..."
        $cmd = "& '$llamaServer' -m '$foundModel' --host 127.0.0.1 --port 8080 -c 8192 --threads 8 --jinja --n-gpu-layers 0"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
        Write-Ok "Server window opened."

        Write-Info "Waiting for server (up to 60s)..."
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 1
            try {
                $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                if ($r.StatusCode -eq 200) { $ready = $true; break }
            } catch { }
        }
        if ($ready) { Write-Ok "Server is up ($i s)" }
        else { Write-Warn "Server not responding after 60s. Check the new window." }
    }
} else {
    Write-Section "Skipping server launch"
}

# 6. Launch CLI
Write-Section "Launching Machia CLI"
Write-Host ""
Write-Host "  workspace: $Workspace" -ForegroundColor DarkGray
Write-Host "  mode:      confirm" -ForegroundColor DarkGray
Write-Host ""

& $pythonCmd -m machia.cli --workspace $Workspace

Write-Section "Done"
Write-Host "  Run the tasks in tasks.md, then collect.ps1." -ForegroundColor Green
Write-Host ""