import logging
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.endpoints import auth_endpoints, jira_endpoints, github_endpoints, github_auth_endpoints
from app.db.base import Base
from app.db.session import engine
from app.endpoints import health
from app.endpoints import worker_test
from app.endpoints import dashboard_endpoints
from app.endpoints import confluence_endpoints
from app.endpoints import job_status
from app.endpoints import metrics_endpoints
from app.endpoints import chat_endpoints
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task
from starlette.middleware.base import BaseHTTPMiddleware  
from starlette.requests import Request  
from app.tasks.refresh_tokens import refresh_expiring_tokens
from app.tasks.jira_scheduler import schedule_jira_sync
# Настройка логгирования
logging.basicConfig(level=logging.INFO)
import asyncio

# --- Подключение роутеров ---
import logging
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware  
from starlette.requests import Request
from starlette.responses import Response

# ... остальные импорты

logger = logging.getLogger(__name__)

app = FastAPI(title="Alpha Agent Backend")
scheduler = BackgroundScheduler()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Alpha Agent API",
        version="1.0.0",
        description="API для Alpha Agent",
        routes=app.routes,
    )
    
    # Добавляем поддержку аутентификации через заголовок
    openapi_schema["components"]["securitySchemes"] = {
        "SessionToken": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Session-Token",
            "description": "Вставьте session_token из URL или cookie"
        },
        "CookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "session_token",
            "description": "Или используйте cookie"
        }
    }
    
    # Применяем ко всем эндпоинтам
    openapi_schema["security"] = [{"SessionToken": []}, {"CookieAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- ПРИНУДИТЕЛЬНЫЙ CORS MIDDLEWARE (ДОЛЖЕН БЫТЬ ПЕРВЫМ) ---
class ForceCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Обрабатываем preflight (OPTIONS) запросы
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, X-Session-Token"
            return response
        
        response = await call_next(request)
        
        # Добавляем CORS заголовки к ответу
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, X-Session-Token"
        
        return response

# Добавляем принудительный CORS middleware ПЕРВЫМ
@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "Backend is alive!"}
app.add_middleware(ForceCorsMiddleware)

# --- Подключение роутеров ---
app.include_router(auth_endpoints.router, prefix="/auth", tags=["Auth"])
app.include_router(jira_endpoints.router, prefix="/jira", tags=["Jira"])
app.include_router(worker_test.router, prefix="/worker", tags=["Worker"])
app.include_router(dashboard_endpoints.router, tags=["Dashboard"])
app.include_router(confluence_endpoints.router, prefix="/confluence", tags=["Confluence"])
app.include_router(job_status.router, tags=["Job Status"])
app.include_router(metrics_endpoints.router, prefix="/metrics", tags=["Metrics"])
app.include_router(chat_endpoints.router, tags=["Chat"])

# GitHub роутеры
app.include_router(github_endpoints.router, tags=["GitHub"])
app.include_router(github_auth_endpoints.router, prefix="/github", tags=["GitHub"])

# --- Стандартный CORS middleware (как запасной) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Логирующий middleware ---
class CORSLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"📥 {request.method} {request.url}")
        logger.info(f"   Origin: {request.headers.get('origin')}")
        logger.info(f"   X-Session-Token: {request.headers.get('x-session-token')}")
        logger.info(f"   All headers: {dict(request.headers)}")  # 👈 Добавь это
        
        response = await call_next(request)
        logger.info(f"📤 Response: {response.status_code}")
        return response

app.add_middleware(CORSLoggingMiddleware)

# ... остальной код (startup, shutdown, health, scheduled_jira_sync)
@app.on_event("startup")
async def startup_event():

    asyncio.create_task(refresh_expiring_tokens())

    asyncio.create_task(schedule_jira_sync())