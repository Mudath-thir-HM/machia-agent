#Requires -Version 5.1
<#
    Machia beta installer (Windows).

    Steps:
      1. Check Python 3.11+
      2. Install the machia package (editable)
      3. Locate the best available N-ATLAS gguf
      4. Seed the workspace with sample files
      5. Launch the unified launcher (model server + web UI + CLI)

    The launcher handles starting llama-server if it is not already up,
    and starting the FastAPI web UI in a background thread. It prints
    the web URL before dropping into the CLI.

    Idempotent — safe to re-run.
#>

[CmdletBinding()]
param(
    [string]$Workspace = "$env:USERPROFILE\machia-workspace",
    [string]$ModelPath = "",
    [ValidateSet("dry-run", "confirm", "auto")]
    [string]$Mode = "confirm",
    [switch]$SkipInstall,
    [switch]$SkipModelCheck,
    [switch]$NoWeb,
    [switch]$NoSpawn
)

$ErrorActionPreference = "Stop"

function Write-Section($text) {
    Write-Host ""
    Write-Host "-- $text " -ForegroundColor Cyan -NoNewline
    Write-Host ("-" * (70 - $text.Length)) -ForegroundColor DarkCyan
}
function Write-Ok($text)   { Write-Host "  OK  " -ForegroundColor Green  -NoNewline; Write-Host $text }
function Write-Warn($text) { Write-Host "  !   " -ForegroundColor Yellow -NoNewline; Write-Host $text }
function Write-Err($text)  { Write-Host "  X   " -ForegroundColor Red    -NoNewline; Write-Host $text }
function Write-Info($text) { Write-Host "  .   " -ForegroundColor DarkGray -NoNewline; Write-Host $text }

# ---------------------------------------------------------------------------
# Find the best N-ATLAS gguf available on this machine.
# ---------------------------------------------------------------------------
function Find-AtlasModel {
    param([string[]]$SearchDirs)

    # Preference order: best CPU trade-off first.
    $preferred = @(
        "q4_k_m", "q4_k_s",
        "q5_k_m", "q5_k_s",
        "q6_k",
        "q8_0",
        "q3_k_m", "q2_k"
    )

    $found = @()
    foreach ($dir in $SearchDirs) {
        if (-not (Test-Path $dir)) { continue }
        try {
            Get-ChildItem -Path $dir -Filter "*.gguf" -File -ErrorAction SilentlyContinue |
                ForEach-Object {
                    $name = $_.Name.ToLower()
                    if ($name -notmatch "atlas") { return }
                    if ($_.Length -lt 2GB) { return }
                    $found += $_
                }
        } catch { }
    }

    if ($found.Count -eq 0) { return $null }

    $ranked = foreach ($f in $found) {
        $name = $f.Name.ToLower()
        $rank = $preferred.Count
        for ($i = 0; $i -lt $preferred.Count; $i++) {
            if ($name -match [regex]::Escape($preferred[$i])) { $rank = $i; break }
        }
        [PSCustomObject]@{ File = $f; Rank = $rank; Size = $f.Length }
    }

    $best = $ranked | Sort-Object Rank, Size | Select-Object -First 1
    return $best.File.FullName
}

function Get-QuantLabel {
    param([string]$path)
    $name = (Split-Path $path -Leaf).ToLower()
    if ($name -match "(q\d+_[a-z]_?[a-z]?)") { return $Matches[1].ToUpper() }
    if ($name -match "(q\d+_\d)")          { return $Matches[1].ToUpper() }
    if ($name -match "(q\d+_k)")           { return $Matches[1].ToUpper() }
    if ($name -match "(q\d+)")             { return $Matches[1].ToUpper() }
    return "?"
}

# ---------------------------------------------------------------------------
# Locate repo root
# ---------------------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path

Write-Host ""
Write-Host "  Machia -- installer" -ForegroundColor Magenta
Write-Host "  repo: $RepoRoot" -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# 1. Python check
# ---------------------------------------------------------------------------

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
    Write-Host ""
    Write-Host "  Install from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Make sure 'Add Python to PATH' is ticked during install." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Install the package
# ---------------------------------------------------------------------------

if (-not $SkipInstall) {
    Write-Section "Installing machia package"
    Push-Location $RepoRoot
    try {
        & $pythonCmd -m pip install -e . --quiet --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            Write-Err "pip install failed."
            Write-Host "  Try manually from the repo root:" -ForegroundColor Yellow
            Write-Host "    $pythonCmd -m pip install -e ." -ForegroundColor Yellow
            exit 1
        }
        Write-Ok "machia installed (editable)"
    } finally {
        Pop-Location
    }
} else {
    Write-Section "Skipping package install"
}

