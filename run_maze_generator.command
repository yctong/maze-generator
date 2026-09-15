#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Maze Generator & Coloring Sheet Engine - macOS / Linux launcher
#
# Double-click this file in Finder (it opens in Terminal), or run it from a
# shell with:  ./run_maze_generator.command
# If macOS refuses to run it, make it executable once:
#     chmod +x run_maze_generator.command
# ---------------------------------------------------------------------------

set -u

# Always operate from the folder this script lives in.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

SCRIPT="generate_maze_script.py"

# Session settings (persist while the menu is open)
OUTDIR="."
MAX_SEARCH=""
JOBS=""

# --- terminal helpers ------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    BOLD="$(tput bold)"; DIM="$(tput dim)"; RED="$(tput setaf 1)"
    GREEN="$(tput setaf 2)"; YELLOW="$(tput setaf 3)"; RESET="$(tput sgr0)"
else
    BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; RESET=""
fi

RULE="===================================================================="

clear_screen() { command -v clear >/dev/null 2>&1 && clear || printf '\n\n'; }
info()  { printf '%s\n' "$*"; }
warn()  { printf '%s[WARN]%s %s\n' "$YELLOW" "$RESET" "$*"; }
err()   { printf '%s[ERROR]%s %s\n' "$RED" "$RESET" "$*" >&2; }
ok()    { printf '%s%s%s\n' "$GREEN" "$*" "$RESET"; }

pause_key() {
    printf '\n'
    read -r -p "Press Return to continue... " _ || true
}

# Opens files/folders with the platform's default handler.
open_path() {
    if command -v open >/dev/null 2>&1; then
        open "$1" >/dev/null 2>&1
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$1" >/dev/null 2>&1
    else
        warn "No 'open'/'xdg-open' available - file is at: $1"
        return 1
    fi
}

# ask_int <varname> <prompt> <default|""> <min> <max>
# Repeats until a valid integer in range is entered.
# Returns 1 when the answer is blank and there is no default.
ask_int() {
    local __var="$1" prompt="$2" default="$3" min="$4" max="$5" ans
    while true; do
        if [ -n "$default" ]; then
            read -r -p "$prompt [default $default]: " ans || return 1
        else
            read -r -p "$prompt: " ans || return 1
        fi
        ans="${ans//[[:space:]]/}"
        if [ -z "$ans" ]; then
            [ -z "$default" ] && return 1
            ans="$default"
        fi
        if ! [[ "$ans" =~ ^[0-9]+$ ]]; then
            warn "\"$ans\" is not a whole number. Try again."
            continue
        fi
        if [ "$ans" -lt "$min" ]; then
            warn "Value must be at least $min. Try again."
            continue
        fi
        if [ "$ans" -gt "$max" ]; then
            warn "Value must be at most $max. Try again."
            continue
        fi
        printf -v "$__var" '%s' "$ans"
        return 0
    done
}

# --- environment checks ----------------------------------------------------
if [ ! -f "$SCRIPT" ]; then
    err "$SCRIPT was not found next to this launcher."
    info "        Expected location: $(pwd)/$SCRIPT"
    pause_key
    exit 1
fi

# Pick an interpreter. A Python that already has Pillow always wins, so a bare
# python3 without the dependency does not shadow a working virtualenv.
PY=""
PY_ANY=""
for candidate in "${PYTHON:-}" python3 python; do
    [ -z "$candidate" ] && continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' >/dev/null 2>&1 || continue
    [ -z "$PY_ANY" ] && PY_ANY="$candidate"
    if "$candidate" -c 'import PIL' >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
[ -z "$PY" ] && PY="$PY_ANY"

if [ -z "$PY" ]; then
    err "No working Python 3 interpreter was found on your PATH."
    info "        Install it with:  brew install python"
    info "        or download from: https://www.python.org/downloads/"
    pause_key
    exit 1
fi

PYVER="$("$PY" --version 2>&1)"

if ! "$PY" -c 'import PIL' >/dev/null 2>&1; then
    warn "Required package \"Pillow\" is missing."
    read -r -p "       Install it now with pip? (Y/N, default Y): " installpil || installpil="N"
    installpil="${installpil:-Y}"
    case "$installpil" in
        [Yy]*)
            printf '\n'
            if ! "$PY" -m pip install --upgrade pillow; then
                warn "System pip refused the install (PEP 668 managed environment?)."
                info "Retrying with --user ..."
                "$PY" -m pip install --user --upgrade pillow || true
            fi
            if ! "$PY" -c 'import PIL' >/dev/null 2>&1; then
                err "Pillow could not be installed. Install it manually, e.g.:"
                info "        $PY -m pip install --break-system-packages pillow"
                info "    or create a virtualenv:"
                info "        $PY -m venv .venv && ./.venv/bin/pip install pillow"
                info "        PYTHON=./.venv/bin/python ./run_maze_generator.command"
                pause_key
                exit 1
            fi
            ;;
        *)
            err "Cannot continue without Pillow."
            pause_key
            exit 1
            ;;
    esac
