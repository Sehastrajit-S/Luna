import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _session_factory():
    from backend.models.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class PromisedActionTests(unittest.TestCase):
    def _ctx(self, user, reply, history=()):
        return SimpleNamespace(user_message=user, full_response=reply, history=list(history), db=_session_factory()())

    def test_false_reminder_claim_creates_the_event(self) -> None:
        from backend.services.chat_pipeline import stage_tools

        six_pm = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
        history = [{"role": "user", "content": "I got a meeting of my deep learning project at 6 p.m. today."},
                   {"role": "assistant", "content": "Got it."}]
        ctx = self._ctx("Added so that I can remember at that time.", "Okay, got it — your reminder's set.", history)
        item = {"kind": "event", "title": "Deep learning project meeting", "datetime": six_pm, "duration_minutes": 60}
        with mock.patch("backend.services.command_parser.schedule.extract_item", new=mock.AsyncMock(return_value=item)):
            asyncio.run(stage_tools._ensure_promised_action(ctx))
            stage_tools._confirm_bare_actions(ctx)
        self.assertIn("[EVENT:Deep learning project meeting|", ctx.full_response)       # finalize will save it
        self.assertIn("Added “Deep learning project meeting” to your calendar", ctx.full_response)

    def test_missing_details_are_admitted_not_faked(self) -> None:
        from backend.services.chat_pipeline import stage_tools

        ctx = self._ctx("remind me", "Sure — your reminder's set!")
        with mock.patch("backend.services.command_parser.schedule.extract_item",
                        new=mock.AsyncMock(return_value={"kind": "task", "title": "", "datetime": None, "duration_minutes": 60})):
            asyncio.run(stage_tools._ensure_promised_action(ctx))
        self.assertEqual(ctx.full_response, "I haven't saved that yet — tell me what to call it and when it is and I'll add it.")

    def test_unrelated_replies_are_untouched(self) -> None:
        from backend.services.chat_pipeline import stage_tools

        ctx = self._ctx("write a helper", "I've added a helper function below.")
        with mock.patch("backend.services.command_parser.schedule.extract_item") as extract:
            asyncio.run(stage_tools._ensure_promised_action(ctx))
        extract.assert_not_called()
        self.assertEqual(ctx.full_response, "I've added a helper function below.")

    def test_task_without_time_is_still_saved(self) -> None:
        from backend.services.command_parser.schedule import to_command

        self.assertEqual(to_command({"kind": "task", "title": "Buy milk", "datetime": None, "duration_minutes": 60}),
                         "[TASK:Buy milk||medium]")
        self.assertIsNone(to_command({"kind": "event", "title": "Call", "datetime": None, "duration_minutes": 30}))


class ReminderJobTests(unittest.TestCase):
    def test_heads_up_start_and_due_each_fire_once(self) -> None:
        from backend.models.database import CalendarEvent, Task
        from backend.services.scheduler import jobs

        factory = _session_factory()
        db = factory()
        now = datetime.utcnow()
        db.add(CalendarEvent(title="DL meeting", start_datetime=now + timedelta(minutes=10)))
        db.add(CalendarEvent(title="Standup", start_datetime=now + timedelta(seconds=20)))
        db.add(CalendarEvent(title="Later", start_datetime=now + timedelta(hours=3)))
        db.add(Task(title="SatPV outline", due_date=now + timedelta(seconds=10)))
        db.add(Task(title="Done thing", due_date=now, completed=True))
        db.commit()

        sent = []
        jobs._announced.clear()
        with mock.patch.object(jobs, "SessionLocal", factory), \
             mock.patch.object(jobs, "send_windows_notification", side_effect=lambda t, m: sent.append(m)), \
             mock.patch.object(jobs, "proactive_queue", []):
            jobs.check_upcoming_events()
            jobs.check_upcoming_events()            # a minute later: nothing repeats
        self.assertEqual(sorted(sent), sorted([
            "Heads up — 'DL meeting' starts in 10 minutes.",
            "'Standup' is starting now.",
            "Reminder: 'SatPV outline' is due now.",
        ]))


