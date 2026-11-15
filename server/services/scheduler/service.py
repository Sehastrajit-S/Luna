"""LunaScheduler: APScheduler wrapper + singleton."""
from apscheduler.schedulers.background import BackgroundScheduler


class LunaScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._running = False

    def start(self):
        if self._running:
            return
        from backend.processes.registry import iter_processes
        for process in iter_processes():
            if process.register_scheduler:
                process.register_scheduler(self.scheduler)
        self.scheduler.start()
        self._running = True

    def stop(self):
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False


luna_scheduler = LunaScheduler()
