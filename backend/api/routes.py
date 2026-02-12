"""
FastAPI-Routen für die Klasseneinteilung Web-App.

Endpunkte:
- POST /api/upload         → Excel-Datei hochladen
- POST /api/optimierung    → Einteilung starten
- GET  /api/pruefung       → Qualitätsprüfung abrufen
- GET  /api/export         → Excel-Export herunterladen
"""

import sys
import os
import tempfile
import json
from pathlib import Path
from dataclasses import asdict

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

import pandas as pd

# Submodul-Pfad einbinden
LIB_PATH = str(Path(__file__).resolve().parent.parent.parent / "lib" / "klasseneinteilung")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from algorithmus import erstelle_zufaellige_einteilung, optimiere_einteilung
from config import ANZAHL_KLASSEN, OPT_ITERATIONEN, OPT_START_TEMPERATUR, OPT_COOLING_RATE
from utils import berechne_gesamtstatistiken
from datenlader import lade_schuelerdaten

from backend.pruefungen.qualitaet import pruefe_einteilung, _get_class_name

router = APIRouter(prefix="/api")

# --- In-Memory State (für Prototyp) ---
_state = {
    "df": None,
    "einteilung": None,
    "pruefung": None,
    "upload_path": None,
}


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """Excel-Datei hochladen und Schülerdaten einlesen."""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Nur Excel-Dateien (.xlsx) werden akzeptiert.")

    # Temporär speichern
    upload_dir = Path(__file__).resolve().parent.parent / "uploads"
    upload_dir.mkdir(exist_ok=True)
    upload_path = upload_dir / file.filename

    content = await file.read()
    with open(upload_path, "wb") as f:
        f.write(content)

    # Daten einlesen
    df = lade_schuelerdaten(str(upload_path))
    if df is None:
        raise HTTPException(status_code=400, detail="Fehler beim Einlesen der Excel-Datei.")

    _state["df"] = df
    _state["upload_path"] = str(upload_path)
    _state["einteilung"] = None
    _state["pruefung"] = None

    # Spalten-Info zurückgeben
    wunsch_spalten = [c for c in df.columns if str(c).startswith("Wunsch_")]

    return {
        "status": "ok",
        "anzahl_schueler": len(df),
        "spalten": list(df.columns),
        "wunsch_spalten": len(wunsch_spalten),
        "hat_trennung": "Trennen_Von" in df.columns,
        "dateiname": file.filename,
    }


@router.post("/optimierung")
def starte_optimierung(
    anzahl_klassen: int = ANZAHL_KLASSEN,
    iterationen: int = OPT_ITERATIONEN,
    start_temp: float = OPT_START_TEMPERATUR,
    cooling_rate: float = OPT_COOLING_RATE,
):
    """Einteilung mit Simulated Annealing optimieren (sync, läuft im Threadpool)."""
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Bitte zuerst eine Excel-Datei hochladen.")

    df = _state["df"]
    gesamtstatistiken = berechne_gesamtstatistiken(df, anzahl_klassen)

    start_einteilung = erstelle_zufaellige_einteilung(df.index, anzahl_klassen)
    finale_einteilung, finaler_score = optimiere_einteilung(
        start_einteilung, df, gesamtstatistiken, anzahl_klassen,
        iterationen=iterationen,
        start_temp=start_temp,
        cooling_rate=cooling_rate,
    )

    _state["einteilung"] = finale_einteilung

    # Automatisch Prüfung durchführen
    pruefung = pruefe_einteilung(finale_einteilung, df)
    _state["pruefung"] = pruefung

    # Klassenlisten für die Antwort aufbauen
    klassen_daten = []
    for i, klasse_ids in enumerate(finale_einteilung):
        klassen_df = df.loc[klasse_ids]
        schueler_liste = []
        for sid, row in klassen_df.iterrows():
            schueler_liste.append({
                "id": int(sid),
                "vorname": str(row.get("Vorname", "")),
                "name": str(row.get("Name", "")),
                "geschlecht": str(row.get("Geschlecht", "")),
                "auffaelligkeit": float(pd.to_numeric(row.get("Auffaelligkeit_Score", 0), errors="coerce") or 0),
            })
        klassen_daten.append({
            "name": _get_class_name(i),
            "schueler": schueler_liste,
        })

    return {
        "status": "ok",
        "score": round(finaler_score, 2),
        "anzahl_klassen": anzahl_klassen,
        "klassen": klassen_daten,
        "pruefung": asdict(pruefung),
    }


