from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health_check(request: Request):

    details = {
        "status": "healthy",
        "version": "4.0.0",
        "service": "rozana-oms"
    }
    return JSONResponse(content=details)

@router.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0