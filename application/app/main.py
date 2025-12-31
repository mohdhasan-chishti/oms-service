from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.connections.database import close_db_pool
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from firebase_admin import credentials
import firebase_admin

from app.logging.utils import initialize_logging, get_app_logger
from app.middlewares.logging_middleware import AuditMiddleware

load_dotenv()

# Initialize Sentry (must be done early, before other imports)
from app.config.sentry import init_sentry
init_sentry()

# Initialize OpenTelemetry (must be done early, before other imports)
# OpenTelemetry removed

# Initialize structured logging
initialize_logging()
logger = get_app_logger('app.main')

# Debug mode detection (DEBUG=false means production)
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

logger.info(f"Running in {'debug' if DEBUG else 'production'} mode")

cred_app = credentials.Certificate("app/auth/firebase_app.json")
firebase_admin.initialize_app(cred_app, name="app")

cred_pos = credentials.Certificate("app/auth/firebase_pos.json")
firebase_admin.initialize_app(cred_pos, name="pos")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Rozana OMS")
    yield
    logger.info("Shutting down Rozana OMS")
    # OpenTelemetry removed
    close_db_pool()

# Disable docs in production (when DEBUG=false)
docs_url = "/docs" if DEBUG else None
redoc_url = "/redoc" if DEBUG else None

app = FastAPI(
    title="Rozana OMS", 
    version="4.0.0", 
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url
)

# OpenTelemetry removed

allowed_origins = os.getenv("ALLOWED_ORIGINS")
if allowed_origins:
   origins = [origin.strip() for origin in allowed_origins.split(",")]
else:
   origins = ["*"]


# Request/Audit logging middleware (place early)
app.add_middleware(AuditMiddleware)

# Transaction Lock Middleware (must be before auth middlewares)
from app.middleware.transaction_lock import TransactionLockMiddleware
app.add_middleware(TransactionLockMiddleware)

# Middlewares
from app.middlewares.firebase_auth_app import FirebaseAuthMiddlewareAPP
from app.middlewares.firebase_auth_pos import FirebaseAuthMiddlewarePOS
from app.middlewares.api_token_validation import APITokenValidationMiddleware
from app.middlewares.customer_validation import CustomerValidationMiddleware
app.add_middleware(FirebaseAuthMiddlewareAPP)
app.add_middleware(FirebaseAuthMiddlewarePOS)
app.add_middleware(APITokenValidationMiddleware)
app.add_middleware(CustomerValidationMiddleware)


logger.info(f"Configuring CORS with allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom exception handlers
from app.middlewares.handlers import register_exception_handlers
register_exception_handlers(app)


# Routes
from app.routes.app import app_router
# from app.routes.web import web_router
from app.routes.pos import pos_router
from app.routes.pos.facility_terminals import facility_terminal_router
from app.routes.health import router as health_router
from app.routes.app.payments import payment_router
from app.routes.webhooks.razorpay_status import webhook_router
from app.routes.webhooks.razorpay_webhook import razorpay_webhook_router
from app.routes.webhooks.cashfree_webhook import cashfree_webhook_router
from app.routes.api import api_router
from app.routes.auth_otp import router as auth_otp_router

app.include_router(app_router, prefix="/app/v1")
app.include_router(payment_router, prefix="/app/v1")
app.include_router(pos_router, prefix="/pos/v1")
app.include_router(facility_terminal_router, prefix="/pos/v1")
app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_otp_router, prefix="/auth")
app.include_router(health_router, tags=["health"])
app.include_router(webhook_router, prefix="/webhooks/v1")
app.include_router(razorpay_webhook_router, prefix="/razorpay")
app.include_router(cashfree_webhook_router, prefix="/cashfree")
