#!/usr/bin/env bash
# Machia beta installer for macOS and Linux.
#
# Usage:
#   ./scripts/beta_pack/install.sh
#   ./scripts/beta_pack/install.sh --workspace ~/my-workspace
#
# Requires: Python 3.11+, llama.cpp (llama-server), ~6 GB free disk.

set -euo pipefail

# ---- Colours --------------------------------------------------------------
C_CYAN='\033[36m'; C_GREEN='\033[32m'; C_YELLOW='\033[33m'
C_RED='\033[31m';  C_DIM='\033[2m';    C_RESET='\033[0m'

section() { printf "\n${C_CYAN}-- %s ${C_RESET}" "$1"; printf -- "-%.0s" {1..60}; printf "\n"; }
ok()      { printf "  ${C_GREEN}OK${C_RESET}  %s\n" "$1"; }
warn()    { printf "  ${C_YELLOW}!${C_RESET}   %s\n" "$1"; }
err()     { printf "  ${C_RED}X${C_RESET}   %s\n" "$1"; }
info()    { printf "  ${C_DIM}.${C_RESET}   %s\n" "$1"; }

# ---- Defaults -------------------------------------------------------------
WORKSPACE="${HOME}/machia-workspace"
SKIP_INSTALL=0
SKIP_MODEL=0
SKIP_SERVER=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)    WORKSPACE="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        --skip-model)   SKIP_MODEL=1;   shift ;;
        --skip-server)  SKIP_SERVER=1;  shift ;;
        -h|--help)
            echo "Usage: $0 [--workspace PATH] [--skip-install] [--skip-model] [--skip-server]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"

printf "\n  ${C_CYAN}Machia -- installer${C_RESET}\n"
printf "  repo: ${C_DIM}%s${C_RESET}\n" "${REPO_ROOT}"

# ---- 1. Python check ------------------------------------------------------
section "Checking Python"
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" --version 2>&1 || true)
        if [[ "$version" =~ Python\ ([0-9]+)\.([0-9]+) ]]; then
            major="${BASH_REMATCH[1]}"
            minor="${BASH_REMATCH[2]}"
            if [[ "$major" -eq 3 && "$minor" -ge 11 ]]; then
                PYTHON="$candidate"
                ok "$candidate $version"
                break
            else
                warn "$candidate $version is too old (need 3.11+)"
            fi
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    err "Python 3.11+ not found."
    echo "  Install it:"
    echo "    macOS:  brew install python@3.11"
    echo "    Ubuntu: sudo apt install python3.11 python3.11-venv"
    exit 1
fi

# ---- 2. Install package ---------------------------------------------------
if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    section "Installing machia package"
    ( cd "$REPO_ROOT" && "$PYTHON" -m pip install -e . --quiet --disable-pip-version-check )
    ok "machia installed (editable)"
else
    section "Skipping package install"
fi

# ---- 3. Model check -------------------------------------------------------
MODEL_PATH=""
if [[ "$SKIP_MODEL" -eq 0 ]]; then
    section "Checking model file"
    for candidate in \
        "${REPO_ROOT}/models/ggml-model-Q4_K_M.gguf" \
        "${HOME}/models/ggml-model-Q4_K_M.gguf" \
        "/opt/models/ggml-model-Q4_K_M.gguf"; do
        if [[ -f "$candidate" ]]; then
            MODEL_PATH="$candidate"
            ok "Model: $candidate"
            break
        fi
    done
    if [[ -z "$MODEL_PATH" ]]; then
        warn "Model file not found."
        echo "  Download it:"
        echo "    pip install -U 'huggingface_hub[cli]'"
        echo "    hf download inuwamobarak/N-ATLaS-8B-GGUF-Q4_K_M \\"
        echo "       ggml-model-Q4_K_M.gguf --local-dir ~/models"
        SKIP_SERVER=1
    fi
else
    section "Skipping model check"
fi

# ---- 4. Workspace ---------------------------------------------------------
section "Preparing workspace"
if [[ ! -d "$WORKSPACE" ]]; then
    mkdir -p "$WORKSPACE"
    ok "Created: $WORKSPACE"
    printf "Hello from Machia.\n" >  "$WORKSPACE/notes.txt"
    printf "jollof rice recipe\n" >  "$WORKSPACE/recipe.txt"
    printf "a fake pdf\n"         >  "$WORKSPACE/report.pdf"
    printf "a fake image\n"       >  "$WORKSPACE/banner.png"
    printf "a fake exe\n"         >  "$WORKSPACE/installer.exe"
    ok "Seeded 5 sample files"
else
    ok "Already exists: $WORKSPACE"
fi

mkdir -p "${HOME}/.machia"

# ---- 5. Model server ------------------------------------------------------
if [[ "$SKIP_SERVER" -eq 0 ]]; then
    section "Model server"
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/health" 2>/dev/null | grep -q 200; then
        ok "Server already running on http://127.0.0.1:8080"
    else
        LLAMA_SERVER="$(command -v llama-server || true)"
        if [[ -z "$LLAMA_SERVER" ]]; then
            err "llama-server not found."
            echo "  Install llama.cpp:"
            echo "    macOS:  brew install llama.cpp"
            echo "    Other:  https://github.com/ggml-org/llama.cpp"
            SKIP_SERVER=1
        else
            info "Starting server in background..."
            NCPU=$( (nproc 2>/dev/null) || (sysctl -n hw.ncpu 2>/dev/null) || echo 8 )
            nohup "$LLAMA_SERVER" \
                -m "$MODEL_PATH" \
                --host 127.0.0.1 --port 8080 \
                -c 8192 --threads "$NCPU" \
                --jinja --n-gpu-layers 0 \
                > "${HOME}/.machia/llama-server.log" 2>&1 &
            info "Waiting for server (up to 60s)..."
            READY=0
            for i in $(seq 1 60); do
                if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/health" 2>/dev/null | grep -q 200; then
                    ok "Server is up (${i}s)"
                    READY=1
                    break
                fi
                sleep 1
            done
            if [[ "$READY" -eq 0 ]]; then
                warn "Server not responding after 60s. Check: ~/.machia/llama-server.log"
            fi
        fi
    fi
else
    section "Skipping server launch"
fi

# ---- 6. Launch CLI --------------------------------------------------------
section "Launching Machia CLI"
printf "\n  workspace: %s\n" "$WORKSPACE"
printf "  mode:      confirm\n\n"

"$PYTHON" -m machia.cli --workspace "$WORKSPACE"

section "Done"
echo "  Run the tasks in tasks.md, then collect.sh"
echo