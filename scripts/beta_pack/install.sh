#!/usr/bin/env bash
# Machia beta installer for macOS and Linux.
#
# Steps:
#   1. Check Python 3.11+
#   2. Install the machia package (editable)
#   3. Locate the best available N-ATLAS gguf
#   4. Seed the workspace with sample files
#   5. Launch the unified launcher (model server + web UI + CLI)

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
# ---- Defaults -------------------------------------------------------------
# Pick the first existing machia-workspace we can find. Fall back to
# the user profile if none exists.
WORKSPACE=""
for candidate in \
    "${HOME}/dev/machia-workspace" \
    "${HOME}/machia-workspace" \
    "${HOME}/Desktop/machia-workspace"; do
    if [[ -d "$candidate" ]]; then
        WORKSPACE="$candidate"
        break
    fi
done
[[ -z "$WORKSPACE" ]] && WORKSPACE="${HOME}/machia-workspace"
MODE="confirm"
SKIP_INSTALL=0
SKIP_MODEL=0
NO_WEB=0
NO_SPAWN=0
MODEL_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)    WORKSPACE="$2"; shift 2 ;;
        --mode)         MODE="$2"; shift 2 ;;
        --model)        MODEL_PATH="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        --skip-model)   SKIP_MODEL=1;   shift ;;
        --no-web)       NO_WEB=1;       shift ;;
        --no-spawn)     NO_SPAWN=1;     shift ;;
        -h|--help)
            cat <<EOF
Usage: $0 [options]

  --workspace PATH   Where to run (default: ~/machia-workspace)
  --mode MODE        dry-run | confirm | auto (default: confirm)
  --model PATH       Explicit path to an N-ATLAS gguf
  --skip-install     Skip 'pip install -e .'
  --skip-model       Skip model file search
  --no-web           Do not start the web UI
  --no-spawn         Do not auto-start llama-server
EOF
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

# ---- find_atlas_model: best available N-ATLAS gguf on this machine --------
find_atlas_model() {
    local search_dirs=("$@")
    local preferred=("q4_k_m" "q4_k_s" "q5_k_m" "q5_k_s" "q6_k" "q8_0" "q3_k_m" "q2_k")
    local found=()

    local dir f name size
    for dir in "${search_dirs[@]}"; do
        [[ -d "$dir" ]] || continue
        while IFS= read -r -d '' f; do
            name=$(basename "$f" | tr '[:upper:]' '[:lower:]')
            [[ "$name" == *"atlas"* ]] || continue
            size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
            [[ "$size" -gt 2147483648 ]] || continue
            found+=("$f")
        done < <(find "$dir" -maxdepth 1 -type f -iname "*.gguf" -print0 2>/dev/null)
    done

    [[ ${#found[@]} -eq 0 ]] && return 1

    local best="" best_rank=99 best_size=0
    local i rank
    for f in "${found[@]}"; do
        name=$(basename "$f" | tr '[:upper:]' '[:lower:]')
        rank=99
        for i in "${!preferred[@]}"; do
            if [[ "$name" == *"${preferred[$i]}"* ]]; then rank=$i; break; fi
        done
        size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
        if (( rank < best_rank )) || { (( rank == best_rank )) && (( size < best_size )); }; then
            best="$f"; best_rank=$rank; best_size=$size
        fi
    done
    echo "$best"
}

quant_label() {
    local name
    name=$(basename "$1" | tr '[:upper:]' '[:lower:]')
    if [[ "$name" =~ (q[0-9]+_[a-z]_?[a-z]?) ]]; then
        echo "${BASH_REMATCH[1]^^}"
    elif [[ "$name" =~ (q[0-9]+_[0-9]) ]]; then
        echo "${BASH_REMATCH[1]^^}"
    elif [[ "$name" =~ (q[0-9]+_k) ]]; then
        echo "${BASH_REMATCH[1]^^}"
    elif [[ "$name" =~ (q[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]^^}"
    else
        echo "?"
    fi
}

# ---- 3. Model discovery ---------------------------------------------------
FOUND_MODEL=""
if [[ "$SKIP_MODEL" -eq 0 ]]; then
    section "Looking for an N-ATLAS model"

    if [[ -n "$MODEL_PATH" && -f "$MODEL_PATH" ]]; then
        FOUND_MODEL="$MODEL_PATH"
        info "Using explicit --model"
    fi

    if [[ -z "$FOUND_MODEL" ]]; then
        SEARCH_DIRS=(
            "${REPO_ROOT}/models"
            "${REPO_ROOT}/../models"
            "C:/dev/models"
            "${HOME}/models"
            "${HOME}/Downloads"
        )
        FOUND_MODEL=$(find_atlas_model "${SEARCH_DIRS[@]}" || true)
    fi

    if [[ -n "$FOUND_MODEL" ]]; then
        SIZE_BYTES=$(stat -f%z "$FOUND_MODEL" 2>/dev/null || stat -c%s "$FOUND_MODEL")
        SIZE_GB=$(awk -v b="$SIZE_BYTES" 'BEGIN { printf "%.2f", b / 1073741824 }')
        QUANT=$(quant_label "$FOUND_MODEL")
        ok "$FOUND_MODEL"
        ok "  quant: $QUANT   size: $SIZE_GB GB"

        # Warn on very large quants.
        if awk -v s="$SIZE_GB" 'BEGIN { exit !(s > 7) }'; then
            warn "This is a large quant. CPU inference will be noticeably slower."
            warn "A Q4_K_M build (~4.9 GB) would run ~2x faster."
        fi
    else
        warn "No N-ATLAS .gguf found in the usual locations."
        echo ""
        echo "  Download one (about 5 GB):"
        echo "    pip install -U 'huggingface_hub[cli]'"
        echo "    hf download inuwamobarak/N-ATLaS-8B-GGUF-Q4_K_M \\"
        echo "       ggml-model-Q4_K_M.gguf --local-dir ~/models"
        echo ""
        warn "Continuing. The launcher will fail unless llama-server is already running."
    fi
else
    section "Skipping model check"
fi

# ---- 4. Seed workspace ----------------------------------------------------
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

# ---- 5. Launch the unified stack -----------------------------------------
section "Launching Machia"
printf "\n  workspace: %s\n" "$WORKSPACE"
printf "  mode:      %s\n" "$MODE"
if [[ "$NO_WEB" -eq 0 ]]; then
    printf "  web UI:    http://127.0.0.1:5000\n"
fi
printf "\n"

LAUNCH_ARGS=(-m machia.launcher --workspace "$WORKSPACE" --mode "$MODE")
[[ -n "$FOUND_MODEL" ]] && LAUNCH_ARGS+=(--model "$FOUND_MODEL")
[[ "$NO_WEB"   -eq 1 ]] && LAUNCH_ARGS+=(--no-web)
[[ "$NO_SPAWN" -eq 1 ]] && LAUNCH_ARGS+=(--no-spawn)

"$PYTHON" "${LAUNCH_ARGS[@]}"

section "Done"
echo "  Session ended. Run the tasks in tasks.md, then collect.sh"
echo