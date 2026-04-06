# Notification API für FritzDECT-Bot

Diese REST-API ermöglicht es der FritzBox, Benachrichtigungen an den Telegram-Bot zu senden.

## Funktionen

- **Sichere API**: IP-Validierung gegen konfigurierte FritzBox-Adressen
- **Mehrere Benachrichtigungstypen**: DoorPowerMeter, DoorFrontDoor, VacationMode
- **Sprachsensitive Benachrichtigungen**: Texte werden pro Sprache in der config.json konfiguriert
- **Benutzerbasierte Benachrichtigungen**: Nur Benutzer mit entsprechenden Einstellungen erhalten Nachrichten
- **Health-Check**: Status-Endpunkte zur Überwachung

## Installation

1. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

2. Konfiguration anpassen:
```bash
cp config.example.json config.json
# config.json bearbeiten und Bot-Token, Admin-Chat-ID etc. eintragen
```

## Konfiguration

### config.json erweitern

Die API benötigt folgende zusätzliche Konfigurationen (siehe `config.example.json`):

```json
{
  "security": {
    "max_failed_attempts": 5,
    "block_duration_days": 2,
    "allowed_fritzbox_ips": ["192.168.178.1"],
    "api_port": 8080
  },
  "notifications": {
    "door_power_meter": {
      "de": "🚪 **Tür vom Stromzähler**\n\nEin Ereignis wurde an der FritzBox ausgelöst.\n\nPrüfe bitte den Status der Geräte.",
      "en": "🚪 **Door Power Meter**\n\nAn event has been triggered at the FritzBox.\n\nPlease check the status of your devices."
    },
    "door_front_door": {
      "de": "🏠 **Haustür**\n\nDie Haustür wurde geöffnet oder geschlossen.",
      "en": "🏠 **Front Door**\n\nThe front door has been opened or closed."
    },
    "vacation_mode": {
      "de": "🏖️ **Urlaubsmodus**\n\nDer Urlaubsmodus wurde aktiviert/deaktiviert.",
      "en": "🏖️ **Vacation Mode**\n\nThe vacation mode has been activated/deactivated."
    },
    "temperature_warning": {
      "de": "🌡️ **Temperaturwarnung**\n\nDie Temperatur hat einen kritischen Wert erreicht.\n\nBitte prüfen Sie die Einstellungen.",
      "en": "🌡️ **Temperature Warning**\n\nThe temperature has reached a critical value.\n\nPlease check your settings."
    },
    "burglar_alarm": {
      "de": "🚨 **EINBRUCHALARM**\n\nEin Einbruchversuch wurde gemeldet.\n\nBitte überprüfen Sie die Situation sofort und rufen Sie bei Bedarf die Polizei!",
      "en": "🚨 **BURGLAR ALARM**\n\nA burglary attempt has been reported.\n\nPlease check the situation immediately and call police if needed!"
    }
  }
}
```

### Sicherheitseinstellungen

- **allowed_fritzbox_ips**: Liste der IP-Adressen, die API-Aufrufe machen dürfen
- **api_port**: Port auf dem die API läuft (Standard: 8080)

### Benachrichtigungseinstellungen

Die Benutzer können jetzt zwischen drei Benachrichtigungs-Modi wählen:

**Benachrichtigungs-Modi:**
- **0 / 'none'** - Keine Benachrichtigung
- **1 / 'silent'** - Silent Notification (ohne Ton)
- **2 / 'push'** - Push-Nachricht (mit Ton)

**Datenbank-Spalten:**
- `notifyDoorPowerMeter` - Modi für Strom/Tür-Meldungen
- `notifyDoorFrontDoor` - Modi für Haustür-Meldungen  
- `notifyVacationMode` - Modi für Urlaubsmodus-Meldungen
- `notifyTemperatureWarning` - Modi für Temperaturwarnungen
- `notifyBurglarAlarm` - Modi für Einbruchalarme
- **Dynamische Spalten** für jeden neuen Benachrichtigungstyp

**Beispiel-Einstellungen:**
```python
# Im Bot-Code:
db.update_notification_setting(chat_id, 'notifyDoorPowerMeter', 'push')  # Push bei Strom-Meldung
db.update_notification_setting(chat_id, 'notifyVacationMode', 'none')     # Keine Urlaubs-Benachrichtigung
db.update_notification_setting(chat_id, 'notifyBurglarAlarm', 'silent')  # Silent bei Einbruch
```

**API-Verhalten:**
- Benutzer mit `none` erhalten keine Benachrichtigung
- Benutzer mit `silent` erhalten stille Benachrichtigung (ohne Ton)
- Benutzer mit `push` erhalten normale Push-Benachrichtigung (mit Ton)

## API-Endpunkte

### Benachrichtigung senden

**GET** `/notify?DoorPowerMeter=1`
**POST** `/notify` mit JSON-Body

Die API unterstützt **dynamische Benachrichtigungstypen**! Jeder Eintrag in der `notifications` Sektion der config.json wird automatisch als Benachrichtigungstyp verfügbar gemacht.

