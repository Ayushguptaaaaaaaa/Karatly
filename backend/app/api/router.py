from fastapi import APIRouter

from app.api.routes import (
    ai_routes,
    auth,
    categories,
    designs,
    health,
    insights_misc,
    periods,
    purchase_plans,
    stock,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(categories.router)
api_router.include_router(designs.router)
api_router.include_router(stock.router)
api_router.include_router(periods.router)
api_router.include_router(insights_misc.router)
api_router.include_router(purchase_plans.router)
api_router.include_router(ai_routes.router)
