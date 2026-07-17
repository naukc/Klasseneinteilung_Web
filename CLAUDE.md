# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Web-App (FastAPI backend + Vanilla-JS frontend) zur automatisierten Klasseneinteilung von Grundschülern. Wird sowohl als lokaler Dev-Server als auch als gepackte Desktop-App (PyInstaller, Browser-basiert mit Auto-Shutdown) ausgeliefert. Code und Kommentare sind auf Deutsch.

## Commands

### Setup
```bash
git clone --recurse-submodules <repo-url>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
The submodule `lib/klasseneinteilung` ships the actual SA-algorithm and **must** be checked out — without it imports in `backend/api/routes.py` fail.

### Dev-Server
```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
# oder
./run.sh
```
Frontend wird vom Backend unter `/` als statisches Mount geliefert, API unter `/api/*`, Swagger unter `/docs`.

### Desktop-Build
```bash
./build.sh                                       # nutzt aktives venv oder .venv/
pyinstaller klasseneinteilung.spec --clean --noconfirm   # manuell
```
Output: `dist/Klasseneinteilung/`. Auf macOS macht `build.sh` zusätzlich `xattr -cr` + Ad-hoc `codesign` gegen Gatekeeper-Probleme.

### Tests
Unit-Tests liegen unter `tests/` und laufen ohne Server:
```bash
python -m pytest tests/
```
`test_persistence.py` (im Repo-Root) ist ein End-to-End-Test gegen einen laufenden Server:
```bash
# In einem Terminal:
uvicorn backend.app:app --port 8000
# In einem zweiten:
python test_persistence.py
```

### Release
Push eines `v*`-Tags triggert `.github/workflows/build.yml` → baut Windows / macOS / Linux Bundles und hängt sie ans Release.

## Architektur

### Submodul-Pattern (wichtig!)
Der Optimierungsalgorithmus lebt im Git-Submodul `lib/klasseneinteilung/` (eigenes Repo, eigene CLI/GUI). Das Web-Repo importiert davon `algorithmus`, `config`, `utils` — der Import-Pfad wird **zur Laufzeit** in `backend/api/routes.py` per `sys.path.insert(0, get_lib_path())` gesetzt. Beim Editieren also nicht versuchen, das Submodul wie normale Pakete zu importieren.

`backend/optimierung_wrapper.py` erweitert den Algorithmus via **Monkey-Patching**: vor `optimiere_einteilung()` wird `algorithmus.bewerte_einteilung` temporär ersetzt durch eine Version, die zusätzlich `Sprengel`-Laufpartner-Bonus rechnet und Fortschritts-Callbacks feuert; im `finally` wird die Original-Funktion zurückgeschrieben. Den Submodul-Code dafür nicht forken — der Wrapper ist absichtlich nicht-invasiv.

### Pfad-Auflösung (Dev vs. gepackt)
`backend/pfade.py` ist die einzige Stelle, die Pfade bestimmt. Sie unterscheidet drei Klassen:
- **Read-only Bundle-Inhalte** (Frontend, Submodul) → `get_base_path()`: Projekt-Root im Dev, `sys._MEIPASS` im gepackten Modus.
- **Veränderbare Uploads / Tempfiles** → `get_data_path()`: `backend/` im Dev, OS-`tempfile`-Verzeichnis im gepackten Modus (kann nicht in `_MEIPASS` schreiben).
- **Dauerhafte gespeicherte Einteilungen** → `get_save_dir()`: OS-AppData (`%APPDATA%`, `~/Library/Application Support`, `~/.local/share`).

Beim Hinzufügen neuer Dateien immer durch diese Helper gehen, sonst bricht der gepackte Build.

### State
Der Server hält **einen** Prototyp-Wide In-Memory-State in `backend/api/routes.py` (`_state` dict mit `df`, `einteilung`, `pruefung`, `upload_path`, `mapping_vorschlaege`). Das ist Single-User-Design für die Desktop-App — kein Lock, keine Sessions. Bei Multi-Tenant-Erweiterungen muss das umgebaut werden.

Persistierte Einteilungen werden als JSON (`df.to_dict(orient="split")` + Einteilung-Liste) unter `get_save_dir()` abgelegt; siehe `/api/assignments*`.

### Optimierungs-Pipeline (POST `/api/optimierung`)
1. `_df_fuer_submodul(df)` konsolidiert mehrere `Trennen_Von_X`-Spalten zu **einer** `Trennen_Von` Spalte und macht Trennungen bidirektional (Algorithmus erwartet dieses Format).
2. SA-Optimierung läuft in eigenem Thread; eine `queue.Queue` puffert Fortschritts-Events.
3. **Post-Processing `_erzwinge_trennungen()`**: Der Algorithmus behandelt Trennungen weich. Diese Funktion läuft danach und verschiebt deterministisch Schüler, bis **alle** Trennungen eingehalten sind (harte Regel). Bei Änderungen am Optimierer beachten: dieser Schritt darf nie übersprungen werden.
4. Antwort geht als **SSE-Stream** (`text/event-stream`) raus mit `fortschritt` / `keepalive` / `ergebnis` / `fehler` Events.

### Spalten-Mapping
Excel/ODS-Imports gehen durch `backend/spaltenmapping.py` → 3-stufige Erkennung (exakt → Alias-Tabelle → Substring). Wenn alle Pflichtspalten sicher matchen, baut `/api/upload` den DataFrame direkt; sonst geht's über `/api/mapping-bestaetigen` mit User-Bestätigung. `ERWARTETE_SPALTEN` (in `spaltenmapping.py`) ist die zentrale Definition der Pflicht- und optionalen Spalten.

### Auto-Shutdown (nur gepackt)
`launcher.py` startet Uvicorn als Daemon-Thread, öffnet den Browser, und startet einen `heartbeat_watchdog`, der `routes.letzter_heartbeat` pollt. Frontend muss alle paar Sekunden `POST /api/heartbeat` schicken; bleibt es > 15s aus, `os._exit(0)`. Im Dev-Modus ist der Watchdog deaktiviert.

Auf Linux wird vor dem Browser-Start `LD_LIBRARY_PATH` aus der env entfernt, weil PyInstaller dort seine gebündelten `.so`s einträgt und sonst System-Tools (Shell, xdg-open) abstürzen.

## Konventionen

- Code, Variablen, Kommentare auf **Deutsch** (auch im Submodul).
- Wenn etwas am Spalten-Mapping geändert wird, immer `ERWARTETE_SPALTEN` als Single Source of Truth nehmen — Frontend (`/api/upload`-Response), Validierung und DataFrame-Aufbau hängen alle daran.
- Hard rule: Trennungen werden post-process erzwungen, Wünsche/Sprengel werden im SA-Score belohnt.
