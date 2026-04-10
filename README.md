# FritzDECT-Bot

Ein Telegram-Bot zur Steuerung und Überwachung von FritzBox-Geräten mit Benachrichtigungs-API.

## 🌟 Features

- **Gerätesteuerung**: FritzBox-Geräte über Telegram steuern
- **Benachrichtigungen**: Automatische Benachrichtigungen bei Ereignissen
- **User-Management**: Mehrbenutzer-System mit Rollen und Berechtigungen
- **Sprachunterstützung**: Deutsch, Englisch, Französisch, Spanisch
- **Sicherheit**: Login-System mit IP-Beschränkungen
- **API**: REST-API für FritzBox-Integration
- **Statistiken**: Geräte-Statistiken und Auswertungen
- **Automatisierung**: Zeitgesteuerte Aktionen und Vorlagen

## 📁 Projektstruktur

```
FritzDECT-Bot/
├── fritzdect_bot.py              # Haupt-Bot-Anwendung
├── notification_api.py           # Benachrichtigungs-API
├── config.json                  # Konfigurationsdatei
├── config.example.json          # Konfigurationsvorlage
├── requirements.txt             # Python-Abhängigkeiten
├── README.md                    # Diese Datei
├── README_API.md               # API-Dokumentation
├── README_FRAMEWORK.md         # Framework-Dokumentation
├── lib/                        # Bibliotheken
│   ├── config.py              # Konfigurations-Handler
│   ├── user_database.py       # Datenbank-Verwaltung
│   ├── fritzbox_api_optimized.py # FritzBox-API
│   ├── settingsMode.py        # Benachrichtigungseinstellungen
│   ├── loginMode.py           # Login-System
│   ├── statisticsMode.py      # Statistik-Funktionen
│   └── automationMode.py     # Automatisierungen
└── database/                  # SQLite-Datenbank
```

## 🚀 Schnellstart

### 1. Installation

```bash
# Repository klonen
git clone <repository-url>
cd FritzDECT-Bot

# Python-Umgebung erstellen
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### 2. Konfiguration

```bash
# Konfigurationsvorlage kopieren
cp config.example.json config.json

# Konfiguration bearbeiten
nano config.json  # oder dein Lieblings-Editor
```

**Wichtige Konfigurationen:**
- `telegram.token`: Bot-Token von BotFather
- `telegram.admin_chat_id`: Admin-Chat-ID
- `fritzbox.host`: FritzBox IP-Adresse
- `fritzbox.username/password`: FritzBox Zugangsdaten
- `security.allowed_fritzbox_ips`: Erlaubte IPs für API

### 3. Bot starten

```bash
# Bot starten mit Standard-Konfiguration (config.json)
python3 fritzdect_bot.py

# Bot mit eigener Konfigurationsdatei
python3 fritzdect_bot.py -c /pfad/zur/config.json
python3 fritzdect_bot.py --config meine_config.json

# API starten mit Standard-Konfiguration (config.json)
python3 notification_api.py

# API mit eigener Konfigurationsdatei
python3 notification_api.py -c /pfad/zur/config.json
python3 notification_api.py --config meine_config.json
```

## 👥 User-Management Workflow

Das User-Management ist ein mehrstufiges Prozess mit verschiedenen Rollen und Berechtigungen:

### 🔄 **User-Onboarding Prozess**

#### **1. Erster Kontakt**
```
Neuer Benutzer → /start
├── Bot prüft ob Benutzer bekannt
├── Wenn unbekannt: Registrierungsprozess
└── Wenn bekannt: Begrüßung mit Status
```

#### **2. Registrierung**
```
Unbekannter Benutzer → Registrierung
├── Bot fragt nach Passwort
├── Passwort-Validierung gegen config.json
├── Bei Erfolg: Benutzer in Datenbank eintragen
└── Bei Fehler: Zugriff verweigert
```

#### **3. Rollen-System**
```
Benutzer-Rollen:
├── **USER** (Standard)
│   ├── Geräte-Status abfragen
│   ├── Eigene Einstellungen ändern
│   └── Basis-Funktionen nutzen
├── **ADMIN** (vom Admin zugewiesen)
│   ├── Alle USER-Funktionen
│   ├── Andere Benutzer verwalten
│   ├── Bot-Konfiguration ändern
│   └── System-Statistiken einsehen
└── **SUPER_ADMIN** (erste chat_id in config.json)
    ├── Alle ADMIN-Funktionen
    ├── Neue ADMINs ernennen
    └── System-Reset durchführen
