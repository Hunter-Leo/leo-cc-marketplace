#!/usr/bin/env bash
set -euo pipefail

mkdir -p src tests

cat > README.md <<'EOF'
# Task API

A small in-memory TODO service.

- `add_task(title)` appends a task
- `list_tasks()` returns a copy
- `delete_task(index)` removes one task

Run the tests with `python3 -m pytest`.
EOF

cat > src/app.py <<'EOF'
TASKS = []


def add_task(title):
    TASKS.append({"title": title, "done": False})
    return TASKS[-1]


def list_tasks():
    return list(TASKS)


def delete_task(index):
    return TASKS.pop(index)
EOF

cat > tests/test_app.py <<'EOF'
from src.app import TASKS, add_task, delete_task, list_tasks


def test_add_task():
    task = add_task("write eval")
    assert task["done"] is False


def test_list_tasks_returns_copy():
    add_task("keep")
    assert list_tasks() is not TASKS


def test_delete_task():
    add_task("remove me")
    assert delete_task(0)["title"] == "remove me"
EOF

git init -q
git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "fixture: task api"
