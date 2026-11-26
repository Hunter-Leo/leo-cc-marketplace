#!/usr/bin/env python3
"""Tool-level capability model and one-time approval tokens (MVP).

usage:
  sancai_capability.py check --tool Bash --command "npm test"
  sancai_capability.py check --tool Write --path src/a.ts
  sancai_capability.py mint --run 001-x --action "git push --force" --diff-sha abc --ttl 600
  sancai_capability.py verify --token .sancai/runs/001-x/L2-harness/tokens/T-1.json
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
import re

import sancai_paths as paths  # type: ignore

import shlex
import subprocess
import sys
import uuid

os.umask(0o077)

DEFAULT_TABLE = {
    "Read": {"reversible": True, "network": False, "mutates_external_state": False},
    "Grep": {"reversible": True, "network": False, "mutates_external_state": False},
    "Glob": {"reversible": True, "network": False, "mutates_external_state": False},
    "Write": {"reversible": True, "network": False, "mutates_external_state": False},
    "Edit": {"reversible": True, "network": False, "mutates_external_state": False},
    "NotebookEdit": {"reversible": True, "network": False, "mutates_external_state": False},
    "TodoWrite": {"reversible": True, "network": False, "mutates_external_state": False},
    "Task": {"reversible": True, "network": False, "mutates_external_state": False},
    "WebSearch": {"reversible": True, "network": True, "mutates_external_state": False},
    "WebFetch": {"reversible": True, "network": True, "mutates_external_state": False},
    "Bash": {
        "reversible": False,
        "network": False,
        "mutates_external_state": True,
        "allowed_commands": [
            "npm test", "npm run", "npm ci", "pnpm test", "pnpm run", "pnpm install",
            "yarn test", "yarn run", "bun test", "bun run", "npx ", "tsc", "eslint",
            "prettier", "pytest", "python -m pytest", "uv run", "uv sync",
            "go test", "go build", "go vet", "cargo test", "cargo build", "cargo check",
            "make", "dotnet test", "dotnet build", "mvn ", "gradle ",
            "git diff", "git status", "git log", "git branch", "git add", "git commit",
            "git show", "git stash", "rg ", "grep ", "ls ", "cat ", "find ", "wc ",
        ],
    },
    "mcp__github__get_issue": {"reversible": True, "network": True, "mutates_external_state": False},
    "mcp__github__list_prs": {"reversible": True, "network": True, "mutates_external_state": False},
    "mcp__github__create_pr": {"reversible": False, "network": True, "mutates_external_state": True},
    "mcp__github__merge_pr": {"reversible": False, "network": True, "mutates_external_state": True},
    "mcp__email__send": {"reversible": False, "network": True, "mutates_external_state": True},
    "mcp__slack__send_message": {"reversible": False, "network": True, "mutates_external_state": True},
    "mcp__cloud__change_permission": {"reversible": False, "network": True, "mutates_external_state": True},
}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def find_root():
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".sancai")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def load_table(root):
    path = paths.capability_table_path(root)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_TABLE


def active_run(root):
    path = paths.active_path(root)
    if not os.path.isfile(path):
        return None
    raw = open(path, encoding="utf-8").read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("run"):
            return data["run"]
    except json.JSONDecodeError:
        pass
    return raw


def git_diff_sha(root):
    proc = subprocess.run(
        ["git", "-C", root, "diff", "HEAD", "--binary"],
        capture_output=True,
    )
    return hashlib.sha256(proc.stdout).hexdigest()


def verify_token(path):
    secret = os.environ.get("SANCAI_SECRET")
    if not secret:
        return False, "SANCAI_SECRET is not set", {}
    try:
        data = json.load(open(path, encoding="utf-8"))
        payload, mac = data["payload"], data["mac"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        return False, f"cannot read token: {exc}", {}
    expected = hmac.new(secret.encode(), canonical(payload).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return False, "bad mac", {}
    exp = datetime.datetime.fromisoformat(payload["expires_at"])
    if now() > exp:
        return False, "expired", {}
    return True, "valid", payload


HARNESS_SCRIPTS = {
    "sancai_state.py", "sancai_check_ac.py", "sancai_gate.py", "sancai_escalate.py",
    "sancai_graph.py", "sancai_card.py", "sancai_cards.py", "sancai_verdict.py",
    "sancai_decide.py", "sancai_requirements.py",
}
HUMAN_DECISION_COMMANDS = {
    "sancai_state.py": {"sign", "accept"},
    "sancai_escalate.py": {"approve", "reject"},
    "sancai_human.py": {"sign", "approve", "reject", "accept"},
    "sancai_requirements.py": {"promote", "accept", "defer", "reject"},
}
READ_ONLY_GIT = {"diff", "status", "log", "show", "branch", "rev-parse", "ls-files", "grep"}
SHELL_META = (";", "&", "|", "<", ">", "`", "$(", "\n", "\r", "(", ")")
WRITE_BINARIES = {"rm", "mv", "cp", "tee", "chmod", "chown", "dd", "truncate", "mkdir", "touch", "ln"}


def _shell_tokens(command):
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    for token in tokens:
        if any(meta in token for meta in SHELL_META):
            return None
    return tokens


def _norm_path(root, path):
    if not path:
        return None
    root_abs = os.path.realpath(root)
    full = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(root_abs, path))
    if full != root_abs and not full.startswith(root_abs + os.sep):
        return None
    norm = os.path.relpath(full, root_abs)
    if norm == ".." or norm.startswith(".." + os.sep) or norm.startswith(".sancai"):
        return None
    return norm


def _claim(root, run):
    if not run:
        return None, []
    path = paths.run_path(root, run)
    if not os.path.isfile(path):
        return None, []
    data = json.load(open(path, encoding="utf-8"))
    claim = data.get("claim")
    if not claim:
        return None, []
    wo = data.get("work_orders", {}).get(claim.get("wo"), {})
    return claim, wo.get("owned_files", [])


def _in_owned(root, path, owned):
    norm = _norm_path(root, path)
    if norm is None:
        return False
    return any(norm == _norm_path(root, f) for f in owned)


def _git_staged_files(root):
    proc = subprocess.run(
        ["git", "-C", root, "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _git_policy(root, run, tokens):
    sub = tokens[1] if len(tokens) > 1 else ""
    if sub in READ_ONLY_GIT:
        if any(t == "--output" or t.startswith("--output=") for t in tokens[2:]):
            return "deny", "git output redirection is not allowed"
        return "allow", f"read-only git {sub}"
    if sub == "add":
        claim, owned = _claim(root, run)
        if not claim:
            return "deny", "git add requires an active claim"
        flags = tokens[2:]
        if any(f in ("-A", "--all", "-u") for f in flags) or "." in flags:
            return "deny", "git add must name explicit owned files"
        paths = [f for f in flags if not f.startswith("-")]
        if not paths:
            return "deny", "git add requires explicit paths"
        for p in set(_git_staged_files(root)) | set(paths):
            if not _in_owned(root, p, owned):
                return "deny", f"git add path outside owned_files: {p}"
        return "allow", "git add within owned_files"
    if sub == "commit":
        claim, owned = _claim(root, run)
        if not claim:
            return "deny", "git commit requires an active claim"
        if any(f in ("-a", "--all") or f.startswith("-a") for f in tokens[2:]):
            return "deny", "git commit -a is not allowed; name owned files explicitly"
        if any(f in ("-o", "--only", "--include") or f.startswith("--only=") for f in tokens[2:]):
            return "deny", "git commit must use the index; -o/--only/--include are not allowed"
        if "--amend" in tokens:
            return "token", "git commit --amend requires a human token"
        for p in _git_staged_files(root):
            if not _in_owned(root, p, owned):
                return "deny", f"staged path outside owned_files: {p}"
        return "allow", "git commit with owned files only"
    if sub in ("switch", "checkout"):
        args = tokens[2:]
        branch = args[1] if len(args) == 2 else ""
        flag = "-c" if sub == "switch" else "-b"
        if len(args) == 2 and args[0] == flag and re.fullmatch(r"sancai/[A-Za-z0-9._-]+", branch):
            return "allow", f"create Sancai run branch {branch}"
        return "token", f"git {sub} requires a human token"
    if sub in ("push", "merge", "rebase", "reset", "clean", "restore", "rm", "mv"):
        return "token", f"git {sub} requires a human token"
    return "token", f"git {sub} requires a human token"


def _read_paths_ok(root, paths):
    for p in paths:
        if not p or p.startswith("-"):
            continue
        if p.startswith("/") or ".." in p.split(os.sep):
            if _norm_path(root, p) is None:
                return False
    return True


def _human_decision(tokens):
    """Return (script, sub) when tokens invoke a human decision command."""
    for i, token in enumerate(tokens):
        base = os.path.basename(token)
        denied = HUMAN_DECISION_COMMANDS.get(base)
        if denied is None:
            continue
        rest = [t for t in tokens[i + 1:] if not t.startswith("-")]
        sub = rest[0] if rest else ""
        if sub in denied:
            return base, sub
    return None


def _bash_policy(root, run, tokens):
    base = os.path.basename(tokens[0])
    decision = _human_decision(tokens)
    if decision is not None:
        script, sub = decision
        return "deny", (
            f"human decision command '{script} {sub}' must be run by a human; "
            "agent Bash is denied"
        )
    if os.path.basename(base) in HARNESS_SCRIPTS or os.path.basename(base) == "sancai_capability.py":
        return "deny", "harness scripts must be invoked with python3, not directly"
    if base in ("python", "python3"):
        if len(tokens) >= 3 and tokens[1] == "-m" and tokens[2] in ("pytest", "unittest"):
            return "allow", "allowed python test runner"
        if any(os.path.basename(t) == "sancai_capability.py" for t in tokens):
            return "deny", "the agent may not invoke the capability CLI"
        script = next((t for t in tokens[1:] if not t.startswith("-")), "")
        if os.path.basename(script) in HARNESS_SCRIPTS:
            return "allow", f"allowed harness script {os.path.basename(script)}"
        return "deny", "arbitrary python scripts are not allowed"
    if base == "uv":
        if len(tokens) >= 3 and tokens[1] == "run" and tokens[2] in ("pytest", "ruff", "mypy"):
            return "allow", "allowed uv test/lint tool"
        if (
            len(tokens) >= 5
            and tokens[1:3] == ["run", "python"]
            and tokens[3] == "-m"
            and tokens[4] in ("pytest", "unittest")
        ):
            return "allow", "allowed uv python test runner"
        if len(tokens) >= 2 and tokens[1] == "sync":
            return "allow", "allowed uv sync"
        return "deny", "uv is limited to test/lint tools"
    if base == "npx":
        if len(tokens) >= 2 and tokens[1] in ("tsc", "eslint", "prettier", "jest", "vitest"):
            return "allow", f"allowed npx tool {tokens[1]}"
        return "deny", "arbitrary npx packages are not allowed"
    if base in ("npm", "pnpm", "yarn", "bun"):
        sub = tokens[1] if len(tokens) > 1 else ""
        if sub == "test":
            return "allow", f"allowed {base} test"
        if sub == "run":
            script = next((t for t in tokens[2:] if not t.startswith("-")), "")
            if script in ("test", "lint", "build", "typecheck", "check"):
                return "allow", f"allowed {base} run {script}"
            return "token", f"{base} run {script or '<missing>'} requires a human token"
        if sub in ("install", "ci", "add", "remove"):
            return "token", f"{base} {sub} changes dependencies; requires a human token"
        return "deny", f"unsupported {base} subcommand"
    if base == "git":
        return _git_policy(root, run, tokens)
    if base in ("rg", "grep"):
        if not _read_paths_ok(root, tokens[2:]):
            return "deny", "reading outside the repository is not allowed"
        return "allow", "read-only search"
    if base in ("ls", "cat", "wc", "pwd", "head", "tail"):
        if base != "pwd" and not _read_paths_ok(root, tokens[1:]):
            return "deny", "reading outside the repository is not allowed"
        return "allow", "read-only command"
    if base == "find":
        if any(t in ("-delete", "-exec", "-execdir", "-ok", "-okdir",
                     "-fprint", "-fprint0", "-fprintf", "-fls") for t in tokens):
            return "deny", "find with write or exec flags is not allowed"
        if len(tokens) > 1 and not tokens[1].startswith("-") and not _read_paths_ok(root, [tokens[1]]):
            return "deny", "reading outside the repository is not allowed"
        return "allow", "read-only find"
    if base == "sed":
        if "-i" in tokens or "--in-place" in tokens:
            return "token", "in-place edit requires a human token"
        return "allow", "read-only sed"
    if base == "make":
        target = next((t for t in tokens[1:] if not t.startswith("-")), "")
        if target in ("test", "build", "lint", "check"):
            return "allow", f"allowed make {target}"
        return "token", f"make {target or '<default>'} requires a human token"
    if base == "go":
        sub = tokens[1] if len(tokens) > 1 else ""
        if sub in ("test", "build", "vet"):
            return "allow", f"allowed go {sub}"
        return "token", f"go {sub or '<default>'} requires a human token"
    if base == "cargo":
        sub = tokens[1] if len(tokens) > 1 else ""
        if sub in ("test", "build", "check", "clippy"):
            return "allow", f"allowed cargo {sub}"
        if sub == "fmt" and any(t in ("--check", "--check-only") for t in tokens[2:]):
            return "allow", "allowed cargo fmt --check"
        return "token", f"cargo {sub or '<default>'} requires a human token"
    if base == "dotnet":
        sub = tokens[1] if len(tokens) > 1 else ""
        if sub in ("test", "build"):
            return "allow", f"allowed dotnet {sub}"
        return "token", f"dotnet {sub or '<default>'} requires a human token"
    if base in ("mvn", "gradle"):
        sub = next((t for t in tokens[1:] if not t.startswith("-")), "")
        if sub in ("test", "package", "verify", "build", "check"):
            return "allow", f"allowed {base} {sub}"
        return "token", f"{base} {sub or '<default>'} requires a human token"
    if base in ("tsc", "eslint", "prettier", "pytest"):
        return "allow", f"allowed tool {base}"
    if base in WRITE_BINARIES:
        return "token", f"{base} requires a human token"
    return "token", "command is not in the safe allowlist"


def find_token(root, run, action, consume=True):
    if not run:
        return False, "no active run", None
    token_dir = paths.tokens_dir(root, run)
    if not os.path.isdir(token_dir):
        return False, "no token directory", None
    current = git_diff_sha(root)
    for name in sorted(os.listdir(token_dir)):
        if name.endswith(".json.used"):
            path = os.path.join(token_dir, name)
            ok, _, payload = verify_token(path)
            if ok and payload.get("action") == action and payload.get("diff_sha") == current:
                return False, "token already consumed for this action", None
    for name in sorted(os.listdir(token_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(token_dir, name)
        ok, _, payload = verify_token(path)
        if not ok or payload.get("action") != action or payload.get("diff_sha") != current:
            continue
        if consume:
            try:
                os.replace(path, path + ".used")
            except OSError:
                return False, "token already consumed", None
        return True, f"allowed by token {name}", payload
    return False, "no valid token for this action and diff", None


def check(root, tool, command=None, path=None, run=None, token_path=None):
    table = load_table(root)
    entry = table.get(tool)
    if entry is None:
        return False, f"tool not in capability table: {tool} (fail closed)"

    run = run or active_run(root)

    if tool == "Bash" and command:
        tokens = _shell_tokens(command)
        if tokens is None:
            return False, "shell metacharacters are not allowed"
        mode, reason = _bash_policy(root, run, tokens)
        if mode == "allow":
            return True, reason
        if mode == "deny":
            return False, reason
        action = command.strip()
        if token_path:
            ok, why, payload = verify_token(token_path)
            if not ok:
                return False, f"invalid token: {why}"
            if payload.get("action") != action:
                return False, "token action mismatch"
            if payload.get("diff_sha") != git_diff_sha(root):
                return False, "token diff mismatch; the working tree changed after approval"
            try:
                os.replace(token_path, token_path + ".used")
            except OSError:
                return False, "token already consumed"
            return True, f"allowed by token {os.path.basename(token_path)}"
        ok, reason, _ = find_token(root, run, action)
        return ok, reason

    if entry.get("reversible") is False:
        action = command or tool
        if token_path:
            ok, why, payload = verify_token(token_path)
            if not ok:
                return False, f"invalid token: {why}"
            if payload.get("action") != action:
                return False, "token action mismatch"
            if payload.get("diff_sha") != git_diff_sha(root):
                return False, "token diff mismatch; the working tree changed after approval"
            try:
                os.replace(token_path, token_path + ".used")
            except OSError:
                return False, "token already consumed"
            return True, f"allowed by token {os.path.basename(token_path)}"
        ok, reason, _ = find_token(root, run, action)
        return ok, reason

    if tool in ("Write", "Edit", "NotebookEdit") and path:
        claim, owned = _claim(root, run)
        if not claim:
            return False, "no active claim; write denied"
        if not _in_owned(root, path, owned):
            return False, f"path not in owned_files of {claim['wo']}: {path}"
    return True, "allowed"

def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def mint(root, run, action, diff_sha, ttl):
    secret = os.environ.get("SANCAI_SECRET")
    if not secret:
        sys.exit("SANCAI_SECRET is not set; refusing to mint a token")
    native_ui = os.environ.get("SANCAI_NATIVE_UI") == "1"
    if not sys.stdin.isatty() and not native_ui and os.environ.get("SANCAI_ALLOW_NONINTERACTIVE_MINT") != "1":
        sys.exit(
            "refusing to mint without an interactive human terminal; "
            "run this command yourself in a terminal"
        )
    if sys.stdin.isatty() and not native_ui:
        print("Approve this exact irreversible action?")
        print(f"  run:    {run}")
        print(f"  action: {action}")
        print(f"  diff:   {diff_sha}")
        print(f"  ttl:    {ttl}s")
        confirm = input("type the action to confirm: ")
        if confirm != action:
            sys.exit("confirmation did not match the action; no token minted")
    payload = {
        "run": run,
        "action": action,
        "diff_sha": diff_sha,
        "nonce": str(uuid.uuid4()),
        "issued_at": now().isoformat(),
        "expires_at": (now() + datetime.timedelta(seconds=ttl)).isoformat(),
    }
    mac = hmac.new(secret.encode(), canonical(payload).encode(), hashlib.sha256).hexdigest()
    out_dir = paths.tokens_dir(root, run)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{payload['nonce']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"payload": payload, "mac": mac}, f, ensure_ascii=False, indent=2)
    print(path)


def verify(path):
    ok, reason, _ = verify_token(path)
    if reason == "SANCAI_SECRET is not set":
        sys.exit("SANCAI_SECRET is not set; cannot verify")
    return ok, reason


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check")
    p.add_argument("--tool", required=True)
    p.add_argument("--command")
    p.add_argument("--path")
    p.add_argument("--run")
    p.add_argument("--token")
    p.set_defaults(func=lambda a: do_check(a))

    p = sub.add_parser("mint")
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--diff-sha", required=True)
    p.add_argument("--ttl", type=int, default=600)
    p.set_defaults(func=lambda a: mint(find_root(), a.run, a.action, a.diff_sha, a.ttl))

    p = sub.add_parser("verify")
    p.add_argument("--token", required=True)
    p.set_defaults(func=lambda a: do_verify(a.token))

    p = sub.add_parser("diff-sha")
    p.set_defaults(func=lambda _: do_diff_sha())

    args = ap.parse_args()
    args.func(args)


def do_check(args):
    root = find_root()
    ok, reason = check(root, args.tool, args.command, args.path, args.run, args.token)
    print(("ALLOW " if ok else "DENY  ") + reason)
    sys.exit(0 if ok else 1)


def do_verify(token):
    ok, reason = verify(token)
    print(("VALID " if ok else "INVALID ") + reason)
    sys.exit(0 if ok else 1)


def do_diff_sha():
    print(git_diff_sha(find_root()))


if __name__ == "__main__":
    main()
