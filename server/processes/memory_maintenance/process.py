from apscheduler.triggers.cron import CronTrigger

from backend.processes.registry import ProcessDef
from backend.processes.memory_maintenance import jobs


def register_scheduler(scheduler):
    scheduler.add_job(jobs.daily_personality_decay, CronTrigger(hour=0, minute=0), id="decay")
    scheduler.add_job(jobs.daily_memory_compaction, CronTrigger(hour=3, minute=0), id="memory_compact")
    scheduler.add_job(jobs.confidence_decay, CronTrigger(day_of_week="sun", hour=2, minute=0), id="confidence_decay")
    scheduler.add_job(jobs.mine_behavioral_patterns, CronTrigger(hour=4, minute=0), id="pattern_mining")


PROCESS = ProcessDef(
    id="memory_maintenance",
    name="Memory maintenance",
    description="Personality decay, memory compaction, confidence decay, and behavior pattern mining.",
    area="memory",
    register_scheduler=register_scheduler,
)
