from apscheduler.triggers.interval import IntervalTrigger

from backend.processes.registry import ProcessDef
from backend.processes.proactive_followups import jobs


def register_scheduler(scheduler):
    scheduler.add_job(jobs.companion_check_in, IntervalTrigger(minutes=10), id="companion_check_in")
    scheduler.add_job(jobs.state_aware_proactive, IntervalTrigger(minutes=10), id="state_proactive")
    scheduler.add_job(jobs.proactive_commitment_followup, IntervalTrigger(hours=4), id="commitment_followup")
    scheduler.add_job(jobs.vision_aware_checkin, IntervalTrigger(minutes=3), id="vision_aware_checkin")


PROCESS = ProcessDef(
    id="proactive_followups",
    name="Proactive follow-ups",
    description="Quiet-stretch check-ins, state-aware prompts, and commitment follow-ups.",
    area="assistant",
    register_scheduler=register_scheduler,
)
