#!/bin/bash
# Startet Backend und öffnet Frontend im Browser
# Nutzung: ./run.sh

echo "🚀 Starte Klasseneinteilung Web-App..."
echo ""
echo "Backend:  http://localhost:8000"
echo "API-Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:8000 (oder frontend/index.html direkt öffnen)"
echo ""

cd "$(dirname "$0")"

# Backend starten (Frontend wird als statische Dateien mitgeliefert)
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
