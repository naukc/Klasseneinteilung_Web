import sys
from pathlib import Path

# Submodul-Pfad ergänzen, damit Tests `algorithmus`, `config`, `utils` importieren können
sys.path.insert(0, str(Path(__file__).parent / "lib" / "klasseneinteilung"))
