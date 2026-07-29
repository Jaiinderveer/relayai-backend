from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.routes import chat, calls, analytics, contacts
from backend.services.automation import start_automation_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(" [RelayAI] Starting background services...")
    start_automation_engine()
    yield
    print(" [RelayAI] Shutting down...")

app = FastAPI(title="RelayAI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(chat.router)
app.include_router(calls.router)
app.include_router(analytics.router)
app.include_router(contacts.router)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "RelayAI Backend Active"}