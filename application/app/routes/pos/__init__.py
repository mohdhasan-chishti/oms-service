# Routes specific to POS clients will live here.
from fastapi import APIRouter

# Import individual routers
from app.routes.pos.orders import pos_router as pos_orders_router
from app.routes.pos.returns import pos_router as pos_returns_router
from app.routes.pos.cart import pos_router as pos_cart_router
from app.routes.pos.gift_cards import pos_router as pos_gift_cards_router
from app.routes.pos.paytm_payments import paytm_router as pos_paytm_router

# Aggregate into a single router that FastAPI can mount at /pos/v1
pos_router = APIRouter(tags=["pos"])
pos_router.include_router(pos_orders_router)
pos_router.include_router(pos_returns_router)
pos_router.include_router(pos_cart_router)
pos_router.include_router(pos_gift_cards_router)
pos_router.include_router(pos_paytm_router)
