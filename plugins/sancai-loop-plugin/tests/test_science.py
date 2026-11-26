"""Tests for automatic science routing and audit records."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sancai_science as science  # noqa: E402


class ScienceDetectTest(unittest.TestCase):
    def test_formula_and_numeric_claim_require_both_agents(self):
        intent = {
            "goal": "implement the published formula",
            "acceptance": [{
                "id": "AC-1",
                "run": "python metric.py",
                "expect": "error < 0.5%",
            }],
        }
        result = science.detect(intent)
        self.assertTrue(result["required"])
        self.assertIn("formula", result["signals"])
        self.assertIn("numeric_claim", result["signals"])
        self.assertEqual(
            set(result["suggested_agents"]),
            {"researcher", "science-auditor"},
        )

    def test_plain_crud_does_not_require_science(self):
        intent = {
            "goal": "add a name field to the settings page",
            "acceptance": [{
                "id": "AC-1",
                "run": "npm test -- settings",
                "expect": "exit_code == 0",
            }],
        }
        result = science.detect(intent)
        self.assertFalse(result["required"])
        self.assertEqual(result["suggested_agents"], [])

    def test_repo_notebook_is_a_signal(self):
        root = tempfile.mkdtemp(prefix="sancai-science-")
        try:
            pathlib.Path(root, "analysis.ipynb").write_text("{}")
            result = science.detect({"goal": "add a report"}, root)
            self.assertTrue(result["required"])
            self.assertIn("notebook", result["signals"])
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)

    def test_required_block_needs_reason_and_researcher(self):
        with self.assertRaises(SystemExit):
            science.validate_block({
                "science": {
                    "required": True,
                    "signals": [],
                    "reasons": [],
                    "agents": [],
                    "confidence": "high",
                }
            })

    def test_legacy_intent_without_science_is_allowed(self):
        science.validate_block({})
        self.assertFalse(science.required({}))


class ScienceAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-science-")
        self.root = pathlib.Path(self.tmp)
        (self.root / ".sancai/runs/001/L2-harness").mkdir(parents=True)
        (self.root / ".sancai/runs/001/L3-intent").mkdir(parents=True)
        self.run_data = {
            "run": "001",
            "state": "executing",
            "intent_file": "L3-intent/intent.json",
        }
        (self.root / ".sancai/runs/001/L2-harness/run.json").write_text(
            json.dumps(self.run_data)
        )
        self.intent = {
            "goal": "implement formula",
            "acceptance": [{"id": "AC-1", "run": "x", "expect": "y"}],
            "science": {
                "required": True,
                "signals": ["formula"],
                "reasons": ["formula"],
                "agents": ["researcher", "science-auditor"],
                "confidence": "high",
            },
        }
        (self.root / ".sancai/runs/001/L3-intent/intent.json").write_text(
            json.dumps(self.intent)
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_audit_blocks(self):
        status = science.audit_status(self.tmp, "001", "WO-001", self.intent)
        self.assertTrue(status["required"])
        self.assertFalse(status["ok"])
        self.assertIn("missing", status["reason"])

    def test_pass_audit_is_ok(self):
        audit = {
            "run": "001", "wo": "WO-001", "verdict": "pass",
            "assertions": [], "deterministic_checks": [],
        }
        path = self.root / ".sancai/runs/001/L2-harness/science-audit/WO-001.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(audit))
        status = science.audit_status(self.tmp, "001", "WO-001", self.intent)
        self.assertTrue(status["ok"])
        self.assertEqual(status["verdict"], "pass")

    def test_fail_audit_is_not_ok(self):
        path = self.root / ".sancai/runs/001/L2-harness/science-audit/WO-001.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"run": "001", "wo": "WO-001", "verdict": "fail"}))
        status = science.audit_status(self.tmp, "001", "WO-001", self.intent)
        self.assertFalse(status["ok"])
        self.assertEqual(status["verdict"], "fail")

    def test_unverifiable_audit_is_not_ok(self):
        path = self.root / ".sancai/runs/001/L2-harness/science-audit/WO-001.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"run": "001", "wo": "WO-001", "verdict": "unverifiable"}))
        status = science.audit_status(self.tmp, "001", "WO-001", self.intent)
        self.assertFalse(status["ok"])
        self.assertEqual(status["verdict"], "unverifiable")

    def test_record_audit_cli(self):
        source = self.root / "audit-source.json"
        source.write_text(json.dumps({"verdict": "unverifiable"}))
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_science.py"),
             "--root", self.tmp, "record-audit",
             "--run", "001", "--wo", "WO-001", "--file", str(source)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        audit = json.loads(pathlib.Path(
            self.tmp, ".sancai/runs/001/L2-harness/science-audit/WO-001.json"
        ).read_text())
        self.assertEqual(audit["verdict"], "unverifiable")
        self.assertEqual(audit["run"], "001")


if __name__ == "__main__":
    unittest.main()
