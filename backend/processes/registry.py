from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Callable, Protocol


class SchedulerLike(Protocol):
    def add_job(self, func, trigger=None, **kwargs): ...


@dataclass(frozen=True)
class ProcessDef:
    id: str
    name: str
    description: str
    area: str
    register_scheduler: Callable[[SchedulerLike], None] | None = None
    start: Callable[[], None] | None = None
    stop: Callable[[], None] | None = None


PROCESS_MODULES = [
    "backend.processes.calendar_reminders.process",
    "backend.processes.memory_maintenance.process",
    "backend.processes.proactive_followups.process",
    "backend.processes.voice_runtime.process",
    "backend.processes.spotify_activity.process",
]


def iter_processes() -> list[ProcessDef]:
    processes: list[ProcessDef] = []
    for module_name in PROCESS_MODULES:
        module = import_module(module_name)
        processes.append(getattr(module, "PROCESS"))
    return processes


def list_processes() -> list[dict]:
    return [
        {
            "id": process.id,
            "name": process.name,
            "description": process.description,
            "area": process.area,
            "scheduler": process.register_scheduler is not None,
            "lifecycle": bool(process.start or process.stop),
        }
        for process in iter_processes()
    ]


def start_lifecycle_processes():
    for process in iter_processes():
        if process.start:
            process.start()


def stop_lifecycle_processes():
    for process in reversed(iter_processes()):
        if process.stop:
            process.stop()
