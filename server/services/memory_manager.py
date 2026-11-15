# Backward-compat shim — all logic lives in backend.services.memory_manager package
from backend.services.memory_manager import *  # noqa: F401, F403
from backend.services.memory_manager import MemoryManager
