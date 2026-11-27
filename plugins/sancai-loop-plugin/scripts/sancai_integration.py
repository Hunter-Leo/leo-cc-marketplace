#!/usr/bin/env python3
"""Run-scope integration gate (G0-R).

G0 verifies one Work Order at a time.  This script runs the intent's
``integration_policy.command`` once every WO is verified, records harness-owned
evidence, and binds that evidence to the exact policy, intent revision, WO
state, HEAD and worktree it was produced against.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys

import sancai_control as control  # type: ignore
import sancai_paths as paths  # type: ignore
import sancai_tests as tests  # type: ignore

SCHEMA_VERSION = 1
VOLATILE = ("started_at", "finished_at", "evidence_sha")


class IntegrationError(Exception):
    pass


def _require(ok, message):
    if not ok:
        raise IntegrationError(message)


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(data):
    if not isinstance(data, str):
        data = canonical(data)
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _normalized(payload):
    return {k: v for k, v in payload.items() if k not in VOLATILE}


def policy_sha(policy):
    return sha(_normalized(policy or {}))


def required(intent):
    policy = (intent or {}).get("integration_policy")
    if policy is None:
        return False
    return bool(policy.get("required", True))


def validate_policy(policy, run=None):
    if policy is None:
        return None
    _require(isinstance(policy, dict), "intent.integration_policy must be an object")
    if not isinstance(policy.get("required", True), bool):
        raise IntegrationError("intent.integration_policy.required must be a boolean")
    is_required = policy.get("required", True)
    if is_required:
        _require(
            _nonempty(policy.get("command")),
            "intent.integration_policy.command is required",
        )
    elif "command" in policy:
        _require(
            _nonempty(policy.get("command")),
            "intent.integration_policy.command must be a non-empty string",
        )
    timeout = policy.get("timeout_seconds", 1800)
    _require(
        isinstance(timeout, int)
        and not isinstance(timeout, bool)
        and 30 <= timeout <= 86400,
        "intent.integration_policy.timeout_seconds must be an integer from 30 to 86400",
    )
    if "report" in policy:
        import sancai_change as change  # type: ignore

        change.validate_report_path(
            policy["report"], "intent.integration_policy.report", run
        )
    ignore = policy.get("ignore_globs", [".sancai/**"])
    _require(
        isinstance(ignore, list) and all(_nonempty(g) for g in ignore),
        "intent.integration_policy.ignore_globs must be a list of strings",
    )
    return policy


def _ignored(path, globs):
    path = path.replace(os.sep, "/")
    for pattern in globs or []:
        pattern = pattern.replace(os.sep, "/")
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and (
            path == pattern[:-3] or path.startswith(pattern[:-3] + "/")
        ):
            return True
    return False


def _git(root, *args):
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        timeout=60,
        check=False,
    )
    return proc.returncode, proc.stdout


def head(root):
    code, out = _git(root, "rev-parse", "HEAD")
    if code != 0:
        return ""
    return out.decode("utf-8", "replace").strip()


def worktree_sha(root, ignore_globs=None):
    """Hash HEAD plus all tracked changes and untracked file contents."""
    globs = list(ignore_globs or []) + [".sancai/**"]
    digest = hashlib.sha256()
    digest.update(("head:" + head(root) + "\n").encode("utf-8"))
    code, diff = _git(root, "diff", "HEAD", "--binary")
    digest.update(b"diff:" if code == 0 else b"diff-unavailable:")
    digest.update(diff if code == 0 else b"")
    code, out = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    files = []
    if code == 0:
        for raw in out.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode("utf-8", "surrogateescape").replace(os.sep, "/")
            if _ignored(rel, globs):
                continue
            files.append(rel)
    for rel in sorted(files):
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        digest.update(("file:" + rel + "\0").encode("utf-8"))
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def wo_state_sha(run_data):
    rows = []
    for wo in (run_data.get("work_orders") or {}).values():
        rows.append(
            {
                "id": wo.get("id"),
                "state": wo.get("state"),
                "req": wo.get("req"),
                "kind": wo.get("kind", "work"),
            }
        )
    rows.sort(key=lambda row: row["id"] or "")
    return sha(rows)


def load_evidence(root, run):
    path = paths.integration_evidence_path(root, run)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _evidence_sha(payload):
    return sha(_normalized(payload))


def evidence_problems(root, run, run_data, intent, evidence=None):
    """Return why the current evidence cannot authorize ``reviewing``."""
    if not required(intent):
        return []
    policy = intent.get("integration_policy") or {}
    if evidence is None:
        evidence = load_evidence(root, run)
    if not evidence:
        return ["integration evidence is missing"]
    problems = []
    if evidence.get("schema_version") != SCHEMA_VERSION:
        problems.append("integration evidence schema_version mismatch")
    if evidence.get("run") != run:
        problems.append("integration evidence belongs to another run")
    if evidence.get("policy_sha") != policy_sha(policy):
        problems.append("integration evidence used a different integration_policy")
    if evidence.get("intent_revision") != intent.get("revision"):
        problems.append("integration evidence used a different intent revision")
    if evidence.get("wo_state_sha") != wo_state_sha(run_data):
        problems.append("Work Order state changed after integration evidence")
    if evidence.get("head") != head(root):
        problems.append("HEAD changed after integration evidence")
    if evidence.get("pre_worktree_sha") != evidence.get("post_worktree_sha"):
        problems.append("integration command mutated the worktree")
    if evidence.get("post_worktree_sha") != worktree_sha(root, policy.get("ignore_globs")):
        problems.append("worktree changed after integration evidence")
    if not evidence.get("success"):
        problems.append(
            "integration command failed (exit %s)" % evidence.get("exit_code")
        )
    if evidence.get("evidence_sha") != _evidence_sha(evidence):
        problems.append("integration evidence hash mismatch")
    report = policy.get("report")
    if report:
        report_path = os.path.join(root, report)
        if not os.path.isfile(report_path):
            problems.append("integration report is missing: " + report)
        else:
            with open(report_path, "rb") as f:
                actual = "sha256:" + hashlib.sha256(f.read()).hexdigest()
            if evidence.get("report_sha") != actual:
                problems.append("integration report changed after evidence")
    return problems


def _archive_attempt(root, run, evidence):
    directory = paths.integration_attempts_dir(root, run)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    stamp = evidence.get("started_at", "").replace(":", "").replace("-", "")
    path = os.path.join(directory, (stamp or "attempt") + ".json")
    index = 1
    while os.path.exists(path):
        index += 1
        path = os.path.join(directory, (stamp or "attempt") + "-%d.json" % index)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_check(root, run, run_data, intent):
    policy = intent.get("integration_policy")
    validate_policy(policy, run)
    command = policy["command"]
    timeout = policy.get("timeout_seconds", 1800)
    ignore = policy.get("ignore_globs", [".sancai/**"])

    before = worktree_sha(root, ignore)
    started = control.now()
    result = tests.run_command(root, command, timeout)
    finished = control.now()
    after = worktree_sha(root, ignore)

    report = policy.get("report")
    report_sha = ""
    if report:
        report_path = os.path.join(root, report)
        if os.path.isfile(report_path):
            with open(report_path, "rb") as f:
                report_sha = "sha256:" + hashlib.sha256(f.read()).hexdigest()

    output = tests.normalize_output(result.get("output", ""))
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "run": run,
        "command": command,
        "timeout_seconds": timeout,
        "policy_sha": policy_sha(policy),
        "intent_revision": intent.get("revision"),
        "wo_state_sha": wo_state_sha(run_data),
        "head": head(root),
        "pre_worktree_sha": before,
        "post_worktree_sha": after,
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out")),
        "success": (
            result.get("exit_code") == 0
            and not result.get("timed_out")
            and before == after
        ),
        "output_head": output[:4000],
        "output_sha": sha(output),
        "report": report or "",
        "report_sha": report_sha,
        "started_at": started,
        "finished_at": finished,
    }
    evidence["evidence_sha"] = _evidence_sha(evidence)
    _archive_attempt(root, run, evidence)
    path = paths.integration_evidence_path(root, run)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(path + ".tmp", path)
    return evidence


def _record_progress(root, run, run_data, intent):
    fp = control.fingerprint(root, run, run_data, intent)
    ctrl = control.control_of(run_data)
    control.observe_progress(ctrl, fp, control.budget_of(intent)["max_attempts"])
    cap = control.no_progress_cap(control.budget_of(intent)["max_attempts"])
    if ctrl.get("no_progress_streak", 0) >= cap:
        control.pause(
            ctrl,
            "no progress across %d integration attempts" % cap,
        )
    return ctrl


def cmd_check(args):
    import sancai_state as state  # type: ignore

    root = state.find_root()
    state.validate_id(args.run, "run")
    path, run_data = state.load_run(root, args.run)
    intent = state.load(paths.intent_path(root, args.run))
    state.require_signed_intent(args.run, intent)
    current = run_data.get("state")
    if current not in ("integrating", "reviewing"):
        raise IntegrationError(
            "integration check requires state integrating or reviewing, got %s" % current
        )
    if not required(intent):
        raise IntegrationError("intent.integration_policy is not required")
    ctrl = control.control_of(run_data)
    if ctrl.get("status") == "paused":
        raise IntegrationError("run is paused: " + (ctrl.get("reason") or "paused"))
    if run_data.get("claim"):
        raise IntegrationError("Work Order is claimed; integration requires no claim")
    for wo in (run_data.get("work_orders") or {}).values():
        if wo.get("state") not in ("verified", "merged"):
            raise IntegrationError(
                "Work Order %s is %s, not verified" % (wo.get("id"), wo.get("state"))
            )

    evidence = run_check(root, args.run, run_data, intent)
    _record_progress(root, args.run, run_data, intent)
    state.save(path, run_data)
    state.append_event(
        root,
        args.run,
        "integration_pass" if evidence["success"] else "integration_fail",
        {"evidence_sha": evidence["evidence_sha"], "exit_code": evidence["exit_code"]},
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["success"] else 1


def cmd_status(args):
    import sancai_state as state  # type: ignore

    root = state.find_root()
    state.validate_id(args.run, "run")
    _, run_data = state.load_run(root, args.run)
    intent = state.load(paths.intent_path(root, args.run))
    evidence = load_evidence(root, args.run)
    problems = evidence_problems(root, args.run, run_data, intent, evidence)
    print(
        json.dumps(
            {
                "run": args.run,
                "state": run_data.get("state"),
                "required": required(intent),
                "present": evidence is not None,
                "success": bool(evidence and evidence.get("success")),
                "problems": problems,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if required(intent) and not problems or not required(intent) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sancai run integration gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="run the integration command and record evidence")
    check.add_argument("--run", required=True)
    check.set_defaults(func=cmd_check)
    status = sub.add_parser("status", help="show integration evidence status")
    status.add_argument("--run", required=True)
    status.set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (IntegrationError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