**Parameter-Namen:**
- Config-Key: `door_power_meter` → API-Parameter: `DoorPowerMeter`
- Config-Key: `door_front_door` → API-Parameter: `DoorFrontDoor`
- Config-Key: `vacation_mode` → API-Parameter: `VacationMode`
- Config-Key: `temperature_warning` → API-Parameter: `TemperatureWarning`
- Config-Key: `burglar_alarm` → API-Parameter: `BurglarAlarm`
- Config-Key: `custom_alert` → API-Parameter: `CustomAlert`

Beispiele mit den Standard-Typen:
```bash
# GET-Anfrage (einfach)
curl "http://localhost:8080/notify?DoorPowerMeter=1"

# GET-Anfrage mit Nachricht (URL-codiert)
curl "http://localhost:8080/notify?DoorPowerMeter=1&note=Test%20Nachricht"

# GET-Anfrage mit Umlauten (URL-codiert)
curl "http://localhost:8080/notify?DoorPowerMeter=1&note=T%C3%BCr%20wurde%20ge%C3%B6ffnet"

# POST-Anfrage (einfach)
curl -X POST http://localhost:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"DoorFrontDoor": 1}'

# POST-Anfrage mit Nachricht (keine Codierung nötig)
curl -X POST http://localhost:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"DoorFrontDoor": 1, "note": "Haustür wurde geöffnet"}'

# POST-Anfrage mit Temperaturwarnung
curl -X POST http://localhost:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"TemperatureWarning": 1, "note": "Temperatur zu hoch"}'

# POST-Anfrage mit Einbruchalarm
curl -X POST http://localhost:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"BurglarAlarm": 1, "note": "Einbruch erkannt"}'
```

**Wichtiger Hinweis zur URL-Codierung:**
- Bei **GET-Anfragen** müssen Sonderzeichen und Leerzeichen URL-codiert werden
- Bei **POST-Anfragen** mit JSON-Body ist keine manuelle Codierung nötig
- Leerzeichen → `%20`, `ü` → `%C3%BC`, `ö` → `%C3%B6`

**Nachrichten-Parameter:**
- `note`: Optionaler Parameter für zusätzliche Textnachrichten von der FritzBox
- Die Nachricht wird in der Telegram-Benachrichtigung mit 📝 **Nachricht:** angezeigt
- Unterstützt bei GET und POST Anfragen

**Neue Benachrichtigungstypen hinzufügen:**
1. In `config.json` unter `notifications` neuen Eintrag hinzufügen
2. API neu starten
3. Sofort verfügbar - kein Code-Änderung nötig!

Beispiel für neuen Typ:
```json
{
  "notifications": {
    "door_power_meter": { ... },
    "door_front_door": { ... },
    "vacation_mode": { ... },
    "temperature_warning": { ... },
    "burglar_alarm": { ... },
    "custom_alert": {
      "de": "⚠️ **Benutzerdefinierter Alarm**\n\nEin benutzerdefiniertes Ereignis ist eingetreten.",
      "en": "⚠️ **Custom Alert**\n\nA custom event has occurred."
    }
  }
}
```

Verwendung: `curl "http://localhost:8080/notify?CustomAlert=1&note=Benutzerdefinierte Nachricht"`

### Health-Check

**GET** `/health`

Gibt den Status der API zurück.

### Status

**GET** `/status`

Gibt detaillierte Informationen über Konfiguration und Datenbank zurück.

## Betrieb

### API starten

```bash
python3 notification_api.py
```

Die API startet auf dem konfigurierten Port (Standard: 8080) und lauscht auf allen Interfaces (0.0.0.0).

### Mit dem Bot zusammen betreiben

Die API kann parallel zum Telegram-Bot laufen:

```bash
# Terminal 1: Bot starten
python3 fritzdect_bot.py

# Terminal 2: API starten  
python3 notification_api.py
```

### FritzBox konfigurieren

In der FritzBox kann eine URL-Weiterleitung oder ein Skript konfiguriert werden, das bei Ereignissen die API aufruft:

```
http://<bot-server-ip>:8080/notify?DoorPowerMeter=1
```

Wichtig: Die IP-Adresse des Bot-Servers muss in `allowed_fritzbox_ips` eingetragen sein.

## Testen

```bash
# API-Test-Script ausführen
python3 test_notification_api.py
```

Das Test-Script prüft:
- Health-Check
- Status-Endpunkt
- Benachrichtigungen (GET/POST)
- Fehlerbehandlung
- IP-Validierung

## Fehlerbehebung

### API nicht erreichbar
- Port korrekt konfiguriert?
- Firewall blockiert den Port?
- API-Prozess läuft?

### Keine Benachrichtigungen
- Telegram-Bot-Token korrekt?
- Benutzer haben `notifyDoorPowerMeter = 1` in der Datenbank?
- FritzBox-IP in `allowed_fritzbox_ips`?

### IP-Block aktiv
- Anfrage kommt von erlaubter IP?
- X-Forwarded-For Header korrekt bei Proxy-Setup?

## Logging

Die API verwendet das konfigurierte Logging-System. Logs enthalten:
- API-Start/Stop
- Anfragen von FritzBox
- Gesendete Benachrichtigungen
- Fehler und Warnungen
