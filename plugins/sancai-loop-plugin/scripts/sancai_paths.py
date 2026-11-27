"""Canonical Sancai Loop runtime paths.

The on-disk layout mirrors the three layers:

    .sancai/
      active
      status.last
      capability-table.json
      runs/<run>/
        L3-intent/
          intent.json
          decisions/cards/*.json
          decisions/escalations/*.json
        L2-harness/
          run.json
          progress.md
          gates/*.json
          evidence/*.json
          verdicts/*.json
          tokens/*.json
        L1-code/
          attempts/
          scratch/
        audit/
          events.jsonl
          graph.json
"""

import os

ROOT = ".sancai"


def sancai_dir(root):
    return os.path.join(root, ROOT)


def project_dir(root):
    return os.path.join(sancai_dir(root), "project")


def requirements_path(root):
    return os.path.join(project_dir(root), "requirements.json")


def backlog_path(root):
    return os.path.join(project_dir(root), "backlog.json")


def blueprint_path(root):
    return os.path.join(project_dir(root), "blueprint.md")


def run_dir(root, run):
    return os.path.join(sancai_dir(root), "runs", run)


def l3_dir(root, run):
    return os.path.join(run_dir(root, run), "L3-intent")


def l2_dir(root, run):
    return os.path.join(run_dir(root, run), "L2-harness")


def l1_dir(root, run):
    return os.path.join(run_dir(root, run), "L1-code")


def audit_dir(root, run):
    return os.path.join(run_dir(root, run), "audit")


def intent_path(root, run, data=None):
    rel = (data or {}).get("intent_file") or "L3-intent/intent.json"
    return os.path.join(run_dir(root, run), rel)


def run_path(root, run):
    return os.path.join(l2_dir(root, run), "run.json")


def events_path(root, run):
    return os.path.join(audit_dir(root, run), "events.jsonl")


def graph_path(root, run):
    return os.path.join(audit_dir(root, run), "graph.json")


def evidence_dir(root, run):
    return os.path.join(l2_dir(root, run), "evidence")


def gates_dir(root, run):
    return os.path.join(l2_dir(root, run), "gates")


def verdicts_dir(root, run):
    return os.path.join(l2_dir(root, run), "verdicts")


def tokens_dir(root, run):
    return os.path.join(l2_dir(root, run), "tokens")


def decisions_dir(root, run):
    return os.path.join(l3_dir(root, run), "decisions")


def research_dir(root, run):
    return os.path.join(l3_dir(root, run), "research")


def science_audit_dir(root, run):
    return os.path.join(l2_dir(root, run), "science-audit")


def cards_dir(root, run):
    return os.path.join(decisions_dir(root, run), "cards")


def escalations_dir(root, run):
    return os.path.join(decisions_dir(root, run), "escalations")


def attempts_dir(root, run):
    return os.path.join(l1_dir(root, run), "attempts")


def scratch_dir(root, run):
    return os.path.join(l1_dir(root, run), "scratch")


def expected_changes_dir(root, run, wo=None):
    base = os.path.join(l1_dir(root, run), "expected-changes")
    return os.path.join(base, wo) if wo else base


def frozen_expected_changes_dir(root, run, wo=None):
    base = os.path.join(l2_dir(root, run), "expected-changes")
    return os.path.join(base, wo) if wo else base


def frozen_expected_change_manifest(root, run, wo):
    return os.path.join(frozen_expected_changes_dir(root, run, wo), "manifest.json")


def integration_dir(root, run):
    return os.path.join(l2_dir(root, run), "integration")


def integration_evidence_path(root, run):
    return os.path.join(integration_dir(root, run), "evidence.json")


def integration_attempts_dir(root, run):
    return os.path.join(integration_dir(root, run), "attempts")


def project_baseline_path(root, run):
    return os.path.join(l2_dir(root, run), "project-baseline.json")


def project_updates_path(root, run):
    return os.path.join(l2_dir(root, run), "project-updates.json")


def closeout_dir(root, run):
    return os.path.join(l2_dir(root, run), "closeout")


def closeout_plan_path(root, run):
    return os.path.join(closeout_dir(root, run), "plan.json")


def closeout_journal_path(root, run):
    return os.path.join(closeout_dir(root, run), "journal.json")


def closeout_lock_path(root, run):
    return os.path.join(closeout_dir(root, run), "lock")


def progress_path(root, run):
    return os.path.join(l2_dir(root, run), "progress.md")


def active_path(root):
    return os.path.join(sancai_dir(root), "active")


def status_last_path(root):
    return os.path.join(sancai_dir(root), "status.last")


def capability_table_path(root):
    return os.path.join(sancai_dir(root), "capability-table.json")


def ensure_run_layout(root, run):
    for path in (
        l3_dir(root, run),
        decisions_dir(root, run),
        cards_dir(root, run),
        escalations_dir(root, run),
        research_dir(root, run),
        l2_dir(root, run),
        evidence_dir(root, run),
        gates_dir(root, run),
        verdicts_dir(root, run),
        science_audit_dir(root, run),
        tokens_dir(root, run),
        l1_dir(root, run),
        attempts_dir(root, run),
        scratch_dir(root, run),
        expected_changes_dir(root, run),
        frozen_expected_changes_dir(root, run),
        integration_dir(root, run),
        integration_attempts_dir(root, run),
        closeout_dir(root, run),
        audit_dir(root, run),
    ):
        os.makedirs(path, mode=0o700, exist_ok=True)
