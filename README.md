# Go2 Autonomy Dashboard

Web-Dashboard für den Unitree Go2 Roboterhund – Kartierung, autonome Navigation,
Keepout-Zonen und ChatGPT-Assistent, vollständig lokal über das Hunde-WLAN.

---

## Architekturüberblick

```
                 ┌─────────────────────────────────────┐
                 │        HUNDE-WLAN (offline)          │
                 │                                      │
  ┌──────────┐  WebRTC  ┌──────────────────────────┐   │
  │ Unitree  │◄────────►│     Service-Rechner       │   │
  │  Go2     │  ROS2    │  ┌────────────────────┐   │   │
  │          │  Topics  │  │  ROS2-Stack         │   │   │
  └──────────┘          │  │  (go2_ros2_sdk)     │   │   │
                        │  └────────┬───────────┘   │   │
                        │           │ rclpy          │   │
                        │  ┌────────▼───────────┐   │   │
                        │  │  FastAPI Backend    │   │   │
                        │  │  + statisches       │   │   │
                        │  │  Frontend-Bundle    │   │   │
                        │  └────────────────────┘   │   │
                        │       http://[ip]:8000     │   │
                        └──────────────┬─────────────┘   │
                                       │                  │
        ┌──────────────────────────────┼─────────────┐   │
        │                             Browser         │   │
        │   ┌──────────┐  ┌──────────┐  ┌─────────┐  │   │
        │   │ Tablet   │  │ Laptop   │  │ Handy   │  │   │
        │   │  (Club)  │  │  (Club)  │  │  (Club) │  │   │
        │   └──────────┘  └──────────┘  └─────────┘  │   │
        └──────────────────────────────────────────────┘   │
                                                           │
              Service-Rechner: zweite Verbindung (Eth/LTE) │
                          │                                 │
                  ┌───────▼──────┐                         │
                  │  OpenAI API  │   (nur für Chat-Funktion)│
                  └──────────────┘                         │
                                                           │
                 └─────────────────────────────────────────┘
```

---

## Setup: Service-Rechner

### Voraussetzungen

- Ubuntu 22.04 / ROS2 Humble
- `go2_ros2_sdk` installiert und konfiguriert
- Python 3.10+
- Node.js 20+

### 1. Repository klonen

```bash
git clone https://github.com/<dein-user>/Roboterhund-.git
cd Roboterhund-
```

### 2. Backend einrichten

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Umgebungsvariablen (`.env` oder Export)

| Variable           | Standard                        | Beschreibung                                         |
|--------------------|---------------------------------|------------------------------------------------------|
| `MOCK_MODE`        | `false`                         | `true` = läuft ohne ROS2/Hardware                   |
| `BACKEND_PIN`      | (leer = kein PIN)               | Optionaler PIN für Steuerbefehle                     |
| `KEEPOUT_OUTPUT_DIR` | `/tmp/go2_keepout`            | Wo PGM/YAML für Keepout-Karte geschrieben wird       |
| `ZONES_FILE`       | `/tmp/go2_zones.json`           | Persistenz der Zonen über Neustarts hinweg           |
| `STATIC_DIR`       | `../frontend/dist`              | Pfad zum gebauten Frontend                           |
| `HOST`             | `0.0.0.0`                       | Bind-Adresse                                         |
| `PORT`             | `8000`                          | Bind-Port                                            |

#### Backend starten

```bash
# Mit ROS2 (Produktiv)
source /opt/ros/humble/setup.bash
source ~/go2_ws/install/setup.bash
BACKEND_PIN=meinGeheimesPin python3 main.py

# Im Mock-Modus (ohne Roboter, zum Testen)
MOCK_MODE=true python3 main.py
```

### 3. Frontend bauen

```bash
cd ../frontend
npm install
npm run build
```

Das Build-Ergebnis landet in `frontend/dist/` und wird vom Backend automatisch
ausgeliefert (StaticFiles). Kein separater Webserver nötig.

### 4. Dashboard aufrufen

Club-Mitglieder verbinden ihr Gerät mit dem Hunde-WLAN und öffnen:

```
http://<IP des Service-Rechners im Hunde-WLAN>:8000
```

Die IP des Service-Rechners im Hunde-Netz ermitteln:

```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

---

## Backend als systemd-Service einrichten (optional, für Autostart)

```ini
# /etc/systemd/system/go2-backend.service
[Unit]
Description=Go2 Dashboard Backend
After=network.target