fi

# --- generation ------------------------------------------------------------
build_args() {
    EXTRA_ARGS=()
    [ -n "${G_SEED:-}" ] && EXTRA_ARGS+=(--seed "$G_SEED")
    [ -n "$MAX_SEARCH" ] && EXTRA_ARGS+=(--max-search "$MAX_SEARCH")
    [ -n "$JOBS" ] && EXTRA_ARGS+=(--jobs "$JOBS")
}

run_gen() {
    local rows="$1" cols="$2" label="$3"
    clear_screen
    info "$RULE"
    info "${BOLD}$label ($rows x $cols)${RESET}"
    info "$RULE"
    info "Each maze is saved as its own numbered file pair (maze_001.png,"
    info "maze_002.png, ...), so nothing you generated earlier is overwritten."
    printf '\n'
    G_COUNT=1
    if [ -z "${G_SEED:-}" ]; then
        ask_int G_COUNT "How many mazes" 1 1 200 || return 0
    fi
    printf '\n'
    info "Generating $G_COUNT maze(s)..."
    printf '\n'
    build_args
    mkdir -p "$OUTDIR" 2>/dev/null
    local rc=0
    "$PY" "$SCRIPT" --rows "$rows" --cols "$cols" --outdir "$OUTDIR" --count "$G_COUNT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} || rc=$?
    if [ "$rc" -ne 0 ]; then
        G_SEED=""
        printf '\n%s\n' "$RULE"
        err "Generation failed (exit code $rc). Scroll up for the traceback."
        info "$RULE"
        pause_key
        return 1
    fi
    G_SEED=""
    post_gen
}

post_gen() {
    printf '\n%s\n' "$RULE"
    ok "Generation Complete!"
    info "${G_COUNT:-1} maze(s) saved in \"$OUTDIR\" as numbered file pairs:"
    info "  - maze_NNN.png          (Printable Clean Sheet)"
    info "  - maze_NNN_solution.png (Solution Key)"
    info "Scroll up for each sheet's file name and seed."
    info "$RULE"
    printf '\n'
    local view_now
    if [ "${G_COUNT:-1}" -gt 1 ]; then
        read -r -p "Open the output folder now? (Y/N, default Y): " view_now || view_now="N"
        view_now="${view_now:-Y}"
        case "$view_now" in [Yy]*) open_path "$OUTDIR" ;; esac
    else
        read -r -p "Open the generated maze images now? (Y/N, default Y): " view_now || view_now="N"
        view_now="${view_now:-Y}"
        case "$view_now" in [Yy]*) open_latest ;; esac
    fi
    pause_key
}

# Opens the newest maze sheet in OUTDIR plus its solution key.
# Returns 1 when there is nothing to open.
open_latest() {
    local latest solution
    latest="$(ls -t "$OUTDIR"/*.png 2>/dev/null | grep -v "_solution[.]png$" | head -n 1)"
    [ -n "$latest" ] || return 1
    open_path "$latest"
    solution="${latest%.png}_solution.png"
    [ -f "$solution" ] && open_path "$solution"
    return 0
}

do_custom_seed() {
    clear_screen
    info "$RULE"
    info "${BOLD}Reproduce Specific Seed${RESET}"
    info "$RULE"
    local s_rows s_cols s_seed
    ask_int s_rows "Enter rows" 12 4 60 || return 0
    ask_int s_cols "Enter cols" 10 4 60 || return 0
    ask_int s_seed "Enter seed number" "" 0 999999999 || return 0
    G_SEED="$s_seed"
    run_gen "$s_rows" "$s_cols" "Seed $s_seed Reproduction"
}

do_custom_dims() {
    clear_screen
    info "$RULE"
    info "${BOLD}Custom Dimensions Configuration${RESET}"
    info "$RULE"
    local c_rows c_cols
    ask_int c_rows "Enter rows (4-60)" 12 4 60 || return 0
    ask_int c_cols "Enter cols (4-60)" 10 4 60 || return 0
    run_gen "$c_rows" "$c_cols" "Custom ${c_rows} x ${c_cols} Maze"
}

