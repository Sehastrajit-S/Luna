"""Budget page: monthly overview, categories with limits, expenses and income.

GET    /api/budget/summary?month=YYYY-MM   totals, per-category spend, entries, 6-month trend
POST   /api/budget/transactions            add an expense or income
PATCH  /api/budget/transactions/{id}       edit one
DELETE /api/budget/transactions/{id}
POST   /api/budget/categories              add a category
PATCH  /api/budget/categories/{id}         rename, change icon or monthly limit
DELETE /api/budget/categories/{id}         its expenses become Uncategorized
GET    /api/budget/export.csv?month=       the month's entries as CSV
POST   /api/budget/receipt                 receipt photo (multipart "image") → draft expense

Errors come back as {"detail": {"kind", "message"}}.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.models.database import get_db
from server.services import budget
from server.services.budget import BudgetError

router = APIRouter(prefix="/api/budget", tags=["budget"])

MAX_RECEIPT_BYTES = 15 * 1024 * 1024

_STATUS = {"bad_request": 400, "bad_image": 400, "no_text": 422, "not_found": 404,
           "conflict": 409, "too_large": 413, "not_configured": 503}


def _error(e: BudgetError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(e.kind, 400), detail={"kind": e.kind, "message": e.message})


class TransactionIn(BaseModel):
    amount: float = Field(..., gt=0)
    kind: Literal["expense", "income"] = "expense"
    description: str = Field("", max_length=200)
    category_id: Optional[int] = None
    date: Optional[str] = None
    source: Literal["manual", "receipt"] = "manual"


class TransactionPatch(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    kind: Optional[Literal["expense", "income"]] = None
    description: Optional[str] = Field(None, max_length=200)
    category_id: Optional[int] = None
    date: Optional[str] = None


class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    icon: str = Field("", max_length=8)
    limit: float = Field(0, ge=0)


class CategoryPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=40)
    icon: Optional[str] = Field(None, max_length=8)
    limit: Optional[float] = Field(None, ge=0)


@router.get("/summary")
def get_summary(month: Optional[str] = Query(None, max_length=7), db: Session = Depends(get_db)):
    try:
        return budget.summary(db, month)
    except BudgetError as e:
        raise _error(e) from e


@router.post("/transactions", status_code=201)
def add_transaction(body: TransactionIn, db: Session = Depends(get_db)):
    try:
        return budget.add_transaction(db, amount=body.amount, kind=body.kind, description=body.description,
                                      category_id=body.category_id, day=body.date, source=body.source)
    except BudgetError as e:
        raise _error(e) from e


@router.patch("/transactions/{txn_id}")
def edit_transaction(txn_id: int, body: TransactionPatch, db: Session = Depends(get_db)):
    try:
        return budget.update_transaction(db, txn_id, body.model_dump(exclude_unset=True))
    except BudgetError as e:
        raise _error(e) from e


@router.delete("/transactions/{txn_id}", status_code=204)
def remove_transaction(txn_id: int, db: Session = Depends(get_db)):
    try:
        budget.delete_transaction(db, txn_id)
    except BudgetError as e:
        raise _error(e) from e
    return Response(status_code=204)


@router.post("/categories", status_code=201)
def add_category(body: CategoryIn, db: Session = Depends(get_db)):
    try:
        return budget.add_category(db, name=body.name, icon=body.icon, limit=body.limit)
    except BudgetError as e:
        raise _error(e) from e


@router.patch("/categories/{cat_id}")
def edit_category(cat_id: int, body: CategoryPatch, db: Session = Depends(get_db)):
    try:
        return budget.update_category(db, cat_id, body.model_dump(exclude_unset=True))
    except BudgetError as e:
        raise _error(e) from e


@router.delete("/categories/{cat_id}", status_code=204)
def remove_category(cat_id: int, db: Session = Depends(get_db)):
    try:
        budget.delete_category(db, cat_id)
    except BudgetError as e:
        raise _error(e) from e
    return Response(status_code=204)


@router.get("/export.csv")
def export(month: Optional[str] = Query(None, max_length=7), db: Session = Depends(get_db)):
    try:
        month = budget.parse_month(month)
        body = budget.export_csv(db, month)
    except BudgetError as e:
        raise _error(e) from e
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="luna-budget-{month}.csv"'})


@router.post("/receipt")
async def read_receipt(image: UploadFile = File(...)):
    data = await image.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise _error(BudgetError("too_large", "That photo is over 15 MB."))
    if not data:
        raise _error(BudgetError("bad_image", "The photo was empty."))
    try:
        # OCR is CPU-bound; keep the event loop free.
        return (await asyncio.to_thread(budget.read_receipt, data)).to_dict()
    except BudgetError as e:
        raise _error(e) from e
