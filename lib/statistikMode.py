#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import importlib.util
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import asyncio
import threading
import logging

# Logger initialisieren
logger = logging.getLogger(__name__)

def load_module(name, filepath):
    """Load a module from file path using importlib"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), filepath))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Load configuration and database modules
config_module = load_module("config", "config.py")
config = config_module.Config()

# Globale Variablen für Fenster-Offen-Modus
window_open_timers = {}  # {chat_id: {ain: end_time, timer_thread: thread}}
window_open_notifications = {}  # {chat_id: {ain: notification_sent}}

def set_window_open_mode(fritz_api, ain, duration_minutes=None, chat_id=None, bot_instance=None):
    """Setzt den Fenster-Offen-Modus für ein Gerät"""
    try:
        # Konfiguration laden
        window_config = config.get('window_open', {})
        
        # Dauer aus Parameter oder Konfiguration
        if duration_minutes is None:
            duration_minutes = window_config.get('default_duration_minutes', 30)
        
        # Maximale Dauer aus Konfiguration
        max_duration_hours = window_config.get('max_duration_hours', 24)
        max_duration_minutes = max_duration_hours * 60
        duration_minutes = min(duration_minutes, max_duration_minutes)
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        end_timestamp = int(end_time.timestamp())
        
        # Versuche verschiedene URLs für sethkrwindowopen
        urls_to_try = [
            f"http://{fritz_api.host}:49000/webservices/homeautoswitch.lua",  # TR-064
            f"http://{fritz_api.host}:80/webservices/homeautoswitch.lua",      # Standard-HTTP
            f"http://{fritz_api.host}:{fritz_api.port}/webservices/homeautoswitch.lua"  # Konfigurierter Port
        ]
        
        # Sicherstellen, dass die SID gesetzt ist
        if not fritz_api.sid:
            logger.error("Keine SID verfügbar - versuche Login")
            if not fritz_api.login():
                logger.error("Login fehlgeschlagen")
                return {'success': False, 'error': 'Login fehlgeschlagen'}
            logger.info(f"Login erfolgreich, SID: {fritz_api.sid}")
        
        for url in urls_to_try:
            logger.debug(f"Versuche URL: {url}")
            params = {
                'sid': fritz_api.sid,
                'ain': ain,
                'switchcmd': 'sethkrwindowopen',
                'endtimestamp': str(end_timestamp)  # Als String gemäß Doku
            }
            
            logger.debug(f"Parameter: {params}")
            response = fritz_api.session.get(url, params=params, timeout=10)
            logger.debug(f"Status: {response.status_code}")
            logger.debug(f"Response: {response.text.strip()}")
            logger.debug(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                logger.debug(f"Erfolg mit URL: {url}")
                # Timer für Erinnerung starten
                if chat_id:
                    # Heizkörper-Namen abfragen
                    heater_name = None
                    try:
                        devices = fritz_api.get_devices()
                        for device in devices:
                            if device.get('ain') == ain:
                                heater_name = device.get('name', f'Heizkörper {ain}')
                                break
                    except Exception as e:
                        logger.debug(f"Konnte Heizkörper-Namen nicht abfragen: {e}")
                    
                    start_window_open_timer(chat_id, ain, end_time, bot_instance, heater_name)
                
                return {
                    'success': True,
                    'end_time': end_time,
                    'end_timestamp': end_timestamp,
                    'duration_minutes': duration_minutes,
                    'url_used': url
                }
            else:
                logger.debug(f"Fehler mit URL: {url} - Status: {response.status_code}")
        
        # Wenn alle Versuche fehlschlagen
        logger.error("Alle URL-Versuche fehlgeschlagen")
        return {'success': False, 'error': 'Alle Verbindungsversuche fehlgeschlagen'}
            
    except Exception as e:
        logger.error(f"Fehler beim Setzen des Fenster-Offen-Modus: {e}")
        return {'success': False, 'error': str(e)}

def disable_window_open_mode(fritz_api, ain):
    """Deaktiviert den Fenster-Offen-Modus für ein Gerät"""
    try:
        # Sicherstellen, dass die SID gesetzt ist
        if not fritz_api.sid:
            logger.error("Keine SID verfügbar - versuche Login")
            if not fritz_api.login():
                logger.error("Login fehlgeschlagen")
                return False
            logger.info(f"Login erfolgreich, SID: {fritz_api.sid}")
        
        # sethkrwindowopen mit endtimestamp=0 senden
        window_open_url = f"http://{fritz_api.host}:{fritz_api.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': fritz_api.sid,
            'ain': ain,
            'switchcmd': 'sethkrwindowopen',
            'endtimestamp': 0  # Originaler Parametername
        }
        
        logger.debug(f"Disable Parameters: {params}")
        response = fritz_api.session.get(window_open_url, params=params, timeout=10)
        logger.debug(f"Disable Status: {response.status_code}")
        logger.debug(f"Disable Response: {response.text.strip()}")
        
        return response.status_code == 200
            
    except Exception as e:
        logger.error(f"Fehler beim Deaktivieren: {e}")
        return False

# Globale Variablen für Timer
global_bot_instance = None

def start_window_open_timer(chat_id, ain, end_time, bot_instance=None, heater_name=None):
    """Startet einen Timer für die Fenster-Offen-Erinnerung"""
    # Alten Timer für dieses Gerät löschen
    if chat_id in window_open_timers and ain in window_open_timers[chat_id]:
        old_thread = window_open_timers[chat_id][ain].get('timer_thread')
        if old_thread and old_thread.is_alive():
            return  # Timer läuft bereits
    
    # Initialisiere Struktur
    if chat_id not in window_open_timers:
        window_open_timers[chat_id] = {}
    if chat_id not in window_open_notifications:
        window_open_notifications[chat_id] = {}
    
    window_open_timers[chat_id][ain] = {
        'end_time': end_time,
        'timer_thread': None
    }
    window_open_notifications[chat_id][ain] = False
    
    # Erinnerungszeit aus Konfiguration laden
    window_config = config.get('window_open', {})
    reminder_minutes = window_config.get('reminder_minutes_before', 5)
    
    # Timer-Funktion mit closures für die benötigten Variablen
    def timer_function(chat_id_param, ain_param, end_time_param, reminder_minutes_param, bot_instance_param, heater_name_param):
        # Warte bis X Minuten vor Ablauf
        notification_time = end_time_param - timedelta(minutes=reminder_minutes_param)
        now = datetime.now()
        
        if notification_time > now:
            sleep_seconds = (notification_time - now).total_seconds()
            threading.Event().wait(sleep_seconds)
        
        # Sende Erinnerung (wenn noch nicht gesendet)
        if not window_open_notifications.get(chat_id_param, {}).get(ain_param, False):
            window_open_notifications[chat_id_param][ain_param] = True
            
            # Erinnerung an den Bot senden
            try:
                if bot_instance_param:
                    # Heizkörper-Namen verwenden, falls verfügbar, sonst AIN
                    display_name = heater_name_param if heater_name_param else ain_param
                    reminder_text = f"🔔 *Erinnerung: Fenster schließen*\n\n"
                    reminder_text += f"🏠 {display_name}\n"
                    reminder_text += f"⏰ Fenster-Offen Modus endet in {reminder_minutes_param} Minuten\n"
                    reminder_text += f"📅 Bitte Fenster schließen"
                    
                    # Bot-Message in einer separaten async-Funktion senden
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        bot_instance_param.send_message(
                            chat_id=chat_id_param,
                            text=reminder_text,
                            parse_mode='Markdown'
                        )
                    )
                    loop.close()
                    logger.info(f"Erinnerung an Chat {chat_id_param} gesendet für Gerät {display_name}")
                else:
                    display_name = heater_name_param if heater_name_param else ain_param
                    logger.info(f"🔔 Erinnerung für Chat {chat_id_param}, Gerät {display_name}: Fenster schließen in {reminder_minutes_param} Minuten")
            except Exception as e:
                display_name = heater_name_param if heater_name_param else ain_param
                logger.error(f"Fehler beim Senden der Erinnerung: {e}")
                # Fallback auf Log-Ausgabe
                logger.info(f"🔔 Erinnerung für Chat {chat_id_param}, Gerät {display_name}: Fenster schließen in {reminder_minutes_param} Minuten")
    
    # Timer starten
    timer_thread = threading.Thread(target=timer_function, args=(chat_id, ain, end_time, reminder_minutes, bot_instance, heater_name), daemon=True)
    timer_thread.start()
    
    window_open_timers[chat_id][ain]['timer_thread'] = timer_thread

def get_window_open_status(fritz_api, ain):
    """Prüft den Status des Fenster-Offen-Modus"""
    try:
        # getdevicelistinfos abrufen und nach windowopenactiv suchen
        device_list_url = f"http://{fritz_api.host}:{fritz_api.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': fritz_api.sid,
            'switchcmd': 'getdevicelistinfos'
        }
        
        response = fritz_api.session.get(device_list_url, params=params, timeout=10)
        
        if response.status_code == 200:
            content = response.text.strip()
            root = ET.fromstring(content)
            
            for device in root.findall('device'):
                device_ain = device.get('identifier') or device.get('ain')
                if device_ain == ain or ain in device_ain:
                    hkr_elem = device.find('hkr')
                    if hkr_elem is not None:
                        windowopen_elem = hkr_elem.find('windowopenactiv')
                        if windowopen_elem is not None:
                            is_active = windowopen_elem.text == '1'
                            
                            # Endzeit prüfen
                            endtime_elem = hkr_elem.find('windowopenactiveendtime')
                            end_timestamp = None
                            end_time = None
                            
                            if endtime_elem is not None:
                                try:
                                    end_timestamp = int(endtime_elem.text)
                                    if end_timestamp > 0:
                                        end_time = datetime.fromtimestamp(end_timestamp)
                                except (ValueError, TypeError):
                                    pass
                            
                            return {
                                'active': is_active,
                                'end_timestamp': end_timestamp,
                                'end_time': end_time
                            }
            
            return {'active': False, 'end_timestamp': None, 'end_time': None}
        
        return None
        
    except Exception as e:
        logger.error(f"Fehler bei Fenster-Status Abfrage: {e}")
        return None

def get_device_next_change_from_list(fritz_api, ain):
    """Holt die nächste Temperaturänderung für ein Gerät über getdevicelistinfos"""
    try:
        # getdevicelistinfos abrufen
        device_list_url = f"http://{fritz_api.host}:{fritz_api.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': fritz_api.sid,
            'switchcmd': 'getdevicelistinfos'
        }
        
        response = fritz_api.session.get(device_list_url, params=params, timeout=10)
        
        if response.status_code == 200:
            content = response.text.strip()
            root = ET.fromstring(content)
            
            # Nach dem spezifischen Gerät suchen
            for device in root.findall('device'):
                device_ain = device.get('identifier') or device.get('ain')
                if device_ain == ain or ain in device_ain:
                    # nextchange für dieses Gerät suchen
                    hkr_elem = device.find('hkr')
                    if hkr_elem is not None:
                        nextchange_elem = hkr_elem.find('nextchange')
                        if nextchange_elem is not None:
                            nextchange_data = {}
                            
                            # tchange (Zieltemperatur)
                            tchange_elem = nextchange_elem.find('tchange')
                            if tchange_elem is not None:
                                tchange_value = tchange_elem.text
                                if tchange_value == '255' or tchange_value == '0xff':
                                    nextchange_data['target_temp'] = None  # unbekannt/undefiniert
                                else:
                                    try:
                                        temp_value = float(tchange_value) / 2  # FritzBox speichert in 0.5°C Schritten
                                        nextchange_data['target_temp'] = temp_value
                                    except (ValueError, TypeError):
                                        nextchange_data['target_temp'] = None
                            
                            # endperiod (Timestamp)
                            endperiod_elem = nextchange_elem.find('endperiod')
                            if endperiod_elem is not None:
                                try:
                                    timestamp = int(endperiod_elem.text)
                                    if timestamp == 0:
                                        nextchange_data['timestamp'] = None  # unbekannt
                                        nextchange_data['datetime'] = None
                                    else:
                                        nextchange_data['timestamp'] = timestamp
                                        nextchange_data['datetime'] = datetime.fromtimestamp(timestamp)
                                except (ValueError, TypeError):
                                    nextchange_data['timestamp'] = None
                                    nextchange_data['datetime'] = None
                            
                            return nextchange_data
            
            return None
        
        return None
        
    except Exception as e:
        logger.error(f"Fehler bei nextchange Abfrage: {e}")
        return None


# Import markupList from config
from lib.config import genMarkupList, LOGIN, MAIN, ADMIN, STATISTICS, Config
# markupList wird zur Laufzeit generiert, nicht beim Import
markupList = None
# TODO: Gruppen-funktionen beachten (Absenk-/Komfortemperatur, Zeitplan edit)??? Alle Fensrter auf setzten DEBUGGEN!!!!
# TODO: Adminmode Testen!!! Alle Scenaren und Vorlagen ausführen lassen. in extra Mode.

def is_vacation_active(fritz_api=None):
    """
    Hilfsfunktion zur Überprüfung ob der Urlaubsmodus aktiv ist
    
    Args:
        fritz_api: FritzBoxAPI Instanz (optional, wird bei None erstellt)
    
    Returns:
        dict: {
            'is_active': bool,           # True wenn Urlaubsmodus aktiv
            'percentage': float,         # Prozentuale Aktivierung
            'active_count': int,         # Anzahl der Heizkörper im Urlaubsmodus
            'total_count': int,         # Gesamtzahl der Heizkörper
            'vacation_temp': float,      # Urlaubstemperatur
            'heaters': list            # Detaillierte Heizkörper-Informationen
        }
    """
    
    # API initialisieren wenn nicht übergeben
    if fritz_api is None:
        from lib.fritzbox_api import FritzBoxAPI
        fritz_api = FritzBoxAPI()
        
        # Login durchführen
        if not fritz_api.login():
            return {
                'is_active': False,
                'percentage': 0.0,
                'active_count': 0,
                'total_count': 0,
                'vacation_temp': 16.0,
                'heaters': [],
                'error': 'Login fehlgeschlagen'
            }
    
    try:
        # Urlaubstemperatur aus Vorlage ermitteln
        from lib.config import Config
        config = Config()
        vacation_on_name = config.get('templates.vacation_on', 'Urlaubsschaltung AN')
        
        template_xml = fritz_api.get_template_list_aha()
        vacation_temp = None
        
        if template_xml:
            templates = fritz_api.parse_template_xml(template_xml)
            
            # Urlaubsvorlagen finden
            for template in templates:
                if template['name'] == vacation_on_name:
                    # Vorlage-Section extrahieren
                    template_start = template_xml.find(f'identifier="{template["identifier"]}"')
                    template_section = template_xml[template_start:template_start+1000]
                    
                    # Nach Temperatur in der Vorlage suchen
                    import re
                    temp_patterns = [
                        r'<temperature[^>]*>([^<]*)</temperature>',
                        r'<hkr[^>]*>([^<]*)</hkr>',
                        r'temperature="([^"]*)"',
                        r'hkr[^=]*="([^"]*)"',
                        r'<hkrsoll[^>]*>([^<]*)</hkrsoll>',
                        r'hkrsoll="([^"]*)"',
                        r'<tsoll[^>]*>([^<]*)</tsoll>',
                        r'tsoll="([^"]*)"'
                    ]
                    
                    for pattern in temp_patterns:
                        matches = re.findall(pattern, template_section)
                        for match in matches:
                            try:
                                temp_value = float(match)
                                # FritzBox speichert oft als *2
                                if temp_value > 50:  # Wahrscheinlich *2 gespeichert
                                    vacation_temp = temp_value / 2
                                else:
                                    vacation_temp = temp_value
                                break
                            except ValueError:
                                continue
                        if vacation_temp is not None:
                            break
                    break
        
        # Wenn keine Urlaubstemperatur gefunden, Standard verwenden
        if vacation_temp is None:
            # Standard-Urlaubstemperatur (kann konfiguriert werden)
            vacation_temp = config.get('templates.vacation_temperature', 16.0)
        
        # Heizkörper analysieren
        devices = fritz_api.get_devices()
        if not devices:
            return {
                'is_active': False,
                'percentage': 0.0,
                'active_count': 0,
                'total_count': 0,
                'vacation_temp': vacation_temp,
                'heaters': [],
                'error': 'Keine Geräte gefunden'
            }
        
        heaters = [device for device in devices if 'thermostat' in device]
        heater_details = []
        vacation_active_count = 0
        
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            ain = heater.get('ain', '')
            thermostat = heater.get('thermostat', {})
            tsoll = thermostat.get('tsoll', '40')  # Standard 20°C = 40
            tist = thermostat.get('tist', '40')
            holiday_active = thermostat.get('holidayactive', '0')
            
            # Zieltemperatur umrechnen
            try:
                target_temp = float(tsoll) / 2
            except (ValueError, TypeError):
                target_temp = 20.0
            
            # Ist-Temperatur umrechnen
            try:
                actual_temp = float(tist) / 2
            except (ValueError, TypeError):
                actual_temp = 20.0
            
            # Prüfen ob Urlaubstemperatur eingestellt ist
            is_vacation_temp = abs(target_temp - vacation_temp) < 0.5
            
            if is_vacation_temp:
                vacation_active_count += 1
            
            heater_details.append({
                'name': name,
                'ain': ain,
                'target_temp': target_temp,
                'actual_temp': actual_temp,
                'is_vacation': is_vacation_temp,
                'holiday_active': holiday_active == '1'
            })
        
        # Ergebnisse berechnen
        total_heaters = len(heaters)
        vacation_percentage = (vacation_active_count / total_heaters) * 100 if total_heaters > 0 else 0.0
        
        return {
            'is_active': vacation_percentage >= 80,  # 80%+ = aktiv
            'percentage': vacation_percentage,
            'active_count': vacation_active_count,
            'total_count': total_heaters,
            'vacation_temp': vacation_temp,
            'heaters': heater_details,
            'error': None
        }
        
    except Exception as e:
        return {
            'is_active': False,
            'percentage': 0.0,
            'active_count': 0,
            'total_count': 0,
            'vacation_temp': 16.0,
            'heaters': [],
            'error': str(e)
        }

# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'status': 'Status',
         'set_temp': 'Temperatur setzen',
         'temp_history': 'Temp.-Verlauf',
         'vacation_mode': 'Urlaubsmodus',
         'window_open_mode': 'Fenster-Offen Modus',
         'back': 'Zurueck'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'status': 'Zeigt Ziel- und Ist-Temperatur aller Heizkörper an',
         'set_temp': 'Setzt die Temperatur für einen Heizkörper',
         'temp_history': 'Zeigt Temperaturverlauf aller Heizungen der letzten 24 Stunden als Graphik an',
         'vacation_mode': 'Schaltet FritzBox-Urlaubsschaltung für alle Heizkörper ein/aus',
         'window_open_mode': 'Aktiviert den Fenster-Offen Modus für Heizkörper mit konfigurierbarer Dauer und Erinnerung',
         'back': 'Wechselt zurück ins Main-Menu'}

async def status(update, context, user_data, markupList):
    bot = context.bot
    chat_id = update.effective_chat.id
    
    # Keyboard am Anfang setzen, damit alle reply_text Aufrufe das richtige Keyboard verwenden
    context.user_data['keyboard'] = markupList[STATISTICS]
    context.user_data['status'] = STATISTICS
    
    # Import FritzBox API (XML-based)
    from lib.fritzbox_api import FritzBoxAPI
    
    try:
        fritz = FritzBoxAPI()
        
        # Hilfsfunktion nutzen um Urlaubsstatus zu prüfen
        vacation_status = is_vacation_active(fritz)
        
        # Konfigurations-Debug-Informationen anzeigen
        #config_info = fritz.get_config_info()
        #message = "🔍 *FritzBox Konfiguration:*\n\n"
        #message += f"Host: {config_info['host']}\n"
        #message += f"Port: {config_info['port']}\n"
        #message += f"Benutzer: {config_info['username'] or '(kein Benutzer)'}\n"
        #message += f"Passwort gesetzt: {'Ja' if config_info['password_set'] else 'Nein'}\n"
        #message += f"Config-Keys: {', '.join(config_info['config_keys'])}\n\n"
        
        #await update.message.reply_text(message, parse_mode='Markdown',
        #                              reply_markup=markupList[STATISTICS])
        
        devices = fritz.get_devices()

        #print(devices)
        
        if not devices:
            await update.message.reply_text("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        # Filter nur Heizkörper (Geräte mit Thermostat-Daten)
        heaters = [device for device in devices if 'thermostat' in device]
        
        if not heaters:
            await update.message.reply_text("Keine Heizkörper gefunden.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        message = "🌡️ *Temperaturen aller Heizkörper:*\n\n"
        
        # Urlaubsstatus in der Status-Anzeige anzeigen
        if vacation_status['error']:
            message += f"⚠️ Urlaubsstatus: {vacation_status['error']}\n\n"
        else:
            if vacation_status['is_active']:
                message += f"🏖️ *Urlaubsmodus: AKTIV* ({vacation_status['percentage']:.1f}%)\n\n"
            else:
                message += f"🏠 *Urlaubsmodus: INAKTIV* ({vacation_status['percentage']:.1f}%)\n\n"
        
        # Hole alle Fenster-Status-Informationen in einem einzigen API-Aufruf
        window_status_cache = {}
        try:
            # Einmaliger API-Aufruf für alle Geräte
            device_list_url = f"http://{fritz.host}:{fritz.port}/webservices/homeautoswitch.lua"
            params = {
                'sid': fritz.sid,
                'switchcmd': 'getdevicelistinfos'
            }
            response = fritz.session.get(device_list_url, params=params, timeout=10)
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                for device in root.findall('device'):
                    device_ain = device.get('identifier')
                    windowopenactiv = device.find('windowopenactiv')
                    windowopenend = device.find('windowopenend')
                    
                    if device_ain and windowopenactiv is not None:
                        window_status_cache[device_ain] = {
                            'active': windowopenactiv.text == '1',
                            'end_time': None
                        }
                        
                        if windowopenend is not None and windowopenend.text:
                            try:
                                end_timestamp = int(windowopenend.text)
                                window_status_cache[device_ain]['end_time'] = datetime.fromtimestamp(end_timestamp)
                            except (ValueError, OSError):
                                pass
        except Exception as e:
            logger.debug(f"Konnte Fenster-Status-Cache nicht erstellen: {e}")
        
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            ain = heater.get('ain', '')
            thermostat = heater['thermostat']
            
            # Temperaturen umrechnen (Werte sind in 0.5°C Schritten)
            tist_value = thermostat.get('tist')
            tsoll_value = thermostat.get('tsoll')
            
            # Fenster-offen-Status aus Cache holen
            window_status = window_status_cache.get(ain, None)
            window_icon = ""
            window_info = ""
            
            # Wenn der Status nicht aktiv ist, prüfen ob wir kürzlich einen erfolgreichen API-Aufruf hatten
            if not (window_status and window_status.get('active')):
                # Prüfen ob für dieses Gerät ein aktiver Timer läuft
                if chat_id in window_open_timers and ain in window_open_timers[chat_id]:
                    timer_info = window_open_timers[chat_id][ain]
                    end_time = timer_info.get('end_time')
                    if end_time and end_time > datetime.now():
                        # API-Aufruf war erfolgreich, auch wenn FritzBox den Status nicht zurückgibt
                        window_icon = " 🪟"
                        remaining_time = end_time - datetime.now()
                        hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            window_info = f"   🪟 Fenster-Offen: {hours}h {minutes}m\n"
                        else:
                            window_info = f"   🪟 Fenster-Offen: {minutes}m\n"
            
            if window_status and window_status.get('active'):
                window_icon = " 🪟"
                if window_status.get('end_time'):
                    remaining_time = window_status['end_time'] - datetime.now()
                    if remaining_time.total_seconds() > 0:
                        hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            window_info = f"   🪟 Fenster-Offen: {hours}h {minutes}m\n"
                        else:
                            window_info = f"   🪟 Fenster-Offen: {minutes}m\n"
                else:
                    window_info = "   🪟 Fenster-Offen: Aktiv\n"
            
            # None-Werte behandeln - wenn keine Temperatur verfügbar, zeige "N/A"
            if tist_value is not None and tsoll_value is not None:
                current_temp = int(tist_value) / 2
                
                # Solltemperatur korrekt interpretieren
                try:
                    tsoll_int = int(tsoll_value)
                    if tsoll_int == 0:
                        target_temp_display = "AUS"
                        target_temp_num = 0  # für Berechnungen
                    elif tsoll_int == 254:
                        target_temp_display = "AUS"
                        target_temp_num = 0  # für Berechnungen
                    elif tsoll_int == 253:
                        target_temp_display = "temp. AUS"
                        status_emoji = "⚠️"  # <--- Änderung hier
                        target_temp_num = 999  # sehr hoher Wert für Berechnungen
                    else:
                        target_temp_num = tsoll_int / 2
                        target_temp_display = f"{target_temp_num:.1f}"
                except (ValueError, TypeError):
                    target_temp_display = "N/A"
                    target_temp_num = 0
                
                # Status-Emoji basierend auf Temperaturdifferenz (nur bei normalen Temperaturen)
                if tsoll_int in [0, 254]:
                    status_emoji = "🔴"  # AUS
                elif tsoll_int == 253:
                    status_emoji = "⚠️"  # temp. AUS
                elif abs(current_temp - target_temp_num) < 0.5:
                    status_emoji = "✅"
                elif current_temp < target_temp_num:
                    status_emoji = "🔥"
                else:
                    status_emoji = "❄️"
                
                # Urlaubs-Icon hinzufügen wenn im Urlaubsmodus
                vacation_icon = ""
                if not vacation_status['error']:
                    for vac_heater in vacation_status['heaters']:
                        if vac_heater['name'] == name and vac_heater['is_vacation']:
                            vacation_icon = " 🏖️"
                            break
                
                message += f"{status_emoji}{vacation_icon}{window_icon} *{name}*\n"
                message += f"   Aktuell: {current_temp:.1f}°C\n"
                if target_temp_display in ["AUS", "temp. AUS"]:
                    message += f"   Ziel: {target_temp_display}\n"
                else:
                    message += f"   Ziel: {target_temp_display}°C\n"
                
                # Fenster-offen Information hinzufügen
                if window_info:
                    message += window_info
            else:
                message += f"❓{window_icon} *{name}*\n"
                message += f"   Aktuell: N/A\n"
                message += f"   Ziel: N/A\n"
                
                # Fenster-offen Information auch bei N/A Temperaturen
                if window_info:
                    message += window_info
            
            # Zusätzliche Infos
            if thermostat.get('batterylow') == '1':
                message += "   ⚠️ Batterie schwach\n"
            
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='Markdown',
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen der Statusdaten: {str(e)}",
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    return context.user_data['status']

async def set_temp(update, context, user_data, markupList):
    bot = context.bot
    
    # Keyboard am Anfang setzen
    context.user_data['keyboard'] = markupList[STATISTICS]
    context.user_data['status'] = STATISTICS
    
    # Import FritzBox API
    from lib.fritzbox_api import FritzBoxAPI
    
    try:
        fritz = FritzBoxAPI()
        devices = fritz.get_devices()
        
        if not devices:
            await update.message.reply_text("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        # Filter nur Heizkörper (Geräte mit Thermostat-Daten)
        heaters = [device for device in devices if 'thermostat' in device]
        
        if not heaters:
            await update.message.reply_text("Keine Heizkörper gefunden.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        # Inline-Keyboard für Heizungsauswahl erstellen
        keyboard = []
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            ain = heater.get('ain', '')
            
            # Aktuelle Temperatur anzeigen
            thermostat = heater['thermostat']
            tist = thermostat.get('tist')
            tsoll = thermostat.get('tsoll')
            
            # Next-Change Information holen
            next_change_info = get_device_next_change_from_list(fritz, ain)
            
            if tist is not None and tsoll is not None:
                current_temp = int(tist) / 2
                target_temp = int(tsoll) / 2
                temp_info = f" ({current_temp:.1f}°C → {target_temp:.1f}°C"
                
                # Nächste Temperaturänderung hinzufügen
                if next_change_info and next_change_info.get('target_temp') and next_change_info.get('datetime'):
                    next_temp = next_change_info['target_temp']
                    next_time = next_change_info['datetime']
                    time_str = next_time.strftime("%H:%M")
                    temp_info += f" → {next_temp:.1f}°C um {time_str})"
                else:
                    temp_info += ")"
            else:
                temp_info = " (N/A)"
            
            # Button-Text erstellen
            button_text = f"{name}{temp_info}"
            callback_data = f"select_heater_{ain}"
            
            keyboard.append([{'text': button_text, 'callback_data': callback_data}])
        
        # Zurück-Button hinzufügen
        keyboard.append([{'text': '❌ Abbrechen', 'callback_data': 'cancel_temp_set'}])
        
        reply_markup = {'inline_keyboard': keyboard}
        
        await update.message.reply_text("🌡️ *Heizung auswählen:*\n\nWähle den Heizkörper, dessen Temperatur du ändern möchtest:",
                                      parse_mode='Markdown',
                                      reply_markup=reply_markup)
        
        # Status speichern für Callback-Handling
        context.user_data['temp_set_mode'] = True
        context.user_data['heaters'] = heaters
        
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Laden der Heizkörper: {str(e)}",
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    return context.user_data['status']

async def vacation_mode(update, context, user_data, markupList):
    """Schaltet alle Heizkörper in den Urlaubsmodus oder zurück"""
    bot = context.bot
    
    # Keyboard am Anfang setzen
    context.user_data['keyboard'] = markupList[STATISTICS]
    context.user_data['status'] = STATISTICS
    
    # Import FritzBox API
    from lib.fritzbox_api import FritzBoxAPI
    from lib.config import Config
    
    try:
        fritz = FritzBoxAPI()
        config = Config()
        
        # Vorlagennamen aus Konfiguration holen
        vacation_on_name = config.get('templates.vacation_on', 'Urlaubsschaltung AN')
        vacation_off_name = config.get('templates.vacation_off', 'Urlaubsschaltung AUS')
        
        devices = fritz.get_devices()
        
        if not devices:
            await update.message.reply_text("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        # Filter nur Heizkörper (Geräte mit Thermostat-Daten)
        heaters = [device for device in devices if 'thermostat' in device]
        
        if not heaters:
            await update.message.reply_text("Keine Heizkörper gefunden.",
                                          reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
            return context.user_data.get('status', STATISTICS)
        
        # Prüfen ob bereits im Urlaubsmodus (Hilfsfunktion nutzen)
        vacation_status_check = is_vacation_active(fritz)
        vacation_active = vacation_status_check['is_active'] if not vacation_status_check['error'] else False
        
        # Zuerst versuchen, die Vorlagenliste über AHA-Interface zu holen
        template_list = fritz.get_template_list_aha()
        
        message = f"🏖️ *FritzBox Urlaubsmodus wird umgeschaltet...*\n\n"
        
        if template_list:
            # XML parsen und Vorlagen extrahieren
            templates = fritz.parse_template_xml(template_list)
            
            #message += f"� *Vorlagen gefunden:* {len(templates)}\n"
            
            # Prüfen, ob Urlaubsvorlagen vorhanden sind
            vacation_templates = []
            for template in templates:
                if template['name'] == vacation_on_name or template['name'] == vacation_off_name:
                    vacation_templates.append(template)
            
            if vacation_templates:
                #For debugging
                #message += f"✅ *Urlaubs-Vorlagen gefunden:*\n"
                #for template in vacation_templates:
                #    message += f"• {template['name']} (ID: {template['id']})\n"
                #message += f"\n"
                
                # Finde "AN" und "AUS" Vorlagen basierend auf Konfiguration
                on_template = None
                off_template = None
                
                for template in vacation_templates:
                    if template['name'] == vacation_on_name:
                        on_template = template
                    elif template['name'] == vacation_off_name:
                        off_template = template
                
                if vacation_active:
                    # Urlaubsmodus deaktivieren
                    message += f"🔄 *Urlaubsmodus wird beendet...*\n\n"
                    
                    # Verwende applytemplate mit Identifier (basierend auf unseren Erkenntnissen)
                    if off_template:
                        try:
                            # Login durchführen
                            if fritz.login():
                                # Vorlage mit applytemplate und Identifier anwenden
                                url = f"http://{fritz.host}:{fritz.port}/webservices/homeautoswitch.lua"
                                params = {
                                    'sid': fritz.sid,
                                    'switchcmd': 'applytemplate',
                                    'ain': off_template['identifier']  # Identifier verwenden!
                                }
                                
                                response = fritz.session.get(url, params=params, timeout=10)
                                
                                if response.status_code == 200:
                                    response_text = response.text.strip()
                                    if response_text == off_template['id']:
                                        message += f"✅ Vorlage '{off_template['name']}' erfolgreich angewendet\n"
                                        message += f"🏠 Heizungen folgen wieder dem normalen Zeitschaltplan!"
                                    else:
                                        message += f"⚠️ Vorlage angewendet, aber unerwartete Antwort: {response_text}\n"
                                        message += f"🏠 Urlaubsmodus sollte beendet sein."
                                else:
                                    message += f"❌ Fehler beim Anwenden der Vorlage (HTTP {response.status_code})\n"
                            else:
                                message += f"❌ Login bei FritzBox fehlgeschlagen\n"
                        except Exception as e:
                            message += f"❌ Fehler bei Vorlagen-Anwendung: {str(e)}\n"
                    else:
                        message += f"❌ Keine 'AUS'-Urlaubsvorlage gefunden\n"
                        message += f"💡 Bitte erstelle 'Urlaubsschaltung AUS' Vorlage in der FritzBox\n"
                        message += f"📖 Anleitung: https://fritzhelp.avm.de/help/de/FRITZ-Box-6890-LTE/avm/021/hilfe_vorlage_hkr_urlaubsschaltung\n"
                        message += f"⚙️ Konfiguriere den Namen in config.json unter 'templates.vacation_off'"
                else:
                    # Urlaubsmodus aktivieren
                    message += f"🏖️ *Urlaubsmodus wird aktiviert...*\n\n"
                    
                    # Verwende applytemplate mit Identifier (basierend auf unseren Erkenntnissen)
                    if on_template:
                        try:
                            # Login durchführen
                            if fritz.login():
                                # Vorlage mit applytemplate und Identifier anwenden
                                url = f"http://{fritz.host}:{fritz.port}/webservices/homeautoswitch.lua"
                                params = {
                                    'sid': fritz.sid,
                                    'switchcmd': 'applytemplate',
                                    'ain': on_template['identifier']  # Identifier verwenden!
                                }
                                
                                response = fritz.session.get(url, params=params, timeout=10)
                                
                                if response.status_code == 200:
                                    response_text = response.text.strip()
                                    if response_text == on_template['id']:
                                        message += f"✅ Vorlage '{on_template['name']}' erfolgreich angewendet\n"
                                        message += f"🏖️ Alle Heizkörper befinden sich jetzt im Urlaubsmodus!"
                                    else:
                                        message += f"⚠️ Vorlage angewendet, aber unerwartete Antwort: {response_text}\n"
                                        message += f"🏖️ Urlaubsmodus sollte aktiviert sein."
                                else:
                                    message += f"❌ Fehler beim Anwenden der Vorlage (HTTP {response.status_code})\n"
                            else:
                                message += f"❌ Login bei FritzBox fehlgeschlagen\n"
                        except Exception as e:
                            message += f"❌ Fehler bei Vorlagen-Anwendung: {str(e)}\n"
                    else:
                        message += f"❌ Keine 'AN'-Urlaubsvorlage gefunden\n"
                        message += f"💡 Bitte erstelle 'Urlaubsschaltung AN' Vorlage in der FritzBox\n"
                        message += f"📖 Anleitung: https://fritzhelp.avm.de/help/de/FRITZ-Box-6890-LTE/avm/021/hilfe_vorlage_hkr_urlaubsschaltung\n"
                        message += f"⚙️ Konfiguriere den Namen in config.json unter 'templates.vacation_on'"
            else:
                message += f"❌ Keine Urlaubs-Vorlagen gefunden\n"
                message += f"💡 Bitte erstelle Urlaubsvorlagen in der FritzBox-Oberfläche\n"
                message += f"📖 Anleitung: https://fritzhelp.avm.de/help/de/FRITZ-Box-6890-LTE/avm/021/hilfe_vorlage_hkr_urlaubsschaltung\n"
                message += f"⚙️ Konfiguriere die Namen in config.json unter 'templates.vacation_on' und 'templates.vacation_off'"
        else:
            message += f"❌ Keine Vorlagen über AHA-Interface gefunden\n"
            message += f"💡 Bitte überprüfe, ob Vorlagen in der FritzBox-Oberfläche erstellt wurden\n"
            message += f"🔧 Stelle sicher, dass die Vorlagen für Heizkörper konfiguriert sind\n"
            message += f"📖 Anleitung: https://fritzhelp.avm.de/help/de/FRITZ-Box-6890-LTE/avm/021/hilfe_vorlage_hkr_urlaubsschaltung\n"
            message += f"⚙️ Konfiguriere die Namen in config.json unter 'templates.vacation_on' und 'templates.vacation_off'"
        
        await update.message.reply_text(message, parse_mode='Markdown',
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
        
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Umschalten des Urlaubsmodus: {str(e)}",
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    return context.user_data['status']

async def temp_history(update, context, user_data, markupList):
    """Zeigt den Temperaturverlauf aller Heizungen der letzten 24 Stunden als Graphik an"""
    # Keyboard am Anfang setzen
    context.user_data['keyboard'] = markupList[STATISTICS]
    context.user_data['status'] = STATISTICS
    
    # Import FritzBox API
    from lib.fritzbox_api import FritzBoxAPI
    
    try:
        # Ladebalken-Nachricht senden
        loading_message = await update.message.reply_text("📊 Lade Temperaturverlauf...", 
                                                     reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
        
        fritz = FritzBoxAPI()
        
        # Login durchführen
        if not fritz.test_credentials():
            await loading_message.edit_text("❌ Login bei FritzBox fehlgeschlagen.")
            return context.user_data.get('status', STATISTICS)
        
        if not fritz.login():
            await loading_message.edit_text("❌ Session bei FritzBox fehlgeschlagen.")
            return context.user_data.get('status', STATISTICS)
        
        # Geräte abrufen
        devices = fritz.get_devices()
        if not devices:
            await loading_message.edit_text("❌ Keine Geräte gefunden.")
            return context.user_data.get('status', STATISTICS)
        
        # Heizkörper filtern
        heaters = [device for device in devices if 'thermostat' in device]
        if not heaters:
            await loading_message.edit_text("❌ Keine Heizkörper gefunden.")
            return context.user_data.get('status', STATISTICS)
        
        # Temperaturhistorien für alle Heizkörper sammeln
        all_histories = []
        successful_analyses = 0
        
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            ain = heater.get('ain', '')
            
            # Historie abrufen
            history = fritz.get_temperature_history(ain)
            if history and history.get('temperatures_celsius'):
                all_histories.append({
                    'name': name,
                    'ain': ain,
                    'temperatures': history['temperatures_celsius'],
                    'current_temp': history['current_temp'],
                    'min_temp': history['min_temp'],
                    'max_temp': history['max_temp'],
                    'avg_temp': history['avg_temp']
                })
                successful_analyses += 1
        
        if not all_histories:
            await loading_message.edit_text("❌ Keine Temperaturverlaufsdaten verfügbar.")
            return context.user_data.get('status', STATISTICS)
        
        # Graphik erstellen
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime, timedelta
            import io
            
            # Figur erstellen
            plt.figure(figsize=(14, 8))
            plt.style.use('seaborn-v0_8' if hasattr(plt.style, 'seaborn-v0_8') else 'default')
            
            # Zeitachse erstellen (96 Datenpunkte im 15-Minuten-Intervall = 24 Stunden)
            end_time = datetime.now()
            time_points = [end_time - timedelta(minutes=15*i) for i in range(95, -1, -1)]
            
            # Farben für verschiedene Heizkörper (kräftigere Farben)
            colors = ['#FF4444', '#00AA00', '#0066CC', '#FF8800', '#AA00FF', '#00CCCC', '#FF1493', '#FFD700']
            
            # Jeden Heizkörper plotten
            for i, history in enumerate(all_histories):
                color = colors[i % len(colors)]
                temps = history['temperatures']
                
                # Plot mit Linie und Markern
                plt.plot(time_points, temps, 
                        label=f"{history['name']} ({history['current_temp']:.1f}°C)",
                        color=color, linewidth=2, marker='o', markersize=3, alpha=0.8)
            
            # Graphik formatieren
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            plt.title(f'Temperaturverlauf aller Heizkörper - letzte 24 Stunden\n{successful_analyses}/{len(heaters)} Heizkörper mit Daten', 
                     fontsize=16, fontweight='bold', pad=20)
            plt.xlabel('Zeit', fontsize=12)
            plt.ylabel('Temperatur (°C)', fontsize=12)
            
            # X-Achse formatieren (stündliche Beschriftungen)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=1))  # Jede Stunde
            plt.xticks(rotation=45)
            
            # Gitter und Legende (unter dem Graphen)
            plt.grid(True, alpha=0.3)
            plt.legend(bbox_to_anchor=(0.5, -0.15), loc='upper center', fontsize=10, ncol=2)
            
            # Zeitstempel hinzufügen
            plt.figtext(0.99, 0.01, f'Erstellt: {current_time}', 
                       ha='right', va='bottom', fontsize=8, style='italic', alpha=0.7)
            
            # Layout anpassen (mehr Platz unten für Legende)
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.2)
            
            # Bild speichern
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='PNG', dpi=100, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close()
            
            # Zusammenfassende Statistik
            summary_text = f"📊 *Temperaturverlauf Analyse*\n\n"
            summary_text += f"✅ {successful_analyses}/{len(heaters)} Heizkörper mit Daten\n"
            summary_text += f"📅 Zeitraum: letzte 24 Stunden\n"
            summary_text += f"⏱️ Auflösung: 15 Minuten\n\n"
            
            summary_text += "*Aktuelle Temperaturen:*\n"
            for history in all_histories:
                trend_emoji = "📈" if history['current_temp'] > history['avg_temp'] else "📉" if history['current_temp'] < history['avg_temp'] else "➡️"
                summary_text += f"{trend_emoji} {history['name']}: {history['current_temp']:.1f}°C "
                summary_text += f"({history['min_temp']:.1f}-{history['max_temp']:.1f}°C)\n"
            
            # Bild senden
            await loading_message.delete()
            await update.message.reply_photo(
                photo=img_buffer,
                caption=summary_text,
                parse_mode='Markdown',
                reply_markup=context.user_data.get('keyboard', markupList[STATISTICS])
            )
            
        except ImportError:
            await loading_message.edit_text("❌ Matplotlib nicht installiert. Bitte installieren Sie:\n"
                                          "`pip install matplotlib`")
        except Exception as e:
            await loading_message.edit_text(f"❌ Fehler beim Erstellen der Graphik: {str(e)}")
    
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen der Temperaturverlaufsdaten: {str(e)}",
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    return context.user_data['status']

async def handle_temp_callback(update, context):
    """Handler für Inline-Keyboard Callbacks bei Temperatursetzung"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        
        if callback_data == 'cancel_temp_set':
            await query.edit_message_text("Temperatursetzung abgebrochen.")
            context.user_data['temp_set_mode'] = False
            return
        
        if callback_data.startswith('select_heater_'):
            ain = callback_data.replace('select_heater_', '')
            heaters = context.user_data.get('heaters', [])
            
            # FritzBox API initialisieren für next_change Abfrage
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            # Verbindung herstellen
            try:
                if not (fritz.login_tr064() or fritz.login()):
                    await query.edit_message_text("Fehler: Verbindung zur FritzBox fehlgeschlagen!")
                    return
            except Exception as e:
                await query.edit_message_text(f"Verbindungsfehler: {str(e)}")
                return
            
            # Gewählten Heizkörper finden
            selected_heater = None
            for heater in heaters:
                if heater.get('ain') == ain:
                    selected_heater = heater
                    break
            
            if not selected_heater:
                await query.edit_message_text("Fehler: Heizkörper nicht gefunden.")
                return
            
            name = selected_heater.get('name', 'Unbekannt')
            thermostat = selected_heater['thermostat']
            tsoll = thermostat.get('tsoll')
            
            # Next-Change Information holen
            next_change_info = get_device_next_change_from_list(fritz, ain)
            
            # Aktuelle Zieltemperatur
            current_target = int(tsoll) / 2 if tsoll is not None else 20.0
            
            # Inline-Keyboard für Temparaturauswahl erstellen
            keyboard = []
            
            # Temperatur-Buttons (16°C bis 28°C in 0.5°C Schritten)
            temps = []
            for temp_c in range(160, 281, 5):  # 16.0°C bis 28.0°C in 0.5°C Schritten
                temp = temp_c / 10
                temps.append(temp)
            
            # Buttons in 4 Spalten anordnen
            row = []
            for i, temp in enumerate(temps):
                # Markiere aktuelle Temperatur
                if abs(temp - current_target) < 0.1:
                    button_text = f"✅ {temp:.1f}°"
                else:
                    button_text = f"{temp:.1f}°"
                
                callback = f"set_temp_{ain}_{int(temp * 2)}"  # Temperatur in 0.5°C Schritten
                row.append({'text': button_text, 'callback_data': callback})
                
                # Neue Reihe nach 4 Buttons
                if len(row) == 4 or i == len(temps) - 1:
                    keyboard.append(row)
                    row = []
            
            # Abbrechen-Button
            keyboard.append([{'text': '❌ Abbrechen', 'callback_data': 'cancel_temp_set'}])
            
            reply_markup = {'inline_keyboard': keyboard}
            
            # Nachricht mit next_change Information erstellen
            message_text = f"🌡️ *Temperatur für {name} wählen:*\n\n"
            message_text += f"Aktuelle Zieltemperatur: {current_target:.1f}°C\n"
            
            # Nächste Temperaturänderung hinzufügen
            if next_change_info and next_change_info.get('target_temp') and next_change_info.get('datetime'):
                next_temp = next_change_info['target_temp']
                next_datetime = next_change_info['datetime']
                time_str = next_datetime.strftime("%H:%M")
                date_str = next_datetime.strftime("%d.%m.%Y")
                
                message_text += f"🔄 Nächste Änderung: {next_temp:.1f}°C um {time_str} Uhr ({date_str})\n"
            
            message_text += f"\nWähle die neue Zieltemperatur:"
            
            await query.edit_message_text(message_text,
                                        parse_mode='Markdown',
                                        reply_markup=reply_markup)
            
            return
        
        if callback_data.startswith('set_temp_'):
            parts = callback_data.replace('set_temp_', '').split('_')
            ain = parts[0]
            temp_value = int(parts[1])  # Temperatur in 0.5°C Schritten
            temp_celsius = temp_value / 2
            
            # Heizkörper-Name finden
            heaters = context.user_data.get('heaters', [])
            heater_name = "Unbekannt"
            for heater in heaters:
                if heater.get('ain') == ain:
                    heater_name = heater.get('name', 'Unbekannt')
                    break
            
            # Temperatur setzen
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            success = fritz.set_temperature(ain, temp_celsius)
            
            if success:
                # Next-Change Information über getdevicelistinfos holen
                next_change_info = get_device_next_change_from_list(fritz, ain)
                
                success_message = f"✅ *Temperatur erfolgreich gesetzt!*\n\n"
                success_message += f"🏠 {heater_name}\n"
                success_message += f"🌡️ Neue Zieltemperatur: {temp_celsius:.1f}°C"
                
                if next_change_info:
                    next_temp = next_change_info.get('target_temp')
                    next_datetime = next_change_info.get('datetime')
                    
                    if next_temp is not None and next_datetime:
                        time_str = next_datetime.strftime("%H:%M")
                        date_str = next_datetime.strftime("%d.%m.%Y")
                        now = datetime.now()
                        
                        if next_datetime.date() == now.date():
                            # Heute
                            success_message += f"\n\n⏰ *Nächste automatische Änderung:*"
                            success_message += f"\n📅 Heute um {time_str} Uhr"
                            success_message += f"\n🔄 Auf {next_temp:.1f}°C (gemäß Zeitplan)"
                        else:
                            # Morgen oder später
                            weekday_name = next_datetime.strftime("%A")
                            success_message += f"\n\n⏰ *Nächste automatische Änderung:*"
                            success_message += f"\n📅 {weekday_name}, {date_str} um {time_str} Uhr"
                            success_message += f"\n🔄 Auf {next_temp:.1f}°C (gemäß Zeitplan)"
                    else:
                        success_message += f"\n\nℹ️ Keine weiteren Zeitplanänderungen gefunden"
                else:
                    success_message += f"\n\nℹ️ Keine Informationen zur nächsten Temperaturänderung verfügbar"
                
                await query.edit_message_text(success_message, parse_mode='Markdown')
            else:
                await query.edit_message_text(f"❌ *Fehler beim Setzen der Temperatur!*\n\n"
                                            f"🏠 {heater_name}\n"
                                            f"🌡️ Gewünschte Temperatur: {temp_celsius:.1f}°C\n\n"
                                            f"Bitte versuche es später erneut.",
                                            parse_mode='Markdown')
            
            # Temp-Set-Mode beenden
            context.user_data['temp_set_mode'] = False
            
    except Exception as e:
        await query.edit_message_text(f"Fehler bei der Temperatursetzung: {str(e)}")
        context.user_data['temp_set_mode'] = False

