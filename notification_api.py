#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import json
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from lib.config import Config
from lib.user_database import UserDatabase

# Telegram Importe mit Fallback und Voice Support
try:
    from telegram import Bot, InputFile
    import io
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    InputFile = None
    io = None
    print("WARNING: telegram module nicht gefunden - API läuft im Test-Modus")

app = Flask(__name__)

class NotificationAPI:
    def __init__(self):
        self.config = Config()
        self.db = UserDatabase()
        
        # Logging konfigurieren
        logging.basicConfig(
            level=logging.WARNING,  # Nur Warnings und Errors anzeigen
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Telegram Bot initialisieren
        if TELEGRAM_AVAILABLE:
            self.bot = Bot(token=self.config.get_telegram_token())
        else:
            self.bot = None
            self.logger.warning("Telegram Bot nicht verfügbar - Benachrichtigungen werden nicht gesendet")
    
    
    def is_allowed_ip(self, request_ip):
        """Prüft ob die IP-Adresse in der erlaubten Liste ist"""
        allowed_ips = self.config.get_allowed_fritzbox_ips()
        return request_ip in allowed_ips
    
    def get_notification_text(self, notification_type, language_code='en'):
        """Holt den Benachrichtigungstext für den angegebenen Typ und die Sprache"""
        notifications = self.config.get_notifications()
        
        if notification_type not in notifications:
            self.logger.warning(f"Unbekannter Benachrichtigungstyp: {notification_type}")
            return f"Unknown notification type: {notification_type}"
        
        texts = notifications[notification_type]
        return texts.get(language_code, texts.get('en', texts.get('de', 'Notification')))
    
    async def send_notification_to_users(self, notification_type, value=1, note=None):
        """Sendet Benachrichtigung an alle Benutzer mit entsprechender Einstellung"""
        if not self.bot:
            self.logger.warning("Telegram Bot nicht verfügbar - keine Benachrichtigungen gesendet")
            return {'success': False, 'message': 'Telegram Bot nicht verfügbar'}
        
        # Benutzer abrufen, die diese Benachrichtigung erhalten möchten
        users = self.db.get_all_users()
        notifications_sent = 0
        calls_made = 0  # Immer 0, da wir keine echten Anrufe mehr machen
        errors = []
        
        for user in users:
            chat_id = user[0]
            is_admin = user[3]
            language_code = user[10] if len(user) > 10 else 'en'
            
            # Dynamisch prüfen ob Benutzer die Benachrichtigung erhalten möchte
            notification_settings = self.db.get_notification_settings(chat_id)
            
            # Config-Key zu Datenbank-Feld-Namen konvertieren
            db_field_name = f"notify{notification_type.title().replace('_', '')}"
            
            user_mode = notification_settings.get(db_field_name, 'none')
            
            # Prüfen ob Benutzer benachrichtigt werden möchte
            if user_mode == 'none':
                continue  # Keine Benachrichtigung
            elif user_mode in ['silent', 'push']:
                should_notify = True
            else:
                should_notify = True  # Fallback
            
            if should_notify:
                try:
                    # Zuerst Nachricht senden
                    text = self.get_notification_text(notification_type, language_code)
                    
                    # Wert an den Text anhängen falls vorhanden
                    if value is not None:
                        text += f"\n\nWert: {value}"
                    
                    # Note an den Text anhängen falls vorhanden
                    if note:
                        text += f"\n\n📝 **Nachricht:** {note}"
                    
                    # Nachricht senden basierend auf Modus
                    if user_mode == 'none':  # none - Keine Benachrichtigung
                        continue  # Überspringen, keine Benachrichtigung
                        
                    elif user_mode == 'silent':  # silent - Silent Notification
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode='Markdown',
                            disable_notification=True  # Silent Notification
                        )
                        notifications_sent += 1
                        self.logger.info(f"Silent Benachrichtigung gesendet an User {chat_id} ({language_code}) - Modus: {user_mode}")
                        
                    elif user_mode == 'push':  # push - Normale Push-Nachricht
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode='Markdown'
                        )
                        notifications_sent += 1
                        self.logger.info(f"Push Benachrichtigung gesendet an User {chat_id} ({language_code}) - Modus: {user_mode}")
                    
                except Exception as e:
                    error_msg = f"Fehler beim Senden an User {chat_id}: {e}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
        
        result = {
            'success': True,
            'notifications_sent': notifications_sent,
            'calls_made': calls_made,
            'errors': errors
        }
        
        if errors:
            result['success'] = False
            result['message'] = f"{notifications_sent} Benachrichtigungen gesendet, aber {len(errors)} Fehler aufgetreten"
        else:
            result['message'] = f"{notifications_sent} Benachrichtigungen erfolgreich gesendet"
        
        return result
    
    def validate_request(self, request_data):
        """Validiert die Anfragedaten"""
        if not request_data:
            return False, "Keine Daten erhalten"
        
        # Dynamisch alle Benachrichtigungstypen aus der Config laden
        notifications = self.config.get_notifications()
        
        # Prüfen welcher Parameter in der Anfrage vorhanden ist
        for param_name in request_data:
            # Config-Key aus Parameter-Namen erstellen (CamelCase zu snake_case)
            config_key = ''.join(['_' + c.lower() if c.isupper() else c for c in param_name]).lstrip('_')
            
            if config_key in notifications:
                return True, config_key
        
        return False, f"Kein gültiger Benachrichtigungstyp gefunden. Erlaubt: {list(notifications.keys())}"

