# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import notifications
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.services.notifier import run_notifications
from app.core.config import settings
scheduler = AsyncIOScheduler()

async def scheduled_notification_job():
    db = SessionLocal()
    try:
        result = await run_notifications(db)
        print(f"[Scheduler] Notifications done: {result}")
    finally:
        db.close()
        
@asynccontextmanager
async def lifespan(app):
    scheduler.add_job(scheduled_notification_job,
                        trigger="cron",
                        hour=8,
                        minute=0,
                        id="daily_notifications")
    scheduler.start()
    print("[SCheduler] Started - daily notifications at 08:00")
    yield
    
    scheduler.shutdown()

app = FastAPI(
    title="Research Assistant API",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(notifications.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "Research Assistant API"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# thêm 2 dòng này vào main.py
from app.database import engine
from app import models

models.Base.metadata.create_all(bind=engine)

# thêm vào main.py
from app.routers import papers
app.include_router(papers.router)

# thêm vào main.py (cạnh dòng include papers router)
from app.routers import search
app.include_router(search.router)

# thêm vào main.py
from app.routers import ai
app.include_router(ai.router)