# Schulhund-Allergie-Constraint

**Status:** Design freigegeben — bereit für Implementierungs-Planung
**Branch:** `feature/schulhund-allergie`
**Datum:** 2026-05-25

## Hintergrund

Eine Lehrerin hat einen Schulhund. In ihrer Klasse dürfen also nur Kinder sein, die garantiert keine Hundehaarallergie haben. Bei der Schüler-Befragung haben einige Eltern Angaben gemacht (`ja`/`nein`), andere haben nicht geantwortet — beide Gruppen (`Allergie=ja` **und** `Angabe fehlt`) müssen aus der Schulhund-Klasse rausgehalten werden.

## Anforderungen

1. **Hard rule:** Die Schulhund-Klasse muss am Ende der Optimierung **garantiert** 0 Allergiker und 0 Unbekannte enthalten — nicht „möglichst wenig".
2. **Konfigurierbar:** Der Nutzer wählt pro Optimierungs-Lauf, welche Klasse (A/B/C/…) die Schulhund-Klasse ist. Default: keine.
3. **Datenquelle:** Neue optionale Spalte `Hundehaarallergie` im Excel/ODS-Import; zusätzlich pro-Schüler-Korrektur im Frontend (analog zu Geschlecht/Auffälligkeit/Migration).
4. **Transparenz:** Eigenes Kriterium im Ampel-System; Banner über dem Klassen-Grid; Allergiker-Schüler bekommen ein Icon.
5. **Rückwärtskompatibilität:** Excel-Dateien ohne `Hundehaarallergie`-Spalte funktionieren unverändert; gespeicherte Einteilungen ohne `schulhund_klasse` laden problemlos.

## Architektur-Entscheidungen

**Score-Bonus im Wrapper + Post-Processing als Sicherheitsnetz** (gewählt von 3 Alternativen). Dieselben Patterns wie Sprengel (Soft-Score im Wrapper) und Trennungen (Hard Post-Processing) — keine Veränderungen am Submodul.

**Warum nicht reines Post-Processing?** Hätte den SA-Algorithmus blind gelassen und am Ende viele Verschiebungen mit Score-Verschlechterung erzwungen.

**Warum nicht Submodul-Patch?** Bricht das bewusste „Submodul nicht anfassen"-Pattern und erhöht die Wartungslast.

## Komponenten

### 1. Datenmodell & Spalten-Mapping (`backend/spaltenmapping.py`)

Neue **optionale** Spalte `Hundehaarallergie` in `ERWARTETE_SPALTEN`:

```python
"Hundehaarallergie": {
    "aliasse": [
        "hundehaarallergie", "hundeallergie", "hund-allergie",
        "allergie hund", "allergie", "tierhaarallergie",
    ],
    "pflicht": False,
},
```

Werte werden normalisiert (neuer Helper, z.B. in `backend/schulhund.py` oder als private Funktion in `spaltenmapping.py`):

| Eingabe | Normalisiert | Bedeutung |
|---|---|---|
| `ja`, `j`, `yes`, `y`, `1`, `true`, `x` | `"ja"` | Allergiker → Hard-Block |
| `nein`, `n`, `no`, `0`, `false`, `-` | `"nein"` | Erlaubt in Schulhund-Klasse |
| leer, `nan`, sonstige | `""` | Unbekannt → Hard-Block |

Single Source of Truth: `darf_in_schulhund_klasse(wert: str) -> bool` — returns `True` nur bei `"nein"`.

Die Vorlage (`backend/vorlage.py`) bekommt die neue Spalte mit Hinweis im Header-Kommentar.

### 2. Optimierungs-Wrapper (`backend/optimierung_wrapper.py`)

Neue Modul-Konstante:
```python
STRAFE_SCHULHUND_VERLETZUNG = -100.0  # Pro Allergiker/Unbekanntem in Schulhund-Klasse
```

Neue Funktion:
```python
def _schulhund_strafe(einteilung, df, schulhund_klasse: int, strafe_pro_kind: float) -> float:
    """Summiert Strafpunkte für Allergiker/Unbekannte in der Schulhund-Klasse."""
```

`optimiere_mit_sprengel()` bekommt zusätzlichen Parameter `schulhund_klasse: int | None = None`. Wenn gesetzt **und** Spalte `Hundehaarallergie` vorhanden, addiert `bewertung_mit_fortschritt` die Strafe.

### 3. Hard-Rule Post-Processing (`backend/api/routes.py`)

Neue Funktion `_erzwinge_schulhund_klasse(einteilung, df, schulhund_klasse, alle_trennungspaare)` — läuft **nach** `_erzwinge_trennungen`:

**Algorithmus:**
1. Sammle alle Allergiker/Unbekannten in der Schulhund-Klasse.
2. Für jeden: durchsuche **alle** anderen Klassen (in beliebiger Reihenfolge, z.B. nach Größe aufsteigend) nach einem Nicht-Allergiker, dessen Tausch keine Trennung verletzen würde.
3. Tausch durchführen (statt einseitige Verschiebung — erhält Klassengrößen).
4. Bei jedem Tausch: Log-Eintrag (analog `trennungen_erzwungen`).
5. Wenn für einen Allergiker kein gültiger Tausch-Partner in irgendeiner anderen Klasse gefunden wird → er bleibt in der Schulhund-Klasse, Log-Eintrag mit `status: "fehler"` und Grund (`"kein nicht-allergiker verfügbar"` oder `"alle kandidaten würden trennung verletzen"`). Optimierung crasht nicht.

Reihenfolge im Pipeline:
```
SA-Optimierung → _erzwinge_trennungen → _erzwinge_schulhund_klasse → pruefe_einteilung
```

### 4. State & API (`backend/api/routes.py`)

`_state` bekommt neuen Eintrag: `"schulhund_klasse": None`.

**`POST /api/optimierung`** — neuer Query-Param `schulhund_klasse: int | None = None`. Wert wird im State persistiert und an Wrapper + Post-Processing durchgereicht.

**`POST /api/verschieben`** — prüft zusätzlich, ob die neue Einteilung die Schulhund-Regel verletzt. Verletzungen kommen im Response-Feld `schulhund_verletzt` (analog `trennungen_verletzt`). Keine Hard-Block, nur Warnung.

**`POST /api/wuensche-speichern`** — `WunschZuordnung` bekommt neues Feld `hundehaarallergie: str | None = None`. Im Handler: Eingabe normalisieren via `darf_in_schulhund_klasse`-Logik, im DataFrame setzen.

**`_schueler_liste_aus_df`** liefert neues Feld pro Schüler: `"hundehaarallergie": "ja"|"nein"|""`.

**Persistenz:**
- `POST /api/assignments` legt zusätzlich `"schulhund_klasse"` ins JSON.
- `GET /api/assignments/{id}` stellt `_state["schulhund_klasse"]` aus dem JSON wieder her (Default `None` für Alt-Speicherstände); Response enthält `"schulhund_klasse"` für UI-Vorbelegung.

### 5. Qualitätsprüfung (`backend/pruefungen/qualitaet.py`)

`KlassenPruefung` Dataclass — neue Felder:
- `ist_schulhund_klasse: bool`
- `schulhund_allergiker: int`
- `schulhund_unbekannt: int`
- `schulhund_ampel: str` (`"gruen"` / `"rot"` / `"n/a"`)

`GesamtPruefung` Dataclass — neues Feld:
- `schulhund_klasse_index: int | None`

`pruefe_einteilung(einteilung, df, schulhund_klasse: int | None = None)` — neuer optionaler Parameter. Aufrufer in `routes.py` (drei Stellen: `/optimierung`, `/verschieben`, `/assignments/{id}`-Load) übergeben den State.

**Ampel-Logik:**
- `schulhund_klasse is None` **oder** Spalte `Hundehaarallergie` fehlt: alle Klassen `"n/a"` → Kriterium taucht im UI nicht auf.
- Für die gewählte Schulhund-Klasse: `"gruen"` wenn 0 Allergiker **und** 0 Unbekannte, sonst `"rot"` (keine Orange-Stufe).
- Für alle anderen Klassen: `"gruen"` (keine Verpflichtung).

### 6. Excel-Export (`/api/export`)

- `Hundehaarallergie`-Spalte ist durch den DataFrame automatisch in den Klassenblättern.
- `Pruefung`-Sheet bekommt zwei neue Spalten: `Schulhund` (Ampel) und `Allergiker/Unbekannt in Klasse` (Zähler), nur für die markierte Klasse gefüllt.

### 7. Frontend (`frontend/index.html`, `app.js`, `style.css`)

**`index.html` — Optimierungs-Panel:**
- Neues Dropdown „Schulhund-Klasse": `— keine —`, `A`, `B`, `C`, …. Anzahl der Optionen folgt dem Wert von „Anzahl Klassen".
- Wenn „Anzahl Klassen" geändert wird, setzt das Dropdown auf `— keine —` zurück (vermeidet ungültige Indices, wenn die neue Anzahl < bisheriger Schulhund-Index ist).
- Hinweis-Text: *„Die gewählte Klasse bleibt frei von Schülern mit Hundehaarallergie oder fehlender Angabe."*

