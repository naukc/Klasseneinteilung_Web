"""
Zentrale Pfad-Auflösung für Entwicklung und gepackte App (PyInstaller).

Im Entwicklungsmodus werden Pfade relativ zum Projekt-Root aufgelöst.
Im gepackten Modus (frozen) liegen gebündelte Dateien in sys._MEIPASS,
veränderbare Daten (Uploads) neben der ausführbaren Datei.
"""

import sys
from pathlib import Path


def ist_gepackt() -> bool:
    """True wenn die App als PyInstaller-Bundle läuft."""
    return getattr(sys, "frozen", False)


def get_base_path() -> Path:
    """
    Basis-Pfad für gebündelte/read-only Dateien (Frontend, Submodul).

    - Entwicklung: Projekt-Root
    - Gepackt: sys._MEIPASS (temporäres Entpackverzeichnis)
    """
    if ist_gepackt():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


import tempfile

def get_data_path() -> Path:
    """
    Pfad für veränderbare Daten (Uploads, temporäre Dateien).

    - Entwicklung: Projekt-Root / backend
    - Gepackt: Temporäres Verzeichnis (OS-spezifisch)
    """
    if ist_gepackt():
        return Path(tempfile.gettempdir()) / "KlasseneinteilungApp"
    return Path(__file__).resolve().parent


def get_frontend_dir() -> Path:
    """Pfad zum Frontend-Verzeichnis."""
    return get_base_path() / "frontend"


def get_lib_path() -> Path:
    """Pfad zum Submodul (lib/klasseneinteilung)."""
    return get_base_path() / "lib" / "klasseneinteilung"


def get_upload_dir() -> Path:
    """Pfad zum Upload-Verzeichnis (schreibbar)."""
    upload_dir = get_data_path() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir
