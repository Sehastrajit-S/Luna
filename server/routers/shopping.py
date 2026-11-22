"""Scan a product's barcode, then compare its price across stores.

POST /api/shopping/barcode/decode    photo or camera frame (multipart "image") → {"code"}
GET  /api/shopping/barcode/{code}    product name, brand, size and image for a UPC/EAN
POST /api/shopping/compare           {"product"} → the store price comparison (same as the
                                     "Store prices" skill in chat)

Errors come back as {"detail": {"kind", "message"}} so the UI can say what to do next.
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from server.services.shopping import ShoppingError, compare_store_prices
from server.services.shopping.barcode import MAX_IMAGE_BYTES, BarcodeError, decode_image_async, lookup

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

_STATUS = {
    "bad_image": 400, "invalid_code": 400, "bad_request": 400,
    "no_barcode": 422, "not_found": 404,
    "rate_limited": 429, "quota_exhausted": 429, "not_configured": 503,
    "invalid_key": 502, "upstream_error": 502,
}


def _error(kind: str, message: str) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(kind, 502), detail={"kind": kind, "message": message})


@router.post("/barcode/decode")
async def decode_barcode(image: UploadFile = File(...)):
    data = await image.read(MAX_IMAGE_BYTES + 1)
    try:
        return {"code": await decode_image_async(data)}
    except BarcodeError as e:
        raise _error(e.kind, e.message) from e


@router.get("/barcode/{code}")
async def barcode_product(code: str):
    try:
        return (await lookup(code)).to_dict()
    except BarcodeError as e:
        raise _error(e.kind, e.message) from e


class CompareIn(BaseModel):
    product: str = Field(..., min_length=2, max_length=200)


@router.post("/compare")
async def compare(body: CompareIn):
    try:
        return await compare_store_prices(body.product)
    except ShoppingError as e:
        raise _error(e.kind, e.message) from e