async def window_open_mode(update, context, user_data, markupList):
    """HKR Fenster-Offen Modus - Hauptfunktion"""
    chat_id = update.effective_chat.id
    
    # Konfiguration für Fenster-Offen Modus laden
    window_config = config.get('window_open', {})
    default_duration = window_config.get('default_duration_minutes', 30)
    reminder_minutes = window_config.get('reminder_minutes_before', 5)
    
    # FritzBox API initialisieren
    from lib.fritzbox_api import FritzBoxAPI
    fritz = FritzBoxAPI()
    
    # Verbindung herstellen
    try:
        if fritz.login_tr064():
            logger.info("✅ TR-064 Verbindung erfolgreich")
        elif fritz.login():
            logger.info("✅ Standard-Login erfolgreich")
        else:
            await update.message.reply_text("❌ Fehler: Verbindung zur FritzBox fehlgeschlagen!",
                                      reply_markup=markupList[STATISTICS])
            return context.user_data['status']
    except Exception as e:
        await update.message.reply_text(f"❌ Verbindungsfehler: {str(e)}",
                                      reply_markup=markupList[STATISTICS])
        return context.user_data['status']
    
    # Geräte abrufen
    try:
        devices = fritz.get_devices()
        if not devices:
            await update.message.reply_text("❌ Keine Geräte gefunden!",
                                      reply_markup=markupList[STATISTICS])
            return context.user_data['status']
        
        heaters = [device for device in devices if 'thermostat' in device]
        if not heaters:
            await update.message.reply_text("❌ Keine Heizkörper gefunden!",
                                      reply_markup=markupList[STATISTICS])
            return context.user_data['status']
        
        # Hole alle Fenster-Status-Informationen in einem einzigen API-Aufruf
        window_status_cache = {}
        try:
            device_list_url = f"http://{fritz.host}:{fritz.port}/webservices/homeautoswitch.lua"
            params = {
                'sid': fritz.sid,
                'switchcmd': 'getdevicelistinfos'
            }
            response = fritz.session.get(device_list_url, params=params, timeout=10)
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                for device in root.findall('device'):
                    device_ain = device.get('identifier')
                    windowopenactiv = device.find('windowopenactiv')
                    
                    if device_ain and windowopenactiv is not None:
                        window_status_cache[device_ain] = windowopenactiv.text == '1'
        except Exception as e:
            logger.debug(f"Konnte Fenster-Status-Cache nicht erstellen: {e}")
        
        # Heizkörper mit vollständigen Status anzeigen
        keyboard = []
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            ain = heater.get('ain', '')
            thermostat = heater.get('thermostat', {})
            
            # Temperaturen und Status berechnen (gleiche Logik wie in status())
            tist_value = thermostat.get('tist')
            tsoll_value = thermostat.get('tsoll')
            
            if tist_value is not None and tsoll_value is not None:
                current_temp = int(tist_value) / 2
                
                # Solltemperatur korrekt interpretieren
                try:
                    tsoll_int = int(tsoll_value)
                    if tsoll_int == 0:
                        target_temp_display = "AUS"
                        status_emoji = "🔴"
                    elif tsoll_int == 254:
                        target_temp_display = "AUS"
                        status_emoji = "🔴"
                    elif tsoll_int == 253:
                        target_temp_display = "temp. AUS"
                        status_emoji = "⚠️"
                    else:
                        target_temp_num = tsoll_int / 2
                        target_temp_display = f"{target_temp_num:.1f}"
                        
                        # Status-Emoji basierend auf Temperaturdifferenz
                        if abs(current_temp - target_temp_num) < 0.5:
                            status_emoji = "✅"
                        elif current_temp < target_temp_num:
                            status_emoji = "🔥"
                        else:
                            status_emoji = "❄️"
                except (ValueError, TypeError):
                    target_temp_display = "N/A"
                    status_emoji = "❓"
                
                # Fenster-Status aus Cache holen
                window_icon = ""
                if window_status_cache.get(ain, False):
                    window_icon = " 🪟"
                
                # Button-Text mit vollem Status
                button_text = f"{status_emoji}{window_icon} {name} ({current_temp:.1f}°C → {target_temp_display})"
            else:
                button_text = f"❓ {name} (N/A)"
            
            callback_data = f"window_heater_{ain}"
            keyboard.append([{'text': button_text, 'callback_data': callback_data}])
        
        # Zusätzliche Optionen
        keyboard.append([{'text': f'🔄 Alle Heizkörper ({default_duration} Min)', 'callback_data': 'window_all_heaters'}])
        keyboard.append([{'text': '🔴 Alle deaktivieren', 'callback_data': 'window_disable_all'}])
        keyboard.append([{'text': '❌ Abbrechen', 'callback_data': 'cancel_window_mode'}])
        
        reply_markup = {'inline_keyboard': keyboard}
        
        await update.message.reply_text(f"🪟 *Fenster-Offen Modus*\n\n"
                                    f"Konfiguration: {default_duration} Minuten, Erinnerung {reminder_minutes} Min. vor Ablauf\n\n"
                                    "Wähle einen Heizkörper oder eine Aktion:\n",
                                    parse_mode='Markdown',
                                    reply_markup=reply_markup)
        
        context.user_data['window_mode'] = True
        return context.user_data['status']
        
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen der Geräte: {str(e)}",
                                      reply_markup=markupList[STATISTICS])
        return context.user_data['status']

