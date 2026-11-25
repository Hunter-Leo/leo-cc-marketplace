"""Core tests for sancai-loop-plugin.

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


class SancaiCoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-test-")
        self.env = os.environ.copy()
        self.env["SANCAI_SECRET"] = "test-secret"
        self.env["SANCAI_ALLOW_NONINTERACTIVE_MINT"] = "1"
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (pathlib.Path(self.tmp) / "a.txt").write_text("base\n")
        (pathlib.Path(self.tmp) / "b.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.intent = pathlib.Path(self.tmp) / "intent.json"
        self.intent.write_text(json.dumps({
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
                        "--intent", "intent.json", "--session-id", "s1")
        self.run_script("sancai_intent.py", "record", "--run", "001-test",
                        "--status", "aligned", "--answers", "clear",
                        "--session-id", "s1", check=True)
        intent_card = self.bind_card("intent", "--run", "001-test")
        self.run_script("sancai_state.py", "sign", "--run", "001-test",
                        "--session-id", "s1", "--message", "confirmed",
                        "--card-id", intent_card["card_id"],
                        "--card-code", intent_card["card_code"], check=True)
        self.run_script("sancai_state.py", "activate", "--run", "001-test")

    def tearDown(self):
        import shutil
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

    def start_execution(self):
        self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)

    def test_full_lifecycle(self):
        self.start_execution()
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        proc = self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.run_script("sancai_verdict.py", "write", "--run", "001-test",
                               "--wo", "WO-001", "--verdict", "pass",
                               "--session-id", "sess-v", "--context-id", "ctx-v",
                               "--prompt-hash", "sha256:x")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.run_script("sancai_gate.py", "--run", "001-test",
                               "--wo", "WO-001", "--apply")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        accept_card = self.bind_card("accept", "--run", "001-test")
        proc = self.run_script("sancai_state.py", "accept", "--message", "confirmed",
                               "--session-id", "s-accept",
                               "--card-id", accept_card["card_id"],
                               "--card-code", accept_card["card_code"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        status = json.loads(self.run_script("sancai_state.py", "status", "--run", "001-test", "--json").stdout)
        self.assertEqual(status["state"], "accepted")
        self.assertEqual(status["work_orders"]["WO-001"]["state"], "verified")

    def test_tty_sign_guard_is_optional(self):
        intent = pathlib.Path(self.tmp) / ".sancai" / "runs" / "001-test" / "L3-intent" / "intent.json"
        self.run_script("sancai_state.py", "init", "--run", "002-tty",
                        "--intent", str(intent), check=True)
        self.run_script("sancai_intent.py", "record", "--run", "002-tty",
                        "--status", "aligned", "--answers", "clear",
                        "--session-id", "sess-h", check=True)
        self.run_script("sancai_state.py", "activate", "--run", "002-tty", check=True)
        tty_card = self.bind_card("intent", "--run", "002-tty")
        env = dict(self.env)
        env["SANCAI_REQUIRE_TTY_SIGN"] = "1"
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_state.py"), "sign",
             "--run", "002-tty", "--session-id", "sess-h", "--message", "confirmed",
             "--card-id", tty_card["card_id"],
             "--card-code", tty_card["card_code"]],
            cwd=self.tmp, capture_output=True, text=True, env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("SANCAI_REQUIRE_TTY_SIGN", proc.stderr)

    def test_transition_requires_clean_tree(self):
        a = pathlib.Path(self.tmp) / "a.txt"
        a.write_text(a.read_text() + "uncommitted\n")
        proc = self.run_script("sancai_state.py", "transition", "--to", "executing")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("uncommitted tracked changes", proc.stderr + proc.stdout)

    def test_overlap_rejected(self):
        self.run_script("sancai_state.py", "transition", "--to", "executing", check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", check=True)
        proc = self.run_script("sancai_state.py", "add-wo", "--id", "WO-002",
                               "--files", "a.txt")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("overlap", proc.stderr)

    def test_capability(self):
        self.start_execution()
        self.assertEqual(self.run_script("sancai_capability.py", "check",
                                         "--tool", "Write", "--path", "a.txt").returncode, 0)
        self.assertNotEqual(self.run_script("sancai_capability.py", "check",
                                            "--tool", "Write", "--path", "b.txt").returncode, 0)
        self.assertEqual(self.run_script("sancai_capability.py", "check",
                                         "--tool", "Bash", "--command", "npm test").returncode, 0)
        self.assertNotEqual(self.run_script("sancai_capability.py", "check",
                                            "--tool", "Bash", "--command", "rm -rf /").returncode, 0)
        self.assertNotEqual(self.run_script("sancai_capability.py", "check",
                                            "--tool", "SomeNewTool").returncode, 0)

    def test_bash_policy_rejects_residual_bypasses(self):
        self.start_execution()
        cases = [
            "npm test; rm -rf victim",
            "find . -fprint victim",
            "git diff --output=victim",
            "git commit -o a.txt",
            "cat /etc/passwd",
            "./sancai_capability.py check --tool Bash --command 'npm test'",
        ]
        for command in cases:
            proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                   "--command", command, "--run", "001-test")
            self.assertNotEqual(proc.returncode, 0, command)

    def test_token_allows_irreversible_and_binds_diff(self):
        self.start_execution()
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed\n")
        diff = self.run_script("sancai_capability.py", "diff-sha").stdout.strip()
        self.assertEqual(len(diff), 64)
        token = self.run_script("sancai_capability.py", "mint", "--run", "001-test",
                                "--action", "rm -rf build", "--diff-sha", diff).stdout.strip()
        self.assertTrue(os.path.isfile(token))
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                               "--command", "rm -rf build", "--run", "001-test")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed again\n")
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                               "--command", "rm -rf build", "--run", "001-test")
        self.assertNotEqual(proc.returncode, 0)

    def test_verdict_requires_evidence(self):
        self.start_execution()
        proc = self.run_script("sancai_verdict.py", "write", "--run", "001-test",
                               "--wo", "WO-001", "--verdict", "pass",
                               "--session-id", "s", "--context-id", "ctx-s", "--prompt-hash", "h")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("evidence not found", proc.stderr)

    def test_escalation_dedupe_and_approve(self):
        self.start_execution()
        args = ["new", "--run", "001-test", "--wo", "WO-001", "--type", "out_of_scope",
                "--what-tried", "edit b.txt", "--evidence", "diff", "--blocking"]
        first = self.run_script("sancai_escalate.py", *args)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_script("sancai_escalate.py", *args)
        self.assertIn("duplicate", second.stdout)
        listing = self.run_script("sancai_escalate.py", "list", "--run", "001-test")
        self.assertIn("ESC-001", listing.stdout)
        card = self.bind_card("approve", "--run", "001-test", "--esc", "ESC-001")
        approved = self.run_script("sancai_escalate.py", "approve", "--run", "001-test",
                                   "--id", "ESC-001", "--message", "confirmed",
                                   "--card-id", card["card_id"],
                                   "--card-code", card["card_code"])
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)

    def test_human_approval_requires_explicit_phrase(self):
        self.start_execution()
        self.run_script("sancai_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
                        "--type", "out_of_scope", "--what-tried", "edit b.txt",
                        "--evidence", "diff", "--blocking", check=True)
        card = self.bind_card("approve", "--run", "001-test", "--esc", "ESC-001")
        vague = self.run_script("sancai_escalate.py", "approve", "--run", "001-test",
                                "--id", "ESC-001", "--message", "ok",
                                "--card-id", card["card_id"],
                                "--card-code", card["card_code"])
        self.assertNotEqual(vague.returncode, 0)
        explicit = self.run_script("sancai_escalate.py", "approve", "--run", "001-test",
                                   "--id", "ESC-001", "--message", "approved",
                                   "--card-id", card["card_id"],
                                   "--card-code", card["card_code"])
        self.assertEqual(explicit.returncode, 0, explicit.stdout + explicit.stderr)

    def test_human_reject_requires_reason(self):
        self.start_execution()
        self.run_script("sancai_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
                        "--type", "out_of_scope", "--what-tried", "edit b.txt",
                        "--evidence", "diff", "--blocking", check=True)
        card = self.bind_card("approve", "--run", "001-test", "--esc", "ESC-001")
        no_reason = self.run_script("sancai_escalate.py", "reject", "--run", "001-test",
                                    "--id", "ESC-001", "--reason", "  ",
                                    "--card-id", card["card_id"],
                                    "--card-code", card["card_code"])
        self.assertNotEqual(no_reason.returncode, 0)
        rejected = self.run_script("sancai_escalate.py", "reject", "--run", "001-test",
                                   "--id", "ESC-001", "--reason", "plan risk too high",
                                   "--card-id", card["card_id"],
                                   "--card-code", card["card_code"])
        self.assertEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
        esc = json.loads((pathlib.Path(self.tmp) / ".sancai" / "runs" / "001-test"
                          / "L3-intent" / "decisions" / "escalations" / "ESC-001.json").read_text())
        self.assertEqual(esc["status"], "rejected")


    def graph(self, *args):
        proc = self.run_script("sancai_graph.py", *args, check=True)
        return json.loads(proc.stdout)

    def card(self, *args):
        proc = self.run_script("sancai_card.py", *args, check=True)
        return json.loads(proc.stdout)

    def bind_card(self, kind, *args, tier="T0"):
        """Render and persist a card, returning it with card_id/card_code."""
        proc = self.run_script("sancai_card.py", kind, *args, "--json",
                               "--tier", tier, check=True)
        return json.loads(proc.stdout)

    def test_graph_position_and_intent_card(self):
        pos = self.graph("position", "--run", "001-test", "--json")
        self.assertEqual(pos["state"], "planning")
        self.assertEqual(pos["stage"], "Requirements")
        self.assertEqual(pos["layer"], "L3")
        card = self.card("current", "--run", "001-test", "--json")
        self.assertEqual(card["type"], "intent")
        self.assertEqual([o["label"] for o in card["options"]], ["Start", "Edit", "Cancel"])

    def test_graph_rejection_and_metrics(self):
        self.start_execution()
        a = pathlib.Path(self.tmp) / "a.txt"
        a.write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001", check=True)
        self.run_script("sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
                        "--verdict", "fail", "--session-id", "v1", "--context-id", "ctx-1",
                        "--prompt-hash", "h1",
                        check=True)
        failed = self.run_script("sancai_gate.py", "--run", "001-test",
                                 "--wo", "WO-001", "--apply")
        self.assertNotEqual(failed.returncode, 0)

        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)
        a.write_text("changed again\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001", check=True)
        self.run_script("sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
                        "--verdict", "pass", "--session-id", "v2", "--context-id", "ctx-2",
                        "--prompt-hash", "h2",
                        check=True)
        self.run_script("sancai_gate.py", "--run", "001-test",
                        "--wo", "WO-001", "--apply", check=True)

        attempts = self.graph("attempts", "--run", "001-test", "--wo", "WO-001", "--json")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["id"], "ATT-001")
        self.assertEqual(attempts[1]["id"], "ATT-002")
        metrics = self.graph("metrics", "--run", "001-test", "--json")
        self.assertEqual(metrics["attempts"], 2)
        self.assertEqual(metrics["rework"], 1)
        self.assertEqual(metrics["rejections"], 1)
        shown = self.run_script("sancai_graph.py", "show", "--run", "001-test", check=True)
        self.assertIn("ATT-001", shown.stdout)
        self.assertIn("ATT-002", shown.stdout)
        self.assertIn("GATE-WO-001", shown.stdout)

    def test_card_approve_then_accept(self):
        self.start_execution()
        self.run_script("sancai_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
                        "--type", "irreversible", "--what-tried", "force push",
                        "--evidence", "diff", "--blocking", check=True)
        card = self.bind_card("current", "--run", "001-test")
        self.assertEqual(card["type"], "approve")
        self.assertEqual(card["trigger"], "ESC-001")
        self.assertEqual(len(card["options"]), 4)
        self.assertEqual(card["layer"], "L3")

        self.run_script("sancai_escalate.py", "approve", "--run", "001-test",
                        "--id", "ESC-001", "--message", "confirmed",
                        "--card-id", card["card_id"],
                        "--card-code", card["card_code"], check=True)
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001", check=True)
        self.run_script("sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
                        "--verdict", "pass", "--session-id", "sv", "--context-id", "ctx-sv",
                        "--prompt-hash", "h",
                        check=True)
        self.run_script("sancai_gate.py", "--run", "001-test",
                        "--wo", "WO-001", "--apply", check=True)

        card = self.card("current", "--run", "001-test", "--json")
        self.assertEqual(card["type"], "accept")
        self.assertEqual(card["layer"], "L3")
        self.assertEqual(len(card["options"]), 3)

    def test_card_out_of_scope_and_ambiguous(self):
        self.start_execution()
        self.run_script("sancai_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
                        "--type", "out_of_scope", "--what-tried", "edit b.txt",
                        "--evidence", "diff", "--blocking", check=True)
        card = self.bind_card("current", "--run", "001-test")
        self.assertEqual(card["type"], "out-of-scope")
        self.assertEqual(card["trigger"], "ESC-001")

        self.run_script("sancai_escalate.py", "approve", "--run", "001-test",
                        "--id", "ESC-001", "--message", "confirmed",
                        "--card-id", card["card_id"],
                        "--card-code", card["card_code"], check=True)
        self.run_script("sancai_escalate.py", "new", "--run", "001-test", "--wo", "WO-001",
                        "--type", "spec_ambiguous", "--what-tried", "two designs",
                        "--evidence", "notes", "--option", "A: smaller",
                        "--option", "B: complete", "--blocking", check=True)
        card = self.card("current", "--run", "001-test", "--json")
        self.assertEqual(card["type"], "ambiguous")
        self.assertEqual(card["trigger"], "ESC-002")
        self.assertEqual(len(card["options"]), 3)

    def test_card_blocked(self):
        self.start_execution()
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "blocked", check=True)
        card = self.card("current", "--run", "001-test", "--json")
        self.assertEqual(card["type"], "blocked")
        self.assertEqual(card["trigger"], "WO-001")
        self.assertEqual(card["layer"], "L3")
        self.assertEqual(len(card["options"]), 3)

    def test_bash_suffix_and_shell_meta_denied(self):
        self.start_execution()
        commands = [
            "npm test; rm -rf victim",
            "npm test && rm -rf victim",
            "npm test || rm -rf victim",
            "npm test `rm -rf victim`",
            "npm test $(rm -rf victim)",
            "npm test | tee /tmp/x",
        ]
        for cmd in commands:
            proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                   "--command", cmd, "--run", "001-test")
            self.assertNotEqual(proc.returncode, 0, cmd)

    def test_agent_cannot_self_mint(self):
        self.start_execution()
        direct = f"{sys.executable} {SCRIPTS / 'sancai_capability.py'} mint --run 001-test --action 'rm -rf build' --diff-sha x"
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                               "--command", direct, "--run", "001-test")
        self.assertNotEqual(proc.returncode, 0)
        via_uv = f"uv run python {SCRIPTS / 'sancai_capability.py'} mint"
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                               "--command", via_uv, "--run", "001-test")
        self.assertNotEqual(proc.returncode, 0)

    def test_token_single_use(self):
        self.start_execution()
        diff = self.run_script("sancai_capability.py", "diff-sha").stdout.strip()
        self.run_script("sancai_capability.py", "mint", "--run", "001-test",
                        "--action", "rm -rf build", "--diff-sha", diff, check=True)
        first = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                "--command", "rm -rf build", "--run", "001-test")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                 "--command", "rm -rf build", "--run", "001-test")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("consumed", second.stdout + second.stderr)

    def test_state_machine_rejects_skips(self):
        proc = self.run_script("sancai_state.py", "transition", "--to", "reviewing")
        self.assertNotEqual(proc.returncode, 0)
        self.start_execution()
        proc = self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                               "--to", "verified")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("sancai_gate", proc.stderr)

    def test_verifier_context_must_differ(self):
        self.start_execution()
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001", check=True)
        proc = self.run_script("sancai_verdict.py", "write", "--run", "001-test",
                               "--wo", "WO-001", "--verdict", "pass",
                               "--session-id", "v", "--context-id", "s1",
                               "--prompt-hash", "h")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("context", proc.stderr)

    def test_blocking_finding_blocks_gate_and_accept(self):
        self.start_execution()
        (pathlib.Path(self.tmp) / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test", "--wo", "WO-001", check=True)
        proc = self.run_script("sancai_verdict.py", "write", "--run", "001-test",
                               "--wo", "WO-001", "--verdict", "pass",
                               "--session-id", "v", "--context-id", "ctx-v",
                               "--prompt-hash", "h", "--finding", "blocker|a.txt:1|missing test|add test")
        self.assertNotEqual(proc.returncode, 0)
        self.run_script("sancai_verdict.py", "write", "--run", "001-test",
                        "--wo", "WO-001", "--verdict", "fail",
                        "--session-id", "v", "--context-id", "ctx-v",
                        "--prompt-hash", "h", "--finding", "blocker|a.txt:1|missing test|add test", check=True)
        failed = self.run_script("sancai_gate.py", "--run", "001-test",
                                 "--wo", "WO-001", "--apply")
        self.assertNotEqual(failed.returncode, 0)
        accept_card = self.bind_card("accept", "--run", "001-test")
        accepted = self.run_script("sancai_state.py", "accept", "--message", "ok",
                                   "--session-id", "s-accept",
                                   "--card-id", accept_card["card_id"],
                                   "--card-code", accept_card["card_code"])
        self.assertNotEqual(accepted.returncode, 0)

    def test_hook_denies_write_outside_executing(self):
        payload = json.dumps({
            "cwd": self.tmp,
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"file_path": os.path.join(self.tmp, "a.txt")},
        })
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--pre-tool"],
            cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(proc.returncode, 0)
        output = json.loads(proc.stdout)
        self.assertEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_hook_stop_blocks_without_session(self):
        payload = json.dumps({"cwd": self.tmp})
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--stop"],
            cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout).get("decision"), "block")

    def test_absolute_owned_path_allowed(self):
        self.start_execution()
        a = str(pathlib.Path(self.tmp) / "a.txt")
        b = str(pathlib.Path(self.tmp) / "b.txt")
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Write",
                               "--path", a, "--run", "001-test")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotEqual(self.run_script("sancai_capability.py", "check", "--tool", "Write",
                                            "--path", b, "--run", "001-test").returncode, 0)

    def test_git_add_checks_already_staged_files(self):
        self.start_execution()
        (pathlib.Path(self.tmp) / "b.txt").write_text("staged outside owned\n")
        self.git("add", "b.txt")
        proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                               "--command", "git add a.txt", "--run", "001-test")
        self.assertNotEqual(proc.returncode, 0)

    def test_run_branch_creation_allowed(self):
        self.start_execution()
        for cmd in ("git switch -c sancai/001-test",
                    "git checkout -b sancai/001-test"):
            proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                   "--command", cmd, "--run", "001-test")
            self.assertEqual(proc.returncode, 0, cmd + "\n" + proc.stdout + proc.stderr)
        for cmd in ("git switch main", "git switch -c feature/x",
                    "git checkout -b main"):
            proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                   "--command", cmd, "--run", "001-test")
            self.assertNotEqual(proc.returncode, 0, cmd)

    def test_arbitrary_run_targets_need_token(self):
        self.start_execution()
        for cmd in ("npm run deploy", "make deploy", "go run ./cmd/server"):
            proc = self.run_script("sancai_capability.py", "check", "--tool", "Bash",
                                   "--command", cmd, "--run", "001-test")
            self.assertNotEqual(proc.returncode, 0, cmd)


    def test_status_line_dedup_and_idle(self):
        payload = json.dumps({"cwd": self.tmp, "session_id": "s1"})

        def status_line():
            return subprocess.run(
                [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--status-line"],
                cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
            )

        first = status_line()
        self.assertIn("Sancai 001-test", first.stdout)
        self.assertIn("additionalContext", first.stdout)
        self.assertEqual(status_line().stdout.strip(), "")
        self.assertEqual(status_line().stdout.strip(), "")
        self.assertIn("additionalContext", status_line().stdout)

        os.remove(pathlib.Path(self.tmp) / ".sancai" / "active")
        self.assertEqual(status_line().stdout.strip(), "")

    def test_status_line_terminal_pointer(self):
        self.run_script("sancai_state.py", "abandon", "--reason", "test")
        active = pathlib.Path(self.tmp) / ".sancai" / "active"
        active.write_text(json.dumps({"run": "001-test", "state": "abandoned"}))
        payload = json.dumps({"cwd": self.tmp})
        first = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--status-line"],
            cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
        )
        self.assertIn("abandoned", first.stdout)
        second = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--status-line"],
            cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(second.stdout.strip(), "")

    def test_timeline_and_progress_card(self):
        self.start_execution()
        timeline = self.graph("timeline", "--run", "001-test", "--last", "5", "--json")
        self.assertTrue(timeline)
        self.assertIn("claimed", [e["event"] for e in timeline])
        proc = self.run_script("sancai_graph.py", "timeline", "--run", "001-test", "--last", "3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("→", proc.stdout)
        card = self.run_script("sancai_card.py", "status", "--run", "001-test")
        self.assertEqual(card.returncode, 0, card.stderr)
        self.assertIn("Sancai progress", card.stdout)
        self.assertIn("read-only", card.stdout)

    def test_deny_reason_includes_status_line(self):
        self.start_execution()
        payload = json.dumps({
            "cwd": self.tmp,
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"file_path": str(pathlib.Path(self.tmp) / "b.txt")},
        })
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "sancai_hook.py"), "--pre-tool"],
            cwd=self.tmp, input=payload, capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(proc.returncode, 0)
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Sancai 001-test", reason)


if __name__ == "__main__":
    unittest.main()