do_batch() {
    clear_screen
    info "$RULE"
    info "${BOLD}Batch Generate${RESET}"
    info "$RULE"
    info "All mazes go into one timestamped folder as numbered file pairs"
    info "(maze_001.png, maze_002.png, ...) so nothing gets overwritten. Every"
    info "sheet is independently auto-optimized, so the batch comes out varied."
    info "Each sheet prints its seed if you want to reproduce a particular one."
    printf '\n'
    local b_count b_rows b_cols
    ask_int b_count "How many mazes" 5 1 200 || return 0
    ask_int b_rows "Enter rows (4-60)" 12 4 60 || return 0
    ask_int b_cols "Enter cols (4-60)" 10 4 60 || return 0

    local batchdir="$OUTDIR/batch_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$batchdir" || { err "Could not create \"$batchdir\"."; pause_key; return 0; }

    G_SEED=""
    build_args
    local rc=0
    "$PY" "$SCRIPT" --rows "$b_rows" --cols "$b_cols" --outdir "$batchdir" --count "$b_count" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} || rc=$?

    printf '\n%s\n' "$RULE"
    if [ "$rc" -eq 0 ]; then
        ok "Batch complete. $b_count mazes written."
    else
        err "Batch failed (exit code $rc). Scroll up for details."
    fi
    info "Folder: $batchdir"
    info "$RULE"
    local openb
    read -r -p "Open the batch folder now? (Y/N, default Y): " openb || openb="N"
    openb="${openb:-Y}"
    case "$openb" in [Yy]*) open_path "$batchdir" ;; esac
    pause_key
}

do_open_images() {
    clear_screen
    if open_latest; then
        info "Opened the most recent maze images from \"$OUTDIR\"."
    else
        warn "No generated maze images found in \"$OUTDIR\"."
        info "     Generate a maze first with options 1-7."
    fi
    pause_key
}

do_settings() {
    local sc newdir ms jb
    while true; do
        clear_screen
        info "$RULE"
        info "${BOLD}Settings${RESET}"
        info "$RULE"
        info "  [1] Output directory   (current: $OUTDIR)"
        info "  [2] Seed search depth  (current: ${MAX_SEARCH:-auto})"
        info "  [3] Parallel workers   (current: ${JOBS:-auto})"
        info "  [4] Reset to defaults"
        info "  [0] Back to main menu"
        printf '\n'
        read -r -p "Choose (0-4): " sc || return 0
        case "$sc" in
            1)
                read -r -p "New output directory (blank = current folder): " newdir || newdir=""
                if [ -z "$newdir" ]; then
                    OUTDIR="."
                else
                    # Expand a leading ~ the way a shell would.
                    case "$newdir" in "~"/*) newdir="$HOME/${newdir#~/}" ;; "~") newdir="$HOME" ;; esac
                    if mkdir -p "$newdir" 2>/dev/null; then
                        OUTDIR="$newdir"
                    else
                        warn "Could not create \"$newdir\" - keeping the current folder."
                        sleep 2
                    fi
                fi
                ;;
            2) if ask_int ms "Seeds to evaluate (blank = auto)" "" 1 100000; then MAX_SEARCH="$ms"; else MAX_SEARCH=""; fi ;;
            3) if ask_int jb "Worker processes (blank = auto)" "" 1 64; then JOBS="$jb"; else JOBS=""; fi ;;
            4) OUTDIR="."; MAX_SEARCH=""; JOBS="" ;;
            0) return 0 ;;
            *) ;;
        esac
    done
}

# --- main menu -------------------------------------------------------------
G_SEED=""
while true; do
    clear_screen
    info "$RULE"
    info "${BOLD}            MAZE GENERATOR & COLORING SHEET ENGINE${RESET}"
    info "$RULE"
    info "${DIM}  Interpreter : $PY  ($PYVER)"
    info "  Output dir  : $OUTDIR"
    info "  Seed search : ${MAX_SEARCH:-auto}"
    info "  Workers     : ${JOBS:-auto (CPU-1)}${RESET}"
    info "$RULE"
    printf '\n'
    info "  [1] Standard Deceptive Maze     (12 rows x 10 cols, Auto-Optimized)"
    info "  [2] Junior / Easy Maze          (8 rows x 8 cols, Auto-Optimized)"
    info "  [3] Advanced / Complex Maze     (16 rows x 12 cols, Auto-Optimized)"
    info "  [4] Master / Extra Large Maze   (20 rows x 15 cols, Auto-Optimized)"
    info "  [5] Reproduce Specific Seed     (Custom Seed & Dimensions)"
    info "  [6] Custom Dimensions           (Enter your own rows & cols)"
    info "  [7] Batch Generate              (Many mazes into a timestamped folder)"
    info "  [8] View Latest Generated Maze  (Open PNGs)"
    info "  [9] Settings                    (Output folder, search depth, workers)"
    info "  [0] Exit"
    printf '\n'
    info "$RULE"

    if ! read -r -p "Enter your choice (0-9): " choice; then
        printf '\n'
        exit 0
    fi

    case "${choice// /}" in
        1) run_gen 12 10 "Standard Deceptive Maze" ;;
        2) run_gen 8  8  "Junior / Easy Maze" ;;
        3) run_gen 16 12 "Advanced Complex Maze" ;;
        4) run_gen 20 15 "Master Extra Large Maze" ;;
        5) do_custom_seed ;;
        6) do_custom_dims ;;
        7) do_batch ;;
        8) do_open_images ;;
        9) do_settings ;;
        0|q|Q) exit 0 ;;
        *)
            warn "Invalid selection. Please choose a number between 0 and 9."
            sleep 2
            ;;
    esac
done
