"""
Qualitätsprüfungen nach der Klasseneinteilung.

Prüft für jede Klasse, wie gut die Einteilung die pädagogischen Ziele erfüllt:
- Geschlechterverteilung (M/W Balance)
- Auffälligkeits-Score (gleichmäßige Belastung)
- Migrationshintergrund (gleichmäßige Verteilung)
- Jungen-Verteilung (gleichmäßig über Klassen)
- Freundschaftswünsche (Erfüllungsquote)
- Trennungsauflagen (keine Verstöße)
- Klassengröße (ausgeglichen)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Schwellenwerte für die Ampel-Bewertung
# ---------------------------------------------------------------------------
SCHWELLEN = {
    "geschlecht_abweichung": {"gruen": 2, "orange": 4},       # max Differenz m-w pro Klasse
    "auffaelligkeit_abweichung_pct": {"gruen": 10, "orange": 25},  # % Abweichung vom Ideal
    "migration_abweichung_pp": {"gruen": 5, "orange": 10},     # Prozentpunkte
    "jungen_abweichung": {"gruen": 1, "orange": 3},            # abs. Abweichung vom Ideal
    "wunsch_quote_pct": {"gruen": 75, "orange": 50},           # % erfüllte Wünsche
    "trennungen_missachtet": {"gruen": 0, "orange": 0},        # 0 = muss perfekt sein
    "klassengroesse_abweichung": {"gruen": 1, "orange": 2},    # max Differenz zum Ideal
}


def _ampel(wert: float, gruen: float, orange: float, niedriger_ist_besser: bool = True) -> str:
    """Gibt 'gruen', 'orange' oder 'rot' zurück."""
    if niedriger_ist_besser:
        if wert <= gruen:
            return "gruen"
        elif wert <= orange:
            return "orange"
        return "rot"
    else:  # höher ist besser (z.B. Wunsch-Quote)
        if wert >= gruen:
            return "gruen"
        elif wert >= orange:
            return "orange"
        return "rot"


@dataclass
class KlassenPruefung:
    """Prüfergebnis für eine einzelne Klasse."""
    klasse_name: str
    anzahl_schueler: int

    # Geschlecht
    maennlich: int = 0
    weiblich: int = 0
    geschlecht_differenz: int = 0
    geschlecht_ampel: str = "gruen"

    # Auffälligkeit
    auffaelligkeit_summe: float = 0.0
    auffaelligkeit_durchschnitt: float = 0.0
    auffaelligkeit_ideal: float = 0.0
    auffaelligkeit_abweichung_pct: float = 0.0
    auffaelligkeit_ampel: str = "gruen"

    # Migration
    migration_anzahl: int = 0
    migration_anteil_pct: float = 0.0
    migration_stufen_anteil_pct: float = 0.0
    migration_abweichung_pp: float = 0.0
    migration_ampel: str = "gruen"

    # Jungen-Verteilung
    jungen_ideal: float = 0.0
    jungen_abweichung: float = 0.0
    jungen_ampel: str = "gruen"

    # Wünsche
    wuensche_gesamt: int = 0
    wuensche_erfuellt: int = 0
    wuensche_nicht_erfuellt: int = 0
    wunsch_quote_pct: float = 0.0
    wunsch_ampel: str = "gruen"

    # Trennungen
    trennungen_gesamt: int = 0
    trennungen_missachtet: int = 0
    trennungen_ampel: str = "gruen"

    # Nicht erfüllte Wünsche im Detail
    nicht_erfuellte_wuensche: list = field(default_factory=list)


@dataclass
class GesamtPruefung:
    """Gesamtergebnis über alle Klassen."""
    klassen: list  # Liste von KlassenPruefung
    gesamt_ampel: str = "gruen"  # schlechteste Ampel über alle Kriterien
    zusammenfassung: dict = field(default_factory=dict)


def _get_class_name(index: int) -> str:
    """Konvertiert 0-basierten Index in alphabetischen Klassennamen."""
    result = ""
    while index >= 0:
        result = chr(ord('A') + (index % 26)) + result
        index = (index // 26) - 1
    return result


def _baue_schueler_klasse_map(einteilung: list) -> dict:
    """Erstellt ein Mapping: Schüler-ID → (Klassen-Index, Klassenname)."""
    mapping = {}
    for i, klasse_ids in enumerate(einteilung):
        name = _get_class_name(i)
        for sid in klasse_ids:
            mapping[int(sid)] = (i, name)
    return mapping


def pruefe_einteilung(einteilung: list, df: pd.DataFrame) -> GesamtPruefung:
    """
    Führt alle Qualitätsprüfungen für eine Einteilung durch.

    Args:
        einteilung: Liste von Listen mit Schüler-IDs pro Klasse
        df: DataFrame mit Schülerdaten (Index = Schüler-ID)

    Returns:
        GesamtPruefung mit allen Ergebnissen
    """
    anzahl_klassen = len(einteilung)
    gesamt_schueler = len(df)

    # Gesamtwerte berechnen
    spalte_migration = "Migrationshintergrund / 2. Staatsangehörigkeit"
    spalte_auffaelligkeit = "Auffaelligkeit_Score"
    wunsch_spalten = [c for c in df.columns if str(c).startswith("Wunsch_")]

    gesamt_migration_anteil = (df[spalte_migration] == "Ja").sum() / gesamt_schueler if gesamt_schueler > 0 else 0
    gesamt_auffaelligkeit = pd.to_numeric(df[spalte_auffaelligkeit], errors="coerce").fillna(0).sum()
    ideal_auffaelligkeit = gesamt_auffaelligkeit / anzahl_klassen
    gesamt_jungen = (df["Geschlecht"] == "m").sum()
    ideal_jungen = gesamt_jungen / anzahl_klassen
    ideal_klassengroesse = gesamt_schueler / anzahl_klassen

    # Mapping: Schüler-ID → Klasse (für Wunschpartner-Klasse)
    schueler_klasse_map = _baue_schueler_klasse_map(einteilung)

    klassen_pruefungen = []
    alle_ampeln = []

    for i, klasse_ids in enumerate(einteilung):
        klassen_df = df.loc[klasse_ids]
        kp = KlassenPruefung(
            klasse_name=_get_class_name(i),
            anzahl_schueler=len(klasse_ids),
        )

        # --- 1. Geschlecht ---
        kp.maennlich = int((klassen_df["Geschlecht"] == "m").sum())
        kp.weiblich = int((klassen_df["Geschlecht"] == "w").sum())
        kp.geschlecht_differenz = abs(kp.maennlich - kp.weiblich)
        s = SCHWELLEN["geschlecht_abweichung"]
        kp.geschlecht_ampel = _ampel(kp.geschlecht_differenz, s["gruen"], s["orange"])
        alle_ampeln.append(kp.geschlecht_ampel)

        # --- 2. Auffälligkeit ---
        kp.auffaelligkeit_summe = float(
            pd.to_numeric(klassen_df[spalte_auffaelligkeit], errors="coerce").fillna(0).sum()
        )
        kp.auffaelligkeit_durchschnitt = round(
            kp.auffaelligkeit_summe / len(klasse_ids), 2
        ) if len(klasse_ids) > 0 else 0.0
        kp.auffaelligkeit_ideal = round(ideal_auffaelligkeit, 2)
        if ideal_auffaelligkeit > 0:
            kp.auffaelligkeit_abweichung_pct = round(
                abs(kp.auffaelligkeit_summe - ideal_auffaelligkeit) / ideal_auffaelligkeit * 100, 1
            )
        s = SCHWELLEN["auffaelligkeit_abweichung_pct"]
        kp.auffaelligkeit_ampel = _ampel(kp.auffaelligkeit_abweichung_pct, s["gruen"], s["orange"])
        alle_ampeln.append(kp.auffaelligkeit_ampel)

        # --- 3. Migration ---
        kp.migration_anzahl = int((klassen_df[spalte_migration] == "Ja").sum())
        kp.migration_anteil_pct = round(
            kp.migration_anzahl / len(klasse_ids) * 100, 1
        ) if len(klasse_ids) > 0 else 0.0
        kp.migration_stufen_anteil_pct = round(gesamt_migration_anteil * 100, 1)
        kp.migration_abweichung_pp = round(
            abs(kp.migration_anteil_pct - kp.migration_stufen_anteil_pct), 1
        )
        s = SCHWELLEN["migration_abweichung_pp"]
        kp.migration_ampel = _ampel(kp.migration_abweichung_pp, s["gruen"], s["orange"])
        alle_ampeln.append(kp.migration_ampel)

        # --- 4. Jungen-Verteilung ---
        kp.jungen_ideal = round(ideal_jungen, 1)
        kp.jungen_abweichung = round(abs(kp.maennlich - ideal_jungen), 1)
        s = SCHWELLEN["jungen_abweichung"]
        kp.jungen_ampel = _ampel(kp.jungen_abweichung, s["gruen"], s["orange"])
        alle_ampeln.append(kp.jungen_ampel)

        # --- 5. Wünsche ---
        if wunsch_spalten:
            klasse_set = set(map(int, klasse_ids))
            gueltige_ids = set(int(x) for x in df.index)

            for schueler_id, row in klassen_df.iterrows():
                wuensche_ids = set()
                for wcol in wunsch_spalten:
                    wish_val = row.get(wcol)
                    wish_id = pd.to_numeric(wish_val, errors="coerce")
                    if pd.notna(wish_id) and int(wish_id) != int(schueler_id) and int(wish_id) != 0:
                        wuensche_ids.add(int(wish_id))

                for wish_id in wuensche_ids:
                    # Ungültige IDs (Schüler existiert nicht) überspringen
                    if wish_id not in gueltige_ids:
                        continue

                    kp.wuensche_gesamt += 1
                    if wish_id in klasse_set:
                        kp.wuensche_erfuellt += 1
                    else:
                        kp.wuensche_nicht_erfuellt += 1

                        wunsch_name = f"{df.loc[wish_id]['Vorname']} {df.loc[wish_id]['Name']}"

                        # Klasse des Wunschpartners ermitteln
                        wunsch_klasse_info = schueler_klasse_map.get(wish_id)
                        wunsch_klasse = wunsch_klasse_info[1] if wunsch_klasse_info else "?"

                        kp.nicht_erfuellte_wuensche.append({
                            "schueler_name": f"{df.loc[schueler_id]['Vorname']} {df.loc[schueler_id]['Name']}",
                            "schueler_id": int(schueler_id),
                            "klasse": _get_class_name(i),
                            "wunsch_name": wunsch_name,
                            "wunsch_id": int(wish_id),
                            "wunsch_klasse": wunsch_klasse,
                        })

        kp.wunsch_quote_pct = round(
            kp.wuensche_erfuellt / kp.wuensche_gesamt * 100, 1
        ) if kp.wuensche_gesamt > 0 else 100.0
        s = SCHWELLEN["wunsch_quote_pct"]
        kp.wunsch_ampel = _ampel(kp.wunsch_quote_pct, s["gruen"], s["orange"], niedriger_ist_besser=False)
        alle_ampeln.append(kp.wunsch_ampel)

        # --- 6. Trennungen (unterstützt mehrere Trennen_Von_X Spalten) ---
        trenn_spalten = sorted([c for c in df.columns if str(c).startswith("Trennen_Von")])
        if trenn_spalten:
            klasse_set = set(map(int, klasse_ids))
            for schueler_id, row in klassen_df.iterrows():
                for ts in trenn_spalten:
                    sep_val = row.get(ts)
                    sep_id = pd.to_numeric(sep_val, errors="coerce")
                    if pd.notna(sep_id) and int(sep_id) > 0:
                        kp.trennungen_gesamt += 1
                        if int(sep_id) in klasse_set:
                            kp.trennungen_missachtet += 1

        s = SCHWELLEN["trennungen_missachtet"]
        kp.trennungen_ampel = _ampel(kp.trennungen_missachtet, s["gruen"], s["orange"])
        alle_ampeln.append(kp.trennungen_ampel)

        klassen_pruefungen.append(kp)

    # --- Gesamt-Ampel ---
    if "rot" in alle_ampeln:
        gesamt_ampel = "rot"
    elif "orange" in alle_ampeln:
        gesamt_ampel = "orange"
    else:
        gesamt_ampel = "gruen"

    # --- Klassengröße prüfen ---
    groessen = [kp.anzahl_schueler for kp in klassen_pruefungen]
    max_abweichung_groesse = max(abs(g - ideal_klassengroesse) for g in groessen)
    s = SCHWELLEN["klassengroesse_abweichung"]
    klassengroesse_ampel = _ampel(max_abweichung_groesse, s["gruen"], s["orange"])
    if klassengroesse_ampel == "rot":
        gesamt_ampel = "rot"
    elif klassengroesse_ampel == "orange" and gesamt_ampel == "gruen":
        gesamt_ampel = "orange"

    # --- Zusammenfassung ---
    gesamt_wuensche = sum(kp.wuensche_gesamt for kp in klassen_pruefungen)
    gesamt_erfuellt = sum(kp.wuensche_erfuellt for kp in klassen_pruefungen)
    zusammenfassung = {
        "anzahl_klassen": anzahl_klassen,
        "anzahl_schueler": gesamt_schueler,
        "klassengroesse_min": min(groessen),
        "klassengroesse_max": max(groessen),
        "klassengroesse_ideal": round(ideal_klassengroesse, 1),
        "klassengroesse_ampel": klassengroesse_ampel,
        "wuensche_gesamt": gesamt_wuensche,
        "wuensche_erfuellt": gesamt_erfuellt,
        "wuensche_quote_pct": round(gesamt_erfuellt / gesamt_wuensche * 100, 1) if gesamt_wuensche > 0 else 100.0,
        "trennungen_missachtet_gesamt": sum(kp.trennungen_missachtet for kp in klassen_pruefungen),
    }

    return GesamtPruefung(
        klassen=klassen_pruefungen,
        gesamt_ampel=gesamt_ampel,
        zusammenfassung=zusammenfassung,
    )
