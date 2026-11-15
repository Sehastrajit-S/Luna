# Process Packages

Each directory here owns one runtime/background process. Keep process changes inside one package when possible.

Recommended package shape:

```text
process_id/
  __init__.py
  process.py   # metadata and registration hooks
  jobs.py      # scheduled/background job implementations
  README.md    # ownership notes and extension points
```

`process.py` owns metadata and registration. `jobs.py` owns scheduled/background behavior. Add `types.py` or helper files when the process grows.

Register the process module in `backend/processes/registry.py`.
