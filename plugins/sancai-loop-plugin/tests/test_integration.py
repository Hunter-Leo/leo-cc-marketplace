"""Run integration gate (G0-R) and H3 closeout tests.

These tests drive the CLI end to end: a run whose intent declares
``integration_policy`` must pass G0-R before it can enter ``reviewing``, and
project ledger TODOs are staged until the human accepts the run.

Run:
  python3 -m unittest discover -s plugins/sancai-loop-plugin/tests -v
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from test_phase1 import Phase1CardTest  # noqa: E402


class IntegrationMixin:
    run_id = "001-test"

    def set_integration_policy(self, command, required=True, timeout=30):
        path = (self.root / ".sancai" / "runs" / self.run_id
                / "L3-intent" / "intent.json")
        intent = json.loads(path.read_text())
        intent["integration_policy"] = {
            "required": required,
            "command": command,
            "timeout_seconds": timeout,
        }
        path.write_text(json.dumps(intent, ensure_ascii=False, indent=2))
        return intent

    def integration(self, *args, check=False):
        return self.run_script("sancai_integration.py", *args, check=check)

    def run_data(self):
        path = (self.root / ".sancai" / "runs" / self.run_id
                / "L2-harness" / "run.json")
        return json.loads(path.read_text())

    def prepare_gated_run(self, command="grep -q changed a.txt"):
        self.set_integration_policy(command)
        self.sign(self.intent_card(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing",
                        check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", self.run_id,
                        "--wo", "WO-001", check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", self.run_id,
            "--wo", "WO-001", "--verdict", "pass", "--session-id", "v",
            "--context-id", "ctx-v", "--prompt-hash", "h", check=True,
        )
        self.run_script("sancai_gate.py", "--run", self.run_id,
                        "--wo", "WO-001", "--apply", check=True)


class IntegrationGateTest(IntegrationMixin, Phase1CardTest):
    def test_last_gate_enters_integrating_not_reviewing(self):
        self.prepare_gated_run()
        self.assertEqual(self.run_data()["state"], "integrating")

    def test_integration_success_unlocks_reviewing_and_accept(self):
        self.prepare_gated_run()
        self.integration("check", "--run", self.run_id, check=True)
        evidence = json.loads(
            (self.root / ".sancai" / "runs" / self.run_id / "L2-harness"
             / "integration" / "evidence.json").read_text()
        )
        self.assertTrue(evidence["success"])
        self.run_script("sancai_state.py", "transition", "--to", "reviewing",
                        check=True)
        card = self.card("accept")
        proc = self.accept(card)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.run_data()["state"], "accepted")

    def test_failed_integration_keeps_run_integrating(self):
        self.prepare_gated_run("grep -q absent a.txt")
        proc = self.integration("check", "--run", self.run_id)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.run_data()["state"], "integrating")
        blocked = self.run_script("sancai_state.py", "transition",
                                  "--to", "reviewing")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("integration", blocked.stderr)

    def test_mutating_integration_command_fails(self):
        self.prepare_gated_run("sh -c 'echo x >> a.txt'")
        proc = self.integration("check", "--run", self.run_id)
        self.assertNotEqual(proc.returncode, 0)
        evidence = json.loads(
            (self.root / ".sancai" / "runs" / self.run_id / "L2-harness"
             / "integration" / "evidence.json").read_text()
        )
        self.assertFalse(evidence["success"])
        self.assertNotEqual(
            evidence["pre_worktree_sha"], evidence["post_worktree_sha"]
        )

    def test_worktree_change_after_evidence_blocks_review(self):
        self.prepare_gated_run()
        self.integration("check", "--run", self.run_id, check=True)
        (self.root / "a.txt").write_text("changed again\n")
        proc = self.run_script("sancai_state.py", "transition",
                               "--to", "reviewing")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("worktree changed", proc.stderr)

    def test_integration_work_order_requires_failed_attempt(self):
        self.prepare_gated_run("grep -q absent a.txt")
        early = self.run_script(
            "sancai_state.py", "add-wo", "--run", self.run_id,
            "--integration", "--id", "WO-INT-001", "--files", "a.txt",
        )
        self.assertNotEqual(early.returncode, 0)
        self.integration("check", "--run", self.run_id)
        back = self.run_script("sancai_state.py", "transition",
                               "--to", "executing")
        self.assertEqual(back.returncode, 0, back.stdout + back.stderr)
        added = self.run_script(
            "sancai_state.py", "add-wo", "--run", self.run_id,
            "--integration", "--id", "WO-INT-001", "--files", "a.txt",
        )
        self.assertEqual(added.returncode, 0, added.stdout + added.stderr)
        self.assertIsNone(self.run_data()["work_orders"]["WO-INT-001"]["req"])

    def test_integration_policy_validation(self):
        self.set_integration_policy("")
        proc = self.sign(self.intent_card(), check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("integration_policy.command", proc.stderr)


class CloseoutTest(IntegrationMixin, Phase1CardTest):
    def ledger(self, *args, check=True):
        return self.run_script("sancai_requirements.py", *args, check=check)

    def make_req(self, title="A related need"):
        proc = self.ledger(
            "capture", "--title", title, "--type", "feature",
            "--priority", "P2", "--source", "run:001-test",
            "--relation", "related", "--json",
        )
        todo = json.loads(proc.stdout)
        self.ledger("promote", todo["id"], "--acceptance", '["It works"]')
        backlog = json.loads(
            (self.root / ".sancai" / "project" / "backlog.json").read_text()
        )["items"]
        req_id = backlog[todo["id"]]["req"]
        self.ledger("accept", req_id, check=True)
        return req_id

    def capture(self, title="A related need"):
        proc = self.ledger(
            "capture", "--title", title, "--type", "feature",
            "--priority", "P2", "--source", "run:001-test",
            "--relation", "related", "--json",
        )
        return json.loads(proc.stdout)

    def test_todos_are_staged_then_published_at_accept(self):
        req_id = self.make_req()
        self.set_integration_policy("grep -q changed a.txt")
        self.ledger("select", "--run", self.run_id, "--req", req_id)
        self.sign(self.intent_card(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing",
                        check=True)
        staged = self.capture(title="Staged during execution")
        backlog = json.loads(
            (self.root / ".sancai" / "project" / "backlog.json").read_text()
        )["items"]
        self.assertFalse(
            any(item["title"] == staged["title"] for item in backlog.values())
        )
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--req", req_id, "--files", "a.txt",
                        "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", self.run_id,
                        "--wo", "WO-001", check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", self.run_id,
            "--wo", "WO-001", "--verdict", "pass", "--session-id", "v",
            "--context-id", "ctx-v", "--prompt-hash", "h", check=True,
        )
        self.run_script("sancai_gate.py", "--run", self.run_id,
                        "--wo", "WO-001", "--apply", check=True)
        self.integration("check", "--run", self.run_id, check=True)
        self.run_script("sancai_state.py", "transition", "--to", "reviewing",
                        check=True)
        card = self.card("accept")
        proc = self.accept(card)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        backlog = json.loads(
            (self.root / ".sancai" / "project" / "backlog.json").read_text()
        )["items"]
        published = [i for i in backlog.values() if i["title"] == staged["title"]]
        self.assertEqual(len(published), 1)
        requirements = json.loads(
            (self.root / ".sancai" / "project" / "requirements.json").read_text()
        )
        self.assertEqual(
            requirements["requirements"][req_id]["status"], "verified"
        )
        self.assertTrue(
            (self.root / ".sancai" / "project" / "blueprint.md").is_file()
        )
        run = self.run_data()
        self.assertIn(published[0]["id"], run["acceptance"]["captured_todos"])

    def test_resume_after_run_accepted_finishes_journal(self):
        req_id = self.make_req()
        self.set_integration_policy("grep -q changed a.txt")
        self.ledger("select", "--run", self.run_id, "--req", req_id)
        self.sign(self.intent_card(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing",
                        check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--req", req_id, "--files", "a.txt",
                        "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", self.run_id,
                        "--wo", "WO-001", check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", self.run_id,
            "--wo", "WO-001", "--verdict", "pass", "--session-id", "v",
            "--context-id", "ctx-v", "--prompt-hash", "h", check=True,
        )
        self.run_script("sancai_gate.py", "--run", self.run_id,
                        "--wo", "WO-001", "--apply", check=True)
        self.integration("check", "--run", self.run_id, check=True)
        self.run_script("sancai_state.py", "transition", "--to", "reviewing",
                        check=True)
        proc = self.accept(self.card("accept"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        journal_path = (
            self.root / ".sancai" / "runs" / self.run_id
            / "L2-harness" / "closeout" / "journal.json"
        )
        journal = json.loads(journal_path.read_text())
        journal["phase"] = "run_accepted"
        journal_path.write_text(json.dumps(journal))
        events_path = (
            self.root / ".sancai" / "runs" / self.run_id
            / "audit" / "events.jsonl"
        )
        before = events_path.read_text().count("outcome_accepted")

        proc = self.run_script(
            "sancai_closeout.py", "resume", "--run", self.run_id, check=True
        )
        self.assertIn("closeout committed", proc.stdout)
        journal = json.loads(journal_path.read_text())
        self.assertEqual(journal["phase"], "committed")
        self.assertEqual(
            events_path.read_text().count("outcome_accepted"), before
        )
        self.assertEqual(self.run_data()["state"], "accepted")

    def test_staging_after_accept_card_invalidates_closeout(self):
        req_id = self.make_req()
        self.set_integration_policy("grep -q changed a.txt")
        self.ledger("select", "--run", self.run_id, "--req", req_id)
        self.sign(self.intent_card(), check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing",
                        check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--req", req_id, "--files", "a.txt",
                        "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", self.run_id,
                        "--wo", "WO-001", check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", self.run_id,
            "--wo", "WO-001", "--verdict", "pass", "--session-id", "v",
            "--context-id", "ctx-v", "--prompt-hash", "h", check=True,
        )
        self.run_script("sancai_gate.py", "--run", self.run_id,
                        "--wo", "WO-001", "--apply", check=True)
        self.integration("check", "--run", self.run_id, check=True)
        self.run_script("sancai_state.py", "transition", "--to", "reviewing",
                        check=True)
        card = self.card("accept")
        self.capture(title="Too late to stage")
        proc = self.accept(card)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("closeout", proc.stderr)
        self.assertEqual(self.run_data()["state"], "reviewing")


if __name__ == "__main__":
    unittest.main()