class CodeAnswerTests(unittest.TestCase):
    """Long answers and code are never read as 'I saved it' claims (that wiped code replies)."""

    CODE_REPLY = ("Here's the endpoint:\n\n```python\n@app.post('/shorten')\ndef shorten(url: str, tasks: BackgroundTasks):\n"
                  "    link = Link(url=url)  # created_at is set, then schedule the cache task\n    return {'code': link.code}\n```\n")

    def test_code_is_not_a_claim(self) -> None:
        from backend.services.command_parser.schedule import claims_saved, wants_saved

        self.assertFalse(claims_saved(self.CODE_REPLY))
        self.assertFalse(wants_saved("Write the FastAPI POST /shorten endpoint", self.CODE_REPLY))
        self.assertTrue(claims_saved("Done — your reminder's set for 6."))
        long_prose = "Here is how it works. " * 30 + "The task was created and added to the calendar module."
        self.assertFalse(claims_saved(long_prose))

    def test_code_reply_survives_the_reply_checks(self) -> None:
        from backend.services.chat_pipeline import stage_tools

        ctx = SimpleNamespace(user_message="Write the FastAPI POST /shorten endpoint", full_response=self.CODE_REPLY,
                              history=[], db=None, system_prompt="", document_context="", messages=[],
                              tool_outputs=[], tools_used=[], attachment_ids=[])
        with mock.patch("backend.services.command_parser.schedule.extract_item") as extract:
            asyncio.run(stage_tools.finish_plain_reply(ctx))
        extract.assert_not_called()
        self.assertEqual(ctx.full_response, self.CODE_REPLY)

    def test_remind_me_what_is_a_recall_question(self) -> None:
        from backend.services.command_parser.schedule import wants_saved

        self.assertFalse(wants_saved("Remind me: what's the project called, and what TTL did we set?", "Snip, 24 hours."))
        self.assertFalse(wants_saved("remind me of the name we picked", "Snip."))
        self.assertTrue(wants_saved("remind me to call mom at 6", "Okay."))

    def test_agent_loop_answer_is_not_overridden_without_a_claim(self) -> None:
        from backend.services.chat_pipeline import stage_tools

        ctx = SimpleNamespace(user_message="set a reminder for the standup", full_response="Which day and time?",
                              route="agent_loop", history=[], db=None, system_prompt="", document_context="",
                              messages=[], tool_outputs=[], tools_used=[], attachment_ids=[])
        with mock.patch("backend.services.command_parser.schedule.extract_item") as extract:
            asyncio.run(stage_tools.finish_plain_reply(ctx))
        extract.assert_not_called()                     # the model asked a question; leave it
        self.assertEqual(ctx.full_response, "Which day and time?")

    def test_future_and_change_claims_are_claims(self) -> None:
        from backend.services.command_parser.schedule import claims_saved

        self.assertTrue(claims_saved("Sure thing.\n\nI'll remind you to stretch at 5 PM."))
        self.assertTrue(claims_saved("Done, moved it to 5 pm."))
        self.assertTrue(claims_saved("Rescheduled the standup to Thursday."))
        self.assertFalse(claims_saved("I updated it to use async/await instead of callbacks."))
        self.assertFalse(claims_saved("You changed the loop to a comprehension, nice."))

    def test_ellipses_stay_in_code(self) -> None:
        from backend.services.response_formatter import format_luna_response

        out = format_luna_response("Well... fine.\n\n```python\ndef f(x=Depends(...)):\n    ...\n```")
        self.assertIn("Depends(...)", out)
        self.assertTrue(out.startswith("Well fine."))


class PhrasingTests(unittest.TestCase):
    def test_noun_first_requests_and_claims(self) -> None:
        from backend.services.command_parser.schedule import wants_saved

        self.assertTrue(wants_saved("I have a meeting for my deep learning project at 6 p.m. Make sure to add that.", "Okay."))
        self.assertTrue(wants_saved("hi", "Got it — your meeting is scheduled for 6 PM."))
        self.assertTrue(wants_saved("thanks", "The task has been added."))

    def test_non_scheduling_messages_are_ignored(self) -> None:
        from backend.services.command_parser.schedule import wants_saved

        self.assertFalse(wants_saved("make it shorter", "Here is a shorter version."))
        self.assertFalse(wants_saved("add a docstring to this function", "I've added a docstring."))
        self.assertFalse(wants_saved("how was the meeting in the movie?", "It was tense."))


