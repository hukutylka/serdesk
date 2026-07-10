from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, auth, public, requests, stats

app = FastAPI(title="IT Helpdesk", version="1.0.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(admin.router)
app.include_router(stats.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def public_page():
    return FileResponse(static_dir / "index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(static_dir / "admin.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
