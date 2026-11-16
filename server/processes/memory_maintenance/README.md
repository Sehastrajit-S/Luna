# Memory Maintenance Process

Owns scheduled memory and personality maintenance:

- Daily personality decay.
- Daily memory compaction.
- Weekly confidence decay.
- Behavioral pattern mining.

Scheduling is registered in `process.py`. Job exports live in `jobs.py`; keep new maintenance jobs in this package.
