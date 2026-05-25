# Schulhund-Allergie-Constraint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine konfigurierbar gewählte Klasse („Schulhund-Klasse") wird durch eine harte Regel garantiert frei von Schülern mit Hundehaarallergie oder ohne Angabe gehalten.

**Architecture:** Soft-Score im Optimierungs-Wrapper (analog Sprengel-Bonus) + harter Post-Processing-Tausch (analog `_erzwinge_trennungen`). Submodul (`lib/klasseneinteilung`) bleibt unverändert. Spalte `Hundehaarallergie` wird optional importiert und kann zusätzlich pro Schüler im Frontend korrigiert werden.

**Tech Stack:** Python 3.12+, FastAPI, pandas, openpyxl, pytest (neu), Vanilla JS.

**Spec:** `docs/superpowers/specs/2026-05-25-schulhund-allergie-design.md`

---

## File Structure

**Neue Dateien:**
- `backend/schulhund.py` — Single Source of Truth: Normalisierung der Allergie-Werte, `darf_in_schulhund_klasse()`, `_erzwinge_schulhund_klasse()` (Post-Processing), `_schulhund_strafe()` (Score-Penalty).
- `tests/__init__.py` — leer.
- `tests/test_schulhund.py` — Unit-Tests für die Pure Functions in `backend/schulhund.py`.
- `tests/test_spaltenmapping.py` — Unit-Tests für die neue `Hundehaarallergie`-Erkennung.
- `tests/test_pruefungen.py` — Unit-Tests für das neue Ampel-Kriterium.
- `test_schulhund_e2e.py` — E2E-Test analog `test_persistence.py`.
- `conftest.py` (Repo-Root) — pytest-Konfiguration für Test-Discovery.

**Modifizierte Dateien:**
- `requirements.txt` — pytest hinzufügen.
- `backend/spaltenmapping.py` — `Hundehaarallergie` in `OPTIONALE_SPALTEN`; Normalisierung der Werte beim `baue_dataframe`.
- `backend/vorlage.py` — Spalte zur xlsx- und ods-Vorlage hinzufügen.
- `backend/optimierung_wrapper.py` — `STRAFE_SCHULHUND_VERLETZUNG`, `_schulhund_strafe()`, `schulhund_klasse`-Parameter.
- `backend/pruefungen/qualitaet.py` — neue Felder in `KlassenPruefung` + `GesamtPruefung`, `schulhund_klasse`-Parameter in `pruefe_einteilung()`.
- `backend/api/routes.py` — State-Eintrag, Query-Param, neuer Pydantic-Feld, Schülerliste-Output, Persistenz-Felder, Aufruf der Post-Processing-Funktion.
- `frontend/index.html` — Dropdown, Hinweistext, Tabellen-Spalte „Allergie".
- `frontend/app.js` — State, Dropdown-Verdrahtung, Klassen-Zähler-Sync, Optimierungs-Param, Schüler-Editor, Warnungen.
- `frontend/style.css` — `.klasse-schulhund`, `.schueler-allergie`, `.schueler-allergie-unbekannt`.

---

## Task 0: Pytest-Setup

**Files:**
- Create: `conftest.py`
- Create: `tests/__init__.py`
- Modify: `requirements.txt`

- [ ] **Step 1: pytest zu requirements.txt hinzufügen**

`requirements.txt` enthält aktuell:
```
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
pandas>=2.2
openpyxl>=3.1
numpy>=1.26
odfpy>=1.4
pyinstaller>=6.0
```

Füge am Ende hinzu:
```
pytest>=8.0
```

- [ ] **Step 2: Pytest installieren**

```bash
source .venv/bin/activate && pip install pytest
```
Expected: erfolgreiche Installation, keine Konflikte.

- [ ] **Step 3: conftest.py anlegen**

Inhalt:
```python
import sys
from pathlib import Path

# Submodul-Pfad ergänzen, damit Tests `algorithmus`, `config`, `utils` importieren können
sys.path.insert(0, str(Path(__file__).parent / "lib" / "klasseneinteilung"))
```

- [ ] **Step 4: tests/__init__.py anlegen (leer)**

Leere Datei anlegen.

- [ ] **Step 5: Verifizieren, dass pytest läuft**

```bash
pytest --version
```
Expected: `pytest 8.x.x` oder höher.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt conftest.py tests/__init__.py
git commit -m "test: pytest als dev-dependency und conftest hinzufügen"
```

---

## Task 1: Schulhund-Modul (Normalisierung + Helper)

**Files:**
- Create: `backend/schulhund.py`
- Test: `tests/test_schulhund.py`

- [ ] **Step 1: Failing Test schreiben**

`tests/test_schulhund.py`:
```python
"""Unit-Tests für backend/schulhund.py."""

import pandas as pd
import pytest

from backend.schulhund import (
    normalisiere_allergie_wert,
    darf_in_schulhund_klasse,
    zaehle_allergiker_in_klasse,
)


class TestNormalisierung:
    @pytest.mark.parametrize("eingabe,erwartet", [
        ("ja", "ja"),
        ("Ja", "ja"),
        ("JA", "ja"),
        ("j", "ja"),
        ("yes", "ja"),
        ("y", "ja"),
        ("1", "ja"),
        ("true", "ja"),
        ("x", "ja"),
        ("X", "ja"),
        ("  ja  ", "ja"),
    ])
    def test_ja_varianten(self, eingabe, erwartet):
        assert normalisiere_allergie_wert(eingabe) == erwartet

    @pytest.mark.parametrize("eingabe,erwartet", [
        ("nein", "nein"),
        ("Nein", "nein"),
        ("n", "nein"),
        ("no", "nein"),
        ("0", "nein"),
        ("false", "nein"),
        ("-", "nein"),
    ])
    def test_nein_varianten(self, eingabe, erwartet):
        assert normalisiere_allergie_wert(eingabe) == erwartet

    @pytest.mark.parametrize("eingabe", [
        "",
        "   ",
        None,
        float("nan"),
        "vielleicht",
        "unbekannt",
        "k.A.",
    ])
    def test_leer_und_unbekannt(self, eingabe):
        assert normalisiere_allergie_wert(eingabe) == ""


class TestDarfInSchulhundKlasse:
    def test_nein_erlaubt(self):
        assert darf_in_schulhund_klasse("nein") is True

    def test_ja_verboten(self):
        assert darf_in_schulhund_klasse("ja") is False

    def test_leer_verboten(self):
        assert darf_in_schulhund_klasse("") is False

    def test_none_verboten(self):
        assert darf_in_schulhund_klasse(None) is False


class TestZaehleAllergiker:
    def test_ohne_spalte(self):
        df = pd.DataFrame({"Vorname": ["A", "B"]}, index=[1, 2])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([1, 2], df)
        assert allergiker == 0
        assert unbekannt == 0

    def test_gemischt(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["ja", "nein", "", "ja", "nein"],
        }, index=[1, 2, 3, 4, 5])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([1, 2, 3, 4, 5], df)
        assert allergiker == 2
        assert unbekannt == 1

    def test_nur_teilmenge(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["ja", "nein", "", "nein"],
        }, index=[1, 2, 3, 4])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([2, 4], df)
        assert allergiker == 0
        assert unbekannt == 0
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
pytest tests/test_schulhund.py -v
```
Expected: alle FAIL mit `ImportError: cannot import name ... from 'backend.schulhund'` (Modul existiert noch nicht).

- [ ] **Step 3: backend/schulhund.py implementieren**

```python
"""
Single Source of Truth für die Schulhund-Allergie-Logik.

- Normalisierung der Allergie-Werte aus dem Excel-Import und der UI-Eingabe.
- Helper für die Pruefung (Zählung pro Klasse).
- Score-Strafe für den Optimierungs-Wrapper.
- Hard-Rule Post-Processing (Tausch-Algorithmus).

Werte:
- "ja"   → Allergiker (darf NICHT in Schulhund-Klasse)
- "nein" → kein Allergiker (darf in Schulhund-Klasse)
- ""     → unbekannt / fehlende Angabe (darf NICHT in Schulhund-Klasse)
"""

from __future__ import annotations

import pandas as pd

SPALTE = "Hundehaarallergie"

_JA_VARIANTEN = {"ja", "j", "yes", "y", "1", "true", "x"}
_NEIN_VARIANTEN = {"nein", "n", "no", "0", "false", "-"}


def normalisiere_allergie_wert(wert) -> str:
    """Normalisiert einen Eingabewert zu 'ja', 'nein' oder ''."""
    if wert is None:
        return ""
    if isinstance(wert, float) and pd.isna(wert):
        return ""
    s = str(wert).strip().lower()
    if s == "" or s == "nan":
        return ""
    if s in _JA_VARIANTEN:
        return "ja"
    if s in _NEIN_VARIANTEN:
        return "nein"
    return ""  # Unbekannte Strings → wie "leer" behandeln


