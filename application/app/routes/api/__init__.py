from fastapi import APIRouter
from app.routes.api.orders import api_router as orders_router
from app.routes.api.returns import api_router as returns_router
from app.routes.api.refunds import api_router as refunds_router

api_router = APIRouter(tags=["api"])
api_router.include_router(orders_router)
api_router.include_router(returns_router)
api_router.include_router(refunds_router)

__all__ = ["api_router"]
