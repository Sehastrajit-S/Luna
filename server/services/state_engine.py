# Backward-compat shim — all logic lives in backend.services.state_engine package
from backend.services.state_engine import *  # noqa: F401, F403
from backend.services.state_engine import (
    UserState,
    STATE_POLICIES,
    get_pc_idle_seconds,
    get_active_app,
    StateEngine,
    state_engine,
)
