from fastapi import APIRouter, HTTPException, Path, Request

from app.core.limiter import LIMIT_GENERAL, limiter
from app.services.stock_service import get_stock_info

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}")
@limiter.limit(LIMIT_GENERAL)
async def stock_detail(
    request: Request,
    symbol: str = Path(pattern=r"^[A-Za-z0-9]{1,10}$", max_length=10),
) -> dict:
    """Return cached data for a single stock symbol.

    Returns 404 if the symbol is not in stock_cache.
    """
    info = get_stock_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail="找不到該股票代碼")
    return info
