from fastapi import FastAPI

from app.endpoints import auth_endpoints, jira_endpoints
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title="Alpha Agent Backend")


# --- Подключение роутеров ---
app.include_router(auth_endpoints.router, prefix="/auth", tags=["Auth"])
app.include_router(jira_endpoints.router, prefix="/jira", tags=["Jira"])


# --- Startup / Shutdown ---
@app.on_event("startup")
def on_startup():
    print("Starting application...")
    
    # fallback если миграции не применили
    Base.metadata.create_all(bind=engine)
    
    print("Database connected")


@app.on_event("shutdown")
def on_shutdown():
    print("Shutting down application...")

@app.get("/health")
def health():
    return {"status": "ok"}