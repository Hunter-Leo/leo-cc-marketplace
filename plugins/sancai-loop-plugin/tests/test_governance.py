"""Expected-change and test-policy governance tests."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
RUN = "001-test"


class BaseGovernanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-governance-")
        self.env = os.environ.copy()
        self.env["SANCAI_SECRET"] = "test-secret"
        self.env["SANCAI_ALLOW_UNATTESTED_VERDICT"] = "1"
        self.env["SANCAI_ALLOW_CARD_TIER_OVERRIDE"] = "1"
        self.env["SANCAI_ALLOW_NONINTERACTIVE_MINT"] = "1"
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        root = pathlib.Path(self.tmp)
        (root / "a.txt").write_text("base\n")
        (root / "golden").mkdir()
        (root / "golden" / "expected.txt").write_text("base\n")
        (root / "run_tests.py").write_text(
            "import json, pathlib, sys\n"
            "report = pathlib.Path(sys.argv[1])\n"
            "ok = pathlib.Path('golden/expected.txt').read_text().strip() == 'base'\n"
            "report.parent.mkdir(parents=True, exist_ok=True)\n"
            "report.write_text(json.dumps({'tests': [{'id': 'test_golden', "
            "'outcome': 'passed' if ok else 'failed'}]}))\n"
            "sys.exit(0 if ok else 1)\n"
        )
        (root / "run_coverage.py").write_text(
            "import json, pathlib, sys\n"
            "report = pathlib.Path(sys.argv[1])\n"
            "report.parent.mkdir(parents=True, exist_ok=True)\n"
            "report.write_text(json.dumps({'files': {'a.txt': {'summary': "
            "{'covered_lines': 90, 'num_statements': 100}}}}))\n"
        )
        self.git("add", "a.txt", "golden/expected.txt")
        self.git("commit", "-qm", "base")
        self.intent = root / "intent.json"
        self.intent.write_text(json.dumps({
            "id": "INT-001",
            "version": 1,
            "goal": "change a.txt while keeping the golden corpus governed",
            "acceptance": [{
                "id": "AC-1", "check": "command",
                "run": "grep -q changed a.txt", "expect": "exit_code == 0",
            }],
            "owned_files": ["a.txt", "golden/expected.txt"],
            "non_goals": ["do not change unrelated files"],
            **self.policies(),
        }))
        self.run_script("sancai_state.py", "init", "--run", RUN,
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        self.run_script("sancai_intent.py", "record", "--run", RUN,
                        "--status", "aligned", "--answers", "clear",
                        "--session-id", "s1", check=True)
        card = self.bind_card("intent")
        self.run_script("sancai_state.py", "sign", "--run", RUN,
                        "--session-id", "s1", "--message", "confirmed",
                        "--card-id", card["card_id"],
                        "--card-code", card["card_code"], check=True)
        self.run_script("sancai_state.py", "activate", "--run", RUN, check=True)

    def policies(self):
        return {
            "test_policy": {
                "command": f"python3 run_tests.py .sancai/runs/{RUN}/L2-harness/test-report.json",
                "report": f".sancai/runs/{RUN}/L2-harness/test-report.json",
                "timeout_seconds": 60,
                "coverage": {
                    "command": f"python3 run_coverage.py .sancai/runs/{RUN}/L2-harness/coverage.json",
                    "report": f".sancai/runs/{RUN}/L2-harness/coverage.json",
                    "core_globs": ["a.txt"],
                    "minimum_core_percent": 80,
                    "enforce": True,
                },
            },
            "change_policy": {
                "expected_change_allowed": True,
                "protected_globs": ["golden/**"],
                "max_changed_files": 2,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp, capture_output=True, text=True)

    def run_script(self, name, *args, check=False):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            cwd=self.tmp, capture_output=True, text=True, env=self.env,
        )
        if check and proc.returncode != 0:
            self.fail(f"{name} failed: {proc.stdout}\n{proc.stderr}")
        return proc

    def bind_card(self, kind):
        proc = self.run_script("sancai_card.py", kind, "--run", RUN,
                               "--json", "--tier", "T0", check=True)
        return json.loads(proc.stdout)

    def start_execution(self):
        self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt,golden/expected.txt",
                        "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        pathlib.Path(self.tmp, "a.txt").write_text("changed\n")

    def propose(self, **overrides):
        data = {
            "id": "EC-001", "wo": "WO-001", "type": "behavior_change",
            "ac": ["AC-1"], "reason": "the oracle now expects the new corpus value",
            "scope": ["golden/**"], "affected_cases": 1,
            "oracle": "semantic", "oracle_ref": "golden/expected.txt",
            "expected_failures": ["test_golden"], "backward_compatible": False,
        }
        data.update(overrides)
        path = pathlib.Path(self.tmp, "ec.json")
        path.write_text(json.dumps(data))
        proc = self.run_script("sancai_change.py", "propose", "--run", RUN,
                               "--wo", "WO-001", "--file", str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def evidence(self):
        path = pathlib.Path(self.tmp, ".sancai/runs", RUN,
                            "L2-harness/evidence/WO-001.json")
        return json.loads(path.read_text())

    def review(self):
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)

    def gate_result(self):
        path = pathlib.Path(self.tmp, ".sancai/runs", RUN,
                            "L2-harness/gates/WO-001.json")
        return json.loads(path.read_text())

    def verify(self, verdict="pass"):
        self.run_script("sancai_verdict.py", "write", "--run", RUN,
                        "--wo", "WO-001", "--verdict", verdict,
                        "--session-id", "sess-v", "--context-id", "ctx-v",
                        "--prompt-hash", "sha256:x", check=True)

class GovernanceTest(BaseGovernanceTest):
    def test_expected_failure_is_classified_and_verified(self):
        self.start_execution()
        pathlib.Path(self.tmp, "golden/expected.txt").write_text("new\n")
        self.propose()
        self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001", check=True)
        ev = self.evidence()
        self.assertTrue(ev["success"])
        self.assertEqual(ev["tests"]["failed"], 1)
        self.assertEqual(ev["tests"]["failures"][0]["expected_by"], "EC-001")
        self.assertEqual(ev["expected_changes"][0]["id"], "EC-001")
        self.assertEqual(ev["integrity_violations"], [])
        self.review()
        self.verify()
        proc = self.run_script("sancai_gate.py", "--run", RUN, "--wo", "WO-001", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_protected_change_without_ec_blocks(self):
        self.start_execution()
        pathlib.Path(self.tmp, "golden/expected.txt").write_text("new\n")
        self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001")
        ev = self.evidence()
        self.assertFalse(ev["success"])
        self.assertTrue(ev["integrity_violations"])
        self.review()
        self.verify()
        proc = self.run_script("sancai_gate.py", "--run", RUN, "--wo", "WO-001", "--apply")
        self.assertNotEqual(proc.returncode, 0)
        gate = self.gate_result()
        self.assertEqual(gate["result"], "blocked")
        self.assertTrue(any("protected change without expected change" in r
                            for r in gate["reasons"]))

    def test_ec_tamper_after_freeze_blocks(self):
        self.start_execution()
        pathlib.Path(self.tmp, "golden/expected.txt").write_text("new\n")
        self.propose()
        self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001", check=True)
        ec_path = pathlib.Path(self.tmp, ".sancai/runs", RUN,
                               "L1-code/expected-changes/WO-001/EC-001.json")
        data = json.loads(ec_path.read_text())
        data["reason"] = "tampered after G0"
        ec_path.write_text(json.dumps(data))
        self.review()
        self.verify()
        proc = self.run_script("sancai_gate.py", "--run", RUN, "--wo", "WO-001", "--apply")
        self.assertNotEqual(proc.returncode, 0)
        gate = self.gate_result()
        self.assertEqual(gate["result"], "blocked")
        self.assertTrue(any("frozen manifest" in r for r in gate["reasons"]))

    def test_underdeclared_affected_cases_blocks(self):
        self.start_execution()
        pathlib.Path(self.tmp, "golden/expected.txt").write_text("new\n")
        self.propose(affected_cases=0)
        proc = self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001")
        self.assertNotEqual(proc.returncode, 0)
        ev = self.evidence()
        self.assertFalse(ev["success"])
        self.assertTrue(any("affected_cases=0" in v for v in ev["integrity_violations"]))
        self.review()
        self.verify()
        proc = self.run_script("sancai_gate.py", "--run", RUN, "--wo", "WO-001", "--apply")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.gate_result()["result"], "blocked")

    def test_coverage_failure_requests_changes(self):
        self.start_execution()
        pathlib.Path(self.tmp, "run_coverage.py").write_text(
            "import json, pathlib, sys\n"
            "report = pathlib.Path(sys.argv[1])\n"
            "report.parent.mkdir(parents=True, exist_ok=True)\n"
            "report.write_text(json.dumps({'files': {'a.txt': {'summary': "
            "{'covered_lines': 50, 'num_statements': 100}}}}))\n"
        )
        proc = self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001")
        self.assertNotEqual(proc.returncode, 0)
        ev = self.evidence()
        self.assertFalse(ev["success"])
        self.assertFalse(ev["coverage"]["passed"])
        self.review()
        self.verify()
        proc = self.run_script("sancai_gate.py", "--run", RUN, "--wo", "WO-001", "--apply")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.gate_result()["result"], "changes_requested")


class MissingCoverageTest(BaseGovernanceTest):
    def policies(self):
        data = super().policies()
        data["test_policy"]["coverage"]["core_globs"] = ["*.txt"]
        return data

    def test_core_file_missing_from_coverage_report_fails(self):
        pathlib.Path(self.tmp, "b.txt").write_text("not measured\n")
        self.start_execution()
        proc = self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001")
        self.assertNotEqual(proc.returncode, 0)
        ev = self.evidence()
        self.assertEqual(ev["coverage"]["core_percent"], 0.0)
        self.assertFalse(ev["coverage"]["passed"])


class LegacyEvidenceTest(BaseGovernanceTest):
    def policies(self):
        return {}

    def test_legacy_evidence_unchanged_without_policies(self):
        self.start_execution()
        self.run_script("sancai_check_ac.py", "--run", RUN, "--wo", "WO-001", check=True)
        ev = self.evidence()
        for key in ("tests", "coverage", "changed_files", "expected_changes"):
            self.assertNotIn(key, ev)


if __name__ == "__main__":
    unittest.main()
