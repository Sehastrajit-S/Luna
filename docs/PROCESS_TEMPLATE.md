# Process Template

Use this structure for new runtime/background processes.

```text
backend/processes/my_process/
  __init__.py
  process.py
  jobs.py
  README.md
```

`process.py`:

```python
from apscheduler.triggers.interval import IntervalTrigger

from backend.processes.registry import ProcessDef
from backend.processes.my_process import jobs


def register_scheduler(scheduler):
    scheduler.add_job(jobs.run, IntervalTrigger(minutes=15), id="my_process_run")


PROCESS = ProcessDef(
    id="my_process",
    name="My process",
    description="What this process owns.",
    area="my_area",
    register_scheduler=register_scheduler,
)
```

`jobs.py`:

```python
def run():
    # Keep job logic here or delegate to backend/services/my_feature.py.
    pass
```

For lifecycle-only processes:

```python
from backend.processes.registry import ProcessDef


def start():
    pass


def stop():
    pass


PROCESS = ProcessDef(
    id="my_runtime",
    name="My runtime",
    description="Long-running runtime feature.",
    area="runtime",
    start=start,
    stop=stop,
)
```
