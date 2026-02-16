# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec-Datei für Klasseneinteilung Desktop-App.

Build:  pyinstaller klasseneinteilung.spec --clean --noconfirm
Output: dist/Klasseneinteilung/
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Frontend (HTML/CSS/JS)
        ("frontend", "frontend"),
        # Submodul (Algorithmus-Code, wird per sys.path importiert)
        ("lib/klasseneinteilung", "lib/klasseneinteilung"),
    ],
    hiddenimports=[
        # Backend-Module
        "backend",
        "backend.app",
        "backend.api",
        "backend.api.routes",
        "backend.pfade",
        "backend.pruefungen",
        "backend.pruefungen.qualitaet",
        "backend.optimierung_wrapper",
        "backend.spaltenmapping",
        "backend.vorlage",
        # Uvicorn-Interna
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # FastAPI / Starlette
        "fastapi",
        "starlette",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        # Datenverarbeitung
        "pandas",
        "numpy",
        "openpyxl",
        "odf",
        "odf.opendocument",
        "odf.table",
        "odf.text",
        "odf.style",
        "odf.office",
        "multipart",
        # Multipart (für File-Upload)
        "multipart.multipart",
        # Encoding
        "encodings",
        "encodings.idna",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "scipy",
        "pytest",
        "webview",
        "gi",
        "cairo",
        "PyGObject",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Klasseneinteilung",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Kein Konsolenfenster auf Windows
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Klasseneinteilung",
)
