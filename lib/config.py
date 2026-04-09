#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os

# Globale Config-Instanz
_global_config = None

class Config:
    def __init__(self, config_file='config.json'):
        global _global_config
        
        # Wenn bereits eine globale Config existiert, diese verwenden
        if _global_config is not None:
            self.config_file = _global_config.config_file
            self.config = _global_config.config
            return
        
        # Erste Instanz - Konfiguration laden mit Fallback
        config_data = self._try_load_config(config_file)
        
        # Wenn das fehlschlägt, Fallback-Konfiguration aus Home-Verzeichnis laden
        if config_data is None:
            fallback_config = os.path.expanduser('~/.fritzdect_config')
            if os.path.exists(fallback_config):
                try:
                    with open(fallback_config, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    self.config_file = fallback_config
                    print(f"Konfiguration aus Fallback-Datei geladen: {fallback_config}")
                except (json.JSONDecodeError, FileNotFoundError):
                    config_data = {}
                    self.config_file = config_file
            else:
                config_data = {}
                self.config_file = config_file
        else:
            self.config_file = config_file
        
        # Erste Instanz - globale Config setzen
        self.config = config_data
        _global_config = self
    
    def _try_load_config(self, config_file):
        """Versucht, eine Konfigurationsdatei zu laden"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def load_config(self):
        try:
            # Absoluten Pfad für bessere Fehlermeldungen
            abs_path = os.path.abspath(self.config_file)
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            abs_path = os.path.abspath(self.config_file)
            print(f"Konfigurationsdatei nicht gefunden: {abs_path}")
            return {}
        except json.JSONDecodeError as e:
            abs_path = os.path.abspath(self.config_file)
            print(f"Fehler beim Lesen der Konfigurationsdatei {abs_path}: {e}")
            return {}
    
    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_telegram_token(self):
        return self.get('telegram.token')
    
    def get_admin_chat_id(self):
        return self.get('telegram.admin_chat_id')
    
    def get_admin_chat_ids(self):
        """Gibt eine Liste von Admin-Chat-IDs zurück"""
        admin_id = self.get('telegram.admin_chat_id')
        if isinstance(admin_id, list):
            return admin_id
        elif admin_id:
            return [admin_id]
        return []
    
    def get_expire_notification_config(self):
        """Gibt die Konfiguration für Ablauf-Benachrichtigungen zurück"""
        return self.get('expire_notifications', {
            'enabled': True,
            'warning_days': [7, 3, 1],  # Tage vor Ablauf warnen
            'weekly_summary': True,
            'summary_day': 1,  # Wochentag (1=Montag)
            'summary_time': '09:00'  # Uhrzeit
        })
    
    def get_telegram_password(self):
        return self.get('telegram.password')
    
    def get_fritzbox_config(self):
        return self.get('fritzbox', {})
    
    def get_database_config(self):
        return self.get('database', {})
    
    def get_logging_config(self):
        return self.get('logging', {'level': 'INFO', 'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'})
    
    def get_security_config(self):
        return self.get('security', {'max_failed_attempts': 5, 'block_duration_days': 2})
    
    def get_max_failed_attempts(self):
        return self.get('security.max_failed_attempts', 5)
    
    def get_block_duration_days(self):
        return self.get('security.block_duration_days', 2)
    
    def get_allowed_fritzbox_ips(self):
        """Gibt die Liste der erlaubten FritzBox-IPs zurück"""
        return self.get('security.allowed_fritzbox_ips', ['192.168.178.1'])
    
    def get_api_port(self):
        """Gibt den API-Port zurück"""
        return self.get('security.api_port', 8080)
    
    def get_notifications(self):
        """Gibt die Benachrichtigungstexte zurück"""
        return self.get('notifications', {})
    
    def get_notification_modes(self):
        """Gibt die konfigurierten Benachrichtigungs-Modi zurück"""
        return {
            'none': {'value': 0, 'description': 'Keine Benachrichtigung', 'icon': '🔕'},
            'silent': {'value': 1, 'description': 'Silent Notification', 'icon': '🔔'},
            'push': {'value': 2, 'description': 'Push-Nachricht', 'icon': '📱'},
            'default_mode': 'none'
        }
    
    def get_default_notification_mode(self):
        """Gibt den Standard-Benachrichtigungsmodus zurück"""
        modes = self.get_notification_modes()
        return modes.get('default_mode', 'none')

# Konstanten für Bot-Zustände
MAIN, LOGIN, ADMIN, STATISTICS, AUTOMATION, SETTINGS = range(6)

# Modi werden in fritzdect_bot.py gesetzt (um zirkuläre Imports zu vermeiden)
modeList = [None, None, None, None, None, None]

# Import hier am Ende der Datei, um zirkuläre Imports zu vermeiden
def init_mode_list():
    """Initialisiert die modeList mit den Klassen"""
    global modeList
    try:
        import lib.loginMode as LoginMode
        import lib.adminMode as AdminMode  
        import lib.statistikMode_optimized as StatistikModeOptimized
        import lib.automationMode_optimized as AutomationModeOptimized
        import lib.settingsMode as SettingsMode
        
        # Globale modeList aktualisieren (nicht lokale Variable!)
        modeList[0] = None  # MAIN
        modeList[1] = LoginMode
        modeList[2] = AdminMode
        modeList[3] = StatistikModeOptimized
        modeList[4] = AutomationModeOptimized
        modeList[5] = SettingsMode
    except ImportError as e:
        # Fallback für Tests ohne vollständige Installation
        print(f"ImportError in init_mode_list: {e}")
        pass

# Tastatur-Layouts
reply_keyboard_main = [['Temperatur setzen', 'Temp.-Verlauf', 'Heizung'],['Automation','Einstellungen','Logout']]

def genMarkupList():
    """Generiert die MarkupList für alle Modi"""
    # Stelle sicher, dass die modeList initialisiert ist
    init_mode_list()
    
    try:
        from telegram import ReplyKeyboardMarkup
    except ImportError:
        # Fallback für Tests ohne Telegram
        ReplyKeyboardMarkup = None
    
    markupList = {}
    for i in range(len(modeList)):
        if modeList[i] != None:
            if ReplyKeyboardMarkup:
                markupList[i] = ReplyKeyboardMarkup(buildKeyboard(modeList[i]), one_time_keyboard=False, resize_keyboard=True)
            else:
                # Fallback: Leere Liste
                markupList[i] = []
        else:
            if ReplyKeyboardMarkup:
                markupList[i] = ReplyKeyboardMarkup(reply_keyboard_main, one_time_keyboard=False, resize_keyboard=True)
            else:
                markupList[i] = []
    return markupList

def getMarkupList(status):
    """Gibt die MarkupList für einen bestimmten Status zurück"""
    try:
        from telegram import ReplyKeyboardMarkup
    except ImportError:
        # Fallback für Tests ohne Telegram
        ReplyKeyboardMarkup = None
    
    if modeList[status] != None:
        if ReplyKeyboardMarkup:
            return ReplyKeyboardMarkup(buildKeyboard(modeList[status]), one_time_keyboard=False, resize_keyboard=True)
        else:
            return []
    return []

def buildKeyboard(classs):
    """Erstellt eine Tastatur aus den Variablen 'tastertur' einer Klasse"""
    temp=[]
    reply_keyboard=[]
    i=0
    
    # Fallback für tastertur Attribut
    if hasattr(classs, 'tastertur'):
        tastertur_values = classs.tastertur.values()
    else:
        # Standard-Tastatur wenn tastertur nicht vorhanden
        tastertur_values = ['Hilfe', 'Zurück']
    
    for v in tastertur_values:
        temp.append(v)
        i=i+1
        if i % 3 == 0:
            reply_keyboard.append(temp)
            temp=[]
    reply_keyboard.append(temp)
    return reply_keyboard

# markupList wird in fritzdect_bot.py generiert
markupList = None

