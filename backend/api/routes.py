"""
FastAPI-Routen für die Klasseneinteilung Web-App.

Endpunkte:
- GET  /api/vorlage            → Vorlage herunterladen (.xlsx oder .ods)
- POST /api/upload              → Datei hochladen + Spalten analysieren
- POST /api/mapping-bestaetigen → Spalten-Mapping bestätigen, DataFrame aufbauen
- GET  /api/schueler            → Schülerliste abrufen (mit Wünschen/Trennungen)
- POST /api/wuensche-speichern  → Wünsche und Trennungen speichern
- POST /api/optimierung         → Einteilung starten
- POST /api/verschieben         → Manuelle Verschiebung
- GET  /api/pruefung            → Qualitätsprüfung abrufen
- GET  /api/export              → Excel-Export herunterladen
"""

import sys
import tempfile
from pathlib import Path
from dataclasses import asdict

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

import pandas as pd

# Submodul-Pfad einbinden
LIB_PATH = str(Path(__file__).resolve().parent.parent.parent / "lib" / "klasseneinteilung")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from algorithmus import erstelle_zufaellige_einteilung
from config import ANZAHL_KLASSEN, OPT_ITERATIONEN, OPT_START_TEMPERATUR, OPT_COOLING_RATE
from utils import berechne_gesamtstatistiken