[Service]
Type=simple
User=<dein-user>
WorkingDirectory=/opt/go2-dashboard/backend
EnvironmentFile=/opt/go2-dashboard/.env
ExecStart=/opt/go2-dashboard/backend/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable go2-backend
sudo systemctl start go2-backend
```

---

## GitHub Actions Self-Hosted Runner einrichten

Der Self-Hosted Runner ermöglicht automatisches Deployment auf dem Service-Rechner.
Der Runner braucht eine **eigene Internetverbindung** (Ethernet oder Mobilfunk),
unabhängig vom Hunde-WLAN (das selbst offline ist).

### Schritt-für-Schritt

1. Gehe in GitHub → dein Repository → **Settings** → **Actions** → **Runners**
2. Klicke **New self-hosted runner**, wähle **Linux x64**
3. Folge den angezeigten Befehlen auf dem Service-Rechner:

```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-*.tar.gz -L <URL aus GitHub>
tar xzf ./actions-runner-linux-x64-*.tar.gz
./config.sh --url https://github.com/<dein-user>/Roboterhund- --token <TOKEN>
```

4. Runner als systemd-Service installieren (damit er nach Neustart läuft):

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

5. Der Runner muss `systemctl restart go2-backend` ausführen können:

```bash
# /etc/sudoers.d/github-runner
<runner-user> ALL=(ALL) NOPASSWD: /bin/systemctl restart go2-backend.service
```

6. Bei jedem Push auf `main` wird jetzt automatisch:
   - Das Frontend gebaut
   - Die Tests ausgeführt
   - Das Build auf den Service-Rechner kopiert
   - Das Backend neu gestartet

---

## Zweite Internetverbindung für die Chat-Funktion

Das Hunde-WLAN (AP-Modus des Go2) hat **kein Internet**. Für ChatGPT braucht
der Service-Rechner eine zweite, unabhängige Verbindung:

- **Ethernet-Kabel** (empfohlen): Standard-Kabelrouter, kein Eingriff ins Hunde-WLAN
- **Mobilfunk-Tethering**: Smartphone über USB → Service-Rechner

Der Service-Rechner hat dann zwei Netzwerkinterfaces:
- `wlan0` (oder ähnlich): Hunde-WLAN → ROS2/Dashboard
- `eth0` (oder ähnlich): Internetverbindung → OpenAI

Mapping, Navigation und Zonen-Editor funktionieren **vollständig ohne Internet**.

---

## Tests ausführen

```bash
cd backend
source .venv/bin/activate
MOCK_MODE=true pytest tests/ -v
```

Die Tests decken ab:
- Keepout-Zonen-Rendering (Polygon → PGM)
- API-Verträge (Health, Map, Status, Zonen, Steuerung)
- PIN-Schutz (korrekte Ablehnung / Akzeptanz)
- Chat-Endpunkt-Fehlerbehandlung (kein Key → 400)
- OpenAI-Key-Sicherheit (wird nicht zurückgegeben)

---

## Checkliste: Erster Test mit echtem Roboter

### Vorbereitung

- [ ] Service-Rechner im Hunde-WLAN eingeloggt
- [ ] ROS2-Stack gestartet: `ros2 launch go2_bringup go2_bringup.launch.py`
- [ ] `MOCK_MODE` auf `false` gesetzt
- [ ] Backend gestartet mit echten ROS2-Variablen
- [ ] Dashboard im Browser geöffnet (`http://<ip>:8000`)

### Karte

- [ ] Tab "Karte" zeigt eine aktive Karte (nicht nur Grau)
- [ ] Karte aktualisiert sich live (1 Hz) wenn der Hund fährt
- [ ] Auflösung, Origin und Dimensionen stimmen mit `ros2 topic echo /map` überein

### Keepout-Zonen

- [ ] Polygon im Map-Editor zeichnen, "Speichern & Anwenden" klicken
- [ ] Datei `/tmp/go2_keepout/keepout.pgm` wurde erstellt
- [ ] Nav2 costmap_filter_info_server wurde neu geladen (Backend-Log prüfen)
- [ ] Roboter fährt beim Navigieren nicht in die markierte Zone

### Navigation

- [ ] Tab "Karte", Werkzeug "Navigation", Klick auf einen freien Punkt
- [ ] Backend-Log zeigt `navigate_to x=... y=...`
- [ ] Roboter fährt zum geklickten Punkt
- [ ] Nav2 Action-Ergebnis: SUCCESS

### STOP

- [ ] STOP-Button im Steuerungs-Tab stoppt den Roboter sofort
- [ ] `cmd_vel` wird auf 0 gesetzt (prüfe mit `ros2 topic echo /cmd_vel`)

### PIN-Schutz

- [ ] `BACKEND_PIN=test1234` gesetzt, Backend neu gestartet
- [ ] Ohne PIN: Dashboard öffnet sich, PIN-Eingabe erscheint
- [ ] Falscher PIN: 401-Fehler
- [ ] Richtiger PIN: Dashboard funktioniert normal

### Chat

- [ ] OpenAI-Key in Einstellungen eingeben
- [ ] Chat-Anfrage senden
- [ ] Antwort erscheint auf Deutsch
- [ ] Ohne Internetverbindung: Fehlermeldung "Keine Internetverbindung..."
- [ ] Mapping/Navigation funktioniert weiterhin ohne Internet

---

## Bekannte Einschränkungen

| Einschränkung | Details |
|---|---|
| Nav2-Integration manuell | `start_mapping`, `save_map`, `navigate_to`, `stop` und `reload_keepout_filter` in `ros2_bridge.py` werfen `NotImplementedError` wenn nicht MOCK_MODE. Die Implementierung ist mit `# [HARDWARE]`-Kommentaren markiert und erfordert Anpassung an den konkreten Nav2-Lifecycle-Service-Namen. |
| OccupancyGrid-Callback | `_on_map_msg` in `ros2_bridge.py` ist vorhanden aber die ROS2-Subscription muss beim echten Node-Start eingerichtet werden. |
| Keepout-Filter-Reload | `reload_keepout_filter` beschreibt den nötigen Lifecycle-Vorgang; die Umsetzung hängt von der Nav2-Version und dem Launch-File ab. |
| PIN wird nicht verschlüsselt übertragen | Das lokale WLAN wird als vertrauenswürdig angesehen. Für erhöhte Sicherheit: HTTPS mit selbst-signiertem Zertifikat einrichten. |
| OpenAI-Key nach Neustart weg | By Design – der Key liegt nur im RAM. Nach jedem Backend-Neustart muss er in den Einstellungen neu eingegeben werden. |
| Keine Authentifizierung für Lesezugriffe | `GET /api/map`, `/api/zones`, `/api/status` sind ohne PIN abrufbar (nur Schreibzugriffe sind geschützt). |
