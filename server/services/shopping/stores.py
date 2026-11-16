"""The stores Luna compares, and how Google Shopping names them as sellers."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Store:
    key: str
    name: str
    domain: str
    # Google Shopping's "source" for this store's own listings. Marketplace
    # sellers ("Walmart - Acme Supplies") are other merchants and don't count.
    source: re.Pattern

    def matches(self, source: str) -> bool:
        return bool(self.source.fullmatch((source or "").strip()))

    @property
    def icon(self) -> str:
        """The store's favicon via Google: no logo files shipped with Luna."""
        return f"https://www.google.com/s2/favicons?domain={self.domain}&sz=64"


STORES: tuple[Store, ...] = (
    Store("walmart", "Walmart", "walmart.com", re.compile(r"walmart(?:\.com)?", re.I)),
    Store("costco", "Costco", "costco.com", re.compile(r"costco(?:\.com)?(?:\s+wholesale)?", re.I)),
    Store("target", "Target", "target.com", re.compile(r"target(?:\.com)?", re.I)),
    Store("sams", "Sam's Club", "samsclub.com", re.compile(r"sam['’]?s\s*club(?:\.com)?", re.I)),
    Store("safeway", "Safeway", "safeway.com", re.compile(r"safeway(?:\.com)?", re.I)),
)

_BY_KEY = {s.key: s for s in STORES}
_ALIASES = {
    "walmart": "walmart", "costco": "costco", "target": "target",
    "sams": "sams", "sam's": "sams", "sams club": "sams", "sam's club": "sams", "samsclub": "sams",
    "safeway": "safeway",
}


def resolve_stores(names: list[str] | None) -> list[Store]:
    """Stores the user asked for, in the canonical order; all of them when none are named."""
    if not names:
        return list(STORES)
    wanted = set()
    for name in names:
        key = _ALIASES.get(re.sub(r"\s+", " ", str(name).strip().lower()).replace("’", "'"))
        if key:
            wanted.add(key)
    return [s for s in STORES if s.key in wanted] or list(STORES)


def store_for_source(source: str, stores: list[Store]) -> Store | None:
    return next((s for s in stores if s.matches(source)), None)
