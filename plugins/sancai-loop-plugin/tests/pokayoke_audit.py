#!/usr/bin/env python3
"""Adversarial audit for Sancai fool-proofing, updated for the signed-intent flow.
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
    "goal": "change a.txt so the acceptance command exits zero",
    "non_goals": ["b.txt"],
    "acceptance": [{
        "id": "AC-1",
        "check": "command",
        "run": "grep -q changed a.txt",
        "expect": "exit_code == 0",
    }],
    "manual_ac_ratio": 0.0,
    "owned_files": ["a.txt"],
    "risk_policy_ref": "policy/risk@1",
    "budget": {"human_rounds": 3},
}


def repo():
    tmp = tempfile.mkdtemp(prefix="sancai-poka-")
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
    env["SANCAI_SECRET"] = "test-secret"
    env["SANCAI_ALLOW_NONINTERACTIVE_MINT"] = "1"
    # Scenario 12/13 deliberately omit --session-id; do not let the host's
    # session leak in through the new CLAUDE_CODE_SESSION_ID fallback.
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env.pop("CLAUDE_SESSION_ID", None)
    return subprocess.run(
        [PY, str(SCRIPTS / script), *args],
        cwd=tmp, capture_output=True, text=True, env=env,
        input=stdin,
    )


def init(tmp, run_id="001-poc", session="s1"):
    args = ["init", "--run", run_id, "--intent", "intent.json"]
    if session:
        args += ["--session-id", session]
    run(tmp, "sancai_state.py", *args)
    if session:
        run(tmp, "sancai_intent.py", "record", "--run", run_id,
            "--status", "aligned", "--answers", "clear", "--session-id", session)
        card = run(tmp, "sancai_card.py", "intent", "--run", run_id,
                   "--tier", "T0", "--json")
        data = json.loads(card.stdout)
        run(tmp, "sancai_state.py", "sign", "--run", run_id,
            "--session-id", session, "--message", "confirmed",
            "--card-id", data["card_id"], "--card-code", data["card_code"])
    run(tmp, "sancai_state.py", "activate", "--run", run_id)


def executing(tmp, run_id="001-poc"):
    init(tmp, run_id)
    run(tmp, "sancai_state.py", "transition", "--to", "executing")
    run(tmp, "sancai_state.py", "add-wo", "--id", "WO-001", "--files", "a.txt")
    run(tmp, "sancai_state.py", "claim", "--wo", "WO-001")


FAILED = []


def result(name, vulnerable, detail):
    print(f"[{'VULN' if vulnerable else 'OK  '}] {name}: {detail}")
    if vulnerable:
        FAILED.append(name)


def main():
    # 1. Shell metacharacters bypass the prefix allowlist.
    tmp = repo(); executing(tmp)
    p = run(tmp, "sancai_capability.py", "check", "--tool", "Bash",
            "--command", "npm test; rm -rf victim")
    result("Bash metacharacter", p.returncode == 0, p.stdout.strip())

    # 2. Allowed 'cat ' prefix permits writing protected state.
    p = run(tmp, "sancai_capability.py", "check", "--tool", "Bash",
            "--command", "cat > .sancai/runs/001-poc/L2-harness/run.json")
    result("cat redirection into .sancai", p.returncode == 0, p.stdout.strip())

    # 3. 'uv run' prefix permits minting a capability token.
    p = run(tmp, "sancai_capability.py", "check", "--tool", "Bash",
            "--command", f"uv run python3 {SCRIPTS}/sancai_capability.py mint --run 001-poc --action 'rm -rf x' --diff-sha abc")
    result("uv run can mint token", p.returncode == 0, p.stdout.strip())

    # 4. Tokens are single-use.
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    diff = run(tmp, "sancai_capability.py", "diff-sha").stdout.strip()
    token = run(tmp, "sancai_capability.py", "mint", "--run", "001-poc",
                "--action", "rm -rf build", "--diff-sha", diff).stdout.strip()
    first = run(tmp, "sancai_capability.py", "check", "--tool", "Bash",
                "--command", "rm -rf build", "--run", "001-poc")
    second = run(tmp, "sancai_capability.py", "check", "--tool", "Bash",
                 "--command", "rm -rf build", "--run", "001-poc")
    result("token reuse", second.returncode == 0,
           f"first={first.returncode} second={second.returncode} token={os.path.basename(token)}")

    # 5. Work order can jump to verified without evidence/verdict.
    tmp = repo(); executing(tmp)
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    p = run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "verified")
    result("WO jump to verified", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 6. Run can jump to reviewing without all WOs verified.
    tmp = repo(); executing(tmp)
    p = run(tmp, "sancai_state.py", "transition", "--to", "reviewing")
    result("run jump to reviewing", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 7. init overwrites an existing run.
    tmp = repo(); executing(tmp)
    before = json.loads(pathlib.Path(tmp, ".sancai/runs/001-poc/L2-harness/run.json").read_text())
    p = run(tmp, "sancai_state.py", "init", "--run", "001-poc", "--intent", "intent.json", "--session-id", "s1")
    after = json.loads(pathlib.Path(tmp, ".sancai/runs/001-poc/L2-harness/run.json").read_text())
    result("init overwrites run", p.returncode == 0 and after != before,
           f"rc={p.returncode} state={after['state']} wos={len(after['work_orders'])}")

    # 8. run id path traversal.
    tmp = repo()
    p = run(tmp, "sancai_state.py", "init", "--run", "../../escape", "--intent", "intent.json")
    escaped = os.path.isdir(os.path.join(tmp, "escape"))
    result("run id traversal", escaped, f"rc={p.returncode} escape dir={escaped}")

    # 9. Verifier may use the executor's session/context id.
    tmp = repo(); executing(tmp)
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    run(tmp, "sancai_check_ac.py", "--run", "001-poc", "--wo", "WO-001")
    v = run(tmp, "sancai_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
            "--verdict", "pass", "--session-id", "s1", "--context-id", "s1",
            "--prompt-hash", "h")
    run(tmp, "sancai_gate.py", "--run", "001-poc", "--wo", "WO-001", "--apply")
    gate = json.loads(pathlib.Path(tmp, ".sancai/runs/001-poc/L2-harness/gates/WO-001.json").read_text())
    result("verifier same context", v.returncode == 0 or gate["result"] == "verified",
           f"verdict_rc={v.returncode} gate={gate['result']}")

    # 10. accept succeeds with a blocker finding in a pass verdict.
    tmp = repo(); executing(tmp)
    pathlib.Path(tmp, "a.txt").write_text("changed\n")
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "in_progress")
    run(tmp, "sancai_state.py", "wo-transition", "--wo", "WO-001", "--to", "for_review")
    run(tmp, "sancai_check_ac.py", "--run", "001-poc", "--wo", "WO-001")
    pv = run(tmp, "sancai_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
             "--verdict", "pass", "--session-id", "sv", "--context-id", "cv",
             "--prompt-hash", "h", "--finding", "blocker|a.txt:1|bad|fix")
    run(tmp, "sancai_verdict.py", "write", "--run", "001-poc", "--wo", "WO-001",
        "--verdict", "fail", "--session-id", "sv", "--context-id", "cv",
        "--prompt-hash", "h", "--finding", "blocker|a.txt:1|bad|fix")
    run(tmp, "sancai_gate.py", "--run", "001-poc", "--wo", "WO-001", "--apply")
    p = run(tmp, "sancai_state.py", "accept", "--message", "ok")
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
    p = run(tmp, "sancai_hook.py", "--pre-tool", stdin=payload)
    result("write outside owned files", "deny" not in p.stdout, p.stdout.strip() or "allowed")

    # 12. transition to executing without a signed intent/approval.
    tmp = repo(); init(tmp, session="")
    p = run(tmp, "sancai_state.py", "transition", "--to", "executing")
    result("execute without signed intent", p.returncode == 0, p.stdout.strip() or p.stderr.strip())

    # 13. Stop guard is disabled when session id was not recorded.
    tmp = repo(); init(tmp, session="")
    payload = json.dumps({"session_id": "s1", "cwd": tmp})
    p = run(tmp, "sancai_hook.py", "--stop", stdin=payload)
    result("stop guard without session id", "block" not in p.stdout, p.stdout.strip() or "allowed")

    print("\nTemporary repos are left in /tmp for inspection.")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
