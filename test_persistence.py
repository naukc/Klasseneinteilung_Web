import json
import time
from urllib import request, parse
from urllib.error import URLError, HTTPError
import mimetypes
import uuid

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
                f'--{boundary}'.encode('utf-8'),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode('utf-8'),
                f'Content-Type: {mimetype}'.encode('utf-8'),
                b'',
                content
            ])
        body.extend([
            f'--{boundary}--'.encode('utf-8'),
            b''
        ])
        data = b'\r\n'.join(body)
    elif data is not None:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        response = request.urlopen(req)
        if stream:
            return response
        content = response.read()
        
        # Determine if we should parse as JSON based on content type or url
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content
    except HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise

def test_persistence():
    print("1. Lade Vorlage herunter...")
    vorlage_content = make_request("GET", f"{BASE_URL}/vorlage?format=xlsx")
    with open("test_vorlage.xlsx", "wb") as f:
        f.write(vorlage_content)
    
    print("2. Datei hochladen...")
    with open("test_vorlage.xlsx", "rb") as f:
        file_content = f.read()
    
    files = {"file": ("test_vorlage.xlsx", file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    upload_data = make_request("POST", f"{BASE_URL}/upload", files=files)
    
    # print("Upload Result:", json.dumps({k: v for k, v in upload_data.items() if k != "schueler"}, indent=2))
    
    if upload_data["braucht_mapping"]:
        print("Sende Mapping Bestätigung...")
        mapping_data = {"mapping": {
            k: v["spalte"] for k, v in upload_data["mapping"].items() if v["spalte"]
        }}
        mapping_res = make_request("POST", f"{BASE_URL}/mapping-bestaetigen", data=mapping_data)
        print("Mapping status:", mapping_res["status"])
        
    print("3. Starte Optimierung...")
    res = make_request("POST", f"{BASE_URL}/optimierung?anzahl_klassen=3&iterationen=100", stream=True)
    ergebnis = None
    for line in res:
        str_line = line.decode('utf-8').strip()
        if str_line.startswith("data: "):
            event = json.loads(str_line[6:])
            if event.get("type") == "ergebnis":
                ergebnis = event
                print("Optimierung fertig, Score:", event["score"])
                break
                
    assert ergebnis is not None, "Fehler beim Optimieren"
    
    print("4. Speichere Einteilung...")
    save_name = "Automatischer Testlauf"
    save_data = make_request("POST", f"{BASE_URL}/assignments", data={"name": save_name})
    print("Speichern-Antwort:", save_data)
    assignment_id = save_data["id"]
    
    print("5. Liste gespeicherte Einteilungen...")
    list_data = make_request("GET", f"{BASE_URL}/assignments")
    print("Gespeicherte:", [a["name"] for a in list_data["assignments"]])
    assert any(a["id"] == assignment_id for a in list_data["assignments"]), "Einteilung nicht in Liste"
    
    print("6. Lade gespeicherte Einteilung...")
    load_data = make_request("GET", f"{BASE_URL}/assignments/{assignment_id}")
    print("Geladen, Anzahl Schüler:", load_data["anzahl_schueler"])
    
    print("7. Lösche gespeicherte Einteilung...")
    del_data = make_request("DELETE", f"{BASE_URL}/assignments/{assignment_id}")
    print("Löschen status:", del_data)
    
    print("ALLE TESTS BESTANDEN!")

if __name__ == "__main__":
    time.sleep(1)
    test_persistence()
