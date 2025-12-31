from fastapi import APIRouter
from app.routes.app.orders import app_router as orders_router
from app.routes.app.returns import app_router as returns_router
from app.routes.app.cart import app_router as cart_router
from app.routes.app.gift_cards import app_router as gift_cards_router

app_router = APIRouter(tags=["app"])
app_router.include_router(orders_router)
app_router.include_router(returns_router)
app_router.include_router(cart_router)
app_router.include_router(gift_cards_router)