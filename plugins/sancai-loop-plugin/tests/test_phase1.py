"""Phase 1 card-binding tests.

Every human touchpoint (sign / approve / reject / accept) must be bound to a
rendered card identified by card_id + card_code. These tests exercise the
binding contract end to end through the CLI plus the hash/dwell primitives in
sancai_cards.

Run:
  python3 -m unittest discover -s plugins/sancai-loop-plugin/tests -v
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sancai_cards  # noqa: E402


class Phase1CardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-phase1-")
        self.root = pathlib.Path(self.tmp)
        self.env = os.environ.copy()
        self.env["SANCAI_SECRET"] = "test-secret"
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
            "goal": "change a.txt",
            "non_goals": ["b.txt"],
            "acceptance": [{
                "id": "AC-1",
                "check": "command",
                "run": "grep -q changed a.txt",
                "expect": "exit_code == 0",
            }],
            "manual_ac_ratio": 0.0,
            "risk_policy_ref": "policy/risk@1",
            "budget": {"human_rounds": 3},
        }))
        self.run_script("sancai_state.py", "init", "--run", "001-test",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
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

    def card(self, kind, *args, tier="T0", check=True):
        proc = self.run_script("sancai_card.py", kind, "--run", "001-test",
                               *args, "--json", "--tier", tier, check=check)
        return json.loads(proc.stdout)

    def intent_card(self, tier="T0"):
        return self.card("intent", tier=tier)

    def sign(self, card=None, check=False):
        card = card or self.intent_card()
        return self.run_script(
            "sancai_state.py", "sign", "--run", "001-test",
            "--session-id", "s1", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
            check=check,
        )

    def start_execution(self, card=None):
        self.sign(card, check=True)
        self.run_script("sancai_state.py", "transition", "--to", "executing",
                        check=True)
        self.run_script("sancai_state.py", "add-wo", "--id", "WO-001",
                        "--files", "a.txt", "--reversible", "true", check=True)
        self.run_script("sancai_state.py", "claim", "--wo", "WO-001", check=True)
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "in_progress", check=True)

    def accept(self, card, *extra, message="confirmed"):
        return self.run_script(
            "sancai_state.py", "accept", "--message", message,
            "--session-id", "s-accept",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
            *extra,
        )

    def prepare_acceptance(self, finding=None):
        """Drive the run to reviewing with a pass verdict and verified gate."""
        self.start_execution()
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test",
                        "--wo", "WO-001", check=True)
        verdict_args = ["write", "--run", "001-test", "--wo", "WO-001",
                        "--verdict", "pass", "--session-id", "v",
                        "--context-id", "ctx-v", "--prompt-hash", "h"]
        if finding:
            verdict_args += ["--finding", finding]
        self.run_script("sancai_verdict.py", *verdict_args, check=True)
        self.run_script("sancai_gate.py", "--run", "001-test",
                        "--wo", "WO-001", "--apply", check=True)
        return self.card("accept")

    # ------------------------------------------------------------------
    # 1. payload tampering
    # ------------------------------------------------------------------
    def test_card_payload_tamper_fails_verification(self):
        card = self.intent_card()
        card_file = (self.root / ".sancai" / "runs" / "001-test" / "L3-intent" / "decisions" / "cards"
                     / f"{card['card_id']}.json")
        saved = json.loads(card_file.read_text())
        with mock.patch.dict(os.environ, {"SANCAI_SECRET": "test-secret"}):
            self.assertEqual(sancai_cards.verify_card(saved), [])
            saved["payload"]["goal"] = "transfer all funds"
            problems = sancai_cards.verify_card(saved)
        self.assertTrue(problems)
        self.assertTrue(any("card_hash mismatch" in p for p in problems), problems)

        card_file.write_text(json.dumps(saved, ensure_ascii=False))
        proc = self.run_script("sancai_card.py", "verify", "--run", "001-test",
                               "--card-id", card["card_id"], "--json")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertFalse(out["verification"]["ok"])
        self.assertTrue(out["verification"]["problems"])

    # ------------------------------------------------------------------
    # 2. wrong code / replay
    # ------------------------------------------------------------------
    def test_wrong_card_code_rejected_and_card_single_use(self):
        card = self.intent_card()
        wrong = self.run_script(
            "sancai_state.py", "sign", "--run", "001-test",
            "--session-id", "s1", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", "deadbeef",
        )
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("card_code mismatch", wrong.stderr)

        self.assertEqual(self.sign(card).returncode, 0)
        replay = self.sign(card)
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("already used", replay.stderr)

    # ------------------------------------------------------------------
    # 3. tier dwell
    # ------------------------------------------------------------------
    def test_t2_card_requires_dwell(self):
        card = self.intent_card(tier="T2")
        too_fresh = self.sign(card)
        self.assertNotEqual(too_fresh.returncode, 0)
        self.assertIn("too fresh", too_fresh.stderr)
        time.sleep(3.3)
        self.assertEqual(self.sign(card, check=True).returncode, 0)

    # ------------------------------------------------------------------
    # 4. sign without a card
    # ------------------------------------------------------------------
    def test_sign_without_card_fails(self):
        proc = self.run_script(
            "sancai_state.py", "sign", "--run", "001-test",
            "--session-id", "s1", "--message", "confirmed",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("card-id", proc.stderr.lower())

    # ------------------------------------------------------------------
    # 5. escalation approve binding
    # ------------------------------------------------------------------
    def test_escalation_approve_requires_card_and_rejects_replay(self):
        self.start_execution()
        self.run_script("sancai_escalate.py", "new", "--run", "001-test",
                        "--wo", "WO-001", "--type", "irreversible",
                        "--what-tried", "force push", "--evidence", "diff",
                        "--blocking", check=True)
        no_card = self.run_script(
            "sancai_escalate.py", "approve", "--run", "001-test",
            "--id", "ESC-001", "--message", "confirmed",
        )
        self.assertNotEqual(no_card.returncode, 0)

        card = self.card("approve", "--esc", "ESC-001")
        approved = self.run_script(
            "sancai_escalate.py", "approve", "--run", "001-test",
            "--id", "ESC-001", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
        )
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        replay = self.run_script(
            "sancai_escalate.py", "approve", "--run", "001-test",
            "--id", "ESC-001", "--message", "confirmed",
            "--card-id", card["card_id"], "--card-code", card["card_code"],
        )
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("not open", replay.stderr)

    # ------------------------------------------------------------------
    # 6. minor finding requires acknowledgement
    # ------------------------------------------------------------------
    def test_accept_minor_finding_requires_ack(self):
        card = self.prepare_acceptance("minor|a.txt:1|naming nit|rename later")
        missing_ack = self.accept(card)
        self.assertNotEqual(missing_ack.returncode, 0)
        self.assertIn("ack-findings", missing_ack.stderr)

        card = self.card("accept")
        ok = self.accept(card, "--ack-findings")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        status = json.loads(self.run_script("sancai_state.py", "status", "--run", "001-test",
                                            "--json").stdout)
        self.assertEqual(status["state"], "accepted")
        self.assertTrue(status["acceptance"]["findings"]["acknowledged"])

    # ------------------------------------------------------------------
    # 7. major finding requires a disposition
    # ------------------------------------------------------------------
    def test_accept_major_finding_requires_disposition(self):
        card = self.prepare_acceptance("major|a.txt:1|unbounded retry|document risk")
        no_disposition = self.accept(card, "--ack-findings")
        self.assertNotEqual(no_disposition.returncode, 0)
        self.assertIn("disposition", no_disposition.stderr)

        card = self.card("accept")
        ok = self.accept(card, "--ack-findings",
                         "--disposition", "waive:accepted risk")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        status = json.loads(self.run_script("sancai_state.py", "status", "--run", "001-test",
                                            "--json").stdout)
        self.assertEqual(status["state"], "accepted")
        dispositions = status["acceptance"]["findings"]["dispositions"]
        self.assertEqual(dispositions[0]["kind"], "waive")
        self.assertEqual(dispositions[0]["reason"], "accepted risk")

    # ------------------------------------------------------------------
    # 8. verdict findings hash
    # ------------------------------------------------------------------
    def test_verdict_findings_hash_matches_library(self):
        self.start_execution()
        (self.root / "a.txt").write_text("changed\n")
        self.run_script("sancai_state.py", "wo-transition", "--wo", "WO-001",
                        "--to", "for_review", check=True)
        self.run_script("sancai_check_ac.py", "--run", "001-test",
                        "--wo", "WO-001", check=True)
        self.run_script(
            "sancai_verdict.py", "write", "--run", "001-test", "--wo", "WO-001",
            "--verdict", "pass", "--session-id", "v", "--context-id", "ctx-v",
            "--prompt-hash", "h",
            "--finding", "minor|a.txt:1|nit one|fix one",
            "--finding", "info|a.txt:2|note two|none",
            check=True,
        )
        verdict = json.loads(
            (self.root / ".sancai" / "runs" / "001-test" / "L2-harness" / "verdicts"
             / "WO-001.json").read_text()
        )
        self.assertIn("findings_hash", verdict)
        self.assertTrue(verdict["findings_hash"].startswith("sha256:"))
        self.assertEqual(verdict["findings_hash"],
                         sancai_cards.findings_hash(verdict["findings"]))

    # ------------------------------------------------------------------
    # 9. findings hash is order independent
    # ------------------------------------------------------------------
    def test_findings_hash_is_order_independent(self):
        first = {"severity": "minor", "file": "a.py:1",
                 "evidence": "e1", "fix": "f1"}
        second = {"severity": "major", "file": "b.py:2",
                  "evidence": "e2", "fix": "f2"}
        self.assertEqual(sancai_cards.findings_hash([first, second]),
                         sancai_cards.findings_hash([second, first]))
        self.assertNotEqual(sancai_cards.findings_hash([first]),
                            sancai_cards.findings_hash([second]))


if __name__ == "__main__":
    unittest.main()
