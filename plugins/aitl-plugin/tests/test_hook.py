"""Tests for the native permission-prompt gate in aitl_hook."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


class NativeGateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="aitl-hook-")
        os.makedirs(os.path.join(self.root, ".aitl", "runs", "r1"), exist_ok=True)
        with open(os.path.join(self.root, ".aitl", "active"), "w", encoding="utf-8") as f:
            f.write("r1\n")
        with open(os.path.join(self.root, ".aitl", "runs", "r1", "run.json"), "w", encoding="utf-8") as f:
            json.dump({"run": "r1", "state": "reviewing", "session_id": "s1", "work_orders": []}, f)

    def hook(self, command):
        payload = {
            "cwd": self.root,
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "aitl_hook.py"), "--pre-tool"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=self.root,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["hookSpecificOutput"]

    def test_decide_accept_uses_native_ask(self):
        out = self.hook(
            f"{sys.executable} {SCRIPTS / 'aitl_decide.py'} accept "
            "--run r1 --message accepted --session-id s1 "
            "--card-id CARD-abc --card-code 12345678"
        )
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("accept", out["permissionDecisionReason"])
        self.assertIn("CARD-abc", out["permissionDecisionReason"])

    def test_decide_mint_uses_native_ask(self):
        out = self.hook(
            f"{sys.executable} {SCRIPTS / 'aitl_decide.py'} mint "
            "--run r1 --action 'git push --force origin main' "
            "--diff-sha abc --ttl 600"
        )
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("mint", out["permissionDecisionReason"])
        self.assertIn("git push --force origin main", out["permissionDecisionReason"])

    def test_direct_state_accept_is_denied(self):
        out = self.hook(
            f"{sys.executable} {SCRIPTS / 'aitl_state.py'} accept "
            "--run r1 --message accepted --session-id s1 "
            "--card-id CARD-abc --card-code 12345678"
        )
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("human decision", out["permissionDecisionReason"])

    def test_decide_with_shell_injection_is_denied(self):
        out = self.hook(
            f"{sys.executable} {SCRIPTS / 'aitl_decide.py'} accept "
            "--run r1 --message accepted --session-id s1 "
            "--card-id CARD-abc --card-code 12345678; rm -rf victim"
        )
        self.assertEqual(out["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
