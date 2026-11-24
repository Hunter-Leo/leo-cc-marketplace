#!/usr/bin/env python3
"""Adversarial audit for AITL fool-proofing, updated for the signed-intent flow.
Does not execute dangerous commands; it asks the capability layer whether they
would be allowed, and checks the state machine's preconditions."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
PY = sys.executable
INTENT = {
    "id": "INT-001",
    "version": 1,
    "goal": "change a.txt",
    "non_goals": ["b.txt"],
    "acceptance": [{
        "id": "AC-1",
        "check": "command",
        "run": "grep -q changed a.txt",
        "expect": "exit_code == 0",
    }],
    "manual_ac_ratio": 0.0,
    "risk_policy_ref": "policy/risk@1",
    "budget": {"human_rounds": 3},
}


def repo():
    tmp = tempfile.mkdtemp(prefix="aitl-poka-")
    subprocess.run(["git", "init", "-q"], cwd=tmp)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp)
    pathlib.Path(tmp, "a.txt").write_text("base\n")
    pathlib.Path(tmp, "b.txt").write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=tmp)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp)
    pathlib.Path(tmp, "intent.json").write_text(json.dumps(INTENT))
    return tmp


def run(tmp, script, *args, stdin=None):
    env = os.environ.copy()
    env["AITL_SECRET"] = "test-secret"
    env["AITL_ALLOW_NONINTERACTIVE_MINT"] = "1"
    return subprocess.run(
        [PY, str(SCRIPTS / script), *args],
        cwd=tmp, capture_output=True, text=True, env=env,
        input=stdin,
    )


def init(tmp, run_id="001-poc", session="s1"):
    args = ["init", "--run", run_id, "--intent", "intent.json"]
    if session:
        args += ["--session-id", session]
    run(tmp, "aitl_state.py", *args)
    if session:
        run(tmp, "aitl_state.py", "sign", "--run", run_id,
            "--session-id", session, "--message", "confirmed")
    run(tmp, "aitl_state.py", "activate", "--run", run_id)


def executing(tmp, run_id="001-poc"):
    init(tmp, run_id)
    run(tmp, "aitl_state.py", "transition", "--to", "executing")
    run(tmp, "aitl_state.py", "add-wo", "--id", "WO-001", "--files", "a.txt")
    run(tmp, "aitl_state.py", "claim", "--wo", "WO-001")


def result(name, vulnerable, detail):
    print(f"[{'VULN' if vulnerable else 'OK  '}] {name}: {detail}")


def main():
    # 1. Shell metacharacters bypass the prefix allowlist.
    tmp = repo(); executing(tmp)
    p = run(tmp, "aitl_capability.py", "check", "--tool", "Bash",
            "--command", "npm test; rm -rf victim")
    result("Bash metacharacter", p.returncode == 0, p.stdout.strip())

    # 2. Allowed 'cat ' prefix permits writing protected state.
    p = run(tmp, "aitl_capability.py", "check", "--tool", "Bash",
            "--command", "cat > .aitl/runs/001-poc/run.json")
    result("cat redirection into .aitl", p.returncode == 0, p.stdout.strip())

    # 3. 'uv run' prefix permits minting a capability token.
    p = run(tmp, "aitl_capability.py", "check", "--tool", "Bash",
            "--command", f"uv run python3 {SCRIPTS}/aitl_capability.py mint --run 001-poc --action 'rm -rf x' --diff-sha abc")
    result("uv run can mint token", p.returncode == 0, p.stdout.strip())

    # 4. Tokens are single-use.
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    diff = run(tmp, "aitl_capability.py", "diff-sha").stdout.strip()
    token = run(tmp, "aitl_capability.py", "mint", "--run", "001-poc",
                "--action", "rm -rf build", "--diff-sha", diff).stdout.strip()
    first = run(tmp, "aitl_capability.py", "check", "--tool", "Bash",
                "--command", "rm -rf build", "--run", "001-poc")
    second = run(tmp, "aitl_capability.py", "check", "--tool", "Bash",
                 "--command", "rm -rf build", "--run", "001-poc")
    result("token reuse", second.returncode == 0,
           f"first={first.returncode} second={second.returncode} token={os.path.basename(token)}")

    # 5. Work order can jump to verified without evidence/verdict.
    tmp = repo(); executing(tmp)
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    p = run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "verified")
    result("WO jump to verified", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 6. Run can jump to reviewing without all WOs verified.
    tmp = repo(); executing(tmp)
    p = run(tmp, "aitl_state.py", "transition", "--to", "reviewing")
    result("run jump to reviewing", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 7. init overwrites an existing run.
    tmp = repo(); executing(tmp)
    before = json.loads(pathlib.Path(tmp, ".aitl/runs/001-poc/run.json").read_text())
    p = run(tmp, "aitl_state.py", "init", "--run", "001-poc", "--intent", "intent.json", "--session-id", "s1")
    after = json.loads(pathlib.Path(tmp, ".aitl/runs/001-poc/run.json").read_text())
    result("init overwrites run", p.returncode == 0 and after != before,
           f"rc={p.returncode} state={after['state']} wos={len(after['work_orders'])}")

    # 8. run id path traversal.
    tmp = repo()
    p = run(tmp, "aitl_state.py", "init", "--run", "../../escape", "--intent", "intent.json")
    escaped = os.path.isdir(os.path.join(tmp, "escape"))
    result("run id traversal", escaped, f"rc={p.returncode} escape dir={escaped}")

    # 9. Verifier may use the executor's session/context id.
    tmp = repo(); executing(tmp)
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    run(tmp, "aitl_check_ac.py", "--run", "001-poc", "--wo", "WO-001")
    v = run(tmp, "aitl_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
            "--verdict", "pass", "--session-id", "s1", "--context-id", "s1",
            "--prompt-hash", "h")
    run(tmp, "aitl_gate.py", "--run", "001-poc", "--wo", "WO-001", "--apply")
    gate = json.loads(pathlib.Path(tmp, ".aitl/runs/001-poc/gate/WO-001.json").read_text())
    result("verifier same context", v.returncode == 0 or gate["result"] == "verified",
           f"verdict_rc={v.returncode} gate={gate['result']}")

    # 10. accept succeeds with a blocker finding in a pass verdict.
    tmp = repo(); executing(tmp)
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "aitl_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    run(tmp, "aitl_check_ac.py", "--run", "001-poc", "--wo", "WO-001")
    pv = run(tmp, "aitl_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
             "--verdict", "pass", "--session-id", "sv", "--context-id", "cv",
             "--prompt-hash", "h", "--finding", "blocker|a.txt:1|bad|fix")
    run(tmp, "aitl_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
        "--verdict", "fail", "--session-id", "sv", "--context-id", "cv",
        "--prompt-hash", "h", "--finding", "blocker|a.txt:1|bad|fix")
    run(tmp, "aitl_gate.py", "--run", "001-poc", "--wo", "WO-001", "--apply")
    p = run(tmp, "aitl_state.py", "accept", "--message", "ok")
    result("accept with blocker finding", pv.returncode == 0 or p.returncode == 0,
           f"pass_verdict_rc={pv.returncode} accept_rc={p.returncode}")

    # 11. PreToolUse denies writes outside an owned file/claim.
    tmp = repo(); executing(tmp)
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": "b.txt"},
        "session_id": "s1",
        "cwd": tmp,
    })
    p = run(tmp, "aitl_hook.py", "--pre-tool", stdin=payload)
    result("write outside owned files", "deny" not in p.stdout, p.stdout.strip() or "allowed")

    # 12. transition to executing without a signed intent/approval.
    tmp = repo(); init(tmp, session="")
    p = run(tmp, "aitl_state.py", "transition", "--to", "executing")
    result("execute without signed intent", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 13. Stop guard is disabled when session id was not recorded.
    tmp = repo(); init(tmp, session="")
    payload = json.dumps({"session_id": "s1", "cwd": tmp})
    p = run(tmp, "aitl_hook.py", "--stop", stdin=payload)
    result("stop guard without session id", "block" not in p.stdout, p.stdout.strip() or "allowed")

    print("\nTemporary repos are left in /tmp for inspection.")


if __name__ == "__main__":
    main()
