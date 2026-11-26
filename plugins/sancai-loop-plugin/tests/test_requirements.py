"""Project requirement ledger tests.

Covers the project ledger (requirements + backlog), intent selection, work
order binding, and the H3 defer path.

Run:
  python3 -m unittest discover -s plugins/sancai-loop-plugin/tests -v
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


class RequirementsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-req-")
        self.root = pathlib.Path(self.tmp)
        self.env = os.environ.copy()
        self.env["SANCAI_SECRET"] = "test-secret"
        self.env["SANCAI_ALLOW_UNATTESTED_VERDICT"] = "1"
        self.env["SANCAI_ALLOW_CARD_TIER_OVERRIDE"] = "1"
        self.env["SANCAI_ALLOW_NONINTERACTIVE_MINT"] = "1"
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.root / "a.txt").write_text("base\n")
        (self.root / "b.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        (self.root / "intent.json").write_text(json.dumps({
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
        }))
        self.run_script("sancai_state.py", "init", "--run", "001-test",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        self.run_script("sancai_intent.py", "record", "--run", "001-test",
                        "--status", "aligned", "--answers", "clear",
                        "--session-id", "s1", check=True)
        self.run_script("sancai_state.py", "activate", "--run", "001-test", check=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp,
                              capture_output=True, text=True)

    def run_script(self, name, *args, check=False):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            cwd=self.tmp, capture_output=True, text=True, env=self.env,
        )
        if check and proc.returncode != 0:
            self.fail(f"{name} failed: {proc.stdout}\n{proc.stderr}")
        return proc

    def ledger(self, *args, check=True):
        return self.run_script("sancai_requirements.py", *args, check=check)

    def capture(self, title="A related need", relation="related", type_="feature"):
        proc = self.ledger(
            "capture", "--title", title, "--type", type_,
            "--priority", "P2", "--source", "run:001-test",
            "--relation", relation, "--json",
        )
        return json.loads(proc.stdout)

    def promote(self, todo, acceptance='["It works"]'):
        return self.ledger("promote", todo["id"], "--acceptance", acceptance)

    def make_req(self, title="A related need"):
        todo = self.capture(title)
        self.promote(todo)
        req_id = self.backlog_item(todo["id"])["req"]
        self.ledger("accept", req_id, check=True)
        return req_id

    def backlog_item(self, todo_id):
        data = json.loads((self.root / ".sancai" / "project" / "backlog.json").read_text())
        return data["items"][todo_id]

    def intent(self):
        return json.loads(
            (self.root / ".sancai" / "runs" / "001-test" / "L3-intent" / "intent.json").read_text()
        )

    def start_execution(self, req=None):
        self.run_script("sancai_state.py", "sign", "--run", "001-test",
                        "--session-id", "s1", "--message", "confirmed",
                        *self.intent_card_args(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)
        args = ["add-wo", "--id", "WO-001", "--files", "a.txt",
                "--reversible", "true"]
        if req:
            args += ["--req", req]
        self.run_script("sancai_state.py", *args, check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)

    def intent_card_args(self):
        proc = self.run_script("sancai_card.py", "intent", "--run", "001-test",
                               "--json", "--tier", "T0", check=True)
        card = json.loads(proc.stdout)
        return ["--card-id", card["card_id"], "--card-code", card["card_code"]]

    # ------------------------------------------------------------------
    def test_capture_promote_accept(self):
        todo = self.capture("Ship the thing")
        self.assertEqual(todo["status"], "pending")
        self.assertEqual(todo["relation"], "related")
        proc = self.promote(todo)
        self.assertIn("proposed", proc.stdout)
        req_id = self.backlog_item(todo["id"])["req"]
        requirements = json.loads(
            (self.root / ".sancai" / "project" / "requirements.json").read_text()
        )["requirements"]
        self.assertEqual(requirements[req_id]["status"], "proposed")
        self.ledger("accept", req_id)
        requirements = json.loads(
            (self.root / ".sancai" / "project" / "requirements.json").read_text()
        )["requirements"]
        self.assertEqual(requirements[req_id]["status"], "accepted")
        self.assertEqual(len(requirements[req_id]["acceptance"]), 1)

    def test_unrelated_capture_never_enters_intent(self):
        unrelated = self.capture("Unrelated cleanup", relation="unrelated")
        self.promote(unrelated)
        unrelated_req = self.backlog_item(unrelated["id"])["req"]
        self.ledger("accept", unrelated_req)
        related_req = self.make_req("Related need")
        self.ledger("select", "--run", "001-test", "--req", related_req)
        selected = self.intent()["requirements"]
        self.assertEqual(selected, [related_req])
        self.assertNotIn(unrelated_req, selected)
        self.assertEqual(self.intent()["revision"], 1)

    def test_select_requires_accepted_requirement(self):
        todo = self.capture()
        self.promote(todo)
        req_id = self.backlog_item(todo["id"])["req"]
        proc = self.ledger("select", "--run", "001-test", "--req", req_id, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not accepted", proc.stderr)

    def test_select_rejects_signed_intent(self):
        req_id = self.make_req()
        self.ledger("select", "--run", "001-test", "--req", req_id)
        self.run_script("sancai_state.py", "sign", "--run", "001-test",
                        "--session-id", "s1", "--message", "confirmed",
                        *self.intent_card_args(), check=True)
        proc = self.ledger("select", "--run", "001-test", "--req", req_id, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("already signed", proc.stderr)

    def test_add_wo_must_bind_selected_requirement(self):
        req_id = self.make_req()
        self.ledger("select", "--run", "001-test", "--req", req_id)
        self.start_execution(req=req_id)
        run = json.loads(
            (self.root / ".sancai" / "runs" / "001-test" / "L2-harness" / "run.json").read_text()
        )
        self.assertEqual(run["work_orders"]["WO-001"]["req"], req_id)

    def test_add_wo_without_req_fails_when_requirements_selected(self):
        req_id = self.make_req()
        self.ledger("select", "--run", "001-test", "--req", req_id)
        self.run_script("sancai_state.py", "sign", "--run", "001-test",
                        "--session-id", "s1", "--message", "confirmed",
                        *self.intent_card_args(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)
        proc = self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                               "--files", "a.txt", "--reversible", "true")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--req", proc.stderr)

    def test_h3_defer_writes_backlog_todo_not_work_order(self):
        req_id = self.make_req()
        self.ledger("select", "--run", "001-test", "--req", req_id)
        self.start_execution(req=req_id)
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001",
                        check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
            "--verdict", "pass", "--session-id", "v", "--context-id", "ctx-v",
            "--prompt-hash", "h", "--finding",
            "major|a.txt:1|unbounded retry|document risk", check=True,
        )
        self.run_script("sancai_gate.py", "--run", "001-test", "--wo", "WO-001",
                        "--apply", check=True)
        proc = self.run_script("sancai_card.py", "accept", "--run", "001-test",
                               "--json", "--tier", "T0", check=True)
        card = json.loads(proc.stdout)
        ok = self.run_script(
            "sancai_state.py", "accept", "--message", "confirmed",
            "--session-id", "s-accept", "--card-id", card["card_id"],
            "--card-code", card["card_code"], "--ack-findings",
            "--disposition", "defer:WO-002",
        )
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        run = json.loads(
            (self.root / ".sancai" / "runs" / "001-test" / "L2-harness" / "run.json").read_text()
        )
        self.assertEqual(list(run["work_orders"]), ["WO-001"])
        todos = json.loads(
            (self.root / ".sancai" / "project" / "backlog.json").read_text()
        )["items"]
        findings = [item for item in todos.values() if item["type"] == "finding"]
        self.assertEqual(len(findings), 1)
        item = findings[0]
        self.assertEqual(item["relation"], "related")
        self.assertEqual(item["source"], "run:001-test/WO:WO-002")
        self.assertEqual(run["acceptance"]["captured_todos"], [item["id"]])
        self.assertEqual(run["acceptance"]["requirements"], {req_id: ["WO-001"]})

    def test_accept_rejects_uncovered_requirement(self):
        req_id = self.make_req()
        self.ledger("select", "--run", "001-test", "--req", req_id)
        self.start_execution(req=req_id)
        run_path = self.root / ".sancai" / "runs" / "001-test" / "L2-harness" / "run.json"
        run = json.loads(run_path.read_text())
        run["work_orders"]["WO-001"]["req"] = "REQ-999"
        run_path.write_text(json.dumps(run))
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001",
                        check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
            "--verdict", "pass", "--session-id", "v", "--context-id", "ctx-v",
            "--prompt-hash", "h", check=True,
        )
        self.run_script("sancai_gate.py", "--run", "001-test", "--wo", "WO-001",
                        "--apply", check=True)
        proc = self.run_script("sancai_card.py", "accept", "--run", "001-test",
                               "--json", "--tier", "T0", check=True)
        card = json.loads(proc.stdout)
        bad = self.run_script(
            "sancai_state.py", "accept", "--message", "confirmed",
            "--session-id", "s-accept", "--card-id", card["card_id"],
            "--card-code", card["card_code"],
        )
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("no verified work order", bad.stderr)

    def test_blueprint_lists_requirements_and_backlog(self):
        req_id = self.make_req()
        self.capture("Loose end", relation="unrelated")
        proc = self.ledger("blueprint")
        text = pathlib.Path(proc.stdout.strip()).read_text()
        self.assertIn(req_id, text)
        self.assertIn("TODO-002", text)
        self.assertIn("## Backlog", text)
        self.assertIn("## Requirements", text)


if __name__ == "__main__":
    unittest.main()
