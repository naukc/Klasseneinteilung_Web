"""E2E-Test für die Schulhund-Allergie-Funktion. Setzt einen laufenden Server auf localhost:8000 voraus."""

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


def upload_und_optimiere(allergien, schulhund_klasse, anzahl_klassen=2, iterationen=1000):
    excel_bytes = baue_test_excel(allergien)
    files = {"file": ("test.xlsx", excel_bytes,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = make_request("POST", f"{BASE_URL}/upload", files=files)
    assert res["braucht_mapping"] is False, "Spalten sollten automatisch erkannt werden"
    assert any("hundehaarallergie" in s for s in res["schueler"])

    params = f"?anzahl_klassen={anzahl_klassen}&iterationen={iterationen}"
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
            if ev.get("type") == "fehler":
                raise RuntimeError(f"Optimierung gescheitert: {ev}")
    assert ergebnis is not None
    return ergebnis


def test_1_optimierung_ohne_schulhund():
    print("Test 1: Optimierung ohne Schulhund-Klasse")
    ergebnis = upload_und_optimiere(
        ["ja", "nein", "", "ja", "nein", "nein"], schulhund_klasse=None
    )
    for kp in ergebnis["pruefung"]["klassen"]:
        assert kp["schulhund_ampel"] == "n/a", f"erwartet n/a, bekommen {kp['schulhund_ampel']}"
    print("  ✓")


def test_2_optimierung_mit_schulhund_klasse_a():
    print("Test 2: Optimierung mit Schulhund-Klasse A")
    ergebnis = upload_und_optimiere(
        ["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=0
    )
    klasse_a = ergebnis["pruefung"]["klassen"][0]
    assert klasse_a["schulhund_ampel"] == "gruen", \
        f"Erwartet gruen, bekommen {klasse_a['schulhund_ampel']}"
    assert klasse_a["schulhund_allergiker"] == 0
    assert klasse_a["schulhund_unbekannt"] == 0
    assert klasse_a["ist_schulhund_klasse"] is True
    print("  ✓")


def test_3_manuelle_verschiebung_loest_warnung_aus():
    print("Test 3: Manuelle Verschiebung eines Allergikers in die Schulhund-Klasse")
    upload_und_optimiere(
        ["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=0
    )
    schueler = make_request("GET", f"{BASE_URL}/schueler")["schueler"]
    allergiker_ids = [s["id"] for s in schueler if s["hundehaarallergie"] == "ja"]
    nein_ids = [s["id"] for s in schueler if s["hundehaarallergie"] == "nein"]
    assert len(allergiker_ids) >= 1 and len(nein_ids) >= 2

    alle_ids = [s["id"] for s in schueler]
    klasse_a = [allergiker_ids[0], nein_ids[0], nein_ids[1]]
    klasse_b = [sid for sid in alle_ids if sid not in klasse_a]
    res = make_request("POST", f"{BASE_URL}/verschieben", data=[klasse_a, klasse_b])
    assert "schulhund_verletzt" in res, "Schulhund-Verletzung sollte gemeldet werden"
    assert any(v["schueler"]["id"] == allergiker_ids[0] for v in res["schulhund_verletzt"])
    print("  ✓")


def test_4_speichern_und_laden_erhaelt_schulhund_klasse():
    print("Test 4: Speichern + Laden erhält Schulhund-Klasse")
    upload_und_optimiere(
        ["nein", "nein", "nein", "ja", "ja", ""], schulhund_klasse=1
    )
    save = make_request(
        "POST", f"{BASE_URL}/assignments",
        data={"name": f"Test_{int(time.time())}"},
    )
    aid = save["id"]
    load = make_request("GET", f"{BASE_URL}/assignments/{aid}")
    assert load["schulhund_klasse"] == 1
    make_request("DELETE", f"{BASE_URL}/assignments/{aid}")
    print("  ✓")


def test_5_zu_viele_allergiker_log_eintrag():
    print("Test 5: Zu viele Allergiker → Log-Eintrag mit status=fehler")
    ergebnis = upload_und_optimiere(
        ["ja", "ja", "ja", "ja", "ja", "ja"], schulhund_klasse=0
    )
    if "schulhund_verschoben" in ergebnis:
        assert any(e["status"] == "fehler" for e in ergebnis["schulhund_verschoben"])
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
    files = {"file": ("alt.xlsx", buf.getvalue(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = make_request("POST", f"{BASE_URL}/upload", files=files)
    assert res["braucht_mapping"] is False
    stream = make_request(
        "POST", f"{BASE_URL}/optimierung?anzahl_klassen=2&iterationen=500", stream=True
    )
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
    time.sleep(0.5)
    test_1_optimierung_ohne_schulhund()
    test_2_optimierung_mit_schulhund_klasse_a()
    test_3_manuelle_verschiebung_loest_warnung_aus()
    test_4_speichern_und_laden_erhaelt_schulhund_klasse()
    test_5_zu_viele_allergiker_log_eintrag()
    test_6_rueckwaertskompatibilitaet_ohne_allergie_spalte()
    print("\nALLE E2E-TESTS BESTANDEN!")
