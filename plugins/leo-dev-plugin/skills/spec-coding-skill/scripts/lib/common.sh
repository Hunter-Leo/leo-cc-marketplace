#!/usr/bin/env bash
# common.sh — Shared helpers for spec-coding-skill utility scripts.
#
# Source this from a script with:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "$SCRIPT_DIR/lib/common.sh"
#
# Provides consistent status logging, git branch helpers, and a file-existence
# reporter so the individual check scripts don't each re-implement them.

# --- Status logging -----------------------------------------------------------
# Prefix a message with a [LEVEL] tag. `log <LEVEL> <msg...>` is the primitive;
# the log_* helpers are thin wrappers for the common levels.
log()      { echo "[$1] ${*:2}"; }
log_pass() { log PASS "$*"; }
log_fail() { log FAIL "$*"; }
log_info() { log INFO "$*"; }
log_warn() { log WARN "$*"; }

# Report a failure and exit non-zero.
die() { log_fail "$*"; exit 1; }

# --- Git helpers --------------------------------------------------------------
# Current branch name (empty when not in a git repo).
current_branch() { git branch --show-current 2>/dev/null; }

# True when the given branch name is a default/trunk branch.
is_default_branch() { [ "$1" = "main" ] || [ "$1" = "master" ]; }

# --- File checks --------------------------------------------------------------
# check_file <path> <pass_msg> [fail_level] [fail_msg] [indent]
#   Prints "[PASS] <pass_msg>" when <path> is a regular file, otherwise
#   "[<fail_level>] <fail_msg>" (defaults: level FAIL, msg "<pass_msg> missing").
#   <indent> is prepended to the emitted line (for nested output).
#   Returns 0 when the file exists, 1 otherwise — callers decide whether a
#   missing file is fatal (`check_file ... || exit 1`) or not (`check_file ... || true`).
check_file() {
    local path="$1" pass_msg="$2" fail_level="${3:-FAIL}" fail_msg="${4:-$2 missing}" indent="${5:-}"
    if [ -f "$path" ]; then
        echo "${indent}[PASS] ${pass_msg}"
        return 0
    fi
    echo "${indent}[${fail_level}] ${fail_msg}"
    return 1
}