async def handle_window_callback(update, context):
    """Handler für Fenster-Offen Modus Callbacks"""
    # Grundlegende Debug-Ausgabe - sollte IMMER erscheinen
    logger.info("=== handle_window_callback aufgerufen ===")
    
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        chat_id = update.effective_chat.id
        
        logger.debug(f"Window callback received: {callback_data}")
        logger.debug(f"Update object: {update}")
        logger.debug(f"Query object: {query}")
        
        if callback_data == 'cancel_window_mode':
            logger.debug("cancel_window_mode callback received")
            await query.edit_message_text("Fenster-Offen Modus abgebrochen.")
            context.user_data['window_mode'] = False
            return
        
        if callback_data == 'window_disable_all':
            logger.debug("window_disable_all callback received")
            # Alle Fenster-Modi deaktivieren
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            logger.debug("fritz.test_credentials() returned True")
            devices = fritz.get_devices()
            heaters = [device for device in devices if 'thermostat' in device]
            
            disabled_count = 0
            for heater in heaters:
                ain = heater.get('ain')
                if disable_window_open_mode(fritz, ain):
                    disabled_count += 1
                    logger.debug(f"Disabled window open for {ain}, result: True")
                else:
                    logger.debug(f"Failed to disable window open for {ain}")
                
            # Timer löschen
            if chat_id in window_open_timers:
                del window_open_timers[chat_id]
            if chat_id in window_open_notifications:
                del window_open_notifications[chat_id]
                
            await query.edit_message_text(f"✅ *Fenster-Offen Modus deaktiviert*\n\n"
                                            f"🔴 {disabled_count} Heizkörper zurückgesetzt",
                                            parse_mode='Markdown')
            logger.debug("window_disable_all callback finished")
            context.user_data['window_mode'] = False
            return
        
        if callback_data == 'window_all_heaters':
            logger.debug("window_all_heaters callback received")
            # Alle Heizkörper mit Konfigurationsdauer setzen
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            # Konfiguration laden
            window_config = config.get('window_open', {})
            default_duration = window_config.get('default_duration_minutes', 30)
            reminder_minutes = window_config.get('reminder_minutes_before', 5)
            
            logger.debug("fritz.test_credentials() returned True")
            devices = fritz.get_devices()
            heaters = [device for device in devices if 'thermostat' in device]
            
            success_count = 0
            end_time = datetime.now() + timedelta(minutes=default_duration)
            
            for heater in heaters:
                ain = heater.get('ain')
                logger.debug(f"Setting window open for {ain} with duration {default_duration}")
                result = set_window_open_mode(fritz, ain, default_duration, chat_id, context.bot)
                logger.debug(f"Result: {result}")
                if result.get('success'):
                    success_count += 1
                
            if success_count > 0:
                time_str = end_time.strftime("%H:%M")
                date_str = end_time.strftime("%d.%m.%Y")
                
                await query.edit_message_text(f"✅ *Fenster-Offen Modus aktiviert*\n\n"
                                                f"🏠 {success_count} Heizkörper\n"
                                                f"⏰ Bis: {date_str} um {time_str} Uhr\n"
                                                f"🔔 Erinnerung: {reminder_minutes} Minuten vor Ablauf",
                                                parse_mode='Markdown')
                logger.debug("window_all_heaters callback finished")
            else:
                await query.edit_message_text("❌ Fehler beim Aktivieren des Fenster-Offen Modus!")
                logger.debug("window_all_heaters callback failed")
            context.user_data['window_mode'] = False
            return
        
        if callback_data.startswith('window_heater_'):
            logger.debug(f"window_heater_ callback received: {callback_data}")
            # Einzelnen Heizkörper mit Konfigurationsdauer aktivieren
            ain = callback_data.replace('window_heater_', '')
            
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            # Konfiguration laden
            window_config = config.get('window_open', {})
            default_duration = window_config.get('default_duration_minutes', 30)
            reminder_minutes = window_config.get('reminder_minutes_before', 5)
            
            logger.debug("fritz.test_credentials() returned True")
            result = set_window_open_mode(fritz, ain, default_duration, chat_id, context.bot)
            logger.debug(f"Single heater result: {result}")
            
            if result.get('success'):
                end_time = result['end_time']
                time_str = end_time.strftime("%H:%M")
                date_str = end_time.strftime("%d.%m.%Y")
                
                # Heizkörper-Name finden
                devices = fritz.get_devices()
                heater_name = "Heizkörper"
                for device in devices:
                    if device.get('ain') == ain:
                        heater_name = device.get('name', 'Heizkörper')
                        break
                
                await query.edit_message_text(f"✅ *Fenster-Offen Modus aktiviert*\n\n"
                                                f"🏠 {heater_name}\n"
                                                f"⏰ Bis: {date_str} um {time_str} Uhr\n"
                                                f"🔔 Erinnerung: {reminder_minutes} Minuten vor Ablauf",
                                                parse_mode='Markdown')
            else:
                await query.edit_message_text(f"❌ Fehler: {result.get('error', 'Unbekannter Fehler')}")
            context.user_data['window_mode'] = False
            return
        
        if callback_data.startswith('window_disable_'):
            logger.debug(f"window_disable_ callback received: {callback_data}")
            # Fenster-Offen Modus für einzelnen Heizkörper deaktivieren
            ain = callback_data.replace('window_disable_', '')
            
            from lib.fritzbox_api import FritzBoxAPI
            fritz = FritzBoxAPI()
            
            logger.debug("fritz.test_credentials() returned True")
            if disable_window_open_mode(fritz, ain):
                # Timer löschen
                if chat_id in window_open_timers and ain in window_open_timers[chat_id]:
                    del window_open_timers[chat_id][ain]
                if chat_id in window_open_notifications and ain in window_open_notifications[chat_id]:
                    del window_open_notifications[chat_id][ain]
                
                # Heizkörper-Name finden
                devices = fritz.get_devices()
                heater_name = "Heizkörper"
                for device in devices:
                    if device.get('ain') == ain:
                        heater_name = device.get('name', 'Heizkörper')
                        break
                
                await query.edit_message_text(f"✅ *Fenster-Offen Modus deaktiviert*\n\n"
                                                f"🏠 {heater_name}\n"
                                                f"🔴 Heizung folgt wieder dem Zeitplan",
                                                parse_mode='Markdown')
            else:
                await query.edit_message_text(f"❌ Fehler beim Deaktivieren!")
            context.user_data['window_mode'] = False
            return
        
        logger.debug(f"Unbekannte callback_data: {callback_data}")
        await query.edit_message_text(f"❌ Unbekannter Callback: {callback_data}")
        context.user_data['window_mode'] = False
        return
        
    except Exception as e:
        await query.edit_message_text(f"Fehler: {str(e)}")
        context.user_data['window_mode'] = False

async def back(update, context, user_data, markupList):
    context.user_data['keyboard'] = markupList[MAIN]
    context.user_data['status'] = MAIN
    await update.message.reply_text('Zurück zum Hauptmenü', reply_markup=markupList[MAIN])
    return context.user_data['status']

async def default(update, context, user_data, markupList):
    return await status(update, context, user_data, markupList)

# Wrapper functions for direct bot calls (update, context signature)
#async def status_wrapper(update, context):.user_data)