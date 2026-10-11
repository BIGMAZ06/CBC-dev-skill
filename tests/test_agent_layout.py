"""Static smoke checks of CBC native agent wiring; no provider calls."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".opencode" / "agents"


class NativeTeamLayoutTests(unittest.TestCase):
    def test_agents_are_declared(self):
        expected = {
            "cbc-coordinator": "primary",
            "cbc-planner": "subagent",
            "cbc-coder": "subagent",
            "cbc-reviewer": "subagent",
            "cbc-qa": "subagent",
            "cbc-debugger": "subagent",
        }
        for name, mode in expected.items():
            with self.subTest(name=name):
                content = (AGENTS / (name + ".md")).read_text()
                self.assertTrue(content.startswith("---\n"))
                self.assertIn("mode: " + mode, content)

    def test_observers_cannot_edit(self):
        for name in ("cbc-planner", "cbc-reviewer", "cbc-qa", "cbc-debugger"):
            with self.subTest(name=name):
                content = (AGENTS / (name + ".md")).read_text()
                self.assertIn("edit: deny", content)

    def test_command_uses_coordinator(self):
        content = (ROOT / ".opencode/commands/cbc-team.md").read_text()
        self.assertIn("agent: cbc-coordinator", content)
        self.assertIn("$ARGUMENTS", content)

    def test_require_actual_verification(self):
        content = (AGENTS / "cbc-coordinator.md").read_text()
        self.assertIn("real, current test evidence", content)
        self.assertIn("not implemented", content.lower())


if __name__ == "__main__":
    unittest.main()
