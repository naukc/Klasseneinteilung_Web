"""
Launcher für die gepackte Desktop-App.

Startet den Uvicorn-Server in einem Hintergrund-Thread, öffnet den
Standard-Browser und überwacht per Heartbeat, ob der Browser-Tab
noch offen ist. Wird der Tab geschlossen, beendet sich die App
automatisch nach kurzer Wartezeit.
"""

import faulthandler
import os
import subprocess
import sys
import socket
import threading
import time
import traceback
from pathlib import Path

import uvicorn


# Heartbeat-Konfiguration
HEARTBEAT_TIMEOUT = 60  # Sekunden ohne Heartbeat → Shutdown
HEARTBEAT_CHECK_INTERVALL = 5  # Prüf-Intervall in Sekunden


def _log_pfad() -> Path:
    """OS-spezifisches Log-Verzeichnis für Diagnose-Output."""
    if sys.platform == "darwin":
        base = Path("~/Library/Logs/Klasseneinteilung").expanduser()
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~")).expanduser() / "Klasseneinteilung" / "logs"
    else:
        base = Path("~/.local/share/Klasseneinteilung/logs").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base / "runtime.log"


def _setup_diagnose_logging():
    """
    Im gepackten Modus: stderr/stdout in Logdatei umleiten und alle
    uncaught Exceptions + Thread-Crashes + Segfaults erfassen.
    """
    if not getattr(sys, "frozen", False):
        return None

    log_file = _log_pfad()
    f = open(log_file, "w", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = f
    sys.stderr = f

    # Native Crashes (Segfaults, Stack-Overflows)
    try:
        faulthandler.enable(f)
    except Exception:
        pass

    # Uncaught Python-Exceptions im Main-Thread
    def _excepthook(exc_type, exc_value, exc_tb):
        f.write("\n=== UNCAUGHT EXCEPTION ===\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        f.flush()
    sys.excepthook = _excepthook

    # Exceptions in beliebigen Threads
    def _thread_excepthook(args):
        f.write(f"\n=== THREAD EXCEPTION ({args.thread.name}) ===\n")
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
        f.flush()
    threading.excepthook = _thread_excepthook

    print(f"=== Klasseneinteilung gestartet (PID {os.getpid()}) ===", flush=True)
    print(f"Plattform: {sys.platform}, Python: {sys.version}", flush=True)
    print(f"Log-Pfad: {log_file}", flush=True)
    return f


def finde_freien_port() -> int:
    """Findet einen freien TCP-Port auf localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def starte_server(port: int) -> None:
    """Startet den Uvicorn-Server."""
    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


def warte_auf_server(port: int, timeout: float = 15.0) -> bool:
    """Wartet bis der Server erreichbar ist."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def oeffne_browser(url: str) -> None:
    """
    Öffnet die URL im Standard-Browser.
    Im gepackten Modus wird LD_LIBRARY_PATH bereinigt, damit System-Programme
    nicht die gebündelten PyInstaller-Bibliotheken laden (verursacht Symbol-Fehler).
    """
    if getattr(sys, "frozen", False):
        env = os.environ.copy()
        # PyInstaller setzt LD_LIBRARY_PATH auf _internal/ – das muss für
        # externe Programme (Browser, Shell) zurückgesetzt werden
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("LD_LIBRARY_PATH_ORIG", None)
        try:
            subprocess.Popen(
                ["xdg-open", url],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            # Fallback: webbrowser-Modul mit bereinigter Umgebung
            import webbrowser
            webbrowser.open(url)
    else:
        import webbrowser
        webbrowser.open(url)


def heartbeat_watchdog() -> None:
    """
    Überwacht den Heartbeat vom Frontend.
    Wenn kein Heartbeat mehr kommt (Browser-Tab geschlossen),
    wird die App beendet.
    """
    from backend.api import routes

    # Erste Karenzzeit: Browser braucht etwas zum Laden
    time.sleep(HEARTBEAT_TIMEOUT)

    while True:
        vergangen = time.time() - routes.letzter_heartbeat
        if vergangen > HEARTBEAT_TIMEOUT:
            print("Kein Heartbeat mehr – App wird beendet.")
            os._exit(0)
        time.sleep(HEARTBEAT_CHECK_INTERVALL)


def main() -> None:
    # Diagnose-Logging als erstes — fängt auch frühe Crashes ab
    _setup_diagnose_logging()

    # Im gepackten Modus: Arbeitsverzeichnis auf _MEIPASS setzen,
    # damit relative Imports funktionieren
    if getattr(sys, "frozen", False):
        os.chdir(sys._MEIPASS)

    port = finde_freien_port()
    url = f"http://127.0.0.1:{port}"

    # Server in Daemon-Thread starten
    server_thread = threading.Thread(
        target=starte_server,
        args=(port,),
        daemon=True,
    )
    server_thread.start()

    if not warte_auf_server(port):
        print("Fehler: Server konnte nicht gestartet werden.", file=sys.stderr)
        sys.exit(1)

    # Nur im gepackten Modus: Watchdog starten (im Dev-Modus stört es)
    if getattr(sys, "frozen", False):
        watchdog_thread = threading.Thread(
            target=heartbeat_watchdog,
            daemon=True,
        )
        watchdog_thread.start()

    # Browser öffnen
    # Im gepackten Modus muss LD_LIBRARY_PATH bereinigt werden, da PyInstaller
    # seine gebündelten .so-Dateien dort einfügt. Das verwirrt System-Programme
    # wie /bin/sh, die zum Starten des Browsers genutzt werden.
    oeffne_browser(url)
    print(f"Klasseneinteilung gestartet: {url}")
    print("Die App beendet sich automatisch wenn der Browser-Tab geschlossen wird.")

    # Hauptthread am Leben halten
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Beendet.")


if __name__ == "__main__":
    main()
