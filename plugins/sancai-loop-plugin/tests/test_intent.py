"""Tests for the intent-alignment tools."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


class IntentAlignmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sancai-intent-")
        self.env = os.environ.copy()
        self.env["SANCAI_SECRET"] = "test-secret"
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (pathlib.Path(self.tmp) / "a.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")

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
            self.fail(f"{name} {' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def write_intent(self, **overrides):
        intent = {
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
        }
        intent.update(overrides)
        (pathlib.Path(self.tmp) / "intent.json").write_text(json.dumps(intent))
        return intent

    def init_run(self):
        self.write_intent()
        self.run_script("sancai_state.py", "init", "--run", "001-intent",
                        "--intent", "intent.json", "--session-id", "s1", check=True)

    def bind_intent_card(self):
        proc = self.run_script("sancai_card.py", "intent", "--run", "001-intent",
                               "--tier", "T0", "--json", check=True)
        data = json.loads(proc.stdout)
        return data["card_id"], data["card_code"]

    def test_clear_intent_is_aligned(self):
        self.init_run()
        proc = self.run_script("sancai_intent.py", "assess", "--run", "001-intent", "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "aligned")
        self.assertEqual(data["questions"], [])

    def test_vague_intent_returns_questions(self):
        self.write_intent(
            goal="make it better and fast",
            non_goals=[],
            owned_files=[],
        )
        self.run_script("sancai_state.py", "init", "--run", "001-intent",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        proc = self.run_script("sancai_intent.py", "assess", "--run", "001-intent", "--json")
        self.assertEqual(proc.returncode, 2)
        data = json.loads(proc.stdout)
        codes = {s["code"] for s in data["signals"]}
        self.assertIn("vague_term:better", codes)
        self.assertIn("vague_term:fast", codes)
        self.assertIn("non_goals_missing", codes)
        self.assertIn("owned_files_missing", codes)
        self.assertTrue(data["questions"])

    def test_sign_requires_alignment(self):
        self.init_run()
        card_id, card_code = self.bind_intent_card()
        proc = self.run_script("sancai_state.py", "sign", "--run", "001-intent",
                               "--session-id", "s1", "--message", "confirmed",
                               "--card-id", card_id, "--card-code", card_code)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("requires intent alignment", proc.stderr + proc.stdout)

        self.run_script("sancai_intent.py", "record", "--run", "001-intent",
                        "--status", "aligned", "--answers", "owner=a.txt",
                        "--session-id", "s1", check=True)
        card_id, card_code = self.bind_intent_card()
        self.run_script("sancai_state.py", "sign", "--run", "001-intent",
                        "--session-id", "s1", "--message", "confirmed",
                        "--card-id", card_id, "--card-code", card_code, check=True)

    def test_deferred_requires_reason(self):
        self.init_run()
        proc = self.run_script("sancai_intent.py", "record", "--run", "001-intent",
                               "--status", "deferred", "--answers", "")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("requires --reason", proc.stderr + proc.stdout)

    def test_questions_json(self):
        self.init_run()
        proc = self.run_script("sancai_intent.py", "questions", "--run", "001-intent",
                               "--json", check=True)
        self.assertEqual(json.loads(proc.stdout), [])

        self.write_intent(goal="make it better", non_goals=[], owned_files=[])
        self.run_script("sancai_state.py", "init", "--run", "002-vague",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        proc = self.run_script("sancai_intent.py", "questions", "--run", "002-vague",
                               "--json", check=True)
        data = json.loads(proc.stdout)
        codes = {item["code"] for item in data}
        self.assertIn("vague_term:better", codes)
        self.assertTrue(all(item["question"] for item in data))

    def init_vague_run(self):
        self.write_intent(goal="make it better and fast", non_goals=[], owned_files=[])
        self.run_script("sancai_state.py", "init", "--run", "002-vague",
                        "--intent", "intent.json", "--session-id", "s1", check=True)
        proc = self.run_script("sancai_intent.py", "assess", "--run", "002-vague", "--json")
        self.assertEqual(proc.returncode, 2)
        return [s["code"] for s in json.loads(proc.stdout)["signals"]]

    def write_resolutions(self, entries):
        path = pathlib.Path(self.tmp) / "resolutions.json"
        path.write_text(json.dumps(entries))
        return str(path)

    def test_aligned_requires_resolutions_for_ambiguous_intent(self):
        self.init_vague_run()
        proc = self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                               "--status", "aligned", "--answers", "ok",
                               "--session-id", "s1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("covering every alignment signal", proc.stderr + proc.stdout)

    def test_record_resolutions_persists_choices(self):
        codes = self.init_vague_run()
        entries = [
            {"code": code, "choice": f"resolution for {code}", "source": "proposed"}
            for code in codes
        ]
        path = self.write_resolutions(entries)
        self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                        "--status", "aligned", "--resolutions", path,
                        "--session-id", "s1", check=True)
        intent = json.loads(
            (pathlib.Path(self.tmp) / ".sancai/runs/002-vague/L3-intent/intent.json").read_text()
        )
        alignment = intent["alignment"]
        self.assertEqual(alignment["status"], "aligned")
        self.assertEqual([r["code"] for r in alignment["resolutions"]], codes)
        self.assertTrue(alignment["answers"])
        self.assertIn("signals_sha", alignment)

    def test_resolution_rejects_unknown_code(self):
        self.init_vague_run()
        entries = [{"code": "not_a_signal", "choice": "x", "source": "user"}]
        path = self.write_resolutions(entries)
        proc = self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                               "--status", "aligned", "--resolutions", path,
                               "--session-id", "s1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown alignment signal", proc.stderr + proc.stdout)

    def test_resolution_rejects_empty_choice(self):
        codes = self.init_vague_run()
        path = self.write_resolutions([{"code": codes[0], "choice": "", "source": "user"}])
        proc = self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                               "--status", "aligned", "--resolutions", path,
                               "--session-id", "s1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("non-empty choice", proc.stderr + proc.stdout)

    def test_resolution_rejects_invalid_source(self):
        codes = self.init_vague_run()
        path = self.write_resolutions(
            [{"code": codes[0], "choice": "x", "source": "agent"}]
        )
        proc = self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                               "--status", "aligned", "--resolutions", path,
                               "--session-id", "s1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("source must be", proc.stderr + proc.stdout)

    def test_deferred_allows_partial_resolutions(self):
        codes = self.init_vague_run()
        path = self.write_resolutions(
            [{"code": codes[0], "choice": "x", "source": "user"}]
        )
        self.run_script("sancai_intent.py", "record", "--run", "002-vague",
                        "--status", "deferred", "--reason", "needs product input",
                        "--resolutions", path, "--session-id", "s1", check=True)

    def test_glossary_and_adr(self):
        self.init_run()
        self.run_script("sancai_intent.py", "glossary", "--run", "001-intent",
                        "--write", check=True)
        context = pathlib.Path(self.tmp) / ".sancai/runs/001-intent/L3-intent/CONTEXT.md"
        self.assertTrue(context.exists())
        self.assertIn("| Term | Definition | Status |", context.read_text())

        self.run_script("sancai_intent.py", "adr", "--run", "001-intent",
                        "--title", "Use Postgres", check=True)
        adr_dir = pathlib.Path(self.tmp) / ".sancai/runs/001-intent/L3-intent/decisions/adr"
        adr = sorted(adr_dir.glob("ADR-001-*.md"))
        self.assertEqual(len(adr), 1)
        self.assertIn("Use Postgres", adr[0].read_text())


if __name__ == "__main__":
    unittest.main()
