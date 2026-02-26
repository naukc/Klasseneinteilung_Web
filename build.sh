#!/bin/bash
# Build-Skript für die Klasseneinteilung Desktop-App.
#
# Voraussetzungen:
#   - Aktiviertes venv mit allen Abhängigkeiten
#
# Nutzung:
#   chmod +x build.sh
#   ./build.sh

set -e

cd "$(dirname "$0")"

echo "=== Klasseneinteilung Desktop-App Build ==="
echo ""

# Prüfe ob wir in einem venv sind
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        echo "Aktiviere .venv..."
        source .venv/bin/activate
    else
        echo "FEHLER: Kein virtuelles Environment gefunden."
        echo "Erstelle eines mit: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
fi

echo "Python: $(python --version)"
echo "PyInstaller: $(pyinstaller --version)"
echo ""

# Build starten
echo "Starte Build..."
pyinstaller klasseneinteilung.spec --clean --noconfirm

echo ""
echo "=== Build erfolgreich! ==="
echo "Output: dist/Klasseneinteilung/"
echo ""

if [ "$(uname)" = "Darwin" ]; then
    echo "⚙️  Fixe macOS-Sicherheitseinstellungen (Quarantine & Ad-hoc Signature)..."
    
    # Entferne Quarantine Flag von allen Dateien, damit nicht bei jedem dylib eine Warnung kommt
    xattr -cr dist/Klasseneinteilung 2>/dev/null || true
    xattr -cr dist/Klasseneinteilung.app 2>/dev/null || true
    
    # Ad-hoc signieren (mit force und deep) verhindert Gatekeeper-Popups für Bibliotheken
    codesign --force --deep -s - dist/Klasseneinteilung 2>/dev/null || true
    if [ -d "dist/Klasseneinteilung.app" ]; then
        codesign --force --deep -s - dist/Klasseneinteilung.app 2>/dev/null || true
    fi
    echo "✅ macOS Fixes angewendet!"
    echo ""
    echo "Starten mit: open dist/Klasseneinteilung.app"
else
    echo "Starten mit: ./dist/Klasseneinteilung/Klasseneinteilung"
fi

