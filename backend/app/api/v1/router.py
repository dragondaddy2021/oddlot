from fastapi import APIRouter

from app.api.v1 import favorites, recommendations, stocks

router = APIRouter(prefix="/api/v1")

router.include_router(recommendations.router)
router.include_router(stocks.router)
router.include_router(favorites.router)
