#Requires -Version 5.1
<#
    Machia beta feedback collector.
    Bundles audit log + skills + versions + workspace listing + feedback.md
    into one zip on the Desktop.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "$env:USERPROFILE\Desktop"
)

$ErrorActionPreference = "Stop"

function Write-Section($text) {
    Write-Host ""
    Write-Host "-- $text " -ForegroundColor Cyan -NoNewline
    Write-Host ("-" * (70 - $text.Length)) -ForegroundColor DarkCyan
}
function Write-Ok($t)   { Write-Host "  OK  " -ForegroundColor Green -NoNewline;  Write-Host $t }
function Write-Warn($t) { Write-Host "  !   " -ForegroundColor Yellow -NoNewline; Write-Host $t }
function Write-Info($t) { Write-Host "  .   " -ForegroundColor DarkGray -NoNewline; Write-Host $t }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path

Write-Host ""
Write-Host "  Machia -- beta feedback collector" -ForegroundColor Magenta
Write-Host "  repo: $RepoRoot" -ForegroundColor DarkGray

$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$stage = Join-Path $env:TEMP "machia-feedback-$stamp"
New-Item -ItemType Directory -Path $stage -Force | Out-Null

Write-Section "Collecting files"

$audit = "$env:USERPROFILE\.machia\audit.jsonl"
if (Test-Path $audit) {
    Copy-Item $audit (Join-Path $stage "audit.jsonl")
    $lines = (Get-Content $audit | Measure-Object -Line).Lines
    Write-Ok "audit.jsonl ($lines records)"
} else {
    Write-Warn "no audit log found at $audit"
}

$skills = Join-Path $RepoRoot "skills"
if (Test-Path $skills) {
    Copy-Item $skills (Join-Path $stage "skills") -Recurse
    $count = (Get-ChildItem $skills -Recurse -Filter "SKILL.md").Count
    Write-Ok "skills/ ($count SKILL.md files)"
} else {
    Write-Warn "no skills folder found"
}

$versions = Join-Path $stage "versions.txt"
@(
    "collected_at: $(Get-Date -Format o)"
    "user:         $env:USERNAME"
    "hostname:     $env:COMPUTERNAME"
    "os:           $((Get-CimInstance Win32_OperatingSystem).Caption)"
    "python:       $((python --version 2>&1))"
    "git_sha:      $((git -C $RepoRoot rev-parse --short HEAD 2>$null))"
) | Out-File -FilePath $versions -Encoding utf8
Write-Ok "versions.txt"

$ws = "$env:USERPROFILE\machia-workspace"
if (Test-Path $ws) {
    Get-ChildItem $ws -Recurse |
        Select-Object FullName, Length, LastWriteTime |
        Format-Table -AutoSize |
        Out-String |
        Out-File -FilePath (Join-Path $stage "workspace-listing.txt") -Encoding utf8
    Write-Ok "workspace-listing.txt"
}

$feedbackCands = @(
    (Join-Path $RepoRoot "scripts\beta_pack\feedback.md"),
    (Join-Path $env:USERPROFILE "Desktop\feedback.md"),
    (Join-Path $env:USERPROFILE "Downloads\feedback.md")
)
$found = $false
foreach ($c in $feedbackCands) {
    if (Test-Path $c) {
        Copy-Item $c (Join-Path $stage "feedback.md")
        Write-Ok "feedback.md"
        $found = $true
        break
    }
}
if (-not $found) { Write-Warn "feedback.md not found" }

Write-Section "Packaging"
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }
$zip = Join-Path $OutputDir "machia-feedback-$stamp.zip"
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
Remove-Item $stage -Recurse -Force

Write-Section "Done"
Write-Host "  Send this file back:" -ForegroundColor Green
Write-Host "    $zip" -ForegroundColor White
Write-Host ""