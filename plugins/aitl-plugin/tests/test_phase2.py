"""Phase 2: human entrypoint, card rendering, decision latency."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aitl_card  # pyright: ignore[reportMissingImports]  # noqa: E402
import aitl_capability  # pyright: ignore[reportMissingImports]  # noqa: E402


class Phase2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aitl-phase2-")
        self.root = pathlib.Path(self.tmp)
        self.env = os.environ.copy()
        self.env["AITL_SECRET"] = "test-secret"
        self.env["AITL_ALLOW_NONINTERACTIVE_MINT"] = "1"
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.root / "a.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        (self.root / "intent.json").write_text(json.dumps({
            "id": "INT-001",
            "version": 1,
            "goal": "change a.txt",
            "non_goals": [],
            "acceptance": [{
                "id": "AC-1",
                "check": "command",
                "run": "grep -q changed a.txt",
                "expect": "exit_code == 0",
            }],
            "manual_ac_ratio": 0.0,
            "risk_policy_ref": "policy/risk@1",
        }))
        self.run_script("aitl_state.py", "init", "--run", "001-test",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        self.run_script("aitl_state.py", "activate", "--run", "001-test", check=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp,
                              capture_output=True, text=True)

    def run_script(self, name, *args, check=False, stdin=None):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            cwd=self.tmp, capture_output=True, text=True, env=self.env,
            stdin=stdin,
        )
        if check and proc.returncode != 0:
            self.fail(f"{name} failed: {proc.stdout}\n{proc.stderr}")
        return proc

    def card(self, kind, *args, tier="T0", check=True):
        proc = self.run_script("aitl_card.py", kind, "--run", "001-test",
                               *args, "--json", "--tier", tier, check=check)
        return json.loads(proc.stdout)

    def sign(self, card):
        return self.run_script(
            "aitl_state.py", "sign", "--run", "001-test",
            "--session-id", "s1", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
        )

    def start_execution(self):
        self.sign(self.card("intent"))
        self.run_script("aitl_state.py", "transition", "--to", "executing", check=True)
        self.run_script("aitl_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", "--reversible", "true", check=True)
        self.run_script("aitl_state.py", "claim", "--wo", "WO-001", check=True)

    # ------------------------------------------------------------------
    # human entrypoint
    # ------------------------------------------------------------------
    def test_human_entrypoint_help(self):
        proc = self.run_script("aitl_human.py", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("human-only", proc.stdout.lower())

    def test_decide_forwards_sign_with_card(self):
        card = self.card("intent")
        proc = self.run_script(
            "aitl_decide.py", "sign", "--run", "001-test",
            "--session-id", "native-ui", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        intent = json.loads((self.root / ".aitl" / "runs" / "001-test"
                             / "intent.json").read_text())
        self.assertEqual(intent["approval"]["approved_in_session"], "native-ui")
        self.assertEqual(intent["approval"]["card_id"], card["card_id"])

    def test_human_entrypoint_requires_tty(self):
        proc = self.run_script(
            "aitl_human.py", "sign", "--run", "001-test",
            "--message", "confirmed", "--session-id", "s1",
            "--card-id", "CARD-000000000000", "--card-code", "00000000",
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("interactive terminal", proc.stderr)

    def test_capability_denies_agent_human_entrypoint(self):
        self.assertEqual(
            aitl_capability._human_decision(["python3", "aitl_human.py", "accept"]),
            ("aitl_human.py", "accept"),
        )

    # ------------------------------------------------------------------
    # card rendering
    # ------------------------------------------------------------------
    def test_escalation_card_renders_custom_options(self):
        self.start_execution()
        self.run_script(
            "aitl_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
            "--type", "out_of_scope", "--what-tried", "tried",
            "--evidence", "e", "--option", "fix capability table",
            "--option", "accept known risk", "--blocking", check=True,
        )
        text = self.run_script("aitl_card.py", "out-of-scope",
                               "--run", "001-test", check=True).stdout
        self.assertIn("fix capability table", text)
        self.assertIn("accept known risk", text)

    def test_accept_card_reply_example_is_accept(self):
        card = {
            "type": "accept", "title": "Acceptance", "run": "r", "stage": "Acceptance",
            "layer": "L3", "progress": "1/1", "trigger": "", "what": ["x"],
            "why": "y", "impact": "z", "options": [],
            "card_id": "CARD-abc", "card_code": "12345678",
        }
        text = aitl_card.render(card)
        self.assertIn("accept CARD-abc 12345678", text)
        self.assertNotIn("confirm CARD-abc", text)

    # ------------------------------------------------------------------
    # latency / metrics
    # ------------------------------------------------------------------
    def test_interactive_intent_sign_without_card(self):
        self.run_script(
            "aitl_state.py", "record-intent", "--run", "001-test",
            "--session-id", "ui", "--message", "confirmed", check=True,
        )
        intent = json.loads((self.root / ".aitl" / "runs" / "001-test"
                             / "intent.json").read_text())
        self.assertEqual(intent["approval"]["source"], "interactive")
        self.assertIsNone(intent["approval"]["card_id"])
        self.run_script("aitl_state.py", "transition", "--to", "executing", check=True)

    def test_interactive_intent_rejects_vague_message(self):
        proc = self.run_script(
            "aitl_state.py", "record-intent", "--run", "001-test",
            "--session-id", "ui", "--message", "ok",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("approval must be one of", proc.stderr)

    def test_sign_records_decision_latency(self):
        card = self.card("intent")
        time.sleep(0.02)
        self.assertEqual(self.sign(card).returncode, 0)
        intent = json.loads((self.root / ".aitl" / "runs" / "001-test"
                             / "intent.json").read_text())
        self.assertGreater(intent["approval"]["latency_seconds"], 0)
        events = (self.root / ".aitl" / "runs" / "001-test"
                  / "events.jsonl").read_text().splitlines()
        signed = [json.loads(line) for line in events
                  if json.loads(line).get("event") == "intent_signed"]
        self.assertGreater(signed[-1]["meta"]["latency_seconds"], 0)

    def test_approve_records_decision_latency(self):
        self.start_execution()
        self.run_script(
            "aitl_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
            "--type", "out_of_scope", "--what-tried", "tried",
            "--evidence", "e", "--blocking", check=True,
        )
        card = self.card("out-of-scope")
        time.sleep(0.02)
        proc = self.run_script(
            "aitl_escalate.py", "approve", "--run", "001-test", "--id", "ESC-001",
            "--message", "approved", "--session-id", "s1",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        esc = json.loads((self.root / ".aitl" / "runs" / "001-test"
                          / "escalations" / "ESC-001.json").read_text())
        self.assertGreater(esc["approved_latency_seconds"], 0)

    def test_graph_metrics_counts_human_minutes(self):
        self.run_script(
            "aitl_state.py", "event", "--run", "001-test",
            "--type", "decision_recorded",
            "--meta", json.dumps({"latency_seconds": 120}),
            check=True,
        )
        proc = self.run_script("aitl_graph.py", "metrics",
                               "--run", "001-test", "--json", check=True)
        metrics = json.loads(proc.stdout)
        self.assertEqual(metrics["human_minutes"], 2.0)
        self.assertEqual(metrics["decisions"], 1)


if __name__ == "__main__":
    unittest.main()
