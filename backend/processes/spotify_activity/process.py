from apscheduler.triggers.interval import IntervalTrigger

from backend.processes.registry import ProcessDef
from backend.processes.spotify_activity import jobs


def register_scheduler(scheduler):
    scheduler.add_job(jobs.sync_spotify_activity, IntervalTrigger(minutes=2), id="spotify_activity_sync")


PROCESS = ProcessDef(
    id="spotify_activity",
    name="Spotify activity sync",
    description="Keeps the tracked 'listening' activity in sync with real Spotify playback state.",
    area="activity",
    register_scheduler=register_scheduler,
)
