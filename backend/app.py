"""
FastAPI Hauptanwendung – Klasseneinteilung Web-App.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.pfade import get_frontend_dir

app = FastAPI(
    title="Klasseneinteilung Web",
    description="Web-App zur automatisierten Klasseneinteilung mit Qualitätsprüfungen",
    version="1.0.0",
)

# CORS für lokale Frontend-Entwicklung
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-Routen
app.include_router(router)

# Frontend static files
frontend_dir = get_frontend_dir()
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