@router.post("/verschieben")
def verschiebe_schueler(neue_einteilung: list[list[int]]):
    """
    Manuelle Verschiebung: Nimmt eine neue Einteilung entgegen,
    aktualisiert den State und gibt die neue Prüfung + Klassendaten zurück.
    """
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Daten geladen.")

    df = _state["df"]

    # Validierung: Alle Schüler-IDs müssen im DataFrame existieren
    alle_ids = set()
    for klasse in neue_einteilung:
        for sid in klasse:
            if sid not in df.index:
                raise HTTPException(status_code=400, detail=f"Schüler-ID {sid} nicht gefunden.")
            if sid in alle_ids:
                raise HTTPException(status_code=400, detail=f"Schüler-ID {sid} doppelt zugewiesen.")
            alle_ids.add(sid)

    if len(alle_ids) != len(df):
        raise HTTPException(
            status_code=400,
            detail=f"Anzahl Schüler stimmt nicht: {len(alle_ids)} vs. {len(df)} erwartet.",
        )

    # State aktualisieren
    _state["einteilung"] = neue_einteilung

    # Prüfung neu berechnen
    pruefung = pruefe_einteilung(neue_einteilung, df)
    _state["pruefung"] = pruefung

    # Klassenlisten aufbauen
    klassen_daten = []
    for i, klasse_ids in enumerate(neue_einteilung):
        klassen_df = df.loc[klasse_ids]
        schueler_liste = []
        for sid, row in klassen_df.iterrows():
            schueler_liste.append({
                "id": int(sid),
                "vorname": str(row.get("Vorname", "")),
                "name": str(row.get("Name", "")),
                "geschlecht": str(row.get("Geschlecht", "")),
                "auffaelligkeit": float(pd.to_numeric(row.get("Auffaelligkeit_Score", 0), errors="coerce") or 0),
            })
        klassen_daten.append({
            "name": _get_class_name(i),
            "schueler": schueler_liste,
        })

    return {
        "status": "ok",
        "klassen": klassen_daten,
        "pruefung": asdict(pruefung),
    }


@router.get("/pruefung")
def hole_pruefung():
    """Letzte Qualitätsprüfung abrufen."""
    if _state["pruefung"] is None:
        raise HTTPException(status_code=400, detail="Keine Einteilung vorhanden. Bitte zuerst Optimierung starten.")

    return asdict(_state["pruefung"])


@router.get("/export")
def exportiere_excel():
    """Ergebnis als Excel-Datei herunterladen."""
    if _state["einteilung"] is None or _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Einteilung vorhanden.")

    df = _state["df"]
    einteilung = _state["einteilung"]

    # Temporäre Datei erstellen
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()

    writer = pd.ExcelWriter(tmp_path, engine="openpyxl")

    # Übersicht
    alle = []
    for i, klasse_ids in enumerate(einteilung):
        tmp_df = df.loc[klasse_ids].copy()
        tmp_df["Klasse"] = _get_class_name(i)
        alle.append(tmp_df)
    gesamt_df = pd.concat(alle)
    gesamt_df.to_excel(writer, sheet_name="Einteilung")

    # Einzelne Klassen
    for i, klasse_ids in enumerate(einteilung):
        df.loc[klasse_ids].to_excel(writer, sheet_name=f"Klasse_{_get_class_name(i)}")

    # Prüfungsergebnis
    if _state["pruefung"]:
        pruef = _state["pruefung"]
        pruef_daten = []
        for kp in pruef.klassen:
            pruef_daten.append({
                "Klasse": kp.klasse_name,
                "Schüler": kp.anzahl_schueler,
                "Männlich": kp.maennlich,
                "Weiblich": kp.weiblich,
                "Geschlecht Δ": kp.geschlecht_differenz,
                "Geschlecht ✓": kp.geschlecht_ampel,
                "Auffälligkeit Σ": kp.auffaelligkeit_summe,
                "Auffälligkeit Ø": kp.auffaelligkeit_durchschnitt,
                "Auffälligkeit ✓": kp.auffaelligkeit_ampel,
                "Migration %": kp.migration_anteil_pct,
                "Migration Δ pp": kp.migration_abweichung_pp,
                "Migration ✓": kp.migration_ampel,
                "Wünsche erfüllt": kp.wuensche_erfuellt,
                "Wünsche offen": kp.wuensche_nicht_erfuellt,
                "Wunsch-Quote %": kp.wunsch_quote_pct,
                "Wünsche ✓": kp.wunsch_ampel,
                "Trennungen miss.": kp.trennungen_missachtet,
                "Trennungen ✓": kp.trennungen_ampel,
            })
        pd.DataFrame(pruef_daten).to_excel(writer, sheet_name="Pruefung", index=False)

    writer.close()

    return FileResponse(
        tmp_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Klasseneinteilung_Ergebnis.xlsx",
    )
