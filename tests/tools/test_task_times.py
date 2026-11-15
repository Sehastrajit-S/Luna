import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _db():
    from backend.models.database import Base
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _local_to_utc(dt: datetime) -> datetime:
    return dt.astimezone().astimezone(timezone.utc).replace(tzinfo=None)


class TaskTimeTests(unittest.TestCase):
    def test_model_times_are_local_and_stored_as_utc(self) -> None:
        from backend.models.database import Task
        from backend.services.command_parser import parse_commands
        from backend.services.command_parser.commands import execute_commands

        db = _db()
        execute_commands(parse_commands("[TASK:satpv paper outline|2026-09-23T22:00:00|high]"), db, 1)
        task = db.query(Task).one()
        self.assertEqual(task.due_date, _local_to_utc(datetime(2026, 9, 23, 22, 0)))
        # Serialised as UTC, a client converting to local time sees 10:00 PM again.
        shown = task.due_date.replace(tzinfo=timezone.utc).astimezone()
        self.assertEqual((shown.hour, shown.minute), (22, 0))

    def test_same_title_updates_the_open_task_instead_of_duplicating(self) -> None:
        from backend.models.database import Task
        from backend.services.command_parser import parse_commands
        from backend.services.command_parser.commands import execute_commands

        db = _db()
        execute_commands(parse_commands("[TASK:satpv paper outline|2026-09-23T15:00:00|high]"), db, 1)
        execute_commands(parse_commands("[TASK:SatPV Paper Outline|2026-09-23T22:00:00|high]"), db, 1)
        tasks = db.query(Task).all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].due_date, _local_to_utc(datetime(2026, 9, 23, 22, 0)))

    def test_completed_tasks_are_not_reused(self) -> None:
        from backend.models.database import Task
        from backend.services.command_parser import parse_commands
        from backend.services.command_parser.commands import execute_commands

        db = _db()
        db.add(Task(title="Gym", completed=True)); db.commit()
        execute_commands(parse_commands("[TASK:Gym|2026-09-24T07:00:00|medium]"), db, 1)
        self.assertEqual(db.query(Task).count(), 2)

    def test_events_crossing_the_hour_are_saved_with_correct_end(self) -> None:
        from backend.models.database import CalendarEvent
        from backend.services.command_parser import parse_commands
        from backend.services.command_parser.commands import execute_commands

        db = _db()
        start = datetime.now().replace(second=0, microsecond=0) + timedelta(days=2)
        start = start.replace(minute=30)
        execute_commands(parse_commands(f"[EVENT:Advisor sync|{start.isoformat()}|60]"), db, 1)
        event = db.query(CalendarEvent).one()                    # previously crashed on minute 90
        self.assertEqual(event.end_datetime - event.start_datetime, timedelta(minutes=60))
        self.assertEqual(event.start_datetime, _local_to_utc(start))


class ConfirmationTests(unittest.TestCase):
    def test_tag_only_reply_gets_a_readable_confirmation(self) -> None:
        from backend.services.chat_pipeline.stage_tools import _confirm_bare_actions

        db = _db()
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        ctx = SimpleNamespace(full_response=f"\n[TASK:satpv paper outline|{tomorrow.isoformat()}|high]",
                              user_message="add a task", db=db)
        _confirm_bare_actions(ctx)
        self.assertTrue(ctx.full_response.startswith("Added task “satpv paper outline” — due tomorrow at 10:00 PM."))
        self.assertIn("[TASK:", ctx.full_response)                  # tag kept so finalize still runs it

    def test_replies_with_text_are_left_alone(self) -> None:
        from backend.services.chat_pipeline.stage_tools import _confirm_bare_actions

        ctx = SimpleNamespace(full_response="Done! [TASK:x|2026-09-24T10:00:00|low]", user_message="", db=_db())
        _confirm_bare_actions(ctx)
        self.assertEqual(ctx.full_response, "Done! [TASK:x|2026-09-24T10:00:00|low]")

    def test_utc_helpers_round_trip(self) -> None:
        from backend.services.time_utils import to_utc_naive, utc_naive_to_local

        local = datetime(2026, 9, 23, 22, 0)
        self.assertEqual(utc_naive_to_local(to_utc_naive(local)), local)
        aware = datetime(2026, 9, 23, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(to_utc_naive(aware), datetime(2026, 9, 23, 22, 0))
        self.assertIsNone(to_utc_naive(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
