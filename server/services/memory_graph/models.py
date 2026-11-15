"""Graph node and edge dataclasses."""
from dataclasses import dataclass


@dataclass
class FactNode:
    id: int
    content: str
    category: str
    confidence: float
    importance: float


@dataclass
class GraphEdge:
    fact_a: int
    fact_b: int
    relation: str
    confidence: float
