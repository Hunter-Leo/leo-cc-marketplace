#!/usr/bin/env bash
# Create an isolated worktree for one eval run.
# usage: setup_task.sh TASK_JSON RUN_DIR
set -euo pipefail

TASK=${1:?task_json}
RUN_DIR=${2:?run_dir}

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$TASK" "$EVALS" "$RUN_DIR" <<'PY'
import json, os, shutil, subprocess, sys

task_path, evals_root, run_dir = sys.argv[1:4]
task = json.load(open(task_path, encoding="utf-8"))
repo_rel = task["repo"]
base = task.get("base_commit", "")
src = os.path.join(evals_root, repo_rel)
work = os.path.join(run_dir, "work")

if not os.path.isdir(src):
    sys.exit(f"snapshot not found: {src}")

os.makedirs(run_dir, exist_ok=True)
if os.path.exists(work):
    shutil.rmtree(work)

if os.path.isdir(os.path.join(src, ".git")) and base and base != "REPLACE_WITH_COMMIT":
    subprocess.run(
        ["git", "-C", src, "worktree", "add", "--detach", work, base],
        check=True,
    )
else:
    shutil.copytree(src, work, symlinks=True)

run_meta = {
    "task_id": task["id"],
    "task": task,
    "repo": repo_rel,
    "base_commit": base,
    "workdir": work,
}
with open(os.path.join(run_dir, "run.json"), "w", encoding="utf-8") as f:
    json.dump(run_meta, f, ensure_ascii=False, indent=2)
print(work)
PY
