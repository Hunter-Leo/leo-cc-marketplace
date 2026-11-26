"""Unit tests for the three-parameter loop-control budget."""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, SCRIPTS)

import sancai_control as control  # noqa: E402


def _intent(budget):
    return {
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
        "budget": budget,
    }


class ControlIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-control-")
        self.env = os.environ.copy()
        self.env.update({
            "SANCAI_SECRET": "test-secret",
            "SANCAI_ALLOW_UNATTESTED_VERDICT": "1",
            "SANCAI_ALLOW_CARD_TIER_OVERRIDE": "1",
        })
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        pathlib.Path(self.tmp, "a.txt").write_text("base\n")
        pathlib.Path(self.tmp, "b.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp, capture_output=True, text=True)

    def run_script(self, name, *args, check=False):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, name), *args],
            cwd=self.tmp, capture_output=True, text=True, env=self.env,
        )
        if check and proc.returncode != 0:
            self.fail(f"{name} failed:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def start(self, budget, execute=True):
        pathlib.Path(self.tmp, "intent.json").write_text(json.dumps(_intent(budget)))
        self.run_script("sancai_state.py", "init", "--run", "001", "--intent",
                        "intent.json", "--session-id", "s1", check=True)
        self.run_script("sancai_intent.py", "record", "--run", "001", "--status",
                        "aligned", "--answers", "clear", "--session-id", "s1",
                        check=True)
        card = json.loads(self.run_script(
            "sancai_card.py", "intent", "--run", "001", "--json", "--tier", "T0",
            check=True,
        ).stdout)
        self.run_script("sancai_state.py", "sign", "--run", "001", "--session-id",
                        "s1", "--message", "confirmed", "--card-id",
                        card["card_id"], "--card-code", card["card_code"], check=True)
        if execute:
            self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)

    def test_second_claim_pauses_when_attempt_budget_is_one(self):
        self.start({"max_attempts": 1, "max_human_rounds": 6,
                    "deadline_seconds": 172800})
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-002",
                        "--files", "b.txt", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "release", check=True)
        proc = self.run_script("sancai_state.py", "claim", "--wo", "WO-002")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("attempt budget exhausted", proc.stderr + proc.stdout)
        run_path = pathlib.Path(self.tmp, ".sancai/runs/001/L2-harness/run.json")
        run_data = json.loads(run_path.read_text())
        self.assertEqual(run_data["control"]["status"], "paused")
        self.assertEqual(run_data["control"]["attempts"], 1)
        nxt = json.loads(
            self.run_script(
                "sancai_graph.py", "next", "--run", "001", "--json", check=True
            ).stdout
        )
        self.assertEqual(nxt["action"], "budget-grant")
        self.assertIn("paused", nxt["reason"])
        status = json.loads(
            self.run_script(
                "sancai_state.py", "status", "--run", "001", "--json", check=True
            ).stdout
        )
        self.assertEqual(status["control"]["status"], "paused")
        self.run_script(
            "sancai_state.py", "budget-grant", "--run", "001",
            "--field", "max_attempts", "--to", "2", "--reason", "test",
            check=True,
        )
        self.run_script("sancai_state.py", "claim", "--wo", "WO-002", check=True)

    def test_human_round_budget_blocks_second_approval(self):
        self.start({"max_attempts": 10, "max_human_rounds": 1,
                    "deadline_seconds": 172800}, execute=False)
        proc = self.run_script(
            "sancai_state.py", "record-intent", "--run", "001",
            "--session-id", "s1", "--message", "confirmed",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("human-round budget exhausted", proc.stderr + proc.stdout)

    def test_no_progress_stop_lease_pauses_and_allows(self):
        self.start({"max_attempts": 3, "max_human_rounds": 6,
                    "deadline_seconds": 172800})
        payload = json.dumps({"cwd": self.tmp, "session_id": "s1"})
        outputs = []
        for _ in range(3):
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "sancai_hook.py"), "--stop"],
                cwd=self.tmp, input=payload, capture_output=True, text=True,
                env=self.env,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            outputs.append(proc.stdout)
        run_path = pathlib.Path(self.tmp, ".sancai/runs/001/L2-harness/run.json")
        run_data = json.loads(run_path.read_text())
        self.assertEqual(run_data["control"]["status"], "paused")
        self.assertIn("no-progress", run_data["control"]["reason"])
        self.assertNotIn('"decision": "block"', outputs[-1])



class ControlBudgetTest(unittest.TestCase):
    def test_legacy_intent_uses_three_defaults(self):
        budget = control.budget_of({})
        self.assertEqual(budget, control.DEFAULT_BUDGET)

    def test_budget_rejects_non_positive_attempts(self):
        with self.assertRaises(SystemExit):
            control.budget_of({"budget": {"max_attempts": 0}})

    def test_run_attempts_are_finite(self):
        ctl = control.new_control()
        wo = {}
        budget = {"max_attempts": 2, "max_human_rounds": 2, "deadline_seconds": 60}
        self.assertTrue(control.consume_attempt(ctl, budget, wo)[0])
        self.assertTrue(control.consume_attempt(ctl, budget, wo)[0])
        ok, reason = control.consume_attempt(ctl, budget, wo)
        self.assertFalse(ok)
        self.assertIn("attempt budget exhausted", reason)
        self.assertEqual(wo["attempts"], 2)

    def test_deadline_pauses_after_wall_clock(self):
        ctl = control.new_control()
        ctl["started_at"] = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=120)
        ).isoformat()
        budget = {"max_attempts": 10, "max_human_rounds": 6, "deadline_seconds": 60}
        self.assertIn("deadline", control.deadline_reason(ctl, budget))

    def test_human_rounds_are_finite(self):
        ctl = control.new_control()
        budget = {"max_attempts": 10, "max_human_rounds": 1, "deadline_seconds": 60}
        self.assertTrue(control.consume_human_round(ctl, budget, "one")[0])
        ok, reason = control.consume_human_round(ctl, budget, "two")
        self.assertFalse(ok)
        self.assertIn("human-round budget exhausted", reason)

    def test_no_progress_lease_uses_derived_cap(self):
        ctl = control.new_control()
        cap = control.no_progress_cap(3)
        self.assertEqual(cap, 2)
        self.assertFalse(control.observe_progress(ctl, "sha256:a", 3))
        self.assertFalse(control.observe_progress(ctl, "sha256:a", 3))
        self.assertTrue(control.observe_progress(ctl, "sha256:a", 3))
        self.assertGreaterEqual(ctl["no_progress_streak"], cap)

    def test_progress_resets_the_streak(self):
        ctl = control.new_control()
        control.observe_progress(ctl, "sha256:a", 10)
        control.observe_progress(ctl, "sha256:a", 10)
        self.assertEqual(ctl["no_progress_streak"], 1)
        control.observe_progress(ctl, "sha256:b", 10)
        self.assertEqual(ctl["no_progress_streak"], 0)

    def test_grants_raise_effective_budget(self):
        ctl = control.new_control()
        ctl["grants"] = [{"field": "max_attempts", "from": 10, "to": 12}]
        budget = control.effective_budget({}, ctl)
        self.assertEqual(budget["max_attempts"], 12)


if __name__ == "__main__":
    unittest.main()