# ---------------------------------------------------------------------------
# 3. Model discovery
# ---------------------------------------------------------------------------

$foundModel = $null
if (-not $SkipModelCheck) {
    Write-Section "Looking for an N-ATLAS model"

    if ($ModelPath) {
        if (Test-Path $ModelPath) {
            $foundModel = (Resolve-Path $ModelPath).Path
            Write-Info "Using explicit --ModelPath"
        } else {
            Write-Warn "Explicit --ModelPath not found: $ModelPath"
        }
    }

    if (-not $foundModel) {
        $searchDirs = @(
            (Join-Path $RepoRoot "models"),
            (Join-Path $RepoRoot "..\models"),
            "C:\dev\models",
            (Join-Path $env:USERPROFILE "models"),
            (Join-Path $env:USERPROFILE "Downloads")
        )
        $foundModel = Find-AtlasModel -SearchDirs $searchDirs
    }

    if ($foundModel) {
        $sizeGb = [math]::Round((Get-Item $foundModel).Length / 1GB, 2)
        $quant  = Get-QuantLabel $foundModel
        Write-Ok "$foundModel"
        Write-Ok "  quant: $quant   size: $sizeGb GB"

        if ($sizeGb -gt 7) {
            Write-Warn "This is a large quant. CPU inference will be noticeably slower."
            Write-Warn "A Q4_K_M build (~4.9 GB) would run ~2x faster."
        }
    } else {
        Write-Warn "No N-ATLAS .gguf found in the usual locations."
        Write-Host ""
        Write-Host "  Download one (about 5 GB):" -ForegroundColor Yellow
        Write-Host "    pip install -U `"huggingface_hub[cli]`"" -ForegroundColor White
        Write-Host "    hf download inuwamobarak/N-ATLaS-8B-GGUF-Q4_K_M ``" -ForegroundColor White
        Write-Host "       ggml-model-Q4_K_M.gguf --local-dir C:\dev\models" -ForegroundColor White
        Write-Host ""
        Write-Host "  Then re-run:" -ForegroundColor Yellow
        Write-Host "    .\scripts\beta_pack\install.ps1 -ModelPath C:\dev\models\ggml-model-Q4_K_M.gguf" -ForegroundColor Yellow
        Write-Host ""
        Write-Warn "Continuing. The launcher will fail unless llama-server is already running."
    }
} else {
    Write-Section "Skipping model check"
}

# ---------------------------------------------------------------------------
# 4. Seed workspace
# ---------------------------------------------------------------------------

Write-Section "Preparing workspace"

if (-not (Test-Path $Workspace)) {
    New-Item -ItemType Directory -Path $Workspace | Out-Null
    Write-Ok "Created: $Workspace"
    "Hello from Machia." | Out-File -FilePath (Join-Path $Workspace "notes.txt")     -Encoding utf8
    "jollof rice recipe" | Out-File -FilePath (Join-Path $Workspace "recipe.txt")    -Encoding utf8
    "a fake pdf"         | Out-File -FilePath (Join-Path $Workspace "report.pdf")    -Encoding utf8
    "a fake image"       | Out-File -FilePath (Join-Path $Workspace "banner.png")    -Encoding utf8
    "a fake exe"         | Out-File -FilePath (Join-Path $Workspace "installer.exe") -Encoding utf8
    Write-Ok "Seeded 5 sample files"
} else {
    Write-Ok "Already exists: $Workspace"
}

# ---------------------------------------------------------------------------
# 5. Launch the unified stack
# ---------------------------------------------------------------------------

Write-Section "Launching Machia"
Write-Host ""
Write-Host "  workspace: $Workspace" -ForegroundColor DarkGray
Write-Host "  mode:      $Mode" -ForegroundColor DarkGray
if (-not $NoWeb) {
    Write-Host "  web UI:    http://127.0.0.1:5000" -ForegroundColor DarkGray
}
Write-Host ""

$launcherArgs = @(
    "-m", "machia.launcher",
    "--workspace", $Workspace,
    "--mode", $Mode
)
if ($foundModel)  { $launcherArgs += @("--model", $foundModel) }
if ($NoWeb)       { $launcherArgs += "--no-web" }
if ($NoSpawn)     { $launcherArgs += "--no-spawn" }

& $pythonCmd @launcherArgs

Write-Section "Done"
Write-Host "  Session ended. Run the tasks in tasks.md, then collect.ps1." -ForegroundColor Green
Write-Host ""