**`index.html` — Klassen-Grid:**
- Banner über dem Grid, wenn `schulhund_klasse_index` gesetzt: *„🐕 Schulhund-Klasse: **A**"*.
- Markierte Klasse bekommt CSS-Klasse `.klasse-schulhund` (dezenter goldener Rand, 🐕-Icon im Header).
- Schüler mit `hundehaarallergie="ja"` bekommen CSS-Klasse `.schueler-allergie` (kleines 🐕-Icon).
- Schüler mit `hundehaarallergie=""` (Unbekannt) bekommen CSS-Klasse `.schueler-allergie-unbekannt` (gedämpftes ❓-Icon) — Transparenz darüber, warum sie evtl. aus der Schulhund-Klasse rausgehalten werden.

**`index.html` — Schüler-Detail-Editor:**
- Neues Dropdown „Hundehaarallergie": `ja` / `nein` / `unbekannt`. Wird beim Speichern als `"ja"`/`"nein"`/`""` ans Backend geschickt.

**`app.js`:**
- State um `schulhundKlasse: number | null` erweitern.
- `starteOptimierung()` hängt `?schulhund_klasse=<index>` an die URL (oder lässt den Param weg).
- `wuenscheSpeichern()` schickt `hundehaarallergie` pro Schüler.
- Drag & Drop: wenn `/api/verschieben`-Response `schulhund_verletzt` enthält, Toast/Warnung anzeigen.
- Beim Laden eines gespeicherten Assignments: Dropdown aus Response vorbelegen.

**`style.css`:**
- `.klasse-schulhund` (goldener Rand + 🐕-Header-Icon).
- `.schueler-allergie` (⚠️/🐕-Icon in der Schüler-Karte).

## Branch- & Merge-Strategie

- Branch `feature/schulhund-allergie` von `main`.
- Inkrementelle Commits (ein Commit pro logischer Etappe).
- Lokaler Merge mit `git merge --no-ff` erst nach abgeschlossener manueller Smoke-Test-Checkliste.
- Kein GitHub PR (Single-Dev, lokales Repo).

## Testing

### Automatisierte E2E-Tests

Neue Datei `test_schulhund.py` (analog zum existierenden `test_persistence.py` — gegen laufenden Server unter `localhost:8000`). Szenarien:

1. Upload Test-Excel mit `Hundehaarallergie`-Spalte → Spalte erkannt, Schülerliste enthält Feld.
2. Optimierung mit `schulhund_klasse=0` → Klasse A hat 0 Allergiker + 0 Unbekannte, Ampel `gruen`.
3. Optimierung ohne `schulhund_klasse` → Verhalten wie bisher, Ampel `n/a`.
4. Manuelle Verschiebung Allergiker → Schulhund-Klasse → Response enthält `schulhund_verletzt`.
5. Speichern + Laden → `schulhund_klasse` bleibt erhalten.
6. Edge Case: zu viele Allergiker → Log mit `status: "fehler"`, kein Crash.

Test-Excel `testdaten/Testliste_mit_Allergien.xlsx` wird im Test-Skript on-the-fly generiert (über die `/api/vorlage`-Route + manuelles Befüllen mit pandas).

### Manueller Smoke-Test (vor Merge)

- Upload alter Datei (ohne Allergie-Spalte) → Feature ist unsichtbar, alles funktioniert wie vorher.
- Upload neuer Datei mit Allergie-Spalte → Dropdown auswählbar.
- Optimierung mit/ohne Schulhund-Klasse; Excel-Export prüfen.
- Drag & Drop eines Allergikers in die Schulhund-Klasse → Warnung erscheint.
- Stammdaten-Korrektur: Allergie-Status pro Schüler im UI ändern, neu optimieren, Ergebnis prüfen.

## Out of Scope

- Mehrere Schulhund-Klassen (es gibt nur eine Hund-Lehrerin).
- Andere Allergie-Arten (Katzen, Pollen, …) — YAGNI, kann später verallgemeinert werden, wenn Bedarf entsteht.
- Konflikt-Auflösung Sprengel ↔ Schulhund: Sprengel ist Soft-Bonus, Schulhund ist Hard-Rule → Schulhund gewinnt automatisch durch die Pipeline-Reihenfolge.

## Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| Zu viele Allergiker → Schulhund-Klasse kann nicht vollständig geräumt werden | Log-Eintrag mit `status: "fehler"`; UI zeigt prominente Warnung; Optimierung crasht nicht. |
| Trennungs- + Schulhund-Constraint zusammen unlösbar | Reihenfolge: Trennungen erst, Schulhund tauscht nur, wenn kein Trennungs-Konflikt entsteht. Verbleibende Allergiker → Log-Fehler (siehe oben). |
| Alte Excel-Dateien brechen | Spalte ist `pflicht=False`; ohne Spalte ist Feature unsichtbar (Ampel `n/a`, Dropdown ohne Effekt). |
| Score-Strafe zu schwach → SA löst nicht selbst | `STRAFE_SCHULHUND_VERLETZUNG = -100.0` deutlich höher als typische Wunsch-Boni; Post-Processing fängt Reste sicher ab. |