# API-Instanz erstellen
notification_api = NotificationAPI()

@app.route('/notify', methods=['POST'])
def notify():
    """Benachrichtigungs-Endpunkt für FritzBox"""
    try:
        # IP-Prüfung
        if not notification_api.is_allowed_ip(request.remote_addr):
            notification_api.logger.warning(f"Zugriff von nicht erlaubter IP: {request.remote_addr}")
            return jsonify({
                'success': False,
                'error': 'Access Denied',
                'message': 'IP-Adresse nicht erlaubt'
            }), 403
        
        # Request-Daten validieren
        request_data = request.get_json() if request.is_json else request.form.to_dict()
        
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Invalid Request',
                'message': 'Keine Daten erhalten'
            }), 400
        
        # Benachrichtigungstyp validieren
        validation_result = notification_api.validate_request(request_data)
        
        if isinstance(validation_result, tuple):
            is_valid, notification_type = validation_result
        else:
            is_valid = False
            notification_type = validation_result
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid Request',
                'message': notification_type
            }), 400
        
        # Wert und Note dynamisch extrahieren
        value = None
        note = None
        
        for param_name, param_value in request_data.items():
            # Config-Key aus Parameter-Namen erstellen (CamelCase zu snake_case)
            config_key = ''.join(['_' + c.lower() if c.isupper() else c for c in param_name]).lstrip('_')
            
            if config_key == notification_type:
                value = param_value
            elif param_name.lower() == 'note':
                note = str(param_value)
        
        # Benachrichtigungen senden (asynchron ausführen)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                notification_api.send_notification_to_users(notification_type, value, note)
            )
        finally:
            loop.close()
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        notification_api.logger.error(f"Unerwarteter Fehler in /notify: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health-Check Endpunkt"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'telegram_available': TELEGRAM_AVAILABLE
    })

@app.route('/status', methods=['GET'])
def status():
    """Status-Endpunkt mit Konfigurationsinfo"""
    try:
        return jsonify({
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'config': {
                'allowed_ips': notification_api.config.get_allowed_fritzbox_ips(),
                'api_port': notification_api.config.get_api_port(),
                'telegram_available': TELEGRAM_AVAILABLE
            },
            'database': {
                'total_users': len(notification_api.db.get_all_users())
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Konfiguration laden
    config = Config()
    port = config.get_api_port()
    
    print(f"Starte Notification API auf Port {port}")
    print(f"Erlaubte IPs: {config.get_allowed_fritzbox_ips()}")
    print(f"Health-Check: http://localhost:{port}/health")
    print(f"Status: http://localhost:{port}/status")
    print(f"Benachrichtigung: http://localhost:{port}/notify?DoorPowerMeter=1")
    
    # Flask-App starten
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