class VerifiedSaveTests(unittest.TestCase):
    """Saves are read back from the database; the reply describes the stored row."""

    def _local_6pm(self):
        return datetime.now().replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=1)

    def test_create_event_tool_converts_to_utc_and_updates_instead_of_duplicating(self) -> None:
        from backend.models.database import CalendarEvent
        from backend.services.time_utils import to_utc_naive
        from backend.services.tool_runner.executor import execute_tool_call

        db = _session_factory()()
        six = self._local_6pm()
        call = {"tool": "create_event", "args": {"title": "Deep learning project meeting",
                                                 "datetime": six.isoformat(timespec="minutes"), "duration": 60}}
        first = asyncio.run(execute_tool_call(call, db, 1))
        call["args"]["title"] = "meeting for my deep learning project"      # reworded, same meeting
        second = asyncio.run(execute_tool_call(call, db, 1))
        call["args"]["datetime"] = (six + timedelta(hours=1)).isoformat(timespec="minutes")
        third = asyncio.run(execute_tool_call(call, db, 1))

        rows = db.query(CalendarEvent).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].start_datetime, to_utc_naive(six + timedelta(hours=1)))
        self.assertEqual(rows[0].end_datetime - rows[0].start_datetime, timedelta(minutes=60))
        self.assertIn("Added", first)
        self.assertIn("6:00 PM", first)
        self.assertIn("Updated", second)
        self.assertIn("Moved", third)
        self.assertIn("7:00 PM", third)

    def test_event_tool_without_time_reports_failure(self) -> None:
        from backend.services.tool_runner.executor import execute_tool_call

        db = _session_factory()()
        result = asyncio.run(execute_tool_call({"tool": "create_event", "args": {"title": "Call"}}, db, 1))
        self.assertIn("couldn't save", result)

    def test_tags_are_saved_before_the_reply_and_confirmed_from_the_db(self) -> None:
        from backend.models.database import Task
        from backend.services.chat_pipeline import stage_tools

        db = _session_factory()()
        due = self._local_6pm().isoformat(timespec="minutes")
        ctx = SimpleNamespace(user_message="add satpv outline", db=db,
                              full_response=f"Sure! Your task is added. [TASK:SatPV outline|{due}|high]")
        stage_tools._save_schedule_now(ctx)
        self.assertEqual(db.query(Task).count(), 1)
        self.assertNotIn("[TASK:", ctx.full_response)          # finalize must not save it twice
        self.assertTrue(ctx.full_response.startswith("Added task “SatPV outline” — due tomorrow at 6:00 PM."))


class FactExtractorSaveTests(unittest.TestCase):
    """The background extractor saves through the same path: UTC, no duplicates."""

    def test_extractor_skips_an_already_saved_meeting_and_converts_new_ones(self) -> None:
        import json as _json
        from backend.models.database import CalendarEvent
        from backend.services import fact_extractor
        from backend.services.command_parser.commands import save_event
        from backend.services.time_utils import to_utc_naive

        db = _session_factory()()
        six = (datetime.now() + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        save_event(db, "Deep learning project meeting", six.isoformat(timespec="minutes"), 60)
        db.commit()
        seven = six + timedelta(hours=1)
        items = [
            {"action": "create_event", "title": "Deep Learning Project Meeting", "datetime": six.isoformat(timespec="minutes")},
            {"action": "create_event", "title": "Gym session", "datetime": seven.isoformat(timespec="minutes")},
        ]
        with mock.patch.object(fact_extractor.ollama, "complete", new=mock.AsyncMock(return_value=_json.dumps(items))):
            asyncio.run(fact_extractor.extract_facts_from_conversation("chat", db, 1, mock.MagicMock()))
        rows = {e.title: e.start_datetime for e in db.query(CalendarEvent).all()}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["Gym session"], to_utc_naive(seven))


if __name__ == "__main__":
    unittest.main(verbosity=2)