```

### 🔐 **Authentifizierung & Sicherheit**

#### **Login-System**
```
Login-Ablauf:
├── Benutzer startet mit /start
├── Bot prüft IP-Adresse (optional)
├── Passwort-Abfrage bei unbekannten Benutzern
├── Temporärer Zugang (24h) nach erfolgreicher Anmeldung
└── Permanenter Zugang nach Admin-Freigabe
```

#### **Sicherheits-Features**
- **IP-Filtering**: Beschränkung auf erlaubte IPs
- **Rate Limiting**: Begrenzte Anfragen pro Minute
- **Failed Attempts**: Sperrung nach fehlgeschlagenen Versuchen
- **Session Management**: Automatischer Logout nach Inaktivität

### 📊 **Benutzer-Verwaltung**

#### **Admin-Funktionen**
```
User-Management (nur ADMIN/SUPER_ADMIN):
├── /admin → Admin-Panel
├── Benutzerliste anzeigen
├── Benutzer-Rolle ändern (USER ↔ ADMIN)
├── Benutzer sperren/entsperren
├── Benutzer löschen
└── Statistiken einsehen
```

#### **Benutzer-Einstellungen**
```
Persönliche Einstellungen (alle Benutzer):
├── /settings → Einstellungen-Menü
├── Sprache ändern (DE/EN/FR/ES)
├── Benachrichtigungs-Modi pro Typ:
│   ├── 🔕 Keine Benachrichtigung
│   ├── 🔔 Silent Notification
│   └── 📱 Push-Nachricht
└── Persönliche Vorlieben speichern
```

### 🗄️ **Datenbank-Struktur**

```sql
CREATE TABLE users (
    chatID INTEGER PRIMARY KEY,
    username TEXT,
    firstName TEXT,
    isAdmin INTEGER DEFAULT 0,
    password TEXT,
    allowedToDatetime TEXT,
    failedAttempts INTEGER DEFAULT 0,
    blockedUntil TEXT,
    language TEXT DEFAULT 'de',
    notifyDoorPowerMeter INTEGER DEFAULT 0,
    notifyDoorFrontDoor INTEGER DEFAULT 0,
    notifyVacationMode INTEGER DEFAULT 0,
    notifyTemperatureWarning INTEGER DEFAULT 0,
    notifyBurglarAlarm INTEGER DEFAULT 0
);
```

### 🔄 **Benutzer-Zustände**

```
Bot-Zustands-System:
├── MAIN (0) → Hauptmenü
├── LOGIN (1) → Login-Prozess
├── ADMIN (2) → Admin-Panel
├── STATISTICS (3) → Statistik-Ansicht
├── AUTOMATION (4) → Automatisierungs-Menü
└── SETTINGS (5) → Einstellungen-Menü
```

## 📡 API-Integration

Die FritzBox kann über die REST-API Benachrichtigungen senden:

### API-Endpunkte
```bash
# Benachrichtigung senden
POST http://localhost:8080/notify
Content-Type: application/json
{
  "DoorPowerMeter": 1,
  "note": "Tür wurde geöffnet"
}

# Health-Check
GET http://localhost:8080/health

# Status-Abfrage
GET http://localhost:8080/status
```

### Unterstützte Benachrichtigungen
- `DoorPowerMeter` - Tür/Strom-Meldungen
- `DoorFrontDoor` - Haustür-Events
- `VacationMode` - Urlaubsmodus-Änderungen
- `TemperatureWarning` - Temperaturwarnungen
- `BurglarAlarm` - Einbruchalarme

📖 **Siehe [`README_API.md`](README_API.md) für vollständige API-Dokumentation**

## 🔧 Bot-Befehle

### Hauptbefehle
```
/start          - Bot starten/registrieren
/help           - Hilfe anzeigen
/status         - Geräte-Status
/devices        - Geräteliste
/automation     - Automatisierungen
/settings       - Einstellungen
/statistics     - Statistiken
```

### Admin-Befehle
```
/admin          - Admin-Panel
/users          - Benutzerliste
/block          - Benutzer sperren
/unblock        - Benutzer entsperren
/promote        - Zum Admin ernennen
/demote         - Admin-Rechte entziehen
```

## 📖 Weitere Dokumentation

- **[API-Dokumentation](README_API.md)** - Vollständige API-Referenz
- **[Framework-Dokumentation](README_FRAMEWORK.md)** - Technische Details und Architektur

## 🛠️ Entwicklung

### Bot-Erweiterung
Neue Funktionen können über das Modul-System hinzugefügt werden:

```python
# Neues Modul erstellen
lib/newMode.py
├── get_mode_name() → Modus-Name
├── get_mode_commands() → Befehlsliste
├── get_callback_handlers() → Callback-Handler
└── handle_*() → Handler-Funktionen
```

### Debug-Modus
```bash
# Debug-Logging aktivieren
export LOG_LEVEL=DEBUG
python3 fritzdect_bot.py
```

## systemd Service Konfiguration

Für den produktiven Betrieb können beide Scripts als systemd Services eingerichtet werden:

### 1. Service-Dateien erstellen

**Bot Service (`/etc/systemd/system/fritzdect-bot.service`):**
```ini
[Unit]
Description=FritzDECT Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=fritzdect
Group=fritzdect
WorkingDirectory=/opt/fritzdect-bot
ExecStart=/usr/bin/python3 /opt/fritzdect-bot/fritzdect_bot.py -c /opt/fritzdect-bot/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fritzdect-bot

