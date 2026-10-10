#!/usr/bin/env bash
# Machia beta feedback collector for macOS and Linux.
# Bundles audit log + skills + versions + workspace listing + feedback.md
# into a single zip on the Desktop.

set -euo pipefail

C_CYAN='\033[36m'; C_GREEN='\033[32m'; C_YELLOW='\033[33m'; C_DIM='\033[2m'; C_RESET='\033[0m'
section() { printf "\n${C_CYAN}-- %s ${C_RESET}" "$1"; printf -- "-%.0s" {1..60}; printf "\n"; }
ok()      { printf "  ${C_GREEN}OK${C_RESET}  %s\n" "$1"; }
warn()    { printf "  ${C_YELLOW}!${C_RESET}   %s\n" "$1"; }
info()    { printf "  ${C_DIM}.${C_RESET}   %s\n" "$1"; }

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"

printf "\n  ${C_CYAN}Machia -- beta feedback collector${C_RESET}\n"
printf "  repo: ${C_DIM}%s${C_RESET}\n" "$REPO_ROOT"

STAMP="$(date +%Y-%m-%d_%H%M%S)"
STAGE="$(mktemp -d "/tmp/machia-feedback-${STAMP}-XXXXXX")"

section "Collecting files"

AUDIT="${HOME}/.machia/audit.jsonl"
if [[ -f "$AUDIT" ]]; then
    cp "$AUDIT" "$STAGE/audit.jsonl"
    LINES=$(wc -l < "$AUDIT" | tr -d ' ')
    ok "audit.jsonl (${LINES} records)"
else
    warn "no audit log at $AUDIT"
fi

SKILLS="${REPO_ROOT}/skills"
if [[ -d "$SKILLS" ]]; then
    cp -R "$SKILLS" "$STAGE/skills"
    COUNT=$(find "$SKILLS" -name "SKILL.md" | wc -l | tr -d ' ')
    ok "skills/ (${COUNT} SKILL.md files)"
else
    warn "no skills folder"
fi

{
    echo "collected_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "user:         ${USER:-unknown}"
    echo "hostname:     $(hostname)"
    echo "os:           $(uname -a)"
    echo "python:       $(python3 --version 2>&1 || python --version 2>&1)"
    echo "git_sha:      $(cd "$REPO_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
} > "$STAGE/versions.txt"
ok "versions.txt"

WS="${HOME}/machia-workspace"
if [[ -d "$WS" ]]; then
    find "$WS" -exec ls -la {} \; > "$STAGE/workspace-listing.txt" 2>/dev/null || true
    ok "workspace-listing.txt"
fi

FOUND_FEEDBACK=0
for c in \
    "${REPO_ROOT}/scripts/beta_pack/feedback.md" \
    "${HOME}/Desktop/feedback.md" \
    "${HOME}/Downloads/feedback.md"; do
    if [[ -f "$c" ]]; then
        cp "$c" "$STAGE/feedback.md"
        ok "feedback.md"
        FOUND_FEEDBACK=1
        break
    fi
done
if [[ "$FOUND_FEEDBACK" -eq 0 ]]; then
    warn "feedback.md not found — include it manually if you filled one in"
fi

section "Packaging"
OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="${HOME}"
ZIP="${OUT_DIR}/machia-feedback-${STAMP}.zip"

if command -v zip >/dev/null 2>&1; then
    ( cd "$STAGE" && zip -qr "$ZIP" . )
else
    tar -czf "${ZIP%.zip}.tar.gz" -C "$STAGE" .
    ZIP="${ZIP%.zip}.tar.gz"
fi

rm -rf "$STAGE"

section "Done"
printf "  Send this file back:\n    ${C_GREEN}%s${C_RESET}\n\n" "$ZIP"