import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _ctx(message, reply="Sure.", route="agent_loop", tools=(), errors=0):
    return SimpleNamespace(conv=SimpleNamespace(id=7), user_message=message, full_response=reply, route=route,
                           tools_used=list(tools), tool_errors=errors, attachment_ids=[], voice=False, cli=False)


class DecisionLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        from server.services import decision_log
        self.log = decision_log
        self.patch = mock.patch.object(decision_log, "DATA_DIR", Path(self.tmp.name))
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.tmp.cleanup()

    def _rows(self):
        files = list((Path(self.tmp.name) / "decisions").glob("*.jsonl"))
        return [json.loads(line) for f in files for line in f.read_text(encoding="utf-8").splitlines()]

    def test_each_turn_records_route_tools_and_rule_decisions(self) -> None:
        self.log.record_turn(_ctx("find the latest ollama release, then add a task to read it tonight",
                                  tools=["web_search", "create_task"]), turn=1)
        (row,) = self._rows()
        self.assertEqual((row["type"], row["route"], row["turn"], row["conversation_id"]), ("turn", "agent_loop", 1, 7))
        self.assertEqual(row["tools"], ["web_search", "create_task"])
        self.assertTrue(row["signals"]["multi_step"])
        self.assertFalse(row["signals"]["crew_explicit"])

    def test_corrections_and_repeats_mark_the_previous_turn(self) -> None:
        self.log.record_turn(_ctx("no, that's not what I asked"), turn=4, previous_user_message="play jazz")
        self.log.record_turn(_ctx("play jazz"), turn=5, previous_user_message="play jazz")
        feedback = [r for r in self._rows() if r["type"] == "feedback"]
        self.assertEqual([(f["turn"], f["signal"]) for f in feedback], [(3, "correction"), (4, "repeat")])

    def test_crew_misfire_is_visible_in_the_signals(self) -> None:
        probe = "Quick check: what's the test budget and the code word?"
        signals = self.log.signals_for(probe, "")
        self.assertFalse(signals["crew_explicit"])

    def test_can_be_turned_off(self) -> None:
        from server.config import settings
        with mock.patch.object(settings, "decision_log_enabled", False):
            self.log.record_turn(_ctx("hello"), turn=1)
        self.assertEqual(self._rows(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