# Umgebungsvariablen
Environment=PYTHONUNBUFFERED=1
Environment=LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
```

**API Service (`/etc/systemd/system/fritzdect-api.service`):**
```ini
[Unit]
Description=FritzDECT Notification API
After=network.target
Wants=network.target

[Service]
Type=simple
User=fritzdect
Group=fritzdect
WorkingDirectory=/opt/fritzdect-bot
ExecStart=/usr/bin/python3 /opt/fritzdect-bot/notification_api.py -c /opt/fritzdect-bot/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fritzdect-api

# Umgebungsvariablen
Environment=PYTHONUNBUFFERED=1
Environment=LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
```

### 2. Benutzer und Verzeichnisse einrichten

```bash
# Systembenutzer erstellen
sudo useradd -r -s /bin/false -d /opt/fritzdect-bot fritzdect

# Verzeichnis erstellen und Berechtigungen setzen
sudo mkdir -p /opt/fritzdect-bot
sudo chown fritzdect:fritzdect /opt/fritzdect-bot

# Projekt kopieren
sudo cp -r /home/joe/Dokumente/Telegram-FritzDECTBot/* /opt/fritzdect-bot/
sudo chown -R fritzdect:fritzdect /opt/fritzdect-bot

# Config-Datei anpassen
sudo nano /opt/fritzdect-bot/config.json
```

### 3. Services aktivieren und starten

```bash
# Services neu laden
sudo systemctl daemon-reload

# Services aktivieren (Autostart)
sudo systemctl enable fritzdect-bot.service
sudo systemctl enable fritzdect-api.service

# Services starten
sudo systemctl start fritzdect-bot.service
sudo systemctl start fritzdect-api.service

# Status prüfen
sudo systemctl status fritzdect-bot.service
sudo systemctl status fritzdect-api.service

# Logs ansehen
sudo journalctl -u fritzdect-bot -f
sudo journalctl -u fritzdect-api -f
```

### 4. Service-Management

```bash
# Services stoppen
sudo systemctl stop fritzdect-bot.service
sudo systemctl stop fritzdect-api.service

# Services neustarten
sudo systemctl restart fritzdect-bot.service
sudo systemctl restart fritzdect-api.service

# Services deaktivieren
sudo systemctl disable fritzdect-bot.service
sudo systemctl disable fritzdect-api.service
```

### 5. Konfiguration mit mehreren Config-Dateien

Falls unterschiedliche Konfigurationen benötigt werden:

```bash
# Mit alternativer Config-Datei
ExecStart=/usr/bin/python3 /opt/fritzdect-bot/fritzdect_bot.py -c /opt/fritzdect-bot/production.json

# Oder mit Umgebungsvariable
Environment=CONFIG_FILE=/opt/fritzdect-bot/production.json
ExecStart=/usr/bin/python3 /opt/fritzdect-bot/fritzdect_bot.py -c ${CONFIG_FILE}
```

## 🐛 Fehlerbehebung

### Häufige Probleme

**Bot startet nicht**
- Konfiguration prüfen (`config.json`)
- Bot-Token gültig?
- Internetverbindung vorhanden?

**Keine Benachrichtigungen**
- FritzBox-IP in `allowed_fritzbox_ips`?
- Benutzer hat Benachrichtigungs-Modus > 0?
- API läuft auf korrektem Port?

**Login-Probleme**
- Passwort korrekt?
- Benutzer bereits in Datenbank?
- IP-Adresse erlaubt?

### Logs überprüfen
```bash
# Bot-Logs
tail -f debug.log

# API-Logs
tail -f api.log
```

## 📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

## 🤝 Beitrag

Für Beiträge und Bug-Reports bitte Issues oder Pull Requests verwenden.

### 🤖 Spezieller Dank

Ein besonderer Dank geht an **Cascade (AI Assistant)** für die umfangreiche Unterstützung bei:

- **User-Management System** - Komplettes Mehrbenutzer-Workflow mit Rollen
- **Benachrichtigungs-API** - REST-API für FritzBox-Integration  
- **Benachrichtigungs-Modi** - Silent/Push/None Benachrichtigungen
- **Datenbank-Migration** - Dynamische Spalten für neue Benachrichtigungstypen
- **Sicherheits-Features** - IP-Filtering, Rate Limiting, Session Management
- **Dokumentation** - Vollständige README-Dateien und API-Dokumentation
- **Code-Optimierung** - Event-Loop Management, Async/Sync-Kompatibilität
- **Fehlerbehebung** - Debugging und Performance-Optimierung

Ohne diese Unterstützung wäre dieses Projekt in seiner aktuellen Form nicht möglich gewesen!

---

**Viel Spaß mit dem FritzDECT-Bot!** 🚀
