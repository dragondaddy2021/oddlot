import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from app.core.limiter import LIMIT_GENERAL, limiter
from app.core.security import get_current_user
from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteCreate(BaseModel):
    symbol: str
    name: str

    @field_validator("symbol")
    @classmethod
    def symbol_upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        return v.strip()


# ── GET /favorites ─────────────────────────────────────────────────────────────

@router.get("")
@limiter.limit(LIMIT_GENERAL)
async def list_favorites(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """Return all favorites for the authenticated user."""
    user_id: str = current_user["sub"]
    resp = (
        get_supabase()
        .table("favorites")
        .select("*")
        .eq("user_id", user_id)
        .order("added_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── POST /favorites ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
@limiter.limit(LIMIT_GENERAL)
async def add_favorite(
    request: Request,
    body: FavoriteCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Add a stock to the authenticated user's favorites.

    Returns 409 if the stock is already in the user's favorites.
    """
    user_id: str = current_user["sub"]
    try:
        resp = (
            get_supabase()
            .table("favorites")
            .insert(
                {
                    "user_id": user_id,
                    "stock_symbol": body.symbol,
                    "stock_name": body.name,
                }
            )
            .execute()
        )
    except Exception as exc:
        err = str(exc)
        if "23505" in err or "duplicate" in err.lower() or "unique" in err.lower():
            raise HTTPException(status_code=409, detail="此股票已在收藏清單中") from exc
        logger.error("favorites insert failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="新增收藏失敗") from exc

    return resp.data[0]


# ── DELETE /favorites/{symbol} ─────────────────────────────────────────────────

@router.delete("/{symbol}", status_code=204)
@limiter.limit(LIMIT_GENERAL)
async def remove_favorite(
    request: Request,
    symbol: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Remove a stock from the authenticated user's favorites."""
    user_id: str = current_user["sub"]
    try:
        (
            get_supabase()
            .table("favorites")
            .delete()
            .eq("user_id", user_id)
            .eq("stock_symbol", symbol.upper())
            .execute()
        )
    except Exception as exc:
        logger.error("favorites delete failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="刪除收藏失敗") from exc

    return Response(status_code=204)
