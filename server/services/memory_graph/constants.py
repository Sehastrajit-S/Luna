"""Relationship type constants for the fact knowledge graph."""

REL_CONTRADICTS = "contradicts"
REL_CONFIRMS    = "confirms"
REL_UPDATES     = "updates"
REL_RELATED     = "related_to"
REL_CAUSED_BY   = "caused_by"
REL_PRECEDES    = "precedes"
REL_PART_OF     = "part_of"

ALL_REL_TYPES = {
    REL_CONTRADICTS, REL_CONFIRMS, REL_UPDATES,
    REL_RELATED, REL_CAUSED_BY, REL_PRECEDES, REL_PART_OF,
}
