# Processes

L.U.N.A. uses a process registry so background work can be contributed in small, owned modules instead of one central file.

## Layout

```text
backend/
  processes/
    registry.py
    calendar_reminders/
      process.py
      README.md
    memory_maintenance/
      process.py
      README.md
    proactive_followups/
      process.py
      README.md
    voice_runtime/
      process.py
      README.md
```

Each process package owns one runtime concern. A process can register scheduled jobs, lifecycle hooks, or both.

## Process Definition

Every process module exports `PROCESS`:

```python
from backend.processes.registry import ProcessDef

PROCESS = ProcessDef(
    id="example_process",
    name="Example process",
    description="What this process owns.",
    area="example",
    register_scheduler=register_scheduler,
    start=start,
    stop=stop,
)
```

All hooks are optional:

- `register_scheduler(scheduler)`: add APScheduler jobs.
- `start()`: start a long-running runtime feature.
- `stop()`: cleanly stop that runtime feature.

## Adding a Process

1. Create `backend/processes/<process_id>/process.py`.
2. Add a package `__init__.py`.
3. Export a `PROCESS` object.
4. Add the module path to `PROCESS_MODULES` in `backend/processes/registry.py`.
5. Keep feature logic in `backend/services/` when it is shared or large.
6. Add or update API routes only if the process needs external controls.

Use `docs/PROCESS_TEMPLATE.md` when adding a new process.

## Current Processes

- `calendar_reminders`: event reminders, overdue task notifications, morning greeting.
- `memory_maintenance`: memory compaction, personality decay, confidence decay, behavior pattern mining.
- `proactive_followups`: quiet-stretch check-ins, state-aware prompts, commitment follow-ups.
- `voice_runtime`: wake word and microphone lifecycle.

## API

`GET /api/agent/processes` returns registered process metadata for UI/debugging.

## Contribution Rule

If a change affects one process, keep the PR inside that process package and the service modules it calls. Avoid adding unrelated jobs to `scheduler.py`; scheduler wiring should live in `backend/processes/*/process.py`.
