"""Luna MCP server — memory and facts.

Exposes: list_facts, search_facts, add_fact
Resources: memory://facts, memory://personality

Run:
    python -m backend.mcp.server_memory
"""
import json
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import DATA_DIR, settings

mcp = FastMCP("luna-memory")

_engine = create_engine(f"sqlite:///{DATA_DIR}/luna.db", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def _session():
    return _Session()


@mcp.resource("memory://facts")
def facts_resource() -> str:
    """All of Luna's stored facts as a JSON resource."""
    with _session() as db:
        rows = db.execute(
            text("SELECT content, category, confidence, created_at FROM facts ORDER BY created_at DESC LIMIT 100")
        ).fetchall()
    return json.dumps(
        [{"content": r[0], "category": r[1], "confidence": r[2], "created_at": r[3]} for r in rows],
        indent=2,
    )


@mcp.resource("memory://personality")
def personality_resource() -> str:
    """Luna's current personality state as a JSON resource."""
    with _session() as db:
        row = db.execute(text("SELECT * FROM personality_state ORDER BY id DESC LIMIT 1")).fetchone()
    if not row:
        return json.dumps({"error": "No personality state found."})
    keys = ["id", "current_mood", "energy_level", "stress_level", "happiness", "curiosity",
            "last_interaction", "notes", "created_at", "updated_at"]
    return json.dumps(dict(zip(keys, row)), indent=2, default=str)


@mcp.tool()
def list_facts(limit: int = 20, category: str = "") -> str:
    """List facts stored in Luna's memory. Optionally filter by category."""
    with _session() as db:
        if category:
            rows = db.execute(
                text("SELECT content, category, confidence FROM facts WHERE category = :c ORDER BY created_at DESC LIMIT :l"),
                {"c": category, "l": limit},
            ).fetchall()
        else:
            rows = db.execute(
                text("SELECT content, category, confidence FROM facts ORDER BY created_at DESC LIMIT :l"),
                {"l": limit},
            ).fetchall()
    if not rows:
        return "No facts found."
    return json.dumps([{"content": r[0], "category": r[1], "confidence": r[2]} for r in rows], indent=2)


@mcp.tool()
def search_facts(query: str) -> str:
    """Search Luna's memory for facts containing the query string."""
    with _session() as db:
        rows = db.execute(
            text("SELECT content, category, confidence FROM facts WHERE content LIKE :q ORDER BY confidence DESC LIMIT 20"),
            {"q": f"%{query}%"},
        ).fetchall()
    if not rows:
        return f"No facts found matching '{query}'."
    return json.dumps([{"content": r[0], "category": r[1], "confidence": r[2]} for r in rows], indent=2)


@mcp.tool()
def add_fact(content: str, category: str = "general") -> str:
    """Add a new fact to Luna's memory."""
    with _session() as db:
        db.execute(
            text(
                "INSERT INTO facts (content, category, confidence, source, created_at, updated_at) "
                "VALUES (:c, :cat, 1.0, 'mcp', :ts, :ts)"
            ),
            {"c": content, "cat": category, "ts": datetime.now(timezone.utc).isoformat()},
        )
        db.commit()
    return f"Fact added: {content}"


if __name__ == "__main__":
    mcp.run()
