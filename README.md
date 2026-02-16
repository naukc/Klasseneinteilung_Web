# Klasseneinteilung

Web-App zur automatisierten Klasseneinteilung von Grundschülern.
Optimiert mit Simulated Annealing unter Berücksichtigung von Geschlechterverteilung, Auffälligkeiten, Migrationshintergrund, Wunschpartnern, Trennungen und Schulsprengeln.

## Download

Fertige Desktop-Anwendungen gibt es unter [**Releases**](../../releases/latest):

| Betriebssystem | Datei |
|---|---|
| Windows | `Klasseneinteilung-Windows.zip` |
| Linux | `Klasseneinteilung-Linux.tar.gz` |

**Windows:** ZIP entpacken → `Klasseneinteilung.exe` starten.
**Linux:** Archiv entpacken → `./Klasseneinteilung` ausführen.

Die App öffnet automatisch den Standard-Browser. Beim Schließen des Browser-Tabs beendet sich die App selbstständig.

## Features

- **Excel-Import** – Schülerlisten im `.xlsx`-, `.xls`- oder `.ods`-Format hochladen
- **Intelligentes Spalten-Mapping** – Spalten werden automatisch erkannt, auch bei abweichenden Bezeichnungen
- **Simulated Annealing** – Optimierte Klasseneinteilung nach konfigurierbaren Kriterien
- **Qualitätsprüfung** – Ampel-System (grün/orange/rot) für 7 Kriterien
- **Drag & Drop** – Schüler manuell zwischen Klassen verschieben mit Live-Update
- **Trennungen** – Harte Regel: Getrennte Schüler landen nie in derselben Klasse
- **Laufpartner** – Kinder aus dem gleichen Sprengel werden bevorzugt zusammen eingeteilt
- **Excel-Export** – Ergebnis als formatierte Excel-Datei herunterladen

## Prüfungskriterien

| Kriterium | Grün | Orange | Rot |
|---|---|---|---|
| Geschlecht (M/W Differenz) | ≤ 2 | ≤ 4 | > 4 |
| Auffälligkeit (% Abweichung) | ≤ 10 % | ≤ 25 % | > 25 % |
| Migration (pp Abweichung) | ≤ 5 pp | ≤ 10 pp | > 10 pp |
| Wunsch-Quote | ≥ 75 % | ≥ 50 % | < 50 % |
| Trennungen missachtet | 0 | – | > 0 |
| Klassengröße (Abweichung) | ≤ 1 | ≤ 2 | > 2 |
| Ohne Laufpartner | 0 | ≤ 2 | > 2 |

## Entwicklung

### Voraussetzungen

- Python 3.12+

### Setup

```bash
git clone --recurse-submodules <repo-url>
cd Klasseneinteilung_Web
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Starten (Entwicklungsmodus)

```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Dann im Browser: http://localhost:8000

### Desktop-App lokal bauen

```bash
./build.sh
# Oder manuell:
pyinstaller klasseneinteilung.spec --clean --noconfirm
./dist/Klasseneinteilung/Klasseneinteilung
```

### Neue Version veröffentlichen

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions baut automatisch für Windows und Linux und hängt die Dateien an das Release an.

## Projektstruktur

```
├── launcher.py                 # Einstiegspunkt Desktop-App (Browser + Auto-Shutdown)
├── backend/
│   ├── app.py                  # FastAPI-Hauptanwendung
│   ├── pfade.py                # Zentrale Pfad-Auflösung (Dev + gepackt)
│   ├── api/routes.py           # REST-API Endpunkte
│   ├── pruefungen/qualitaet.py # Qualitätsprüfungen (Ampel-System)
│   ├── optimierung_wrapper.py  # Wrapper mit Sprengel-Erweiterung
│   ├── spaltenmapping.py       # Intelligentes Spalten-Mapping
│   └── vorlage.py              # Vorlagen-Generierung
├── frontend/
│   ├── index.html              # Single Page Application
│   ├── style.css               # UI-Styling
│   └── app.js                  # Frontend-Logik (Vanilla JS)
├── lib/klasseneinteilung/      # Git-Submodul (Algorithmus)
├── requirements.txt            # Python-Abhängigkeiten
├── klasseneinteilung.spec      # PyInstaller Build-Konfiguration
├── build.sh                    # Lokales Build-Skript
└── .github/workflows/build.yml # CI/CD für automatische Builds
```

## Lizenz

Dieses Projekt ist für den internen Schulgebrauch bestimmt.