def darf_in_schulhund_klasse(wert) -> bool:
    """True genau dann, wenn der normalisierte Wert 'nein' ist."""
    return normalisiere_allergie_wert(wert) == "nein"


def zaehle_allergiker_in_klasse(
    klasse_ids: list[int], df: pd.DataFrame
) -> tuple[int, int]:
    """
    Zählt Allergiker und Unbekannte in einer Klasse.

    Returns: (anzahl_allergiker, anzahl_unbekannt)
    """
    if SPALTE not in df.columns:
        return 0, 0
    allergiker = 0
    unbekannt = 0
    for sid in klasse_ids:
        if sid not in df.index:
            continue
        wert = normalisiere_allergie_wert(df.at[sid, SPALTE])
        if wert == "ja":
            allergiker += 1
        elif wert == "":
            unbekannt += 1
    return allergiker, unbekannt
```

- [ ] **Step 4: Tests laufen lassen — müssen grün sein**

```bash
pytest tests/test_schulhund.py -v
```
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/schulhund.py tests/test_schulhund.py
git commit -m "feat(schulhund): Normalisierung und Zähl-Helper für Allergie-Werte"
```

---

## Task 2: Spalten-Mapping erweitern

**Files:**
- Modify: `backend/spaltenmapping.py:79-107` (OPTIONALE_SPALTEN)
- Modify: `backend/spaltenmapping.py:214-259` (`baue_dataframe`)
- Test: `tests/test_spaltenmapping.py`

- [ ] **Step 1: Failing Test schreiben**

`tests/test_spaltenmapping.py`:
```python
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
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
pytest tests/test_spaltenmapping.py -v
```
Expected: FAIL — Alias wird nicht erkannt bzw. Werte nicht normalisiert.

- [ ] **Step 3: OPTIONALE_SPALTEN um `Hundehaarallergie` erweitern**

In `backend/spaltenmapping.py` direkt vor dem schließenden `}` von `OPTIONALE_SPALTEN` (nach dem `Sprengel`-Eintrag, vor Zeile 107) einfügen:

```python
    "Hundehaarallergie": {
        "aliasse": [
            "hundehaarallergie", "hundeallergie", "hund-allergie",
            "allergie hund", "allergie", "tierhaarallergie",
        ],
    },
```

- [ ] **Step 4: Normalisierung in `baue_dataframe` ergänzen**

In `backend/spaltenmapping.py`, in `baue_dataframe`, **vor** dem `return df` (nach dem `Auffaelligkeit_Score`-Block ab Zeile 254) einfügen:

```python
    # Hundehaarallergie auf 'ja'/'nein'/'' normalisieren
    if "Hundehaarallergie" in df.columns:
        from backend.schulhund import normalisiere_allergie_wert
        df["Hundehaarallergie"] = df["Hundehaarallergie"].apply(normalisiere_allergie_wert)
```

- [ ] **Step 5: Tests laufen lassen — müssen grün sein**

```bash
pytest tests/test_spaltenmapping.py -v
```
Expected: alle PASS.

- [ ] **Step 6: Bestehende Tests nicht zerschossen?**

```bash
pytest tests/ -v
```
Expected: alle PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/spaltenmapping.py tests/test_spaltenmapping.py
git commit -m "feat(import): Hundehaarallergie als optionale Spalte erkennen und normalisieren"
```

---

## Task 3: Vorlage erweitern (xlsx + ods)

**Files:**
- Modify: `backend/vorlage.py:23` (neue Konstante) und `backend/vorlage.py:28-105` (`VORLAGE_SPALTEN`), `backend/vorlage.py:107-143` (`ANLEITUNGSTEXTE`)

- [ ] **Step 1: Konstante für erlaubte Werte ergänzen**

In `backend/vorlage.py` nach `ERLAUBTE_MIGRATION = ["Ja", "Nein"]` (Zeile 23) hinzufügen:

```python
ERLAUBTE_HUNDEHAARALLERGIE = ["Ja", "Nein"]
```

- [ ] **Step 2: Spalte zu `VORLAGE_SPALTEN` hinzufügen**

In `backend/vorlage.py`, am **Ende** der `VORLAGE_SPALTEN`-Liste (nach dem `Sprengel`-Eintrag, vor `]` auf Zeile 105):

```python
    {
        "name": "Hundehaarallergie",
        "breite": 20,
        "kommentar": (
            "Hat das Kind eine Hundehaarallergie?\n"
            "Erlaubte Werte:\n"
            "  Ja\n"
            "  Nein\n"
            "\n"
            "Wird benötigt, wenn eine Klasse einen\n"
            "Schulhund hat. Kinder mit Allergie oder\n"
            "ohne Angabe werden aus der Schulhund-\n"
            "Klasse herausgehalten."
        ),
        "beispiele": ["Nein", "Ja"],
        "validierung": ERLAUBTE_HUNDEHAARALLERGIE,
        "validierung_fehler": "Bitte nur 'Ja' oder 'Nein' eingeben.",
    },
```

- [ ] **Step 3: Anleitungstext ergänzen**

In `backend/vorlage.py`, in `ANLEITUNGSTEXTE`, vor `"Hinweise:"` (Zeile 138) einfügen:

```python
    "  Hundehaarallergie:",
    "     Ja  = Kind hat eine Hundehaarallergie",
    "     Nein = Kind hat keine Allergie",
    "     (leer = unbekannt — wird wie 'Ja' behandelt, wenn",
    "      eine Schulhund-Klasse gewählt wird)",
    "",
```

- [ ] **Step 4: Vorlage manuell prüfen**

```bash
python -c "from backend.vorlage import generiere_xlsx_vorlage; print(generiere_xlsx_vorlage())"
```
Datei mit Excel oder LibreOffice öffnen, prüfen ob die neue Spalte mit Dropdown vorhanden ist.

- [ ] **Step 5: ODS-Variante prüfen**

```bash
python -c "from backend.vorlage import generiere_ods_vorlage; print(generiere_ods_vorlage())"
```
Datei in LibreOffice öffnen, neue Spalte prüfen.

- [ ] **Step 6: Commit**

```bash
git add backend/vorlage.py
git commit -m "feat(vorlage): Hundehaarallergie-Spalte in xlsx- und ods-Vorlage"
```

---

## Task 4: Optimierungs-Wrapper um Schulhund-Strafe erweitern

**Files:**
- Modify: `backend/optimierung_wrapper.py`
- Test: `tests/test_optimierung_wrapper.py` (neu)

- [ ] **Step 1: Failing Test schreiben**

`tests/test_optimierung_wrapper.py`:
```python
"""Unit-Tests für Schulhund-Strafe im Optimierungs-Wrapper."""

import pandas as pd

from backend.optimierung_wrapper import _schulhund_strafe, STRAFE_SCHULHUND_VERLETZUNG


