from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from server.processes.registry import ProcessDef
from server.processes.calendar_reminders import jobs


def register_scheduler(scheduler):
    scheduler.add_job(jobs.check_upcoming_events, IntervalTrigger(minutes=1), id="events")  # reminders at -15 min, start, and task due times
    scheduler.add_job(jobs.check_overdue_tasks, CronTrigger(hour=8, minute=0), id="tasks")
    scheduler.add_job(jobs.morning_greeting, CronTrigger(hour=8, minute=1), id="morning")


PROCESS = ProcessDef(
    id="calendar_reminders",
    name="Calendar reminders",
    description="Upcoming events, overdue tasks, and morning greeting notifications.",
    area="calendar",
    register_scheduler=register_scheduler,
)
