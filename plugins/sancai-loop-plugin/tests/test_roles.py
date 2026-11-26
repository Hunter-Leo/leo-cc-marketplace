"""Contract tests for H1 research roles and research references."""
import pathlib
import re
import sys
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sancai_state as state  # noqa: E402


def frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        raise AssertionError(f"missing frontmatter: {path}")
    data = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


class RoleContractTest(unittest.TestCase):
    def test_h1_roles_exist_and_are_read_only(self):
        for name in ("sancai-explorer", "sancai-design-critic"):
            path = PLUGIN / "agents" / f"{name}.md"
            self.assertTrue(path.exists(), name)
            meta = frontmatter(path)
            self.assertEqual(meta.get("name"), name)
            self.assertIn("tools", meta)
            self.assertNotIn("Edit", meta["tools"])
            self.assertIn("Write", meta["tools"])

    def test_onboarding_exists_and_is_referenced(self):
        onboarding = PLUGIN / "references" / "agent-onboarding.md"
        self.assertTrue(onboarding.exists())
        for name in ("sancai-explorer", "sancai-design-critic"):
            text = (PLUGIN / "agents" / f"{name}.md").read_text()
            self.assertIn("agent-onboarding.md", text)


class ResearchRefsTest(unittest.TestCase):
    def intent(self, refs):
        return {
            "goal": "change a.txt",
            "non_goals": [],
            "acceptance": [{
                "id": "AC-1",
                "check": "command",
                "run": "true",
                "expect": "exit_code == 0",
            }],
            "research_refs": refs,
        }

    def test_relative_refs_are_allowed(self):
        state.validate_intent(self.intent([
            "L3-intent/research/inspect.md",
            "L3-intent/research/design-review.md",
        ]))

    def test_absolute_ref_is_rejected(self):
        with self.assertRaises(SystemExit):
            state.validate_intent(self.intent(["/etc/passwd"]))

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(SystemExit):
            state.validate_intent(self.intent(["L3-intent/../../secret.md"]))

    def test_legacy_intent_without_refs_is_allowed(self):
        intent = self.intent(None)
        intent.pop("research_refs")
        state.validate_intent(intent)


if __name__ == "__main__":
    unittest.main()
