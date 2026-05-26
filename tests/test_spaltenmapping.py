"""Unit-Tests für Hundehaarallergie-Erkennung im Spalten-Mapping."""

import tempfile

import pandas as pd
import pytest

from backend.spaltenmapping import finde_spalten_mapping, baue_dataframe


def _schreibe_test_xlsx(daten: dict) -> str:
    """Hilfsfunktion: schreibt einen DataFrame in eine temp .xlsx."""
    df = pd.DataFrame(daten)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    tmp.close()
    return tmp.name


class TestMapping:
    @pytest.mark.parametrize("spaltenname", [
        "Hundehaarallergie",
        "hundehaarallergie",
        "Hundeallergie",
        "Hund-Allergie",
        "Allergie Hund",
        "Tierhaarallergie",
        "Allergie",
    ])
    def test_erkennt_aliasse(self, spaltenname):
        spalten = ["Vorname", "Name", "Geschlecht", "Auffaelligkeit", "Migration", spaltenname]
        ergebnis = finde_spalten_mapping(spalten)
        assert ergebnis["mapping"]["Hundehaarallergie"]["spalte"] == spaltenname

    def test_fehlende_spalte_kein_fehler(self):
        spalten = ["Vorname", "Name", "Geschlecht", "Auffaelligkeit", "Migration"]
        ergebnis = finde_spalten_mapping(spalten)
        # Optionale Spalte → kein "nicht_gefunden"-Eintrag, alle Pflichtspalten sicher
        assert ergebnis["alle_pflicht_sicher"] is True


class TestBaueDataframe:
    def test_allergie_spalte_wird_normalisiert(self):
        pfad = _schreibe_test_xlsx({
            "Vorname": ["Anna", "Ben", "Clara"],
            "Name": ["A", "B", "C"],
            "Geschlecht": ["w", "m", "w"],
            "Auffaelligkeit_Score": [0, 0, 0],
            "Migrationshintergrund / 2. Staatsangehörigkeit": ["Nein", "Nein", "Nein"],
            "Hundehaarallergie": ["Ja", "nein", ""],
        })
        mapping = {
            "Vorname": "Vorname",
            "Name": "Name",
            "Geschlecht": "Geschlecht",
            "Auffaelligkeit_Score": "Auffaelligkeit_Score",
            "Migrationshintergrund / 2. Staatsangehörigkeit": "Migrationshintergrund / 2. Staatsangehörigkeit",
            "Hundehaarallergie": "Hundehaarallergie",
        }
        df = baue_dataframe(pfad, mapping)
        assert list(df["Hundehaarallergie"]) == ["ja", "nein", ""]
