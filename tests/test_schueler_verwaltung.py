"""Unit-Tests für das Hinzufügen und Entfernen von Schülern über die API."""

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.api import routes
from backend.api.routes import SchuelerNeu, schueler_hinzufuegen, schueler_entfernen

MIG_SPALTE = "Migrationshintergrund / 2. Staatsangehörigkeit"


def _test_df() -> pd.DataFrame:
    """Baut einen DataFrame im App-Format (Index = Schüler-ID)."""
    df = pd.DataFrame({
        "Vorname": ["Anna", "Ben", "Clara"],
        "Name": ["Alpha", "Beta", "Gamma"],
        "Geschlecht": ["w", "m", "w"],
        "Auffaelligkeit_Score": [0, 3, 0],
        MIG_SPALTE: ["Nein", "Ja", "Nein"],
        "Wunsch_1": [2, 0, 1],
        "Trennen_Von_1": [0, 3, 0],
    })
    df.index = range(1, len(df) + 1)
    df.index.name = "Schüler-ID"
    return df


@pytest.fixture
def state():
    """Setzt den In-Memory-State auf einen Testdatensatz und räumt danach auf."""
    alt = dict(routes._state)
    routes._state["df"] = _test_df()
    routes._state["einteilung"] = [[1, 2], [3]]
    routes._state["pruefung"] = "dummy"
    yield routes._state
    routes._state.update(alt)


class TestHinzufuegen:
    def test_neue_id_und_stammdaten(self, state):
        antwort = schueler_hinzufuegen(SchuelerNeu(
            vorname="Dora", name="Delta", geschlecht="w",
            auffaelligkeit=5, migration="Ja",
        ))
        assert antwort["status"] == "ok"
        assert antwort["schueler_id"] == 4
        assert antwort["anzahl_schueler"] == 4

        df = state["df"]
        assert df.at[4, "Vorname"] == "Dora"
        assert df.at[4, "Geschlecht"] == "w"
        assert df.at[4, "Auffaelligkeit_Score"] == 5
        assert df.at[4, MIG_SPALTE] == "Ja"
        # Wunsch-/Trennungsspalten mit 0 initialisiert
        assert int(df.at[4, "Wunsch_1"]) == 0
        assert int(df.at[4, "Trennen_Von_1"]) == 0

    def test_verwirft_einteilung(self, state):
        schueler_hinzufuegen(SchuelerNeu(vorname="Dora", name="Delta", geschlecht="w"))
        assert state["einteilung"] is None
        assert state["pruefung"] is None

    def test_geschlecht_wird_normalisiert(self, state):
        schueler_hinzufuegen(SchuelerNeu(vorname="Emil", name="Epsilon", geschlecht=" M "))
        assert state["df"].at[4, "Geschlecht"] == "m"

    def test_legt_sprengel_spalte_an(self, state):
        assert "Sprengel" not in state["df"].columns
        schueler_hinzufuegen(SchuelerNeu(
            vorname="Dora", name="Delta", geschlecht="w", sprengel="Nord",
        ))
        assert state["df"].at[4, "Sprengel"] == "Nord"
        # Bestandsschüler bekommen leeren Sprengel
        assert state["df"].at[1, "Sprengel"] == ""

    def test_antwort_enthaelt_neue_schuelerliste(self, state):
        antwort = schueler_hinzufuegen(SchuelerNeu(vorname="Dora", name="Delta", geschlecht="w"))
        ids = [s["id"] for s in antwort["schueler"]]
        assert ids == [1, 2, 3, 4]

    @pytest.mark.parametrize("kwargs", [
        {"vorname": "  ", "name": "Delta", "geschlecht": "w"},
        {"vorname": "Dora", "name": "", "geschlecht": "w"},
        {"vorname": "Dora", "name": "Delta", "geschlecht": "x"},
        {"vorname": "Dora", "name": "Delta", "geschlecht": "w", "auffaelligkeit": 4},
        {"vorname": "Dora", "name": "Delta", "geschlecht": "w", "migration": "Vielleicht"},
    ])
    def test_ungueltige_eingaben(self, state, kwargs):
        with pytest.raises(HTTPException) as exc:
            schueler_hinzufuegen(SchuelerNeu(**kwargs))
        assert exc.value.status_code == 400
        # Nichts wurde hinzugefügt
        assert len(state["df"]) == 3

    def test_ohne_daten(self, state):
        state["df"] = None
        with pytest.raises(HTTPException) as exc:
            schueler_hinzufuegen(SchuelerNeu(vorname="A", name="B", geschlecht="w"))
        assert exc.value.status_code == 400


class TestEntfernen:
    def test_entfernt_zeile(self, state):
        antwort = schueler_entfernen(2)
        assert antwort["status"] == "ok"
        assert antwort["anzahl_schueler"] == 2
        assert 2 not in state["df"].index

    def test_bereinigt_referenzen(self, state):
        # Anna (1) wünscht sich Ben (2); Ben trennt von Clara (3)
        schueler_entfernen(2)
        df = state["df"]
        assert int(df.at[1, "Wunsch_1"]) == 0       # Verweis auf 2 entfernt
        assert int(df.at[3, "Wunsch_1"]) == 1        # Verweis auf 1 bleibt

    def test_verwirft_einteilung(self, state):
        schueler_entfernen(3)
        assert state["einteilung"] is None
        assert state["pruefung"] is None

    def test_unbekannte_id(self, state):
        with pytest.raises(HTTPException) as exc:
            schueler_entfernen(99)
        assert exc.value.status_code == 404

    def test_id_wird_nicht_wiederverwendet(self, state):
        """Nach Entfernen der höchsten ID darf ein neuer Schüler zwar deren
        ID bekommen — aber Referenzen darauf wurden zuvor bereinigt."""
        schueler_entfernen(3)
        antwort = schueler_hinzufuegen(SchuelerNeu(vorname="Dora", name="Delta", geschlecht="w"))
        assert antwort["schueler_id"] == 3
        # Bens Trennung zeigte auf die alte 3 (Clara) und wurde bereinigt
        assert int(state["df"].at[2, "Trennen_Von_1"]) == 0
