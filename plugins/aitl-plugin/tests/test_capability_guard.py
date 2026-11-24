"""Tests for the human-decision command guard in aitl_capability.

An agent-run Bash must not be able to invoke the CLIs that record human
decisions (intent sign/accept, escalation approve/reject). Rendering, verdict
writes, and read-only subcommands stay allowed; G3 validates the verifier's
context instead of blocking the write.

Run:
  python3 -m unittest discover -s plugins/aitl-plugin/tests -v
"""
import os
import pathlib
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aitl_capability  # noqa: E402


class CapabilityGuardTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="aitl-cap-")

    def deny(self, command):
        ok, reason = aitl_capability.check(self.root, "Bash", command)
        self.assertFalse(ok, command)
        self.assertIn("human decision", reason)
        return reason

    def allow(self, command):
        ok, reason = aitl_capability.check(self.root, "Bash", command)
        self.assertTrue(ok, f"{command}: {reason}")
        return reason

    def script(self, name):
        return str(SCRIPTS / name)

    def test_state_accept_denied(self):
        self.deny(f"python3 {self.script('aitl_state.py')} accept --run 001-x")

    def test_state_sign_denied(self):
        self.deny(
            f"python3 {self.script('aitl_state.py')} sign --run 001-x "
            "--card-id CARD-abc --card-code 12345678"
        )

    def test_escalate_approve_denied_direct_path(self):
        self.deny(
            f"./plugins/aitl-plugin/scripts/aitl_escalate.py approve "
            "--run 001-x --esc E-1"
        )

    def test_escalate_reject_denied(self):
        self.deny(f"python3 {self.script('aitl_escalate.py')} reject --run 001-x --esc E-1")

    def test_verdict_write_allowed(self):
        self.allow(f"python3 {self.script('aitl_verdict.py')} write --run 001-x")

    def test_native_decide_allowed(self):
        self.allow(
            f"python3 {self.script('aitl_decide.py')} accept --run 001-x "
            "--message accepted --session-id s --card-id CARD-abc --card-code 12345678"
        )

    def test_uv_run_python_sign_denied(self):
        self.deny(f"uv run python {self.script('aitl_state.py')} sign --run 001-x")

    def test_state_status_allowed(self):
        self.allow(f"python3 {self.script('aitl_state.py')} status")

    def test_escalate_list_allowed(self):
        self.allow(f"python3 {self.script('aitl_escalate.py')} list --run 001-x")

    def test_card_current_allowed(self):
        self.allow(f"python3 {self.script('aitl_card.py')} current")

    def test_verdict_list_allowed(self):
        self.allow(f"python3 {self.script('aitl_verdict.py')} list")


if __name__ == "__main__":
    unittest.main()
