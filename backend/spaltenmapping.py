"""
Intelligentes Spalten-Mapping für den flexiblen Excel-/ODS-Import.

Erkennt Spalten automatisch anhand von:
1. Exaktem Match (case-insensitive)
2. Alias-Tabelle (häufige Varianten)
3. Substring-Match (Teilstring-Erkennung)

Baut anschließend den DataFrame im Zielformat auf (kompatibel mit dem Submodul).
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Erwartete Pflichtspalten mit Alias-Varianten
# ---------------------------------------------------------------------------
ERWARTETE_SPALTEN: dict[str, dict] = {
    "Vorname": {
        "aliasse": [
            "vorname", "first name", "firstname", "vname", "given name",
            "rufname",
        ],
        "pflicht": True,
    },
    "Name": {
        "aliasse": [
            "name", "nachname", "familienname", "last name", "lastname",
            "surname", "family name", "lname", "familename",
        ],
        "pflicht": True,
    },
    "Geschlecht": {
        "aliasse": [
            "geschlecht", "gender", "sex", "m/w", "m/f", "geschl",
        ],
        "pflicht": True,
    },
    "Auffaelligkeit_Score": {
        "aliasse": [
            "auffaelligkeit_score", "auffälligkeit_score",
            "auffaelligkeit", "auffälligkeit", "score",
            "auffälligkeitsscore", "auffaelligkeitsscore",
            "besonderheiten", "auffällig", "auffaellig",
            "foerderbedarf", "förderbedarf", "auffaelligkeit score",
            "auffälligkeit score",
        ],
        "pflicht": True,
    },
    "Migrationshintergrund / 2. Staatsangehörigkeit": {
        "aliasse": [
            "migrationshintergrund / 2. staatsangehörigkeit",
            "migrationshintergrund / 2. staatsangehoerigkeit",
            "migrationshintergrund", "migration",
            "staatsangehörigkeit", "staatsangehoerigkeit",
            "2. staatsangehörigkeit", "herkunft",
            "migrationshintergrund / staatsangehörigkeit",
        ],
        "pflicht": True,
    },
}

# Optionale Spalten (für Rückwärtskompatibilität mit altem Excel-Format)
OPTIONALE_SPALTEN: dict[str, dict] = {
    "Wunsch_1": {
        "aliasse": ["wunsch_1", "wunsch 1", "wunschpartner_1", "wunschpartner 1", "1. wunsch"],
    },
    "Wunsch_2": {
        "aliasse": ["wunsch_2", "wunsch 2", "wunschpartner_2", "wunschpartner 2", "2. wunsch"],
    },
    "Wunsch_3": {
        "aliasse": ["wunsch_3", "wunsch 3", "wunschpartner_3", "wunschpartner 3", "3. wunsch"],
    },
    "Wunsch_4": {
        "aliasse": ["wunsch_4", "wunsch 4", "wunschpartner_4", "wunschpartner 4", "4. wunsch"],
    },
    "Trennen_Von": {
        "aliasse": [
            "trennen_von", "trennen von", "trennung",
            "nicht zusammen", "getrennt von", "trennungswunsch",
            "trennen_von_1", "trennung_1",
        ],
    },
    "Trennen_Von_2": {
        "aliasse": ["trennen_von_2", "trennung_2", "2. trennung"],
    },
    "Trennen_Von_3": {
        "aliasse": ["trennen_von_3", "trennung_3", "3. trennung"],
    },
    "Trennen_Von_4": {
        "aliasse": ["trennen_von_4", "trennung_4", "4. trennung"],
    },
    "Schüler-ID": {
        "aliasse": [
            "schüler-id", "schueler-id", "schülerid", "schuelerid",
            "id", "nr", "nummer", "schülernummer", "schuelernummer",
        ],
    },
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _normalisiere(text: str) -> str:
    """Normalisiert einen String für den Vergleich (lowercase, trim, Umlaute)."""
    s = str(text).lower().strip()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return s


def _finde_beste_uebereinstimmung(
    ziel_name: str,
    aliasse: list[str],
    norm_gefunden: dict[str, str],
    bereits_zugeordnet: set[str],
) -> tuple[str, str] | None:
    """
    Findet die beste Übereinstimmung für eine Ziel-Spalte.

    Returns: (original_spaltenname, confidence) oder None.
    confidence ist "sicher" oder "vorschlag".
    """
    ziel_norm = _normalisiere(ziel_name)

    # 1. Exakter Match
    if ziel_norm in norm_gefunden and ziel_norm not in bereits_zugeordnet:
        return (norm_gefunden[ziel_norm], "sicher")

    # 2. Alias-Match
    for alias in aliasse:
        alias_norm = _normalisiere(alias)
        if alias_norm in norm_gefunden and alias_norm not in bereits_zugeordnet:
            return (norm_gefunden[alias_norm], "sicher")

    # 3. Substring-Match
    for norm_s, original_s in norm_gefunden.items():
        if norm_s in bereits_zugeordnet:
            continue
        if len(ziel_norm) >= 3 and (ziel_norm in norm_s or norm_s in ziel_norm):
            return (original_s, "vorschlag")
        for alias in aliasse:
            alias_norm = _normalisiere(alias)
            if len(alias_norm) >= 3 and (alias_norm in norm_s or norm_s in alias_norm):
                return (original_s, "vorschlag")

    return None


# ---------------------------------------------------------------------------
# Hauptfunktionen
# ---------------------------------------------------------------------------

def finde_spalten_mapping(gefundene_spalten: list[str]) -> dict:
    """
    Analysiert die gefundenen Spalten und gibt Mapping-Vorschläge zurück.

    Returns:
        {
            "mapping": {
                "Vorname": {"spalte": "First Name", "confidence": "sicher"},
                "Name":    {"spalte": null, "confidence": "nicht_gefunden"},
                ...
            },
            "alle_spalten": ["First Name", "Last Name", ...],
            "nicht_zugeordnet": ["Extra-Spalte", ...],
            "alle_pflicht_sicher": true/false,
        }
    """
    norm_gefunden = {_normalisiere(s): s for s in gefundene_spalten}
    zugeordnet: set[str] = set()
    mapping: dict[str, dict] = {}

    alle_spalten_def = {**ERWARTETE_SPALTEN, **OPTIONALE_SPALTEN}

    for ziel_name, config in alle_spalten_def.items():
        treffer = _finde_beste_uebereinstimmung(
            ziel_name, config.get("aliasse", []), norm_gefunden, zugeordnet,
        )
        if treffer:
            original_name, confidence = treffer
            mapping[ziel_name] = {"spalte": original_name, "confidence": confidence}
            zugeordnet.add(_normalisiere(original_name))
        else:
            # Nur Pflichtspalten als "nicht_gefunden" aufnehmen
            if ziel_name in ERWARTETE_SPALTEN:
                mapping[ziel_name] = {"spalte": None, "confidence": "nicht_gefunden"}

    # Alle Pflichtspalten sicher erkannt?
    alle_pflicht_sicher = all(
        mapping.get(name, {}).get("confidence") == "sicher"
        for name in ERWARTETE_SPALTEN
    )

    nicht_zugeordnet = [s for s in gefundene_spalten if _normalisiere(s) not in zugeordnet]

    return {
        "mapping": mapping,
        "alle_spalten": gefundene_spalten,
        "nicht_zugeordnet": nicht_zugeordnet,
        "alle_pflicht_sicher": alle_pflicht_sicher,
    }


def baue_dataframe(upload_path: str, mapping: dict[str, str]) -> pd.DataFrame:
    """
    Liest die hochgeladene Datei und baut den DataFrame mit korrekten
    Spaltennamen auf (kompatibel mit dem Submodul-Format).

    Args:
        upload_path: Pfad zur hochgeladenen Datei (.xlsx, .xls oder .ods)
        mapping: Dict von {Ziel-Spaltenname: Original-Spaltenname-in-Datei}
                 Werte können None sein (Spalte nicht vorhanden).
    """
    # Datei einlesen
    if upload_path.endswith(".ods"):
        df = pd.read_excel(upload_path, engine="odf")
    else:
        df = pd.read_excel(upload_path)

    # Spalten umbenennen gemäß Mapping (nur gültige Mappings)
    rename_map = {v: k for k, v in mapping.items() if v is not None}
    df = df.rename(columns=rename_map)

    # Leere Zeilen entfernen
    if "Name" in df.columns:
        df.dropna(subset=["Name"], inplace=True)

    # Schüler-ID als Index setzen
    if "Schüler-ID" in df.columns:
        # NaN-Werte in Schüler-ID entfernen und zu int konvertieren
        df = df.dropna(subset=["Schüler-ID"])
        df["Schüler-ID"] = df["Schüler-ID"].astype(int)
        df = df.set_index("Schüler-ID")
    else:
        # Auto-IDs generieren (1-basiert)
        df.index = range(1, len(df) + 1)
        df.index.name = "Schüler-ID"

    # Geschlecht normalisieren (wie im Submodul)
    if "Geschlecht" in df.columns:
        df["Geschlecht"] = df["Geschlecht"].astype(str).str.lower().str.strip()

    # Auffaelligkeit_Score sicherstellen (numerisch, Default 0)
    if "Auffaelligkeit_Score" in df.columns:
        df["Auffaelligkeit_Score"] = pd.to_numeric(
            df["Auffaelligkeit_Score"], errors="coerce"
        ).fillna(0)

    return df


def _safe_int(wert, default: int = 0) -> int:
    """Konvertiert einen Wert sicher zu int (NaN-safe)."""
    num = pd.to_numeric(wert, errors="coerce")
    if pd.isna(num):
        return default
    return int(num)


def extrahiere_bestehende_wuensche(df: pd.DataFrame) -> list[dict]:
    """
    Extrahiert bestehende Wünsche und Trennungen aus dem DataFrame
    (für Rückwärtskompatibilität mit altem Excel-Format).

    Returns:
        Liste von {"schueler_id": int, "wuensche": [int, ...], "trennen_von": [int, ...]}
    """
    wunsch_spalten = sorted([c for c in df.columns if str(c).startswith("Wunsch_")])
    trenn_spalten = sorted([c for c in df.columns if str(c).startswith("Trennen_Von")])

    zuordnungen = []
    for sid in df.index:
        wuensche = []
        for ws in wunsch_spalten:
            wert_int = _safe_int(df.at[sid, ws])
            if wert_int > 0 and wert_int in df.index and wert_int != sid:
                wuensche.append(wert_int)

        trennen_von = []
        for ts in trenn_spalten:
            tv_int = _safe_int(df.at[sid, ts])
            if tv_int > 0 and tv_int in df.index and tv_int != sid:
                trennen_von.append(tv_int)

        zuordnungen.append({
            "schueler_id": int(sid),
            "wuensche": wuensche,
            "trennen_von": trennen_von,
        })

    return zuordnungen


def validiere_dataframe(df: pd.DataFrame) -> list[dict]:
    """
    Prüft den DataFrame auf ungültige Werte und gibt eine Liste von
    Hinweisen zurück.

    Returns:
        Liste von {
            "schueler_id": int,
            "name": "Vorname Name",
            "spalte": str,
            "wert": str,
            "hinweis": str,
        }
    """
    from backend.vorlage import ERLAUBTE_AUFFAELLIGKEIT, ERLAUBTE_GESCHLECHT, ERLAUBTE_MIGRATION

    hinweise = []

    for sid, row in df.iterrows():
        vorname = str(row.get("Vorname", ""))
        name = str(row.get("Name", ""))
        voller_name = f"{vorname} {name}".strip()

        # Geschlecht prüfen
        geschlecht = str(row.get("Geschlecht", "")).strip()
        if geschlecht and geschlecht not in ERLAUBTE_GESCHLECHT:
            hinweise.append({
                "schueler_id": int(sid),
                "name": voller_name,
                "spalte": "Geschlecht",
                "wert": geschlecht,
                "hinweis": f"Ungültiger Wert '{geschlecht}'. Erlaubt: m (männlich), w (weiblich).",
            })

        # Auffälligkeits-Score prüfen
        auff_raw = row.get("Auffaelligkeit_Score")
        if pd.notna(auff_raw):
            auff_num = pd.to_numeric(auff_raw, errors="coerce")
            if pd.isna(auff_num):
                hinweise.append({
                    "schueler_id": int(sid),
                    "name": voller_name,
                    "spalte": "Auffaelligkeit_Score",
                    "wert": str(auff_raw),
                    "hinweis": f"'{auff_raw}' ist keine Zahl. Erlaubte Werte: {', '.join(str(x) for x in ERLAUBTE_AUFFAELLIGKEIT)}.",
                })
            elif int(auff_num) not in ERLAUBTE_AUFFAELLIGKEIT and int(auff_num) != 0:
                hinweise.append({
                    "schueler_id": int(sid),
                    "name": voller_name,
                    "spalte": "Auffaelligkeit_Score",
                    "wert": str(int(auff_num)),
                    "hinweis": (
                        f"Wert {int(auff_num)} ist nicht erlaubt. "
                        f"Erlaubte Werte: {', '.join(str(x) for x in ERLAUBTE_AUFFAELLIGKEIT)}. "
                        f"Leer lassen bei keiner Auffälligkeit."
                    ),
                })

        # Migrationshintergrund prüfen
        migration_spalte = "Migrationshintergrund / 2. Staatsangehörigkeit"
        migration = row.get(migration_spalte)
        if pd.notna(migration):
            migration_str = str(migration).strip()
            if migration_str and migration_str not in ERLAUBTE_MIGRATION:
                hinweise.append({
                    "schueler_id": int(sid),
                    "name": voller_name,
                    "spalte": "Migration",
                    "wert": migration_str,
                    "hinweis": f"Ungültiger Wert '{migration_str}'. Erlaubt: Ja, Nein.",
                })

    return hinweise


def wuensche_einfuegen(df: pd.DataFrame, zuordnungen: list[dict]) -> pd.DataFrame:
    """
    Fügt Wunsch- und Trennungsspalten in den DataFrame ein.

    Args:
        df: DataFrame mit Schülerdaten
        zuordnungen: Liste von {"schueler_id", "wuensche", "trennen_von"}
    """
    # Bestehende Wunsch-/Trennungsspalten entfernen
    alte_spalten = [c for c in df.columns if str(c).startswith("Wunsch_")]
    alte_spalten += [c for c in df.columns if str(c).startswith("Trennen_Von")]
    df = df.drop(columns=alte_spalten, errors="ignore")

    # Maximale Anzahl Wünsche ermitteln
    max_wuensche = max((len(z["wuensche"]) for z in zuordnungen), default=0)
    if max_wuensche == 0:
        max_wuensche = 1  # Mindestens eine Wunsch-Spalte

    # Maximale Anzahl Trennungen ermitteln
    max_trennungen = max((len(z["trennen_von"]) for z in zuordnungen), default=0)
    if max_trennungen == 0:
        max_trennungen = 1  # Mindestens eine Trennungs-Spalte

    # Neue Spalten anlegen
    for i in range(max_wuensche):
        df[f"Wunsch_{i + 1}"] = 0
    for i in range(max_trennungen):
        df[f"Trennen_Von_{i + 1}"] = 0

    # Werte eintragen
    for z in zuordnungen:
        sid = z["schueler_id"]
        if sid not in df.index:
            continue
        for i, wid in enumerate(z["wuensche"]):
            if i < max_wuensche:
                df.at[sid, f"Wunsch_{i + 1}"] = int(wid)
        for i, tid in enumerate(z["trennen_von"]):
            if i < max_trennungen:
                df.at[sid, f"Trennen_Von_{i + 1}"] = int(tid)

    return df
