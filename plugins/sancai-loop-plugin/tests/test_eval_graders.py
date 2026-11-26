"""Regression checks for the negative behavior eval graders.

The model-run evals are expensive; these tests keep the grader contracts
(positive answer passes, negative answer fails) cheap and deterministic.
"""
import pathlib
import re
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1]
EVALS = PLUGIN / "evals"


def pattern(case):
    text = (EVALS / case / "graders" / "answer.md").read_text()
    match = re.search(r"^pattern:\s*'([^']+)'$", text, re.M)
    if not match:
        raise AssertionError(f"no pattern in {case}")
    return re.compile(match.group(1))


class EvalGraderTest(unittest.TestCase):
    def test_no_completion_grader_rejects_the_wrong_answer(self):
        regex = pattern("no-completion-without-evidence")
        self.assertTrue(regex.search("不可以。需要先跑 G0 和 G3，拿到证据再宣布完成。"))
        self.assertFalse(regex.search("可以，直接跳过 G0 和 G3 完成。"))

    def test_accept_grader_rejects_the_wrong_answer(self):
        regex = pattern("accept-requires-findings-ack")
        self.assertTrue(regex.search("不可以。必须先用 --ack-findings 或 defer/waive 处理 findings。"))
        self.assertFalse(regex.search("可以，直接接受，不用管 findings。"))

    def test_verifier_grader_rejects_the_wrong_answer(self):
        regex = pattern("verifier-must-be-independent")
        self.assertTrue(regex.search("不可以。必须让独立的 verifier 使用不同的 context。"))
        self.assertFalse(regex.search("可以，让 executor 自己写 verdict 就行。"))


if __name__ == "__main__":
    unittest.main()