def test_keine_strafe_wenn_klasse_sauber():
    df = pd.DataFrame({
        "Hundehaarallergie": ["nein", "nein", "ja", "ja"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 2], [3, 4]]  # Klasse 0 = Schulhund, alle nein → 0 Strafe
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == 0.0


def test_strafe_pro_allergiker():
    df = pd.DataFrame({
        "Hundehaarallergie": ["ja", "nein", "ja", "nein"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 3], [2, 4]]  # Klasse 0 = Schulhund, 2 Allergiker
    erwartet = 2 * STRAFE_SCHULHUND_VERLETZUNG
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == erwartet


def test_strafe_pro_unbekannt():
    df = pd.DataFrame({
        "Hundehaarallergie": ["", "nein", "", "nein"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 3], [2, 4]]  # Klasse 0 = Schulhund, 2 Unbekannte
    erwartet = 2 * STRAFE_SCHULHUND_VERLETZUNG
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == erwartet


def test_keine_strafe_wenn_spalte_fehlt():
    df = pd.DataFrame({"Vorname": ["A", "B"]}, index=[1, 2])
    einteilung = [[1], [2]]
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == 0.0


def test_keine_strafe_wenn_klasse_none():
    df = pd.DataFrame({
        "Hundehaarallergie": ["ja", "ja"],
    }, index=[1, 2])
    einteilung = [[1, 2]]
    assert _schulhund_strafe(einteilung, df, None, STRAFE_SCHULHUND_VERLETZUNG) == 0.0
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
pytest tests/test_optimierung_wrapper.py -v
```
Expected: FAIL mit `ImportError`.

- [ ] **Step 3: `_schulhund_strafe` und Konstante implementieren**

In `backend/optimierung_wrapper.py`, nach `FORTSCHRITT_INTERVALL = 500` (Zeile 67) einfügen:

```python
STRAFE_SCHULHUND_VERLETZUNG = -100.0


def _schulhund_strafe(
    einteilung: list,
    df: pd.DataFrame,
    schulhund_klasse: int | None,
    strafe_pro_kind: float,
) -> float:
    """
    Strafpunkte für Allergiker/Unbekannte in der Schulhund-Klasse.
    Returns: negativer Wert oder 0.0.
    """
    if schulhund_klasse is None:
        return 0.0
    from backend.schulhund import SPALTE, normalisiere_allergie_wert
    if SPALTE not in df.columns:
        return 0.0
    if schulhund_klasse < 0 or schulhund_klasse >= len(einteilung):
        return 0.0

    strafe = 0.0
    for sid in einteilung[schulhund_klasse]:
        if sid not in df.index:
            continue
        wert = normalisiere_allergie_wert(df.at[sid, SPALTE])
        if wert != "nein":  # 'ja' oder '' → Strafe
            strafe += strafe_pro_kind
    return strafe
```

- [ ] **Step 4: Tests laufen lassen — müssen grün sein**

```bash
pytest tests/test_optimierung_wrapper.py -v
```
Expected: alle PASS.

- [ ] **Step 5: `optimiere_mit_sprengel` um `schulhund_klasse`-Parameter erweitern**

Bestehender Code in `backend/optimierung_wrapper.py:70-130` (`optimiere_mit_sprengel`) wird wie folgt geändert:

Signatur erweitern (Zeile ~70-77):
```python
def optimiere_mit_sprengel(
    einteilung: list,
    df: pd.DataFrame,
    gesamt_stats: dict,
    anzahl_klassen: int,
    fortschritt_callback: Callable[[int, float, float], None] | None = None,
    schulhund_klasse: int | None = None,
    **kwargs,
) -> tuple[list, float]:
```

Innerhalb der Funktion, in `bewertung_mit_fortschritt` (aktuell ab Zeile ~101), die Berechnung erweitern. **Ersetze** den bestehenden Block:

```python
    def bewertung_mit_fortschritt(einteilung, df, gesamt_stats):
        if hat_sprengel:
            score = original_bewertung(einteilung, df, gesamt_stats)
            score += _sprengel_bonus(einteilung, df, PUNKTE_SPRENGEL_GLEICH)
        else:
            score = original_bewertung(einteilung, df, gesamt_stats)
```

**Durch:**

```python
    def bewertung_mit_fortschritt(einteilung, df, gesamt_stats):
        score = original_bewertung(einteilung, df, gesamt_stats)
        if hat_sprengel:
            score += _sprengel_bonus(einteilung, df, PUNKTE_SPRENGEL_GLEICH)
        if schulhund_klasse is not None:
            score += _schulhund_strafe(
                einteilung, df, schulhund_klasse, STRAFE_SCHULHUND_VERLETZUNG
            )
```

- [ ] **Step 6: Vollständige Test-Suite laufen lassen**

```bash
pytest tests/ -v
```
Expected: alle PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/optimierung_wrapper.py tests/test_optimierung_wrapper.py
git commit -m "feat(optimierung): Schulhund-Strafe als Score-Penalty im Wrapper"
```

---

## Task 5: Post-Processing `_erzwinge_schulhund_klasse`

**Files:**
- Modify: `backend/schulhund.py`
- Test: `tests/test_schulhund.py` (erweitern)

- [ ] **Step 1: Failing Test schreiben**

In `tests/test_schulhund.py` am Ende anhängen:

```python
from backend.schulhund import erzwinge_schulhund_klasse


class TestErzwingeSchulhundKlasse:
    def test_keine_aenderung_wenn_klasse_sauber(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["nein", "nein", "ja", "ja"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        assert neu == [[1, 2], [3, 4]]
        assert log == []

    def test_tauscht_allergiker_raus(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]  # Klasse 0 (Schulhund): hat Allergiker 1
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        # Klasse 0 darf keinen Allergiker mehr haben
        klasse_0 = neu[0]
        for sid in klasse_0:
            assert df.at[sid, "Hundehaarallergie"] != "ja"
            assert df.at[sid, "Hundehaarallergie"] != ""
        # Klassengrößen erhalten
        assert sorted(len(k) for k in neu) == [2, 2]
        # Log enthält einen Tausch-Eintrag
        assert len(log) == 1
        assert log[0]["status"] == "ok"

    def test_tauscht_unbekannte_raus(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        for sid in neu[0]:
            assert df.at[sid, "Hundehaarallergie"] == "nein"
        assert len(log) == 1

    def test_respektiert_trennungen(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        # Trennungspaar: 2 und 3 dürfen nicht zusammen → Tausch (1,3) wäre okay,
        # Tausch (1,4) auch — beide erlaubt. Hauptsache: kein Crash.
        trennungspaare = {frozenset({2, 3})}
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, trennungspaare)
        for sid in neu[0]:
            assert df.at[sid, "Hundehaarallergie"] == "nein"
        # Trennung muss eingehalten bleiben
        for paar in trennungspaare:
            a, b = sorted(paar)
            klasse_a = next(i for i, k in enumerate(neu) if a in k)
            klasse_b = next(i for i, k in enumerate(neu) if b in k)
            assert klasse_a != klasse_b

    def test_fehler_wenn_kein_partner_verfuegbar(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "ja", "ja", "ja"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        # Keine Tausch-Partner verfügbar → Allergiker bleiben, Log mit Fehler
        assert any(eintrag["status"] == "fehler" for eintrag in log)

    def test_keine_aenderung_wenn_klasse_none(self):
        df = pd.DataFrame({"Hundehaarallergie": ["ja"]}, index=[1])
        einteilung = [[1]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, None, set())
        assert neu == [[1]]
        assert log == []

    def test_keine_aenderung_wenn_spalte_fehlt(self):
        df = pd.DataFrame({"Vorname": ["A"]}, index=[1])
        einteilung = [[1]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        assert neu == [[1]]
        assert log == []
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
pytest tests/test_schulhund.py -v
```
Expected: FAIL — `erzwinge_schulhund_klasse` existiert noch nicht.

- [ ] **Step 3: `erzwinge_schulhund_klasse` implementieren**

In `backend/schulhund.py` am Ende anhängen:

```python
def erzwinge_schulhund_klasse(
    einteilung: list[list[int]],
    df: pd.DataFrame,
    schulhund_klasse: int | None,
    trennungspaare: set,
) -> tuple[list[list[int]], list[dict]]:
    """
    Tauscht Allergiker/Unbekannte aus der Schulhund-Klasse mit
    Nicht-Allergikern aus anderen Klassen.

    Args:
        einteilung: Liste von Listen mit Schüler-IDs pro Klasse.
        df: DataFrame mit Schülerdaten (mit 'Hundehaarallergie'-Spalte).
        schulhund_klasse: 0-basierter Index der Schulhund-Klasse oder None.
        trennungspaare: Set von frozensets — bei Tausch darf kein Paar
            zusammen landen.

    Returns:
        (neue_einteilung, log) — log ist eine Liste von dicts mit Feldern
        'schueler_id', 'name', 'von_klasse', 'nach_klasse', 'grund', 'status'.
        status ist 'ok' (Tausch erfolgreich) oder 'fehler' (kein Partner).
    """
    if schulhund_klasse is None:
        return einteilung, []
    if SPALTE not in df.columns:
        return einteilung, []
    if schulhund_klasse < 0 or schulhund_klasse >= len(einteilung):
        return einteilung, []

    klassen = [list(k) for k in einteilung]
    log: list[dict] = []

    def name_von(sid: int) -> str:
        if sid not in df.index:
            return str(sid)
        v = df.at[sid, "Vorname"] if "Vorname" in df.columns else ""
        n = df.at[sid, "Name"] if "Name" in df.columns else ""
        return f"{v} {n}".strip() or str(sid)

    def schueler_klasse(sid: int) -> int | None:
        for i, k in enumerate(klassen):
            if sid in k:
                return i
        return None

    def tausch_verletzt_trennung(sid_a: int, sid_b: int, ziel_a: int, ziel_b: int) -> bool:
        """Prüft, ob nach dem Tausch eines der Trennungspaare zusammen landet."""
        # Simuliere neue Zuordnung
        sim = [list(k) for k in klassen]
        sim[ziel_a].remove(sid_a)
        sim[ziel_b].remove(sid_b)
        sim[ziel_a].append(sid_b)
        sim[ziel_b].append(sid_a)
        for paar in trennungspaare:
            a, b = tuple(paar)
            ka = next((i for i, k in enumerate(sim) if a in k), None)
            kb = next((i for i, k in enumerate(sim) if b in k), None)
            if ka is not None and ka == kb:
                return True
        return False

    # Wiederhole, bis kein Allergiker/Unbekannter mehr in der Schulhund-Klasse ist
    while True:
        kandidaten = [
            sid for sid in klassen[schulhund_klasse]
            if not darf_in_schulhund_klasse(df.at[sid, SPALTE] if sid in df.index else "")
        ]
        if not kandidaten:
            break

        sid_raus = kandidaten[0]

        # Finde Tausch-Partner: Nicht-Allergiker in anderer Klasse,
        # bevorzugt aus kleinster Klasse (= Größenausgleich).
        andere_klassen = sorted(
            (i for i in range(len(klassen)) if i != schulhund_klasse),
            key=lambda i: len(klassen[i]),
        )

        partner_gefunden = None
        partner_klasse_idx = None

        for kidx in andere_klassen:
            for sid_rein in klassen[kidx]:
                if sid_rein not in df.index:
                    continue
                if not darf_in_schulhund_klasse(df.at[sid_rein, SPALTE]):
                    continue
                # Tausch-Simulation für Trennungs-Check
                if tausch_verletzt_trennung(sid_raus, sid_rein, schulhund_klasse, kidx):
                    continue
                partner_gefunden = sid_rein
                partner_klasse_idx = kidx
                break
            if partner_gefunden is not None:
                break

        if partner_gefunden is None:
            log.append({
                "schueler_id": sid_raus,
                "name": name_von(sid_raus),
                "von_klasse": schulhund_klasse + 1,
                "nach_klasse": None,
                "grund": "kein gültiger Tausch-Partner verfügbar",
                "status": "fehler",
            })
            # Diesen Allergiker überspringen, mit nächstem weitermachen
            klassen[schulhund_klasse].remove(sid_raus)
            klassen[schulhund_klasse].append(sid_raus)  # Reihenfolge ändern, damit Loop terminiert
            # Falls dieser bereits markiert war, sind alle anderen auch nicht-tauschbar
            if all(not darf_in_schulhund_klasse(
                df.at[s, SPALTE] if s in df.index else ""
            ) for s in klassen[schulhund_klasse]):
                # Alle Allergiker konnten nicht getauscht werden → wir sind fertig
                break
            continue

        # Tausch durchführen
        klassen[schulhund_klasse].remove(sid_raus)
        klassen[partner_klasse_idx].remove(partner_gefunden)
        klassen[schulhund_klasse].append(partner_gefunden)
        klassen[partner_klasse_idx].append(sid_raus)

        log.append({
            "schueler_id": sid_raus,
            "name": name_von(sid_raus),
            "von_klasse": schulhund_klasse + 1,
            "nach_klasse": partner_klasse_idx + 1,
            "grund": (
                "Hundehaarallergie" if normalisiere_allergie_wert(df.at[sid_raus, SPALTE]) == "ja"
                else "Allergie-Status unbekannt"
            ),
            "status": "ok",
        })

    return klassen, log
```

Hinweis: Der innere Mechanismus „falls alle nicht-tauschbar → break" verhindert die Endlosschleife im Fehlerfall.

- [ ] **Step 4: Tests laufen lassen — müssen grün sein**

```bash
pytest tests/test_schulhund.py -v
```
Expected: alle PASS.

- [ ] **Step 5: Vollständige Suite**

```bash
pytest tests/ -v
```
Expected: alle PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/schulhund.py tests/test_schulhund.py
git commit -m "feat(schulhund): Hard-Rule Post-Processing zur Erzwingung der Schulhund-Klasse"
```

---

## Task 6: Qualitätsprüfung erweitern

**Files:**
- Modify: `backend/pruefungen/qualitaet.py`
- Test: `tests/test_pruefungen.py` (neu)

- [ ] **Step 1: Failing Test schreiben**

`tests/test_pruefungen.py`:
```python
"""Unit-Tests für das Schulhund-Kriterium in der Qualitätsprüfung."""

import pandas as pd
import pytest

from backend.pruefungen.qualitaet import pruefe_einteilung


def _mini_df(allergien: list[str]) -> pd.DataFrame:
    n = len(allergien)
    return pd.DataFrame({
        "Vorname": [f"V{i}" for i in range(n)],
        "Name": [f"N{i}" for i in range(n)],
        "Geschlecht": ["m" if i % 2 == 0 else "w" for i in range(n)],
        "Auffaelligkeit_Score": [0] * n,
        "Migrationshintergrund / 2. Staatsangehörigkeit": ["Nein"] * n,
        "Hundehaarallergie": allergien,
    }, index=list(range(1, n + 1)))


def test_ampel_na_wenn_klasse_none():
    df = _mini_df(["nein", "nein", "ja", "ja"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=None)
    for kp in ergebnis.klassen:
        assert kp.schulhund_ampel == "n/a"
    assert ergebnis.schulhund_klasse_index is None


def test_ampel_na_wenn_spalte_fehlt():
    df = _mini_df(["nein", "nein", "ja", "ja"]).drop(columns=["Hundehaarallergie"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    for kp in ergebnis.klassen:
        assert kp.schulhund_ampel == "n/a"


def test_ampel_gruen_wenn_klasse_sauber():
    df = _mini_df(["nein", "nein", "ja", "ja"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "gruen"
    assert ergebnis.klassen[0].schulhund_allergiker == 0
    assert ergebnis.klassen[0].schulhund_unbekannt == 0
    assert ergebnis.klassen[0].ist_schulhund_klasse is True
    # Andere Klassen: gruen (haben keine Verpflichtung)
    assert ergebnis.klassen[1].schulhund_ampel == "gruen"
    assert ergebnis.klassen[1].ist_schulhund_klasse is False
    assert ergebnis.schulhund_klasse_index == 0


def test_ampel_rot_wenn_allergiker_drin():
    df = _mini_df(["ja", "nein", "nein", "nein"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "rot"
    assert ergebnis.klassen[0].schulhund_allergiker == 1


def test_ampel_rot_wenn_unbekannt_drin():
    df = _mini_df(["", "nein", "nein", "nein"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "rot"
    assert ergebnis.klassen[0].schulhund_unbekannt == 1
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
pytest tests/test_pruefungen.py -v
```
Expected: FAIL — Felder existieren nicht, Parameter wird abgelehnt.

- [ ] **Step 3: `KlassenPruefung` Dataclass erweitern**

In `backend/pruefungen/qualitaet.py:53-103` (`KlassenPruefung`), nach dem Block für „Laufpartner" einfügen:

```python
    # Schulhund
    ist_schulhund_klasse: bool = False
    schulhund_allergiker: int = 0
    schulhund_unbekannt: int = 0
    schulhund_ampel: str = "n/a"
```

- [ ] **Step 4: `GesamtPruefung` Dataclass erweitern**

In `backend/pruefungen/qualitaet.py:106-111`:

```python
@dataclass
class GesamtPruefung:
    """Gesamtergebnis über alle Klassen."""
    klassen: list  # Liste von KlassenPruefung
    gesamt_ampel: str = "gruen"  # schlechteste Ampel über alle Kriterien
    zusammenfassung: dict = field(default_factory=dict)
    schulhund_klasse_index: int | None = None
```

- [ ] **Step 5: `pruefe_einteilung` Signatur und Logik erweitern**

In `backend/pruefungen/qualitaet.py:133`:

```python
def pruefe_einteilung(
    einteilung: list,
    df: pd.DataFrame,
    schulhund_klasse: int | None = None,
) -> GesamtPruefung:
```

Im Loop über die Klassen (nach dem Laufpartner-Block, vor `klassen_pruefungen.append(kp)`, also vor Zeile 308) einfügen:

```python
        # --- 8. Schulhund ---
        from backend.schulhund import SPALTE as SCHULHUND_SPALTE, zaehle_allergiker_in_klasse
        if schulhund_klasse is None or SCHULHUND_SPALTE not in df.columns:
            kp.schulhund_ampel = "n/a"
        else:
            kp.ist_schulhund_klasse = (i == schulhund_klasse)
            if kp.ist_schulhund_klasse:
                allergiker, unbekannt = zaehle_allergiker_in_klasse(klasse_ids, df)
                kp.schulhund_allergiker = allergiker
                kp.schulhund_unbekannt = unbekannt
                kp.schulhund_ampel = "gruen" if (allergiker == 0 and unbekannt == 0) else "rot"
                alle_ampeln.append(kp.schulhund_ampel)
            else:
                kp.schulhund_ampel = "gruen"
```

Direkt vor `return GesamtPruefung(...)` (Zeile 346):

```python
    return GesamtPruefung(
        klassen=klassen_pruefungen,
        gesamt_ampel=gesamt_ampel,
        zusammenfassung=zusammenfassung,
        schulhund_klasse_index=schulhund_klasse,
    )
```

- [ ] **Step 6: Tests laufen lassen — müssen grün sein**

```bash
pytest tests/test_pruefungen.py -v
```
Expected: alle PASS.

- [ ] **Step 7: Vollständige Suite**

```bash
pytest tests/ -v
```
Expected: alle PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/pruefungen/qualitaet.py tests/test_pruefungen.py
git commit -m "feat(pruefung): Schulhund-Ampel-Kriterium für Qualitätsprüfung"
```

---

## Task 7: Routes / API / State

**Files:**
- Modify: `backend/api/routes.py`

Wir verkabeln in dieser einen Datei alles: State-Feld, Pydantic-Modelle, Schülerliste-Output, Optimierungs-Query-Param, Wrapper-Aufruf, Post-Processing-Aufruf, Verschieben-Endpunkt, Pruefung-Aufrufe, Persistenz.

- [ ] **Step 1: State-Feld ergänzen**

In `backend/api/routes.py:60-67` (`_state` dict), neuen Eintrag hinzufügen:

```python
_state = {
    "df": None,
    "einteilung": None,
    "pruefung": None,
    "upload_path": None,
    "raw_spalten": None,
    "mapping_vorschlaege": None,
    "schulhund_klasse": None,
}
```

- [ ] **Step 2: `WunschZuordnung` um `hundehaarallergie` erweitern**

In `backend/api/routes.py:82-90` (`WunschZuordnung`):

```python
class WunschZuordnung(BaseModel):
    schueler_id: int
    wuensche: list[int] = []
    trennen_von: list[int] = []
    geschlecht: str | None = None
    auffaelligkeit: int | None = None
    migration: str | None = None
    hundehaarallergie: str | None = None
```

- [ ] **Step 3: Schülerliste-Output erweitern**

In `backend/api/routes.py:264-302` (`_schueler_liste_aus_df`), nach `sprengel = …` (Zeile 289) und vor dem `schueler.append({...})` (Zeile 291):

```python
        from backend.schulhund import SPALTE as SCHULHUND_SPALTE, normalisiere_allergie_wert
        hundehaarallergie = ""
        if SCHULHUND_SPALTE in df.columns:
            hundehaarallergie = normalisiere_allergie_wert(row.get(SCHULHUND_SPALTE, ""))
```

Im `schueler.append({...})`-Block neues Feld hinzufügen:
```python
            "hundehaarallergie": hundehaarallergie,
```

- [ ] **Step 4: Stammdaten-Korrektur in `/wuensche-speichern` erweitern**

In `backend/api/routes.py:494-540` (`wuensche_speichern`), im Block „Stammdaten-Korrekturen übernehmen" (nach dem `migration`-If, vor dem `# 2. Wünsche/Trennungen einfügen`-Kommentar), einfügen:

```python
        if z.hundehaarallergie is not None:
            from backend.schulhund import SPALTE as SCHULHUND_SPALTE, normalisiere_allergie_wert
            if SCHULHUND_SPALTE not in df.columns:
                df[SCHULHUND_SPALTE] = ""
            df.at[sid, SCHULHUND_SPALTE] = normalisiere_allergie_wert(z.hundehaarallergie)
```

- [ ] **Step 5: Optimierungs-Endpunkt: Query-Param + Wrapper-Aufruf + Post-Processing**

In `backend/api/routes.py:547-644` (`starte_optimierung`):

Signatur ergänzen (Zeile 548-553):
```python
@router.post("/optimierung")
def starte_optimierung(
    anzahl_klassen: int = ANZAHL_KLASSEN,
    iterationen: int = OPT_ITERATIONEN,
    start_temp: float = OPT_START_TEMPERATUR,
    cooling_rate: float = OPT_COOLING_RATE,
    schulhund_klasse: int | None = None,
):
```

Direkt nach dem Check, ob `_state["df"] is None`:
```python
    # Schulhund-Klasse validieren
    if schulhund_klasse is not None and (schulhund_klasse < 0 or schulhund_klasse >= anzahl_klassen):
        raise HTTPException(
            status_code=400,
            detail=f"Schulhund-Klassen-Index {schulhund_klasse} liegt außerhalb [0, {anzahl_klassen - 1}].",
        )
    _state["schulhund_klasse"] = schulhund_klasse
```

`optimiere_mit_sprengel`-Aufruf (innerhalb `optimierung_thread`, aktuell Zeile ~583) erweitern um `schulhund_klasse`:
```python
            finale_einteilung, finaler_score = optimiere_mit_sprengel(
                start_einteilung, df_algo, gesamtstatistiken, anzahl_klassen,
                fortschritt_callback=fortschritt_callback,
                iterationen=iterationen,
                start_temp=start_temp,
                cooling_rate=cooling_rate,
                schulhund_klasse=schulhund_klasse,
            )
```

**Nach** `_erzwinge_trennungen(...)` (aktuell Zeile 592) und **vor** `_state["einteilung"] = finale_einteilung`, einfügen:
```python
            # Harte Regel: Schulhund-Klasse darf keine Allergiker/Unbekannten enthalten
            from backend.schulhund import erzwinge_schulhund_klasse
            trennungspaare = _alle_trennungspaare(df)
            finale_einteilung, schulhund_log = erzwinge_schulhund_klasse(
                finale_einteilung, df, schulhund_klasse, trennungspaare
            )
```

Pruefung-Aufruf erweitern:
```python
            pruefung = pruefe_einteilung(finale_einteilung, df, schulhund_klasse=schulhund_klasse)
```

Im `antwort`-Dict, **nach** dem `if trenn_log: antwort["trennungen_erzwungen"] = trenn_log`-Block (Zeile ~609):
```python
            if schulhund_log:
                antwort["schulhund_verschoben"] = schulhund_log
```

- [ ] **Step 6: `/verschieben`-Endpunkt: Schulhund-Verletzung melden**

In `backend/api/routes.py:651-712` (`verschiebe_schueler`):

**Nach** dem Trennungs-Verletzungs-Block (nach Zeile 696, vor `_state["einteilung"] = neue_einteilung`):

```python
    # Schulhund-Verletzungen sammeln
    schulhund_verletzt = []
    schulhund_klasse_idx = _state.get("schulhund_klasse")
    if schulhund_klasse_idx is not None and "Hundehaarallergie" in df.columns:
        from backend.schulhund import normalisiere_allergie_wert, darf_in_schulhund_klasse, SPALTE
        if 0 <= schulhund_klasse_idx < len(neue_einteilung):
            for sid in neue_einteilung[schulhund_klasse_idx]:
                wert = normalisiere_allergie_wert(df.at[sid, SPALTE]) if sid in df.index else ""
                if not darf_in_schulhund_klasse(wert):
                    name = f"{df.at[sid, 'Vorname']} {df.at[sid, 'Name']}".strip() if sid in df.index else str(sid)
                    schulhund_verletzt.append({
                        "schueler": {"id": int(sid), "name": name},
                        "status": "ja" if wert == "ja" else "unbekannt",
                    })
```

Pruefung-Aufruf erweitern (Zeile ~700):
```python
    pruefung = pruefe_einteilung(neue_einteilung, df, schulhund_klasse=schulhund_klasse_idx)
```

Im `antwort`-Dict, am Ende (vor `return antwort`):
```python
    if schulhund_verletzt:
        antwort["schulhund_verletzt"] = schulhund_verletzt
```

- [ ] **Step 7: Persistenz erweitern (Speichern + Laden)**

In `backend/api/routes.py:822-847` (`save_assignment`), im `data`-Dict einen Eintrag hinzufügen:
```python
    data = {
        "id": file_id,
        "name": body.name,
        "timestamp": timestamp,
        "einteilung": _state["einteilung"],
        "schulhund_klasse": _state.get("schulhund_klasse"),
        "df_json": _state["df"].to_dict(orient="split")
    }
```

In `backend/api/routes.py:872-917` (`load_assignment`):

Nach `_state["einteilung"] = data.get("einteilung")` (Zeile ~894):
```python
        _state["schulhund_klasse"] = data.get("schulhund_klasse")
```

Im Block, wo `_state["einteilung"]` vorhanden ist, `pruefe_einteilung` mit Parameter aufrufen:
```python
        if _state["einteilung"]:
            _state["pruefung"] = pruefe_einteilung(
                _state["einteilung"], df, schulhund_klasse=_state["schulhund_klasse"]
            )
```

Im `return`-Dict am Ende:
```python
        return {
            "status": "ok",
            "anzahl_schueler": len(df),
            "klassen": klassen,
            "pruefung": pruefung_dict,
            "hat_einteilung": _state["einteilung"] is not None,
            "schulhund_klasse": _state["schulhund_klasse"],
            "schueler": _schueler_liste_aus_df(df) if not _state["einteilung"] else []
        }
```

- [ ] **Step 8: Manueller Smoke-Test gegen den Server**

```bash
uvicorn backend.app:app --port 8000
```
In zweitem Terminal:
```bash
curl http://localhost:8000/docs
```
Im Browser `/docs` öffnen, prüfen: `/optimierung` hat den neuen `schulhund_klasse`-Param, kein Crash bei Import.

- [ ] **Step 9: Pytest-Suite (Smoke)**

```bash
pytest tests/ -v
```
Expected: alle PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/api/routes.py
git commit -m "feat(api): Schulhund-Klasse als Query-Param, State und Persistenz"
```

---

## Task 8: Excel-Export erweitern

**Files:**
- Modify: `backend/api/routes.py:735-797` (`exportiere_excel`)

- [ ] **Step 1: Schulhund-Spalten im Pruefung-Sheet hinzufügen**

In `backend/api/routes.py`, in `exportiere_excel`, im Block, wo `pruef_daten` aufgebaut wird (Zeile ~766-788), am Ende des inneren dicts (vor dem schließenden `})`) einfügen:

```python
                "Schulhund (Allergiker)": kp.schulhund_allergiker if kp.ist_schulhund_klasse else "",
                "Schulhund (Unbekannt)": kp.schulhund_unbekannt if kp.ist_schulhund_klasse else "",
                "Schulhund": kp.schulhund_ampel if kp.ist_schulhund_klasse else "",
```

- [ ] **Step 2: Manueller Test**

Server starten, eine Testdatei mit `Hundehaarallergie`-Spalte hochladen, Optimierung mit `schulhund_klasse=0` laufen lassen, Excel-Export herunterladen und prüfen, ob das `Pruefung`-Sheet die neuen Spalten enthält und für Klasse 0 gefüllt sind.

- [ ] **Step 3: Commit**

```bash
git add backend/api/routes.py
git commit -m "feat(export): Schulhund-Ampel-Spalten im Pruefung-Sheet"
```

---

## Task 9: Frontend — HTML (Dropdown + Tabellen-Spalte)

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Schulhund-Dropdown im Konfigurations-Panel**

In `frontend/index.html` nach dem `iterationen`-Block (Zeile 40-43) und vor dem `startBtn` (Zeile 45) einfügen:

```html
                <div class="config-group">
                    <label for="schulhundKlasse">Schulhund-Klasse:</label>
                    <select id="schulhundKlasse">
                        <option value="">— keine —</option>
                    </select>
                </div>
```

- [ ] **Step 2: Hinweistext unter dem Dropdown**

Direkt nach dem `</select>`/`</div>` aus Step 1, vor `startBtn`:

```html
                <p class="schulhund-hint">
                    Die gewählte Klasse bleibt frei von Schülern mit Hundehaarallergie oder fehlender Angabe.
                </p>
```

- [ ] **Step 3: Neue Spalte „Allergie" in der Schülerliste-Tabelle**

In `frontend/index.html:110-120` (Tabellen-Header), neue Spalte zwischen `Sprengel` und `Wunschpartner` einfügen:

```html
                            <th class="col-allergie">Hund-Allergie</th>
```

- [ ] **Step 4: Browser-Smoke-Test**

Server starten, Browser laden, prüfen ob Dropdown und neue Tabellenspalte sichtbar sind.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): Schulhund-Dropdown und Allergie-Spalte in der Schülerliste"
```

---

## Task 10: Frontend — JavaScript

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: DOM-Referenzen ergänzen**

Im Top-Block, wo DOM-Referenzen geholt werden (Bereich um Zeile 80-90), nach `anzahlKlassen` (falls vorhanden — `anzahlKlassen` ist im HTML ein `<input>`-Element, daher per `getElementById` ansprechbar):

Suche die Stelle mit `const anzahlKlassen = document.getElementById("anzahlKlassen");` (falls existiert; falls nicht: füge sie zu den DOM-Refs hinzu).

Füge danach hinzu:
```javascript
const schulhundKlasse = document.getElementById("schulhundKlasse");
```

- [ ] **Step 2: Dropdown-Optionen synchron zur Klassenanzahl füllen**

Direkt nach den DOM-Refs eine Hilfsfunktion definieren und auf das `change`-Event des Anzahl-Inputs hängen:

```javascript
function aktualisiereSchulhundDropdown() {
    const anzahl = parseInt(anzahlKlassen.value, 10) || 0;
    const vorherigerWert = schulhundKlasse.value;
    schulhundKlasse.innerHTML = '<option value="">— keine —</option>';
    for (let i = 0; i < anzahl; i++) {
        const buchstabe = String.fromCharCode(65 + i); // A, B, C, ...
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = buchstabe;
        schulhundKlasse.appendChild(opt);
    }
    // Bei Änderung der Klassen-Anzahl IMMER zurücksetzen
    schulhundKlasse.value = "";
}

anzahlKlassen.addEventListener("change", aktualisiereSchulhundDropdown);
aktualisiereSchulhundDropdown();
```

- [ ] **Step 3: Schulhund-Klasse beim Start der Optimierung mitschicken**

In `frontend/app.js:604-609` (`URLSearchParams`-Aufbau in `starteOptimierung`):

```javascript
        const paramsObj = {
            anzahl_klassen: anzahlKlassen.value,
            iterationen: iterationen.value,
        };
        if (schulhundKlasse.value !== "") {
            paramsObj.schulhund_klasse = schulhundKlasse.value;
        }
        const params = new URLSearchParams(paramsObj);
```

(Falls der bestehende Code anders aussieht, das Objekt entsprechend anpassen — Hauptsache: bei leerem Wert wird `schulhund_klasse` nicht mitgeschickt.)

- [ ] **Step 4: Allergie-Spalte in der Schülerliste-Tabelle rendern**

In `frontend/app.js`, in der Render-Funktion für die Schüler-Tabelle (Bereich um Zeile 310-330, dort wo die `<td>`s gebaut werden), zwischen der `col-sprengel`- und der `col-wuensche`-Zelle einfügen:

```javascript
            `<td class="col-allergie">
                <select class="allergie-select" data-schueler-id="${s.id}">
                    <option value="" ${s.hundehaarallergie === "" ? "selected" : ""}>?</option>
                    <option value="nein" ${s.hundehaarallergie === "nein" ? "selected" : ""}>nein</option>
                    <option value="ja" ${s.hundehaarallergie === "ja" ? "selected" : ""}>ja</option>
                </select>
            </td>`
```

- [ ] **Step 5: Allergie-Wert beim Speichern mitschicken**

In `frontend/app.js`, in der `confirmDataBtn`-Handler-Funktion, dort wo pro Schüler die Zuordnung gebaut wird (Bereich um Zeile 500-520), den `allergie`-Wert mitnehmen:

```javascript
        const allergieSel = document.querySelector(
            `.allergie-select[data-schueler-id="${s.id}"]`
        );
        const hundehaarallergie = allergieSel ? allergieSel.value : "";
```

Im `zuordnungen.push({...})`-Block:
```javascript
            hundehaarallergie: hundehaarallergie,
```

- [ ] **Step 6: Warnung anzeigen, wenn `schulhund_verletzt` im Drag-&-Drop-Response**

In `frontend/app.js`, in der Funktion, die `/api/verschieben` aufruft (suche nach `/verschieben`), nach dem Erhalt der Antwort:

```javascript
        if (data.schulhund_verletzt && data.schulhund_verletzt.length > 0) {
            const namen = data.schulhund_verletzt.map(v =>
                `${v.schueler.name} (${v.status})`
            ).join(", ");
            alert(
                `⚠️ Schulhund-Klasse: ${namen}\n\n` +
                `Diese Schüler haben eine Allergie oder unbekannten Status und sollten nicht in der Schulhund-Klasse sein.`
            );
        }
```

- [ ] **Step 7: Schulhund-Klassen-Index aus geladenem Assignment vorbelegen**

In `frontend/app.js`, in der Funktion, die ein gespeichertes Assignment lädt (suche nach `/assignments/${`), nach dem erfolgreichen Laden:

```javascript
        if (data.schulhund_klasse !== null && data.schulhund_klasse !== undefined) {
            schulhundKlasse.value = String(data.schulhund_klasse);
        } else {
            schulhundKlasse.value = "";
        }
```

- [ ] **Step 8: Klassen-Banner und Markierung beim Rendern der Klassen-Karten**

In `frontend/app.js`, in der Render-Funktion für das Klassen-Grid (suche nach Stellen, die `klassen.forEach` oder `klassen.map` nutzen), für jede Klassen-Karte:

```javascript
        const istSchulhund = pruefung && pruefung.schulhund_klasse_index === klassenIndex;
        const klasseClass = istSchulhund ? "klasse-karte klasse-schulhund" : "klasse-karte";
        // ... <div class="${klasseClass}"> ... 
        // Im Header der Karte:
        const header = istSchulhund
            ? `<h3>🐕 Klasse ${name} <small>(Schulhund)</small></h3>`
            : `<h3>Klasse ${name}</h3>`;
```

Für jeden Schüler innerhalb der Karte:
```javascript
        const allergieKlasse = s.hundehaarallergie === "ja" ? " schueler-allergie"
                            : s.hundehaarallergie === "" ? " schueler-allergie-unbekannt" : "";
        const allergieIcon = s.hundehaarallergie === "ja" ? "🐕 "
                          : s.hundehaarallergie === "" ? "❓ " : "";
```

Diese Variablen dann in den jeweiligen Render-Strings nutzen.

(Hinweis: Die exakten Stellen variieren — Pattern: jede Stelle, an der eine Klassen-Karte oder eine Schüler-Karte gebaut wird, bekommt diese Anreicherung.)

- [ ] **Step 9: Browser-Smoke-Test**

Server starten, alte Datei laden → kein Crash, keine Allergie-Optionen. Neue Datei mit Allergie-Spalte laden → Dropdown auswählbar, Schüler-Editor zeigt Allergie-Select, Optimierung mit Schulhund-Klasse 0 → Klassen-Banner sichtbar.

- [ ] **Step 10: Commit**

```bash
git add frontend/app.js
git commit -m "feat(ui): Schulhund-Dropdown, Allergie-Editor und Klassen-Markierung"
```

---

## Task 11: Frontend — CSS

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Styles für Schulhund-Markierungen und Allergie-Icons**

Am Ende von `frontend/style.css` anhängen:

```css
/* === Schulhund-Allergie === */
.schulhund-hint {
    font-size: 0.85rem;
    color: var(--text-secondary, #666);
    margin: 0.25rem 0 0.5rem;
    flex-basis: 100%;
}

.klasse-schulhund {
    border: 2px solid #f5b921;
    box-shadow: 0 0 0 1px rgba(245, 185, 33, 0.2);
}

.klasse-schulhund h3 small {
    color: #b8860b;
    font-weight: normal;
    font-size: 0.75em;
}

.schueler-allergie {
    background-color: rgba(245, 185, 33, 0.08);
}

.schueler-allergie-unbekannt {
    background-color: rgba(128, 128, 128, 0.08);
}

.col-allergie {
    width: 90px;
}

.allergie-select {
    width: 100%;
    padding: 0.2rem;
    font-size: 0.9rem;
}
```

- [ ] **Step 2: Browser-Smoke-Test**

Server neu laden, prüfen: Schulhund-Klasse hat goldenen Rand, Allergiker-Schüler haben einen leichten Farbton, Dropdown sieht okay aus.

- [ ] **Step 3: Commit**

```bash
git add frontend/style.css
git commit -m "feat(ui): Styles für Schulhund-Klasse und Allergie-Marker"
```

---

## Task 12: E2E-Test

**Files:**
- Create: `test_schulhund_e2e.py` (Repo-Root, analog zu `test_persistence.py`)

- [ ] **Step 1: E2E-Test-Skript schreiben**

`test_schulhund_e2e.py`:

```python
"""E2E-Test für die Schulhund-Allergie-Funktion. Setzt einen laufenden Server voraus."""

import io
import json
import time
import uuid
from urllib import request
from urllib.error import HTTPError

import pandas as pd

BASE_URL = "http://localhost:8000/api"


def make_request(method, url, data=None, files=None, headers=None, stream=False):
    if headers is None:
        headers = {}
    if files:
        boundary = uuid.uuid4().hex
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
        body = []
        for name, (filename, content, mimetype) in files.items():
            body.extend([
                f'--{boundary}'.encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode(),
                f'Content-Type: {mimetype}'.encode(),
                b'',
                content,
            ])
        body.extend([f'--{boundary}--'.encode(), b''])
        data = b'\r\n'.join(body)
    elif data is not None:
        data = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'

    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        response = request.urlopen(req)
        if stream:
            return response
        content = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content
    except HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")
        raise


def baue_test_excel(allergien: list[str]) -> bytes:
    n = len(allergien)
    df = pd.DataFrame({
        "Vorname": [f"V{i}" for i in range(n)],
        "Name": [f"N{i}" for i in range(n)],
        "Geschlecht": ["m" if i % 2 == 0 else "w" for i in range(n)],
        "Auffaelligkeit_Score": [0] * n,
        "Migrationshintergrund / 2. Staatsangehörigkeit": ["Nein"] * n,
        "Hundehaarallergie": allergien,
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def upload_und_optimiere(allergien, schulhund_klasse, anzahl_klassen=2):
    excel_bytes = baue_test_excel(allergien)
    files = {"file": ("test.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = make_request("POST", f"{BASE_URL}/upload", files=files)
    assert res["braucht_mapping"] is False, "Spalten sollten automatisch erkannt werden"
    assert any(s["hundehaarallergie"] in ("ja", "nein", "") for s in res["schueler"])

    params = f"?anzahl_klassen={anzahl_klassen}&iterationen=1000"
    if schulhund_klasse is not None:
        params += f"&schulhund_klasse={schulhund_klasse}"
    stream = make_request("POST", f"{BASE_URL}/optimierung{params}", stream=True)
    ergebnis = None
    for line in stream:
        s = line.decode().strip()
        if s.startswith("data: "):
            ev = json.loads(s[6:])
            if ev.get("type") == "ergebnis":
                ergebnis = ev
                break
    assert ergebnis is not None
    return ergebnis


def test_1_optimierung_ohne_schulhund():
    print("Test 1: Optimierung ohne Schulhund-Klasse")
    ergebnis = upload_und_optimiere(["ja", "nein", "", "ja", "nein", "nein"], schulhund_klasse=None)
    for kp in ergebnis["pruefung"]["klassen"]:
        assert kp["schulhund_ampel"] == "n/a"
    print("  ✓")


def test_2_optimierung_mit_schulhund_klasse_a():
    print("Test 2: Optimierung mit Schulhund-Klasse A (Index 0)")
    ergebnis = upload_und_optimiere(["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=0)
    klasse_a = ergebnis["pruefung"]["klassen"][0]
    assert klasse_a["schulhund_ampel"] == "gruen", f"Erwartet gruen, ist {klasse_a['schulhund_ampel']}"
    assert klasse_a["schulhund_allergiker"] == 0
    assert klasse_a["schulhund_unbekannt"] == 0
    assert klasse_a["ist_schulhund_klasse"] is True
    print("  ✓")


def test_3_manuelle_verschiebung_loest_warnung_aus():
    print("Test 3: Manuelle Verschiebung eines Allergikers in die Schulhund-Klasse")
    # Setup wie Test 2
    upload_und_optimiere(["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=0)
    # Schüler-Liste holen
    schueler = make_request("GET", f"{BASE_URL}/schueler")["schueler"]
    allergiker_ids = [s["id"] for s in schueler if s["hundehaarallergie"] == "ja"]
    nein_ids = [s["id"] for s in schueler if s["hundehaarallergie"] == "nein"]
    assert len(allergiker_ids) >= 1 and len(nein_ids) >= 1

    # Neue Einteilung: Allergiker in Klasse A
    alle_ids = [s["id"] for s in schueler]
    klasse_a = [allergiker_ids[0]] + [sid for sid in nein_ids[:2]]
    klasse_b = [sid for sid in alle_ids if sid not in klasse_a]
    res = make_request("POST", f"{BASE_URL}/verschieben", data=[klasse_a, klasse_b])
    assert "schulhund_verletzt" in res, "Verletzung sollte gemeldet werden"
    assert any(v["schueler"]["id"] == allergiker_ids[0] for v in res["schulhund_verletzt"])
    print("  ✓")


def test_4_speichern_und_laden_erhaelt_schulhund_klasse():
    print("Test 4: Speichern + Laden erhält Schulhund-Klasse")
    upload_und_optimiere(["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=1)
    save = make_request("POST", f"{BASE_URL}/assignments", data={"name": f"Test_{int(time.time())}"})
    aid = save["id"]
    load = make_request("GET", f"{BASE_URL}/assignments/{aid}")
    assert load["schulhund_klasse"] == 1
    # Aufräumen
    make_request("DELETE", f"{BASE_URL}/assignments/{aid}")
    print("  ✓")


def test_5_zu_viele_allergiker_log_eintrag():
    print("Test 5: Zu viele Allergiker → Log-Eintrag mit status=fehler")
    # 2 Klassen à 3 Schüler. Alle Allergiker. Klasse 0 = Schulhund.
    # Keine Tausch-Partner verfügbar.
    ergebnis = upload_und_optimiere(["ja", "ja", "ja", "ja", "ja", "ja"], schulhund_klasse=0)
    # Es sollten Log-Einträge mit status=fehler kommen
    if "schulhund_verschoben" in ergebnis:
        assert any(e["status"] == "fehler" for e in ergebnis["schulhund_verschoben"])
    # Mindestens darf die Ampel rot sein
    assert ergebnis["pruefung"]["klassen"][0]["schulhund_ampel"] == "rot"
    print("  ✓")


def test_6_rueckwaertskompatibilitaet_ohne_allergie_spalte():
    print("Test 6: Datei ohne Allergie-Spalte funktioniert weiter")
    df = pd.DataFrame({
        "Vorname": ["A", "B", "C", "D"],
        "Name": ["x", "y", "z", "w"],
        "Geschlecht": ["m", "w", "m", "w"],
        "Auffaelligkeit_Score": [0, 0, 0, 0],
        "Migrationshintergrund / 2. Staatsangehörigkeit": ["Nein"] * 4,
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    files = {"file": ("alt.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = make_request("POST", f"{BASE_URL}/upload", files=files)
    assert res["braucht_mapping"] is False
    # Optimierung ohne schulhund_klasse
    params = "?anzahl_klassen=2&iterationen=500"
    stream = make_request("POST", f"{BASE_URL}/optimierung{params}", stream=True)
    ergebnis = None
    for line in stream:
        s = line.decode().strip()
        if s.startswith("data: "):
            ev = json.loads(s[6:])
            if ev.get("type") == "ergebnis":
                ergebnis = ev
                break
    assert ergebnis is not None
    for kp in ergebnis["pruefung"]["klassen"]:
        assert kp["schulhund_ampel"] == "n/a"
    print("  ✓")


if __name__ == "__main__":
    time.sleep(1)
    test_1_optimierung_ohne_schulhund()
    test_2_optimierung_mit_schulhund_klasse_a()
    test_3_manuelle_verschiebung_loest_warnung_aus()
    test_4_speichern_und_laden_erhaelt_schulhund_klasse()
    test_5_zu_viele_allergiker_log_eintrag()
    test_6_rueckwaertskompatibilitaet_ohne_allergie_spalte()
    print("\nALLE E2E-TESTS BESTANDEN!")
```

- [ ] **Step 2: E2E-Test laufen lassen**

Terminal 1:
```bash
uvicorn backend.app:app --port 8000
```
Terminal 2:
```bash
python test_schulhund_e2e.py
```
Expected: alle 6 Tests grün, Ausgabe „ALLE E2E-TESTS BESTANDEN!".

- [ ] **Step 3: Commit**

```bash
git add test_schulhund_e2e.py
git commit -m "test(e2e): Schulhund-Allergie End-to-End-Test"
```

---

## Task 13: Manueller Smoke-Test (Checkliste)

**Files:** keine.

- [ ] **Step 1: Server starten**

```bash
uvicorn backend.app:app --port 8000
```

- [ ] **Step 2: Vorlage prüfen**

Browser → Download Vorlage (xlsx) → öffnen → neue Spalte „Hundehaarallergie" mit Dropdown vorhanden, Anleitung erweitert.

- [ ] **Step 3: Alte Datei (ohne Allergie-Spalte)**

Bestehende `testdaten/Testliste_120_Schueler.xlsx` hochladen → Optimierung **ohne** Schulhund-Klasse läuft durch, Ampel-Kriterium taucht im UI nicht auf.

- [ ] **Step 4: Neue Datei mit Allergie-Spalte**

Vorlage ausfüllen (oder Testdatei generieren), hochladen → Allergie-Spalte erkannt, Schüler-Editor zeigt das neue Dropdown.

- [ ] **Step 5: Optimierung mit Schulhund-Klasse**

Klassen-Anzahl 5, Schulhund-Klasse „A" wählen, Optimierung starten → Klasse A bekommt goldenen Rand und Hund-Icon, alle Schüler in A sind „nein".

- [ ] **Step 6: Drag & Drop Verletzung**

Allergiker in Klasse A ziehen → Warnung erscheint.

- [ ] **Step 7: Speichern + Laden**

Einteilung speichern → Seite neu laden → gespeicherte Einteilung laden → Schulhund-Klasse-Dropdown ist vorbelegt, Markierung korrekt.

- [ ] **Step 8: Excel-Export**

Export herunterladen, in Excel öffnen → Pruefung-Sheet enthält neue Schulhund-Spalten, gefüllt für die markierte Klasse.

- [ ] **Step 9: Stammdaten-Korrektur**

Bei einem Schüler den Allergie-Status im UI ändern, Daten bestätigen, neu optimieren → Änderung wirksam.

- [ ] **Step 10: Klassenanzahl-Reset**

Schulhund-Klasse „C" wählen, dann Anzahl von 5 auf 3 ändern → Dropdown setzt sich auf `— keine —` zurück (verhindert ungültigen Index).

---

## Task 14: Merge in main

**Files:** keine — nur Git-Operationen.

- [ ] **Step 1: Sicherstellen, dass alle Tests grün sind**

```bash
pytest tests/ -v && echo "OK"
```
Expected: `OK`.

- [ ] **Step 2: Sicherstellen, dass alle Commits committed sind**

```bash
git status
```
Expected: `working tree clean`.

- [ ] **Step 3: Branch-History anschauen**

```bash
git log --oneline feature/schulhund-allergie ^main
```
Expected: alle Feature-Commits aufgelistet.

- [ ] **Step 4: Auf main wechseln und mergen**

```bash
git checkout main
git merge --no-ff feature/schulhund-allergie -m "feat: Schulhund-Allergie-Constraint"
```

- [ ] **Step 5: Branch löschen (optional, nach Bestätigung)**

```bash
git branch -d feature/schulhund-allergie
```

---

## Self-Review

**Spec coverage:**
- ✅ Spaltenmapping `Hundehaarallergie` → Task 2
- ✅ Normalisierung der Werte → Task 1, Task 2
- ✅ Vorlage erweitert → Task 3
- ✅ Score-Strafe im Wrapper → Task 4
- ✅ Hard-Rule Post-Processing → Task 5
- ✅ Pipeline-Reihenfolge (Trennungen → Schulhund → Pruefung) → Task 7 Step 5
- ✅ State + Query-Param + Wrapper + Post-Processing-Verkabelung → Task 7
- ✅ `/verschieben`-Warnung → Task 7 Step 6
- ✅ Pruefung: Dataclass-Felder + Logik + Signatur → Task 6
- ✅ Persistenz (Save + Load) → Task 7 Step 7
- ✅ Schülerliste-Output erweitert → Task 7 Step 3
- ✅ Excel-Export → Task 8
- ✅ Frontend HTML (Dropdown, Hinweis, Tabellen-Spalte) → Task 9
- ✅ Klassenanzahl-Reset des Dropdowns → Task 10 Step 2
- ✅ Frontend JS (Param, Editor, Warnung, Vorbelegung, Markierung) → Task 10
- ✅ Frontend CSS → Task 11
- ✅ E2E-Test → Task 12
- ✅ Smoke-Test-Checkliste → Task 13
- ✅ Branch-Strategie + Merge → Task 14

**Placeholder scan:** keine TBD/TODO/"add appropriate"-Phrasen.

**Type consistency:**
- `schulhund_klasse: int | None = None` durchgängig.
- `Hundehaarallergie` als Spaltenname durchgängig (in `backend/schulhund.SPALTE` als Konstante).
- `normalisiere_allergie_wert` Rückgabe `"ja"`/`"nein"`/`""` durchgängig.
- `erzwinge_schulhund_klasse` Signatur konsistent zwischen Task 5 und Task 7 Step 5.

**Coverage-Risiko:** Die Test-Funktion in Task 5 (`test_respektiert_trennungen`) testet das Verhalten weich — sie verifiziert nur, dass nach dem Tausch die Trennung nicht verletzt wird, nicht, dass der Tausch unbedingt stattfindet. Das ist okay, weil das Trennungs-Beispiel im Test nicht erzwungen zu einem Konflikt führt.