from backend.optimierung_wrapper import optimiere_mit_sprengel
from backend.pruefungen.qualitaet import pruefe_einteilung, _get_class_name
from backend.vorlage import generiere_xlsx_vorlage, generiere_ods_vorlage
from backend.spaltenmapping import (
    finde_spalten_mapping,
    baue_dataframe,
    extrahiere_bestehende_wuensche,
    wuensche_einfuegen,
    validiere_dataframe,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# In-Memory State (für Prototyp)
# ---------------------------------------------------------------------------
_state = {
    "df": None,
    "einteilung": None,
    "pruefung": None,
    "upload_path": None,
    "raw_spalten": None,       # Roh-Spalten der hochgeladenen Datei
    "mapping_vorschlaege": None,  # Ergebnis von finde_spalten_mapping()
}


# ---------------------------------------------------------------------------
# Pydantic-Modelle für Request-Bodies
# ---------------------------------------------------------------------------

class MappingBestaetigung(BaseModel):
    """Vom Frontend bestätigtes Spalten-Mapping."""
    mapping: dict[str, str | None]  # {Ziel-Spalte: Original-Spalte oder None}


class WunschZuordnung(BaseModel):
    schueler_id: int
    wuensche: list[int] = []
    trennen_von: list[int] = []
    # Optionale Korrekturen an Stammdaten
    geschlecht: str | None = None
    auffaelligkeit: int | None = None
    migration: str | None = None


class WuenscheSpeichern(BaseModel):
    zuordnungen: list[WunschZuordnung]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _safe_int(wert, default=0) -> int:
    """Konvertiert einen Wert sicher zu int (NaN-safe)."""
    num = pd.to_numeric(wert, errors="coerce")
    if pd.isna(num):
        return default
    return int(num)


def _alle_trennungspaare(df: pd.DataFrame) -> set[frozenset[int]]:
    """
    Extrahiert ALLE Trennungspaare aus dem DataFrame (aus allen Trennen_Von_X Spalten).
    Gibt ein Set von frozensets zurück: {frozenset({a, b}), ...}
    """
    trenn_spalten = sorted([c for c in df.columns if str(c).startswith("Trennen_Von")])
    paare = set()
    for sid, row in df.iterrows():
        for ts in trenn_spalten:
            tv = _safe_int(row.get(ts, 0))
            if tv > 0 and tv in df.index and tv != sid:
                paare.add(frozenset({int(sid), int(tv)}))
    return paare


def _df_fuer_submodul(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bereitet den DataFrame für das Submodul auf.
    - Konsolidiert mehrere Trennen_Von_X Spalten → eine Trennen_Von Spalte
    - Macht Trennungen bidirektional (wenn A von B getrennt werden soll,
      wird auch B→A gesetzt), damit der Algorithmus besser optimiert.
    """
    df_kopie = df.copy()

    # Alle Trennungspaare sammeln
    paare = _alle_trennungspaare(df_kopie)

    # Bidirektionale Zuordnung: Jeder Schüler bekommt seinen ersten Trennungspartner
    trenn_map: dict[int, int] = {}
    for paar in paare:
        a, b = sorted(paar)
        if a not in trenn_map:
            trenn_map[a] = b
        if b not in trenn_map:
            trenn_map[b] = a

    # Alte Trennungsspalten entfernen, neue einzelne Spalte setzen
    alte_spalten = [c for c in df_kopie.columns if str(c).startswith("Trennen_Von")]
    df_kopie.drop(columns=alte_spalten, errors="ignore", inplace=True)
    df_kopie["Trennen_Von"] = 0
    for sid, partner in trenn_map.items():
        if sid in df_kopie.index:
            df_kopie.at[sid, "Trennen_Von"] = partner

    return df_kopie


def _erzwinge_trennungen(
    einteilung: list[list[int]],
    df: pd.DataFrame,
) -> tuple[list[list[int]], list[dict]]:
    """
    Erzwingt alle Trennungen als harte Regel.

    Prüft ob Trennungspaare in derselben Klasse sind und verschiebt
    Schüler solange, bis alle Trennungen eingehalten werden.

    Returns:
        (bereinigte_einteilung, log_der_verschiebungen)
    """
    paare = _alle_trennungspaare(df)
    if not paare:
        return einteilung, []

    # Einteilung als veränderbare Listen kopieren
    klassen = [list(k) for k in einteilung]
    log = []

    # Klassen-Zuordnung: Schüler-ID → Klassen-Index
    def baue_zuordnung():
        z = {}
        for ki, klasse in enumerate(klassen):
            for sid in klasse:
                z[sid] = ki
        return z

    max_durchlaeufe = 100  # Sicherheit gegen Endlosschleifen

    for durchlauf in range(max_durchlaeufe):
        zuordnung = baue_zuordnung()
        verletzt = []

        for paar in paare:
            ids = sorted(paar)
            a, b = ids[0], ids[1]
            if a in zuordnung and b in zuordnung:
                if zuordnung[a] == zuordnung[b]:
                    verletzt.append((a, b))

        if not verletzt:
            break  # Alle Trennungen eingehalten ✓

        # Pro Durchlauf ein Paar auflösen
        a, b = verletzt[0]
        klasse_idx = zuordnung[a]

        # Entscheide welchen Schüler wir verschieben:
        # → Den, der weniger andere Trennungspartner in der Zielklasse hätte
        # → Verschiebe in die Klasse mit der geringsten Schülerzahl
        beste_zielklasse = None
        bester_schueler = None
        bester_score = float("inf")

        for schueler in (a, b):
            for zi in range(len(klassen)):
                if zi == klasse_idx:
                    continue

                # Prüfe ob die Verschiebung neue Trennungsverletzungen erzeugt
                neue_verletzungen = 0
                for paar2 in paare:
                    if schueler in paar2:
                        partner = (paar2 - {schueler}).pop()
                        if partner in set(klassen[zi]):
                            neue_verletzungen += 1

                if neue_verletzungen > 0:
                    continue  # Diese Zielklasse würde neue Konflikte erzeugen

                # Score: bevorzuge kleinere Klassen
                score = len(klassen[zi])
                if score < bester_score:
                    bester_score = score
                    beste_zielklasse = zi
                    bester_schueler = schueler

        if beste_zielklasse is None:
            # Fallback: Verschiebe in kleinste Klasse ohne neue Konflikte zu prüfen
            # (sollte selten vorkommen)
            kleinste = min(
                (i for i in range(len(klassen)) if i != klasse_idx),
                key=lambda i: len(klassen[i]),
            )
            bester_schueler = b  # Zweiten Schüler verschieben
            beste_zielklasse = kleinste

        # Verschiebung durchführen
        klassen[klasse_idx].remove(bester_schueler)
        klassen[beste_zielklasse].append(bester_schueler)

        name = ""
        if bester_schueler in df.index:
            row = df.loc[bester_schueler]
            name = f"{row.get('Vorname', '')} {row.get('Name', '')}".strip()

        log.append({
            "schueler_id": bester_schueler,
            "name": name,
            "von_klasse": klasse_idx + 1,
            "nach_klasse": beste_zielklasse + 1,
            "grund": f"Trennung von Schüler {a if bester_schueler == b else b}",
        })

    return klassen, log


def _schueler_liste_aus_df(df: pd.DataFrame) -> list[dict]:
    """Baut die Schülerliste für die API-Antwort (inkl. Wünsche/Trennungen)."""
    wunsch_spalten = sorted([c for c in df.columns if str(c).startswith("Wunsch_")])
    trenn_spalten = sorted([c for c in df.columns if str(c).startswith("Trennen_Von")])

    schueler = []
    for sid, row in df.iterrows():
        # Wünsche extrahieren
        wuensche = []
        for ws in wunsch_spalten:
            wert = _safe_int(row.get(ws, 0))
            if wert > 0 and wert in df.index and wert != sid:
                wuensche.append(wert)

        # Trennungen extrahieren
        trennen_von = []
        for ts in trenn_spalten:
            tv = _safe_int(row.get(ts, 0))
            if tv > 0 and tv in df.index and tv != sid:
                trennen_von.append(tv)

        auff_raw = pd.to_numeric(row.get("Auffaelligkeit_Score", 0), errors="coerce")
        auff = 0.0 if pd.isna(auff_raw) else float(auff_raw)

        sprengel_wert = row.get("Sprengel", "")
        sprengel = str(sprengel_wert).strip() if pd.notna(sprengel_wert) else ""

        schueler.append({
            "id": int(sid),
            "vorname": str(row.get("Vorname", "")),
            "name": str(row.get("Name", "")),
            "geschlecht": str(row.get("Geschlecht", "")),
            "auffaelligkeit": auff,
            "migration": str(row.get("Migrationshintergrund / 2. Staatsangehörigkeit", "")),
            "sprengel": sprengel,
            "wuensche": wuensche,
            "trennen_von": trennen_von,
        })
    return schueler


def _klassen_daten_aus_einteilung(df: pd.DataFrame, einteilung: list) -> list[dict]:
    """Baut die Klassenlisten für die API-Antwort."""
    klassen_daten = []
    for i, klasse_ids in enumerate(einteilung):
        klassen_df = df.loc[klasse_ids]
        schueler_liste = []
        for sid, row in klassen_df.iterrows():
            auff_raw = pd.to_numeric(row.get("Auffaelligkeit_Score", 0), errors="coerce")
            sprengel_wert = row.get("Sprengel", "")
            schueler_liste.append({
                "id": int(sid),
                "vorname": str(row.get("Vorname", "")),
                "name": str(row.get("Name", "")),
                "geschlecht": str(row.get("Geschlecht", "")),
                "auffaelligkeit": 0.0 if pd.isna(auff_raw) else float(auff_raw),
                "sprengel": str(sprengel_wert).strip() if pd.notna(sprengel_wert) else "",
            })
        klassen_daten.append({
            "name": _get_class_name(i),
            "schueler": schueler_liste,
        })
    return klassen_daten


# ===================================================================
# Endpunkte
# ===================================================================


# ---------------------------------------------------------------------------
# Vorlage herunterladen
# ---------------------------------------------------------------------------

@router.get("/vorlage")
def vorlage_herunterladen(format: str = Query("xlsx", pattern="^(xlsx|ods)$")):
    """Vorlage als .xlsx oder .ods herunterladen."""
    if format == "ods":
        pfad = generiere_ods_vorlage()
        return FileResponse(
            pfad,
            media_type="application/vnd.oasis.opendocument.spreadsheet",
            filename="Schuelerdaten_Vorlage.ods",
        )
    else:
        pfad = generiere_xlsx_vorlage()
        return FileResponse(
            pfad,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="Schuelerdaten_Vorlage.xlsx",
        )


# ---------------------------------------------------------------------------
# Upload + Spalten-Analyse
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_datei(file: UploadFile = File(...)):
    """
    Datei hochladen und Spalten analysieren.

    Akzeptiert .xlsx, .xls und .ods.
    Gibt Mapping-Vorschläge zurück. Wenn alle Pflichtspalten sicher
    erkannt wurden, wird der DataFrame direkt aufgebaut und die
    Schülerliste mitgeliefert.
    """
    erlaubte_endungen = (".xlsx", ".xls", ".ods")
    if not file.filename.endswith(erlaubte_endungen):
        raise HTTPException(
            status_code=400,
            detail=f"Nur {', '.join(erlaubte_endungen)} Dateien werden akzeptiert.",
        )

    # Temporär speichern
    upload_dir = Path(__file__).resolve().parent.parent / "uploads"
    upload_dir.mkdir(exist_ok=True)
    upload_path = upload_dir / file.filename

    content = await file.read()
    with open(upload_path, "wb") as f:
        f.write(content)

    # Roh-Spalten einlesen
    try:
        if str(upload_path).endswith(".ods"):
            raw_df = pd.read_excel(str(upload_path), engine="odf")
        else:
            raw_df = pd.read_excel(str(upload_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Einlesen der Datei: {e}")

    gefundene_spalten = list(raw_df.columns.astype(str))
    mapping_ergebnis = finde_spalten_mapping(gefundene_spalten)

    _state["upload_path"] = str(upload_path)
    _state["raw_spalten"] = gefundene_spalten
    _state["mapping_vorschlaege"] = mapping_ergebnis
    _state["einteilung"] = None
    _state["pruefung"] = None

    antwort = {
        "status": "ok",
        "dateiname": file.filename,
        "anzahl_zeilen": len(raw_df),
        "braucht_mapping": not mapping_ergebnis["alle_pflicht_sicher"],
        "mapping": mapping_ergebnis["mapping"],
        "alle_spalten": mapping_ergebnis["alle_spalten"],
        "nicht_zugeordnet": mapping_ergebnis["nicht_zugeordnet"],
    }

    # Wenn alle Pflichtspalten sicher erkannt: DataFrame direkt aufbauen
    if mapping_ergebnis["alle_pflicht_sicher"]:
        finales_mapping = {
            k: v["spalte"]
            for k, v in mapping_ergebnis["mapping"].items()
            if v["spalte"] is not None
        }
        try:
            df = baue_dataframe(str(upload_path), finales_mapping)
            _state["df"] = df
            antwort["schueler"] = _schueler_liste_aus_df(df)
            antwort["anzahl_schueler"] = len(df)
            antwort["validierung"] = validiere_dataframe(df)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Fehler beim Aufbau der Daten: {e}")

    return antwort


# ---------------------------------------------------------------------------
# Spalten-Mapping bestätigen
# ---------------------------------------------------------------------------

@router.post("/mapping-bestaetigen")
def mapping_bestaetigen(body: MappingBestaetigung):
    """
    Vom Benutzer bestätigtes Spalten-Mapping übernehmen.
    Baut den DataFrame auf und gibt die Schülerliste zurück.
    """
    if _state["upload_path"] is None:
        raise HTTPException(status_code=400, detail="Bitte zuerst eine Datei hochladen.")

    # Mapping validieren: Alle Pflichtspalten müssen zugeordnet sein
    from backend.spaltenmapping import ERWARTETE_SPALTEN
    for spalte in ERWARTETE_SPALTEN:
        if body.mapping.get(spalte) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Pflichtspalte '{spalte}' ist nicht zugeordnet.",
            )

    try:
        df = baue_dataframe(_state["upload_path"], body.mapping)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Aufbau der Daten: {e}")

    _state["df"] = df
    _state["einteilung"] = None
    _state["pruefung"] = None

    return {
        "status": "ok",
        "anzahl_schueler": len(df),
        "schueler": _schueler_liste_aus_df(df),
        "validierung": validiere_dataframe(df),
    }


# ---------------------------------------------------------------------------
# Schülerliste abrufen
# ---------------------------------------------------------------------------

@router.get("/schueler")
def hole_schueler():
    """Aktuelle Schülerliste abrufen (mit Wünschen/Trennungen)."""
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Daten geladen.")

    return {
        "status": "ok",
        "schueler": _schueler_liste_aus_df(_state["df"]),
        "anzahl_schueler": len(_state["df"]),
    }


# ---------------------------------------------------------------------------
# Wünsche und Trennungen speichern
# ---------------------------------------------------------------------------

@router.post("/wuensche-speichern")
def wuensche_speichern(body: WuenscheSpeichern):
    """
    Wunsch-/Trennungszuordnungen und Stammdaten-Korrekturen aus der UI übernehmen.
    Aktualisiert den DataFrame und re-validiert.
    """
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Daten geladen.")

    df = _state["df"]

    # 1. Stammdaten-Korrekturen übernehmen
    for z in body.zuordnungen:
        sid = z.schueler_id
        if sid not in df.index:
            continue
        if z.geschlecht is not None:
            df.at[sid, "Geschlecht"] = z.geschlecht.lower().strip()
        if z.auffaelligkeit is not None:
            df.at[sid, "Auffaelligkeit_Score"] = z.auffaelligkeit
        if z.migration is not None:
            mig_spalte = "Migrationshintergrund / 2. Staatsangehörigkeit"
            if mig_spalte in df.columns:
                df.at[sid, mig_spalte] = z.migration

    # 2. Wünsche/Trennungen einfügen
    zuordnungen = [z.model_dump() for z in body.zuordnungen]
    df = wuensche_einfuegen(df, zuordnungen)
    _state["df"] = df

    # 3. Re-Validierung
    hinweise = validiere_dataframe(df)

    # Wunsch-Info
    wunsch_spalten = [c for c in df.columns if str(c).startswith("Wunsch_")]
    anzahl_mit_wunsch = sum(
        1 for _, row in df.iterrows()
        if any(_safe_int(row.get(ws, 0)) > 0 for ws in wunsch_spalten)
    )

    return {
        "status": "ok",
        "anzahl_schueler": len(df),
        "wunsch_spalten": len(wunsch_spalten),
        "schueler_mit_wuenschen": anzahl_mit_wunsch,
        "hat_trennung": any(c.startswith("Trennen_Von") for c in df.columns),
        "validierung": hinweise,
    }


# ---------------------------------------------------------------------------
# Optimierung starten
# ---------------------------------------------------------------------------

@router.post("/optimierung")
def starte_optimierung(
    anzahl_klassen: int = ANZAHL_KLASSEN,
    iterationen: int = OPT_ITERATIONEN,
    start_temp: float = OPT_START_TEMPERATUR,
    cooling_rate: float = OPT_COOLING_RATE,
):
    """Einteilung mit Simulated Annealing optimieren (sync, läuft im Threadpool)."""
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Bitte zuerst eine Datei hochladen.")

    df = _state["df"]
    # Submodul erwartet eine einzelne Trennen_Von-Spalte
    df_algo = _df_fuer_submodul(df)

    gesamtstatistiken = berechne_gesamtstatistiken(df_algo, anzahl_klassen)

    start_einteilung = erstelle_zufaellige_einteilung(df_algo.index, anzahl_klassen)
    finale_einteilung, finaler_score = optimiere_mit_sprengel(
        start_einteilung, df_algo, gesamtstatistiken, anzahl_klassen,
        iterationen=iterationen,
        start_temp=start_temp,
        cooling_rate=cooling_rate,
    )

    # Harte Regel: ALLE Trennungen erzwingen (Post-Processing)
    finale_einteilung, trenn_log = _erzwinge_trennungen(finale_einteilung, df)

    _state["einteilung"] = finale_einteilung

    # Prüfung mit Original-df (alle Trennungsspalten)
    pruefung = pruefe_einteilung(finale_einteilung, df)
    _state["pruefung"] = pruefung

    antwort = {
        "status": "ok",
        "score": round(finaler_score, 2),
        "anzahl_klassen": anzahl_klassen,
        "klassen": _klassen_daten_aus_einteilung(df, finale_einteilung),
        "pruefung": asdict(pruefung),
    }

    if trenn_log:
        antwort["trennungen_erzwungen"] = trenn_log

    return antwort


# ---------------------------------------------------------------------------
# Manuelle Verschiebung
# ---------------------------------------------------------------------------

@router.post("/verschieben")
def verschiebe_schueler(neue_einteilung: list[list[int]]):
    """
    Manuelle Verschiebung: Nimmt eine neue Einteilung entgegen,
    aktualisiert den State und gibt die neue Prüfung + Klassendaten zurück.
    """
    if _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Daten geladen.")

    df = _state["df"]

    # Validierung
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

    # Prüfe ob Trennungen verletzt werden
    paare = _alle_trennungspaare(df)
    verletzungen = []
    zuordnung = {}
    for ki, klasse in enumerate(neue_einteilung):
        for sid in klasse:
            zuordnung[sid] = ki

    for paar in paare:
        ids = sorted(paar)
        a, b = ids[0], ids[1]
        if a in zuordnung and b in zuordnung and zuordnung[a] == zuordnung[b]:
            name_a = f"{df.at[a, 'Vorname']} {df.at[a, 'Name']}".strip() if a in df.index else str(a)
            name_b = f"{df.at[b, 'Vorname']} {df.at[b, 'Name']}".strip() if b in df.index else str(b)
            verletzungen.append({
                "schueler_a": {"id": a, "name": name_a},
                "schueler_b": {"id": b, "name": name_b},
                "klasse": zuordnung[a] + 1,
            })

    _state["einteilung"] = neue_einteilung

    pruefung = pruefe_einteilung(neue_einteilung, df)
    _state["pruefung"] = pruefung

    antwort = {
        "status": "ok",
        "klassen": _klassen_daten_aus_einteilung(df, neue_einteilung),
        "pruefung": asdict(pruefung),
    }

    if verletzungen:
        antwort["trennungen_verletzt"] = verletzungen

    return antwort


# ---------------------------------------------------------------------------
# Qualitätsprüfung abrufen
# ---------------------------------------------------------------------------

@router.get("/pruefung")
def hole_pruefung():
    """Letzte Qualitätsprüfung abrufen."""
    if _state["pruefung"] is None:
        raise HTTPException(
            status_code=400,
            detail="Keine Einteilung vorhanden. Bitte zuerst Optimierung starten.",
        )
    return asdict(_state["pruefung"])


# ---------------------------------------------------------------------------
# Excel-Export
# ---------------------------------------------------------------------------

@router.get("/export")
def exportiere_excel():
    """Ergebnis als Excel-Datei herunterladen."""
    if _state["einteilung"] is None or _state["df"] is None:
        raise HTTPException(status_code=400, detail="Keine Einteilung vorhanden.")

    df = _state["df"]
    einteilung = _state["einteilung"]

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
                "Geschlecht": kp.geschlecht_ampel,
                "Auffälligkeit Σ": kp.auffaelligkeit_summe,
                "Auffälligkeit Ø": kp.auffaelligkeit_durchschnitt,
                "Auffälligkeit": kp.auffaelligkeit_ampel,
                "Migration %": kp.migration_anteil_pct,
                "Migration Δ pp": kp.migration_abweichung_pp,
                "Migration": kp.migration_ampel,
                "Wünsche erfüllt": kp.wuensche_erfuellt,
                "Wünsche offen": kp.wuensche_nicht_erfuellt,
                "Wunsch-Quote %": kp.wunsch_quote_pct,
                "Wünsche": kp.wunsch_ampel,
                "Trennungen miss.": kp.trennungen_missachtet,
                "Trennungen": kp.trennungen_ampel,
                "Ohne Laufpartner": kp.ohne_laufpartner,
                "Laufpartner": kp.laufpartner_ampel,
            })
        pd.DataFrame(pruef_daten).to_excel(writer, sheet_name="Pruefung", index=False)

    writer.close()

    return FileResponse(
        tmp_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Klasseneinteilung_Ergebnis.xlsx",
    )
