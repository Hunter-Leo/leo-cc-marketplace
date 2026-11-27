#!/usr/bin/env python3
"""Expected-change proposals and deterministic protected-path checks.

The executor never edits ``.sancai`` files directly. It submits an EC draft
through ``sancai_change.py propose``; G0 freezes the draft under L2 and G3
compares the live draft with that frozen manifest.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

import sancai_paths as paths  # type: ignore

TYPES = {"behavior_change", "corpus_rebaseline", "oracle_fix"}
ORACLES = {"exact", "semantic", "property", "statistical", "human"}
TERMINAL = ("accepted", "abandoned")
VOLATILE = ("collected_at", "written_at", "created_at", "updated_at",
            "started_at", "finished_at", "timestamp", "duration_ms")


class ChangeError(Exception):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _require(ok, message):
    if not ok:
        raise ChangeError(message)


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def find_root():
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".sancai")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_rel_path(value, field, run=None):
    _require(_nonempty(value), f"{field} must be a non-empty string")
    _require(not os.path.isabs(value), f"{field} must be relative: {value!r}")
    _require("\\" not in value, f"{field} must use POSIX separators: {value!r}")
    parts = value.split("/")
    _require(".." not in parts, f"{field} must stay inside the run: {value!r}")
    norm = os.path.normpath(value).replace(os.sep, "/")
    _require(norm not in ("", "."), f"{field} is empty")
    if run is not None:
        prefix = f".sancai/runs/{run}"
        _require(
            norm == prefix or norm.startswith(prefix + "/"),
            f"{field} must be inside .sancai/runs/{run}: {value!r}",
        )
    return norm


def validate_glob(value, field):
    _require(_nonempty(value), f"{field} entries must be non-empty strings")
    _require(not os.path.isabs(value), f"{field} must be relative: {value!r}")
    _require("\\" not in value, f"{field} must use POSIX separators: {value!r}")
    _require(".." not in value.split("/"), f"{field} must stay inside the repo: {value!r}")
    if value == ".sancai" or value.startswith(".sancai/"):
        raise ChangeError(f"{field} must not target .sancai: {value!r}")
    return value


def validate_report_path(value, field, run=None):
    path = validate_rel_path(value, field, run)
    if run is not None:
        prefix = f".sancai/runs/{run}/L2-harness/"
        _require(path.startswith(prefix), f"{field} must be under {prefix}: {value!r}")
    return path


def validate_test_policy(policy, run=None):
    if policy is None:
        return None
    _require(isinstance(policy, dict), "intent.test_policy must be an object")
    _require(_nonempty(policy.get("command")), "intent.test_policy.command is required")
    timeout = policy.get("timeout_seconds", 1800)
    _require(
        isinstance(timeout, int) and not isinstance(timeout, bool) and 30 <= timeout <= 86400,
        "intent.test_policy.timeout_seconds must be an integer from 30 to 86400",
    )
    report = policy.get("report")
    if report is not None:
        validate_report_path(report, "intent.test_policy.report", run)
    coverage = policy.get("coverage")
    if coverage is not None:
        _require(isinstance(coverage, dict), "intent.test_policy.coverage must be an object")
        if coverage.get("command") is not None:
            _require(
                _nonempty(coverage.get("command")),
                "intent.test_policy.coverage.command must be a non-empty string",
            )
        enforce = coverage.get("enforce", True)
        _require(
            isinstance(enforce, bool),
            "intent.test_policy.coverage.enforce must be boolean",
        )
        cov_report = coverage.get("report")
        if cov_report is not None:
            validate_report_path(cov_report, "intent.test_policy.coverage.report", run)
        elif enforce:
            raise ChangeError(
                "intent.test_policy.coverage.report is required when enforce=true"
            )
        core = coverage.get("core_globs")
        if core is not None:
            _require(
                isinstance(core, list) and core,
                "intent.test_policy.coverage.core_globs must be a non-empty list",
            )
            for pattern in core:
                validate_glob(pattern, "intent.test_policy.coverage.core_globs")
        elif enforce:
            raise ChangeError(
                "intent.test_policy.coverage.core_globs is required when enforce=true"
            )
        minimum = coverage.get("minimum_core_percent")
        if minimum is not None:
            _require(
                isinstance(minimum, (int, float)) and not isinstance(minimum, bool)
                and 0 <= minimum <= 100,
                "intent.test_policy.coverage.minimum_core_percent must be 0..100",
            )
        elif enforce:
            raise ChangeError(
                "intent.test_policy.coverage.minimum_core_percent is required when enforce=true"
            )
    return policy


def validate_change_policy(policy):
    if policy is None:
        return None
    _require(isinstance(policy, dict), "intent.change_policy must be an object")
    allowed = policy.get("expected_change_allowed", False)
    _require(isinstance(allowed, bool), "intent.change_policy.expected_change_allowed must be boolean")
    globs = policy.get("protected_globs", [])
    _require(isinstance(globs, list), "intent.change_policy.protected_globs must be a list")
    for pattern in globs:
        validate_glob(pattern, "intent.change_policy.protected_globs")
    maximum = policy.get("max_changed_files", 50)
    _require(
        isinstance(maximum, int) and not isinstance(maximum, bool) and maximum >= 0,
        "intent.change_policy.max_changed_files must be an integer >= 0",
    )
    threshold = policy.get("science_audit_above")
    if threshold is not None:
        _require(
            isinstance(threshold, int) and not isinstance(threshold, bool) and threshold >= 0,
            "intent.change_policy.science_audit_above must be an integer >= 0",
        )
    baseline = policy.get("baseline_id")
    if baseline is not None:
        _require(_nonempty(baseline), "intent.change_policy.baseline_id must be a non-empty string")
    rollback = policy.get("require_rollback_plan", False)
    _require(isinstance(rollback, bool), "intent.change_policy.require_rollback_plan must be boolean")
    return policy


def _segment_regex(segment):
    out = []
    i = 0
    while i < len(segment):
        ch = segment[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            end = segment.find("]", i + 1)
            if end == -1:
                out.append(re.escape(ch))
            else:
                body = segment[i + 1:end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = end
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def glob_regex(pattern):
    parts = pattern.split("/")
    translated = []
    for index, part in enumerate(parts):
        if part == "**":
            translated.append(".*" if index == len(parts) - 1 else "(?:[^/]+/)*")
        else:
            translated.append(_segment_regex(part))
    return "^" + "/".join(translated) + "$"


def glob_match(path, pattern):
    return re.match(glob_regex(pattern), path) is not None


def _glob_covers(protected, scope):
    if protected == scope:
        return True
    if protected.endswith("/**"):
        base = protected[:-3]
        if not base:
            return True
        if scope == base or scope.startswith(base + "/"):
            return True
    if not any(ch in scope for ch in "*?["):
        return glob_match(scope, protected)
    return False


def scope_is_protected(scope, protected_globs):
    return any(_glob_covers(p, scope) for p in protected_globs)


def validate_expected_change(ec, policy, wo, intent, changed=None):
    if not isinstance(ec, dict):
        raise ChangeError("expected change must be an object")
    for key in ("approved", "approved_by", "approved_at"):
        if key in ec:
            raise ChangeError(f"expected change cannot self-approve ({key})")
    ec_id = ec.get("id")
    _require(
        isinstance(ec_id, str) and re.fullmatch(r"EC-[A-Za-z0-9][A-Za-z0-9._-]*", ec_id),
        f"expected change id must look like EC-001: {ec_id!r}",
    )
    _require(ec.get("wo") == wo, f"{ec_id} must target work order {wo}")
    _require(ec.get("type") in TYPES, f"{ec_id}.type must be one of {sorted(TYPES)}")
    _require(_nonempty(ec.get("reason")), f"{ec_id}.reason must be a non-empty string")
    req = ec.get("req")
    selected = intent.get("requirements") or []
    if selected:
        _require(req in selected, f"{ec_id}.req must be one of the selected requirements")
    elif req is not None:
        _require(_nonempty(req), f"{ec_id}.req must be a non-empty string when present")
    acs = ec.get("ac")
    _require(isinstance(acs, list) and acs, f"{ec_id}.ac must be a non-empty list")
    known_ac = {
        item.get("id") for item in intent.get("acceptance", [])
        if isinstance(item, dict)
    }
    for ac in acs:
        _require(_nonempty(ac), f"{ec_id}.ac entries must be non-empty strings")
        if known_ac:
            _require(ac in known_ac, f"{ec_id}.ac references unknown acceptance criterion {ac!r}")
    scopes = ec.get("scope")
    _require(isinstance(scopes, list) and scopes, f"{ec_id}.scope must be a non-empty list")
    for scope in scopes:
        validate_glob(scope, f"{ec_id}.scope")
        _require(
            scope_is_protected(scope, policy.get("protected_globs", [])),
            f"{ec_id}.scope is outside change_policy.protected_globs: {scope!r}",
        )
    affected = ec.get("affected_cases")
    _require(
        isinstance(affected, int) and not isinstance(affected, bool) and affected >= 0,
        f"{ec_id}.affected_cases must be an integer >= 0",
    )
    _require(ec.get("oracle") in ORACLES, f"{ec_id}.oracle must be one of {sorted(ORACLES)}")
    _require(_nonempty(ec.get("oracle_ref")), f"{ec_id}.oracle_ref must be a non-empty string")
    expected = ec.get("expected_failures", [])
    _require(isinstance(expected, list), f"{ec_id}.expected_failures must be a list")
    _require(
        all(_nonempty(item) for item in expected),
        f"{ec_id}.expected_failures entries must be non-empty strings",
    )
    for field in ("old_baseline", "new_baseline", "migration"):
        if field in ec:
            _require(isinstance(ec[field], str), f"{ec_id}.{field} must be a string")
    backward = ec.get("backward_compatible")
    _require(isinstance(backward, bool), f"{ec_id}.backward_compatible must be boolean")
    if policy.get("require_rollback_plan") and not _nonempty(ec.get("rollback")):
        raise ChangeError(f"{ec_id}.rollback is required by change_policy")
    if changed is not None:
        applies = [
            path for path in changed
            if any(glob_match(path, scope) for scope in scopes)
        ]
        _require(
            len(applies) == affected,
            f"{ec_id}.affected_cases={affected} but {len(applies)} changed files match scope",
        )
    return ec


def changed_files(root):
    out = set()
    proc = subprocess.run(
        ["git", "-C", root, "diff", "HEAD", "--name-status", "-M"],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            if status.startswith(("R", "C")) and len(parts) >= 3:
                out.add(parts[1])
                out.add(parts[2])
            else:
                out.add(parts[1])
    proc = subprocess.run(
        ["git", "-C", root, "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode == 0:
        out.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    clean = []
    for path in out:
        path = path.replace("\\", "/")
        if path == ".sancai" or path.startswith(".sancai/"):
            continue
        if path:
            clean.append(path)
    return sorted(set(clean))


def protected_changes(changed, protected_globs):
    return sorted({
        path for path in changed
        if any(glob_match(path, pattern) for pattern in protected_globs)
    })


def _live_ecs(root, run, wo):
    directory = paths.expected_changes_dir(root, run, wo)
    if not os.path.isdir(directory):
        return []
    result = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        stem = name[:-5]
        item = {
            "id": stem,
            "path": os.path.relpath(path, paths.run_dir(root, run)).replace(os.sep, "/"),
            "sha256": sha_file(path),
        }
        try:
            item["data"] = load(path)
        except (OSError, ValueError) as exc:
            item["error"] = f"cannot read {name}: {exc}"
        result.append(item)
    return result


def _manifest_ecs(ecs):
    return [
        {"id": item["id"], "path": item["path"], "sha256": item["sha256"],
         "data": item.get("data")}
        for item in ecs if isinstance(item, dict) and item.get("id")
    ]


def ec_data_sha(data):
    return "sha256:" + sha_bytes(canonical(data).encode())


def expected_change_drift(evidence_ecs, manifest):
    """Compare the EC snapshot in G0 evidence with the frozen manifest."""
    frozen = {
        item.get("id"): ec_data_sha(item.get("data"))
        for item in ((manifest or {}).get("ecs") or [])
        if isinstance(item, dict) and item.get("id")
    }
    observed = {
        item.get("id"): item.get("ec_sha")
        for item in (evidence_ecs or [])
        if isinstance(item, dict) and item.get("id")
    }
    problems = []
    for ec_id in sorted(
        {key for key in set(frozen) | set(observed) if isinstance(key, str)}
    ):
        if ec_id not in observed:
            problems.append(f"evidence is missing expected change {ec_id}")
        elif ec_id not in frozen:
            problems.append(f"evidence has unknown expected change {ec_id}")
        elif frozen[ec_id] != observed[ec_id]:
            problems.append(f"evidence expected change {ec_id} differs from the frozen manifest")
    return problems


def freeze_expected_changes(root, run, wo, changed=None):
    run_data = load(paths.run_path(root, run))
    intent = load(paths.intent_path(root, run, run_data))
    policy = validate_change_policy(intent.get("change_policy"))
    live = _live_ecs(root, run, wo)
    if policy is None:
        violations = [
            f"expected change proposal without change_policy: {item['path']}"
            for item in live
        ]
        return {
            "required": False, "ok": not violations, "ecs": [],
            "manifest_sha": None, "violations": violations, "frozen": False,
        }
    manifest_path = paths.frozen_expected_change_manifest(root, run, wo)
    if os.path.isfile(manifest_path):
        try:
            manifest = load(manifest_path)
        except (OSError, ValueError) as exc:
            return {
                "required": True, "ok": False, "ecs": [],
                "manifest_sha": sha_file(manifest_path),
                "violations": [f"unreadable frozen expected-change manifest: {exc}"],
                "frozen": True,
            }
        if not isinstance(manifest, dict):
            return {
                "required": True, "ok": False, "ecs": [],
                "manifest_sha": sha_file(manifest_path),
                "violations": ["frozen expected-change manifest must be an object"],
                "frozen": True,
            }
        violations = []
        if manifest.get("run") != run or manifest.get("work_order") != wo:
            violations.append("frozen expected-change manifest is for another run/work order")
        frozen_map = {
            item.get("id"): item.get("sha256")
            for item in (manifest.get("ecs") or [])
            if isinstance(item, dict) and item.get("id")
        }
        live_map = {item["id"]: item["sha256"] for item in live}
        if frozen_map != live_map:
            violations.append("expected changes differ from the frozen manifest")
        return {
            "required": True, "ok": not violations,
            "ecs": _manifest_ecs(manifest.get("ecs") or []),
            "manifest_sha": sha_file(manifest_path),
            "violations": violations, "frozen": True,
        }

    if changed is None:
        changed = changed_files(root)
    violations = []
    valid = []
    seen = set()
    for item in live:
        if item["id"] in seen:
            violations.append(f"duplicate expected change id: {item['id']}")
            continue
        seen.add(item["id"])
        if item.get("error"):
            violations.append(item["error"])
            continue
        data = item.get("data")
        try:
            _require(data.get("id") == item["id"], f"{item['id']}.id must match its filename")
            validate_expected_change(data, policy, wo, intent, changed)
        except ChangeError as exc:
            violations.append(str(exc))
            continue
        valid.append(item)
    if violations:
        return {
            "required": True, "ok": False, "ecs": _manifest_ecs(valid),
            "manifest_sha": None, "violations": violations, "frozen": False,
        }
    manifest = {
        "run": run,
        "work_order": wo,
        "baseline_id": policy.get("baseline_id"),
        "frozen_at": now(),
        "ecs": _manifest_ecs(valid),
    }
    save(manifest_path, manifest)
    return {
        "required": True, "ok": True, "ecs": _manifest_ecs(valid),
        "manifest_sha": sha_file(manifest_path), "violations": [], "frozen": True,
    }


def check_frozen_manifest(root, run, wo, require=False):
    run_data = load(paths.run_path(root, run))
    intent = load(paths.intent_path(root, run, run_data))
    policy = validate_change_policy(intent.get("change_policy"))
    if policy is None:
        return {"required": False, "ok": True, "manifest": None, "sha": None,
                "reason": "no change_policy"}
    manifest_path = paths.frozen_expected_change_manifest(root, run, wo)
    if not os.path.isfile(manifest_path):
        return {"required": True, "ok": not require, "manifest": None, "sha": None,
                "reason": "missing frozen expected-change manifest"}
    try:
        manifest = load(manifest_path)
    except (OSError, ValueError) as exc:
        return {"required": True, "ok": False, "manifest": None, "sha": None,
                "reason": f"unreadable frozen expected-change manifest: {exc}"}
    if not isinstance(manifest, dict):
        return {"required": True, "ok": False, "manifest": None, "sha": None,
                "reason": "frozen expected-change manifest must be an object"}
    if manifest.get("run") != run or manifest.get("work_order") != wo:
        return {"required": True, "ok": False, "manifest": None, "sha": None,
                "reason": "frozen expected-change manifest is for another run/work order"}
    frozen_map = {
        item.get("id"): item.get("sha256")
        for item in (manifest.get("ecs") or [])
        if isinstance(item, dict) and item.get("id")
    }
    live_map = {item["id"]: item["sha256"] for item in _live_ecs(root, run, wo)}
    if frozen_map != live_map:
        return {"required": True, "ok": False, "manifest": manifest,
                "sha": sha_file(manifest_path),
                "reason": "live expected changes differ from the frozen manifest"}
    return {"required": True, "ok": True, "manifest": manifest,
            "sha": sha_file(manifest_path), "reason": ""}


def reset_freeze(root, run, wo):
    """Archive a prior G0 freeze before a rework claim starts a new attempt."""
    path = paths.frozen_expected_change_manifest(root, run, wo)
    if os.path.isfile(path):
        stamp = re.sub(r"[^0-9A-Za-z_.-]", "-", now())
        os.replace(path, path + f".superseded-{stamp}")


def requires_science(intent, expected_changes):
    if bool((intent.get("science") or {}).get("required")):
        return True
    if any(item.get("type") == "corpus_rebaseline" for item in expected_changes):
        return True
    policy = intent.get("change_policy") or {}
    threshold = policy.get("science_audit_above")
    if threshold is not None and expected_changes:
        total = sum(item.get("affected_cases", 0) for item in expected_changes)
        if total >= threshold:
            return True
    return False


def classify(root, run, wo, intent, changed, test_info=None, frozen=None):
    policy = validate_change_policy(intent.get("change_policy"))
    if policy is None:
        return None
    if frozen is None:
        frozen = freeze_expected_changes(root, run, wo, changed)
    protected = protected_changes(changed, policy.get("protected_globs", []))
    violations = list(frozen.get("violations", []))
    expected_changes = []
    expected_failures = {}
    stale = []
    applies_all = set()
    for entry in frozen.get("ecs", []):
        data = entry.get("data") or {}
        applies = [
            path for path in protected
            if any(glob_match(path, scope) for scope in data.get("scope", []))
        ]
        applies_all.update(applies)
        if len(applies) != data.get("affected_cases"):
            violations.append(
                f"{data.get('id')}.affected_cases={data.get('affected_cases')} "
                f"but {len(applies)} changed files match scope"
            )
        if not applies:
            stale.append(f"{data.get('id')} has no changed protected files")
        for test_id in data.get("expected_failures", []):
            expected_failures[test_id] = data.get("id")
        expected_changes.append({
            "id": data.get("id"),
            "ec_sha": "sha256:" + sha_bytes(canonical(data).encode()),
            "type": data.get("type"),
            "scope": data.get("scope", []),
            "affected_cases": data.get("affected_cases", 0),
            "oracle": data.get("oracle"),
            "oracle_ref": data.get("oracle_ref"),
            "applies_to": applies,
            "approved": bool(policy.get("expected_change_allowed")),
            "approved_by": "intent-policy",
        })
    for path in protected:
        if path not in applies_all:
            violations.append(f"protected change without expected change: {path}")
    total = len(applies_all)
    if total > policy.get("max_changed_files", 50):
        violations.append(
            f"changed protected files ({total}) exceed max_changed_files="
            f"{policy.get('max_changed_files', 50)}"
        )
    if protected and not policy.get("expected_change_allowed"):
        violations.append("protected changes are not allowed by change_policy")

    unclassified = []
    report_invalid = bool(test_info and test_info.get("report_invalid"))
    if expected_failures and (not test_info or report_invalid):
        violations.append("expected failures require a valid structured test report")
    failed_ids = set((test_info or {}).get("failed_ids") or [])
    if test_info and not report_invalid:
        missing = sorted(set(expected_failures) - failed_ids)
        for test_id in missing:
            stale.append(f"expected failure did not occur: {test_id}")
        unclassified = sorted(failed_ids - set(expected_failures))
        if not failed_ids and test_info.get("exit_code") not in (0, None):
            unclassified.append("test command exited nonzero but the report has no failures")
    elif test_info and test_info.get("timed_out"):
        unclassified.append("test command timed out")
    elif test_info and test_info.get("exit_code") not in (0, None):
        unclassified.append("test command failed without a structured report")

    return {
        "changed_files": changed,
        "protected_changes": protected,
        "integrity_violations": sorted(set(violations)),
        "expected_changes": expected_changes,
        "manifest_sha": frozen.get("manifest_sha"),
        "expected_failures": expected_failures,
        "stale": stale,
        "unclassified": unclassified,
        "regressions": unclassified,
        "science_required": requires_science(intent, expected_changes),
    }


def cmd_propose(args):
    root = os.path.abspath(args.root or find_root())
    run_data = load(paths.run_path(root, args.run))
    if run_data.get("state") in TERMINAL:
        raise ChangeError(f"cannot propose an expected change for a {run_data['state']} run")
    claim = run_data.get("claim") or {}
    if claim.get("wo") != args.wo:
        raise ChangeError(f"sancai_change.py propose requires the active claim for {args.wo}")
    wo = (run_data.get("work_orders") or {}).get(args.wo) or {}
    if wo.get("state") != "in_progress":
        raise ChangeError(f"{args.wo} must be in_progress to propose an expected change")
    intent = load(paths.intent_path(root, args.run, run_data))
    policy = validate_change_policy(intent.get("change_policy"))
    if policy is None:
        raise ChangeError("intent.change_policy is required for expected changes")
    draft = load(args.file)
    validate_expected_change(draft, policy, args.wo, intent)
    target = os.path.join(
        paths.expected_changes_dir(root, args.run, args.wo),
        draft["id"] + ".json",
    )
    save(target, draft)
    print(target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_propose)
    args = ap.parse_args()
    try:
        args.func(args)
    except ChangeError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
