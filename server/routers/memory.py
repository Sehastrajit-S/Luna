from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.models.database import get_db, Fact, FactRelationship
from backend.models.schemas import FactOut, FactCreate, StatusResponse
from backend.services.memory_manager import MemoryManager
from backend.services.personality import PersonalityEngine
from backend.models.schemas import PersonalityOut

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/facts", response_model=list[FactOut])
def get_facts(category: str = None, db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    return memory.get_all_facts(category)


@router.post("/facts", response_model=FactOut)
async def add_fact(fact: FactCreate, db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    fact_id = await memory.store_fact(fact.content, fact.category, confidence=fact.confidence)
    return db.query(Fact).filter_by(id=fact_id).first()


@router.delete("/facts/{fact_id}", response_model=StatusResponse)
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    fact = db.query(Fact).filter_by(id=fact_id).first()
    if fact:
        fact.is_active = False
        db.commit()
    return StatusResponse(status="ok")


@router.get("/search")
async def search_memories(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    results = await memory.retrieve_relevant(q, n=10)
    return {"results": results, "query": q}


@router.get("/personality", response_model=PersonalityOut)
def get_personality(db: Session = Depends(get_db)):
    engine = PersonalityEngine(db)
    return engine.get_state()


@router.post("/compact")
async def compact_memory(db: Session = Depends(get_db)):
    memory = MemoryManager(db)
    removed = await memory.compact_facts()
    return {"ok": True, "removed": removed}


@router.get("/graph")
def get_memory_graph(db: Session = Depends(get_db)):
    """Return active facts + detected relationships for analysis."""
    from datetime import datetime as _dt
    now = _dt.utcnow()
    facts = (
        db.query(Fact)
        .filter(Fact.is_active == True)
        .order_by(Fact.importance.desc())
        .limit(200)
        .all()
    )
    fact_ids = {f.id for f in facts}
    edges = (
        db.query(FactRelationship)
        .filter(
            FactRelationship.fact_id_a.in_(fact_ids),
            FactRelationship.fact_id_b.in_(fact_ids),
        )
        .all()
    )
    return {
        "nodes": [
            {
                "id": f.id, "content": f.content, "category": f.category,
                "memory_type": f.memory_type, "importance": f.importance,
                "confidence": f.confidence,
            }
            for f in facts
        ],
        "edges": [
            {
                "source": e.fact_id_a, "target": e.fact_id_b,
                "relationship": e.relationship, "confidence": e.confidence,
                "note": e.note,
            }
            for e in edges
        ],
    }


@router.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    from backend.services.activity_tracker import ActivityTracker, Activity
    tracker = ActivityTracker(db)
    acts = tracker.get_recent_activities(20)
    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "status": a.status,
            "category": a.category,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "last_updated": a.last_updated.isoformat() if a.last_updated else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "progress_notes": a.progress_notes or [],
        }
        for a in acts
    ]
