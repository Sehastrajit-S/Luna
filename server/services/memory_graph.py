# Backward-compat shim — all logic lives in backend.services.memory_graph package
from backend.services.memory_graph import *  # noqa: F401, F403
from backend.services.memory_graph import (
    REL_CONTRADICTS,
    REL_CONFIRMS,
    REL_UPDATES,
    REL_RELATED,
    REL_CAUSED_BY,
    REL_PRECEDES,
    REL_PART_OF,
    ALL_REL_TYPES,
    FactNode,
    GraphEdge,
    MemoryGraph,
)
