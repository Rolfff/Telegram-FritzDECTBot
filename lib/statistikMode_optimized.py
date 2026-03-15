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
from typing import Dict, List, Optional, Tuple

# Logger initialisieren
logger = logging.getLogger(__name__)

# Telegram Importe
try:
    from telegram import ReplyKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    ReplyKeyboardMarkup = None

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
STATISTICS = config_module.STATISTICS

# Import der optimierten API
from lib.fritzbox_api_optimized import OptimizedFritzBoxAPI

# Globale Variablen für Fenster-Offen-Modus
window_open_timers = {}  # {chat_id: {ain: end_time, timer_thread: thread}}
window_open_notifications = {}  # {chat_id: {ain: notification_sent}}

class OptimizedStatisticsManager:
    """Optimierter Statistik-Manager mit Caching und Batch-Operationen"""
    
    def __init__(self):
        self.fritz_api = OptimizedFritzBoxAPI()
        self._stats_cache = {}
        self._cache_timeout = 60  # 1 Minute Cache für Statistiken
        self._last_login_time = 0
        self._login_cache_duration = 300  # 5 Minuten Login-Cache
    
    def _ensure_login(self) -> bool:
        """Stellt sicher dass Login gültig ist und vermeidet BlockTime"""
        import time
        current_time = time.time()
        
        # Prüfen ob Login noch gültig oder Cache abgelaufen
        if (current_time - self._last_login_time > self._login_cache_duration or 
            not self.fritz_api.sid or 
            self.fritz_api.sid == "0000000000000000"):
            
            print(f"DEBUG: Login erforderlich - letzter Login: {current_time - self._last_login_time:.1f}s her")
            if self.fritz_api.login():
                self._last_login_time = current_time
                print(f"DEBUG: Login erfolgreich - SID: {self.fritz_api.sid}")
                return True
            else:
                print(f"DEBUG: Login fehlgeschlagen - BlockTime möglich")
                return False
        else:
            print(f"DEBUG: Login noch gültig - SID: {self.fritz_api.sid}")
            return True
    
    def set_window_open_mode(self, ain: str, duration_minutes: Optional[int] = None, 
                           chat_id: Optional[int] = None, bot_instance=None) -> Dict:
        """Setzt den Fenster-Offen-Modus mit optimierter AHA-Schnittstelle"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return {'success': False, 'error': 'Login fehlgeschlagen - FritzBox möglicherweise gesperrt'}
            
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
            
            # Optimierter AHA-Aufruf
            success = self.fritz_api.set_window_open_mode(ain, end_timestamp)
            
            if success:
                # Timer für Erinnerung starten
                if chat_id:
                    heater_name = self._get_device_name(ain)
                    start_window_open_timer(chat_id, ain, end_time, bot_instance, heater_name)
                
                return {
                    'success': True,
                    'end_time': end_time,
                    'end_timestamp': end_timestamp,
                    'duration_minutes': duration_minutes
                }
            else:
                return {'success': False, 'error': 'AHA-Kommando fehlgeschlagen'}
                
        except Exception as e:
            logger.error(f"Fehler beim Setzen des Fenster-Offen-Modus: {e}")
            return {'success': False, 'error': str(e)}
    
    def disable_window_open_mode(self, ain: str) -> bool:
        """Deaktiviert den Fenster-Offen-Modus"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return False
            
            return self.fritz_api.disable_window_open_mode(ain)
        except Exception as e:
            logger.error(f"Fehler beim Deaktivieren: {e}")
            return False
    
    def _get_device_name(self, ain: str) -> str:
        """Holt Gerätenamen mit Caching"""
        try:
            device = self.fritz_api.get_device_by_ain(ain, use_cache=True)
            return device.name if device else f'Heizkörper {ain}'
        except Exception as e:
            logger.debug(f"Konnte Heizkörper-Namen nicht abfragen: {e}")
            return f'Heizkörper {ain}'
    
    def get_window_open_status(self, ain: str) -> Dict:
        """Prüft den Status des Fenster-Offen-Modus mit optimierter API"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return {'windowopenactiv': False, 'error': 'Login fehlgeschlagen'}
            
            device = self.fritz_api.get_device_by_ain(ain, use_cache=True)
            logger.info(f"Gerät gefunden: {device is not None}")
            if device:
                logger.info(f"Gerätename: {device.name}")
                logger.info(f"Thermostat-Daten: {device.thermostat}")
            
            if device and device.thermostat:
                windowopenactiv = device.thermostat.get('windowopenactiv')
                windowopenactiveendtime = device.thermostat.get('windowopenactiveendtime')
                logger.info(f"windowopenactiv: {windowopenactiv}")
                logger.info(f"windowopenactiveendtime: {windowopenactiveendtime}")
                
                return {
                    'windowopenactiv': windowopenactiv == '1',
                    'windowopenactiveendtime': windowopenactiveendtime,
                    'device_name': device.name
                }
            return {'windowopenactiv': False, 'device_name': 'Unbekannt'}
        except Exception as e:
            logger.error(f"Fehler bei Fenster-Status: {e}")
            return {'windowopenactiv': False, 'error': str(e)}
    
    def get_next_temperature_change(self, ain: str) -> Dict:
        """Holt die nächste Temperaturänderung über direkten XML-API-Aufruf"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return {'error': 'Login fehlgeschlagen'}
            
            # Direkter API-Aufruf wie im alten StatistikMode
            device_list_url = f"http://{self.fritz_api.host}:{self.fritz_api.port}/webservices/homeautoswitch.lua"
            
            params = {
                'sid': self.fritz_api.sid,
                'switchcmd': 'getdevicelistinfos'
            }
            
            response = self.fritz_api.session.get(device_list_url, params=params, timeout=10)
            logger.info(f"Next-Change API Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text.strip()
                logger.info(f"Next-Change XML Content Length: {len(content)}")
                root = ET.fromstring(content)
                
                # Nach dem spezifischen Gerät suchen
                for device in root.findall('device'):
                    device_ain = device.get('identifier') or device.get('ain')
                    logger.debug(f"Vergleiche AIN: {device_ain} mit gesuchter AIN: {ain}")
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
                                    logger.info(f"Next-Change tchange Wert: {tchange_value}")
                                    if tchange_value == '255' or tchange_value == '0xff':
                                        nextchange_data['tchange'] = None  # unbekannt/undefiniert
                                    else:
                                        try:
                                            temp_value = float(tchange_value)
                                            nextchange_data['tchange'] = temp_value
                                            logger.info(f"Next-Change Temperatur: {temp_value/2:.1f}°C")
                                        except (ValueError, TypeError):
                                            nextchange_data['tchange'] = None
                                
                                # endperiod (Timestamp)
                                endperiod_elem = nextchange_elem.find('endperiod')
                                if endperiod_elem is not None:
                                    try:
                                        timestamp = int(endperiod_elem.text)
                                        if timestamp == 0:
                                            nextchange_data['endperiod'] = None  # unbekannt
                                        else:
                                            nextchange_data['endperiod'] = timestamp
                                            logger.info(f"Next-Change Zeit: {datetime.fromtimestamp(timestamp)}")
                                    except (ValueError, TypeError):
                                        nextchange_data['endperiod'] = None
                                
                                # Gerätename holen
                                device_name = device.get('name', 'Unbekannt')
                                nextchange_data['device_name'] = device_name
                                
                                logger.info(f"Next-Change gefunden: {nextchange_data}")
                                return nextchange_data
                
                logger.info(f"Kein nextchange für AIN {ain} in XML gefunden")
                return {'error': 'Keine nextchange Information gefunden'}
            else:
                logger.error(f"Next-Change API Fehler: {response.status_code}")
                return {'error': f'API Fehler: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Fehler bei nextchange: {e}")
            return {'error': str(e)}
    
    def get_all_window_status(self) -> Dict[str, Dict]:
        """Holt alle Fenster-Status in einem optimierten Batch-Aufruf"""
        try:
            devices = self.fritz_api.get_devices(use_cache=True)
            window_status = {}
            
            for device in devices:
                if device.thermostat:
                    window_status[device.ain] = {
                        'name': device.name,
                        'windowopenactiv': device.thermostat.get('windowopenactiv') == '1',
                        'windowopenactiveendtime': device.thermostat.get('windowopenactiveendtime')
                    }
            
            return window_status
        except Exception as e:
            logger.error(f"Fehler bei allen Fenster-Status: {e}")
            return {}
    
    def get_temperature_history(self, ain: str, hours: int = 24) -> Optional[Dict]:
        """Holt die Temperaturhistorie mit optimierter API"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return None
            
            # Cache-Check
            cache_key = f"temp_history_{ain}_{hours}"
            if cache_key in self._stats_cache:
                cache_entry = self._stats_cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self._cache_timeout:
                    return cache_entry['data']
            
            # API-Aufruf
            stats = self.fritz_api.get_device_stats(ain)
            if not stats or 'stats' not in stats:
                return None
            
            # Temperatur-Statistiken extrahieren
            temp_stats = stats['stats'].get('temperature', [])
            if not temp_stats:
                return None
            
            # Daten aufbereiten
            data_points = temp_stats[0].get('values', [])
            grid_seconds = temp_stats[0].get('grid', 900)
            datatime = temp_stats[0].get('datatime')
            
            # Filtere None-Werte
            valid_data = [x for x in data_points if x is not None]
            
            if not valid_data:
                return None
            
            # Temperaturen umrechnen (0.1°C)
            temperatures = [temp / 10 for temp in valid_data]
            
            # Statistiken berechnen
            result = {
                'ain': ain,
                'device_name': self._get_device_name(ain),
                'total_points': len(data_points),
                'valid_points': len(valid_data),
                'grid_seconds': grid_seconds,
                'last_update': datetime.fromtimestamp(datatime) if datatime else None,
                'temperatures_celsius': temperatures,
                'min_temp': min(temperatures),
                'max_temp': max(temperatures),
                'avg_temp': sum(temperatures) / len(temperatures),
                'current_temp': temperatures[-1] if temperatures else None,
                'time_range_hours': len(valid_data) * grid_seconds / 3600
            }
            
            # Cache aktualisieren
            self._stats_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Fehler bei Temperaturhistorie: {e}")
            return None
    
    def is_vacation_active(self) -> Dict:
        """
        Überprüfung ob Urlaubsmodus aktiv mit optimierter API
        """
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return {
                    'is_active': False,
                    'percentage': 0.0,
                    'active_count': 0,
                    'total_count': 0,
                    'vacation_temp': 16.0,
                    'heaters': [],
                    'error': 'Login fehlgeschlagen'
                }
            
            # Urlaubstemperatur aus Vorlage ermitteln
            vacation_on_name = config.get('templates.vacation_on', 'Urlaubsschaltung AN')
            
            templates = self.fritz_api.get_templates(use_cache=True)
            vacation_temp = None
            
            # Urlaubsvorlagen finden
            for template in templates:
                if template.name == vacation_on_name:
                    # Temperatur aus ApplyMask extrahieren
                    if 'hkr_temperature' in template.applymask:
                        # Hier müsste die Temperatur aus der Vorlage extrahiert werden
                        # Da die AVM-Doku hier keine Details gibt, nehmen wir Standard
                        vacation_temp = config.get('templates.vacation_temperature', 16.0)
                    break
            
            # Wenn keine Urlaubstemperatur gefunden, Standard verwenden
            if vacation_temp is None:
                vacation_temp = config.get('templates.vacation_temperature', 16.0)
            
            # Heizkörper analysieren
            devices = self.fritz_api.get_devices(use_cache=True)
            if not devices:
                return {
                    'is_active': False,
                    'percentage': 0.0,
                    'active_count': 0,
                    'total_count': 0,
                    'vacation_temp': vacation_temp,
                    'heaters': [],
                    'error': 'Fehler: Keine Geräte von FritzBox empfangen'
                }
            
            heaters = [device for device in devices if device.thermostat]
            heater_details = []
            vacation_active_count = 0
            
            for heater in heaters:
                tsoll = heater.thermostat.get('tsoll', '40')
                holiday_active = heater.thermostat.get('holidayactive', '0')
                device_lock = heater.thermostat.get('devicelock', '0')
                lock = heater.thermostat.get('lock', '0')
                
                # Zieltemperatur umrechnen
                try:
                    target_temp = float(tsoll) / 2 if tsoll and tsoll != '' else 20.0
                except (ValueError, TypeError):
                    target_temp = 20.0
                
                # Prüfen ob Urlaubstemperatur eingestellt ist (bessere Prüfung)
                is_vacation_temp = abs(target_temp - vacation_temp) < 0.5
                
                # Prüfen ob Urlaub aktiv ist (holidayactive als String oder int behandeln)
                holiday_active_bool = holiday_active == '1' or holiday_active == 1
                
                # Zusätzlich prüfen ob Gerät gesperrt ist (kann durch Urlaubsvorlage passieren)
                is_locked = device_lock == '1' or lock == '1'
                
                # Urlaub gilt als aktiv wenn: Urlaubstemperatur ODER holidayactive ODER (Urlaubstemperatur + gesperrt)
                if is_vacation_temp or holiday_active_bool or (is_vacation_temp and is_locked):
                    vacation_active_count += 1
                
                heater_details.append({
                    'name': heater.name,
                    'ain': heater.ain,
                    'target_temp': target_temp,
                    'is_vacation': is_vacation_temp,
                    'holiday_active': holiday_active_bool,
                    'is_locked': is_locked
                })
            
            # Ergebnisse berechnen
            total_heaters = len(heaters)
            vacation_percentage = (vacation_active_count / total_heaters) * 100 if total_heaters > 0 else 0.0
            
            # Bessere Erkennung: 50%+ gilt als aktiv, da nicht alle Heizkörper immer korrekt antworten
            is_active = vacation_percentage >= 50
            
            # Debug-Informationen hinzufügen
            logger.info(f"Urlaubs-Prüfung: {vacation_active_count}/{total_heaters} Heizkörper aktiv ({vacation_percentage:.1f}%)")
            for heater in heater_details:
                if heater['is_vacation'] or heater['holiday_active'] or heater['is_locked']:
                    logger.info(f"  - {heater['name']}: Temp={heater['target_temp']:.1f}°C, Vacation={heater['is_vacation']}, Holiday={heater['holiday_active']}, Locked={heater['is_locked']}")
            
            return {
                'is_active': is_active,
                'percentage': vacation_percentage,
                'active_count': vacation_active_count,
                'total_count': total_heaters,
                'vacation_temp': vacation_temp,
                'heaters': heater_details,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Urlaubs-Prüfung: {e}")
            return {
                'is_active': False,
                'percentage': 0.0,
                'active_count': 0,
                'total_count': 0,
                'vacation_temp': 16.0,
                'heaters': [],
                'error': str(e)
            }
    
    def apply_vacation_template(self, active: bool = True) -> Dict:
        """Wendet Urlaubsvorlage an mit optimierter API"""
        try:
            # Sicherstellen dass Login gültig ist
            if not self._ensure_login():
                return {'success': False, 'error': 'Login fehlgeschlagen'}
            
            vacation_on_name = config.get('templates.vacation_on', 'Urlaubsschaltung AN')
            vacation_off_name = config.get('templates.vacation_off', 'Urlaubsschaltung AUS')
            
            template_name = vacation_on_name if active else vacation_off_name
            
            # Cache löschen um aktuelle Vorlagen zu erhalten
            self.fritz_api.clear_cache()
            
            # Vorlage suchen
            templates = self.fritz_api.get_templates(use_cache=False)
            target_template = None
            
            for template in templates:
                if template.name == template_name:
                    target_template = template
                    break
            
            if not target_template:
                return {
                    'success': False,
                    'error': f'Vorlage "{template_name}" nicht gefunden. Verfügbare Vorlagen: {[t.name for t in templates]}'
                }
            
            # Vorlage anwenden
            success = self.fritz_api.apply_template(target_template.identifier)
            
            # Bei erfolgreicher Anwendung Tastensperren prüfen und ggf. entfernen
            if success and not active:  # Nur beim Deaktivieren des Urlaubs
                self._unlock_thermostats_after_vacation()
            
            return {
                'success': success,
                'template_name': template_name,
                'template_identifier': target_template.identifier,
                'error': None if success else 'Vorlagen-Anwendung fehlgeschlagen'
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Urlaubsvorlage: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _unlock_thermostats_after_vacation(self):
        """Entfernt Tastensperren von Thermostaten nach Urlaubs-Deaktivierung"""
        try:
            devices = self.fritz_api.get_devices(use_cache=False)
            heaters = [device for device in devices if device.thermostat]
            
            unlocked_count = 0
            for heater in heaters:
                device_lock = heater.thermostat.get('devicelock', '0')
                lock = heater.thermostat.get('lock', '0')
                
                # Wenn Gerät gesperrt ist, versuchen zu entsperren
                if device_lock == '1' or lock == '1':
                    logger.info(f"Entsperre Thermostat {heater.name} (AIN: {heater.ain})")
                    
                    # Versuche, die Sperre aufzuheben (setdevicelock Befehl)
                    # Hinweis: Dies funktioniert nur wenn die FritzBox dies unterstützt
                    try:
                        # setdevicelock 0 = Sperre aufheben
                        result = self.fritz_api._execute_aha_command('setdevicelock', ain=heater.ain, param='0')
                        if result is not None:
                            unlocked_count += 1
                            logger.info(f"Thermostat {heater.name} erfolgreich entsperrt")
                        else:
                            logger.warning(f"Konnte Thermostat {heater.name} nicht entsperren")
                    except Exception as e:
                        logger.warning(f"Fehler beim Entsperren von {heater.name}: {e}")
            
            if unlocked_count > 0:
                logger.info(f"{unlocked_count} Thermostate nach Urlaubs-Ende entsperrt")
            
        except Exception as e:
            logger.error(f"Fehler beim Entsperren der Thermostate: {e}")
    
    def clear_cache(self):
        """Löscht alle Caches"""
        self.fritz_api.clear_cache()
        self._stats_cache.clear()


def get_callback_handlers():
    """Gibt die Callback-Handler-Konfiguration für StatistikMode zurück"""
    return {
        'patterns': [
            r'select_heater_.*',
            r'set_temp_.*',
            r'cancel_temp_set',
            r'cancel_window_mode',
            r'window_disable_all', 
            r'window_all_heaters',
            r'window_heater_.*',
            r'window_disable_.*'
        ],
        'handler': StatistikModeOptimized.handle_temp_callback
    }

# Globale Instanz
stats_manager = OptimizedStatisticsManager()

# Module-level tastertur für Bot-Kompatibilität
tastertur = {
    'status': 'Status',
    'set_temp': 'Temperatur setzen',
    'temp_history': 'Temp.-Verlauf',
    'vacation_mode': 'Urlaubsmodus',
    'window_open_mode': 'Fenster-Offen Modus',
    'back': 'Zurueck'
}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {
    'status': 'Zeigt Ziel- und Ist-Temperatur aller Heizkörper an',
    'set_temp': 'Setzt die Temperatur für einen Heizkörper',
    'temp_history': 'Zeigt Temperaturverlauf aller Heizungen der letzten 24 Stunden als Graphik an',
    'vacation_mode': 'Schaltet FritzBox-Urlaubsschaltung für alle Heizkörper ein/aus',
    'window_open_mode': 'Aktiviert den Fenster-Offen Modus für Heizkörper mit konfigurierbarer Dauer und Erinnerung',
    'back': 'Wechselt zurück ins Main-Menu'
}

def get_keyboard_markup(keyboard_data):
    """Hilfsfunktion zur konsistenten Keyboard-Behandlung"""
    if not TELEGRAM_AVAILABLE or not ReplyKeyboardMarkup:
        return None
    
    # Wenn keyboard_data bereits ein ReplyKeyboardMarkup Objekt ist
    if isinstance(keyboard_data, ReplyKeyboardMarkup):
        return keyboard_data
    
    # Wenn keyboard_data eine Liste ist, erstelle ReplyKeyboardMarkup
    if isinstance(keyboard_data, (list, tuple)):
        return ReplyKeyboardMarkup(keyboard_data, resize_keyboard=True)
    
    # Fallback: leere Liste
    return ReplyKeyboardMarkup([], resize_keyboard=True)

# Timer-Funktionen (behalten für Kompatibilität)
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
    
    # Timer-Funktion
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
                    display_name = heater_name_param if heater_name_param else ain_param
                    reminder_text = f"🔔 *Erinnerung: Fenster schließen*\n\n"
                    reminder_text += f"🏠 {display_name}\n"
                    reminder_text += f"⏰ Fenster-Offen Modus endet in {reminder_minutes_param} Minuten\n"
                    reminder_text += f"📅 Bitte Fenster schließen"
                    
                    # Bot-Message in separater async-Funktion senden
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def send_reminder():
                        try:
                            await bot_instance_param.send_message(
                                chat_id=chat_id_param,
                                text=reminder_text,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Fehler beim Senden der Erinnerung: {e}")
                    
                    loop.run_until_complete(send_reminder())
                    loop.close()
                    
            except Exception as e:
                logger.error(f"Fehler bei Timer-Funktion: {e}")
    
    # Timer starten
    timer_thread = threading.Thread(
        target=timer_function,
        args=(chat_id, ain, end_time, reminder_minutes, bot_instance, heater_name),
        daemon=True
    )
    
    window_open_timers[chat_id][ain]['timer_thread'] = timer_thread
    timer_thread.start()

# Legacy-Funktionen für Kompatibilität
def set_window_open_mode(fritz_api, ain, duration_minutes=None, chat_id=None, bot_instance=None):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return stats_manager.set_window_open_mode(ain, duration_minutes, chat_id, bot_instance)

def disable_window_open_mode(fritz_api, ain):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return stats_manager.disable_window_open_mode(ain)

def get_window_open_status(fritz_api, ain):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return stats_manager.get_window_open_status(ain)

def get_next_temperature_change(fritz_api, ain):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return stats_manager.get_next_temperature_change(ain)

def is_vacation_active(fritz_api=None):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return stats_manager.is_vacation_active()

# Zusätzliche Funktionen für Haupt-Bot-Kompatibilität
async def set_temp(update, context, user_data, markupList):
    """Temperatur setzen mit optimierter API"""
    try:
        bot = context.bot
        
        # Keyboard am Anfang setzen
        # Wenn markupList[STATISTICS] leer ist (Test-Modus), dynamisch erstellen
        if markupList and STATISTICS in markupList and markupList[STATISTICS]:
            context.user_data['keyboard'] = markupList[STATISTICS]
        else:
            # Dynamisch erstellen für Test-Modus oder wenn markupList leer
            import lib.config
            if hasattr(lib.config, 'ReplyKeyboardMarkup') and lib.config.ReplyKeyboardMarkup:
                context.user_data['keyboard'] = lib.config.ReplyKeyboardMarkup(
                    lib.config.buildKeyboard(tastertur), 
                    resize_keyboard=True
                )
            else:
                context.user_data['keyboard'] = lib.config.buildKeyboard(tastertur)
        
        context.user_data['status'] = STATISTICS
        
        # Sicherstellen dass Login gültig ist
        if not stats_manager._ensure_login():
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
                    elif reply_func:
                        reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
            return user_data.get('status', STATISTICS)
        
        # Geräte mit optimierter API abrufen (ohne Cache für frische Daten)
        devices = stats_manager.fritz_api.get_devices(use_cache=False)
        logger.info(f"Geräte gefunden: {len(devices)}")
        heaters = [d for d in devices if d.thermostat and d.thermostat.get('tsoll') is not None]
        logger.info(f"Heizkörper gefunden: {len(heaters)}")
        
        if not heaters:
            await update.message.reply_text("Keine Heizkörper gefunden.",
                                          reply_markup=get_keyboard_markup(context.user_data.get('keyboard', [])))
            return context.user_data.get('status', STATISTICS)
        
        # Inline-Keyboard für Heizungsauswahl erstellen
        keyboard = []
        for heater in heaters:
            name = heater.name
            ain = heater.ain
            
            # Aktuelle Temperatur anzeigen
            tist = heater.thermostat.get('tist')
            tsoll = heater.thermostat.get('tsoll')
            
            # Next-Change Information holen
            next_change_info = stats_manager.get_next_temperature_change(ain)
            
            if tist is not None and tsoll is not None:
                current_temp = int(tist) / 2
                target_temp = int(tsoll) / 2
                temp_info = f" ({current_temp:.1f}°C → {target_temp:.1f}°C"
                
                # Nächste Temperaturänderung hinzufügen
                if next_change_info and not next_change_info.get('error') and next_change_info.get('tchange'):
                    next_temp = next_change_info['tchange']
                    if next_temp is not None:
                        next_temp_display = next_temp / 2 if next_temp > 0 else 0
                        temp_info += f" → {next_temp_display:.1f}°C)"
                    else:
                        temp_info += ")"
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
        logger.error(f"Fehler beim Laden der Heizkörper: {str(e)}")
        await update.message.reply_text(f"Fehler beim Laden der Heizkörper: {str(e)}",
                                      reply_markup=context.user_data.get('keyboard', markupList[STATISTICS]))
    
    return context.user_data.get('status', STATISTICS)

async def status(update, context, user_data, markupList):
    """Heizungs-Status mit optimierter API und voller Funktionalität (aus Original übernommen)"""
    try:
        bot = getattr(context, 'bot', None)
        chat_id = getattr(update.effective_chat, 'id', 12345) if hasattr(update, 'effective_chat') else 12345
        
        # Keyboard am Anfang setzen, damit alle reply_text Aufrufe das richtige Keyboard verwenden
        # Wenn markupList[STATISTICS] leer ist (Test-Modus), dynamisch erstellen
        if markupList and STATISTICS in markupList and markupList[STATISTICS]:
            context.user_data['keyboard'] = markupList[STATISTICS]
        else:
            # Dynamisch erstellen für Test-Modus oder wenn markupList leer
            import lib.config
            if hasattr(lib.config, 'ReplyKeyboardMarkup') and lib.config.ReplyKeyboardMarkup:
                context.user_data['keyboard'] = lib.config.ReplyKeyboardMarkup(
                    lib.config.buildKeyboard(tastertur), 
                    resize_keyboard=True
                )
            else:
                context.user_data['keyboard'] = lib.config.buildKeyboard(tastertur)
        
        context.user_data['status'] = STATISTICS
        
        # Hilfsfunktion nutzen um Urlaubsstatus zu prüfen
        vacation_status = is_vacation_active()
        
        # Sicherstellen dass Login gültig ist
        if not stats_manager._ensure_login():
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
                    elif reply_func:
                        reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
            return user_data.get('status', STATISTICS)
        
        devices = stats_manager.fritz_api.get_devices(use_cache=False)
        
        if not devices:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.",
                                                  reply_markup=keyboard_markup)
                else:
                    # Prüfen ob reply_text async ist
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.")
                    elif reply_func:
                        reply_func("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.")
            return user_data.get('status', STATISTICS)
        
        # Filter nur Heizkörper (Geräte mit Thermostat-Daten)
        heaters = [device for device in devices if device.thermostat]
        
        if not heaters:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("Keine Heizkörper gefunden.",
                                                  reply_markup=keyboard_markup)
                else:
                    # Prüfen ob reply_text async ist
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("Keine Heizkörper gefunden.")
                    elif reply_func:
                        reply_func("Keine Heizkörper gefunden.")
            return user_data.get('status', STATISTICS)
        
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
            device_list_url = f"http://{stats_manager.fritz_api.host}:{stats_manager.fritz_api.port}/webservices/homeautoswitch.lua"
            params = {
                'sid': stats_manager.fritz_api.sid,
                'switchcmd': 'getdevicelistinfos'
            }
            response = stats_manager.fritz_api.session.get(device_list_url, params=params, timeout=10)
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
            name = heater.name
            ain = heater.ain
            thermostat = heater.thermostat
            
            # Temperaturen umrechnen (Werte sind in 0.5°C Schritten)
            tist_value = thermostat.get('tist')
            tsoll_value = thermostat.get('tsoll')
            
            # Tastensperre prüfen (nur anzeigen wenn gesperrt)
            device_lock = thermostat.get('devicelock', '0')
            lock = thermostat.get('lock', '0')
            is_locked = device_lock == '1' or lock == '1'
            lock_icon = " 🔒" if is_locked else ""
            lock_info = ""
            if is_locked:
                lock_info = f"   🔒 Tasten gesperrt\n"
            
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
                        status_emoji = "⚠️"
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
                
                message += f"{status_emoji}{vacation_icon}{window_icon}{lock_icon} *{name}*\n"
                message += f"   Aktuell: {current_temp:.1f}°C\n"
                if target_temp_display in ["AUS", "temp. AUS"]:
                    message += f"   Ziel: {target_temp_display}\n"
                else:
                    message += f"   Ziel: {target_temp_display}°C\n"
                
                # Tastensperre Information hinzufügen (nur wenn gesperrt)
                if lock_info:
                    message += lock_info
                
                # Fenster-offen Information hinzufügen
                if window_info:
                    message += window_info
            else:
                message += f"❓{window_icon}{lock_icon} *{name}*\n"
                message += f"   Aktuell: N/A\n"
                message += f"   Ziel: N/A\n"
                
                # Tastensperre Information auch bei N/A Temperaturen (nur wenn gesperrt)
                if lock_info:
                    message += lock_info
                
                # Fenster-offen Information auch bei N/A Temperaturen
                if window_info:
                    message += window_info
        
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard = user_data.get('keyboard', [])
                # Prüfen ob keyboard bereits ein ReplyKeyboardMarkup Objekt ist
                if isinstance(keyboard, ReplyKeyboardMarkup):
                    keyboard_markup = keyboard
                else:
                    # Keyboard ist eine Liste von Strings, erstelle ReplyKeyboardMarkup
                    keyboard_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(message, reply_markup=keyboard_markup, parse_mode='Markdown')
            else:
                # Prüfen ob reply_text async ist
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(message, parse_mode='Markdown')
                elif reply_func:
                    reply_func(message)
        return user_data.get('status', STATISTICS)
        
    except Exception as e:
        logger.error(f"Fehler bei Heizungs-Status: {e}")
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(
                    f"❌ Fehler bei der Statusabfrage: {str(e)}",
                    reply_markup=keyboard_markup
                )
            else:
                # Prüfen ob reply_text async ist
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(f"❌ Fehler bei der Statusabfrage: {str(e)}")
                elif reply_func:
                    reply_func(f"❌ Fehler bei der Statusabfrage: {str(e)}")
        return user_data['status']

async def temp_history(update, context, user_data, markupList):
    """Zeigt den Temperaturverlauf aller Heizungen der letzten 24 Stunden als Graphik an"""
    try:
        bot = context.bot
        chat_id = update.effective_chat.id
        
        # Keyboard am Anfang setzen
        # Wenn markupList[STATISTICS] leer ist (Test-Modus), dynamisch erstellen
        if markupList and STATISTICS in markupList and markupList[STATISTICS]:
            context.user_data['keyboard'] = markupList[STATISTICS]
        else:
            # Dynamisch erstellen für Test-Modus oder wenn markupList leer
            import lib.config
            if hasattr(lib.config, 'ReplyKeyboardMarkup') and lib.config.ReplyKeyboardMarkup:
                context.user_data['keyboard'] = lib.config.ReplyKeyboardMarkup(
                    lib.config.buildKeyboard(tastertur), 
                    resize_keyboard=True
                )
            else:
                context.user_data['keyboard'] = lib.config.buildKeyboard(tastertur)
        
        context.user_data['status'] = STATISTICS
        
        # Ladebalken-Nachricht senden
        loading_message = await update.message.reply_text("📊 Lade Temperaturverlauf...", 
                                                     reply_markup=context.user_data.get('keyboard', []))
        
        # Sicherstellen dass Login gültig ist
        if not stats_manager._ensure_login():
            await loading_message.edit_text("❌ Login bei FritzBox fehlgeschlagen.")
            return user_data.get('status', STATISTICS)
        
        # Geräte abrufen
        devices = stats_manager.fritz_api.get_devices(use_cache=False)
        if not devices:
            await loading_message.edit_text("❌ Keine Geräte gefunden.")
            return user_data.get('status', STATISTICS)
        
        # Heizkörper filtern
        heaters = [device for device in devices if device.thermostat and device.thermostat.get('tsoll') is not None]
        if not heaters:
            await loading_message.edit_text("❌ Keine Heizkörper gefunden.")
            return user_data.get('status', STATISTICS)
        
        # Temperaturhistorien für alle Heizkörper sammeln
        all_histories = []
        successful_analyses = 0
        
        for heater in heaters:
            name = heater.name
            ain = heater.ain
            
            # Historie abrufen
            history = stats_manager.get_temperature_history(ain)
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
            return user_data.get('status', STATISTICS)
        
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
                
                # Zeitachse für diesen Heizkörper erstellen (gleiche Länge wie Temperatur-Array)
                temp_count = len(temps)
                temp_time_points = [end_time - timedelta(minutes=15*j) for j in range(temp_count-1, -1, -1)]
                
                # Plot mit Linie und Markern
                plt.plot(temp_time_points, temps, 
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
                reply_markup=context.user_data.get('keyboard', [])
            )
            
        except ImportError:
            try:
                await loading_message.edit_text("❌ Matplotlib nicht installiert. Bitte installieren Sie:\n"
                                              "`pip install matplotlib`")
            except Exception as edit_error:
                logger.error(f"Fehler beim Editieren der Nachricht: {edit_error}")
                await update.message.reply_text("❌ Matplotlib nicht installiert. Bitte installieren Sie:\n"
                                              "`pip install matplotlib`",
                                              reply_markup=context.user_data.get('keyboard', []))
        except Exception as e:
            try:
                await loading_message.edit_text(f"❌ Fehler beim Erstellen der Graphik: {str(e)}")
            except Exception as edit_error:
                logger.error(f"Fehler beim Editieren der Nachricht: {edit_error}")
                await update.message.reply_text(f"❌ Fehler beim Erstellen der Graphik: {str(e)}",
                                              reply_markup=context.user_data.get('keyboard', []))
    
    except Exception as e:
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(f"Fehler beim Abrufen der Temperaturverlaufsdaten: {str(e)}",
                                              reply_markup=keyboard_markup)
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(f"Fehler beim Abrufen der Temperaturverlaufsdaten: {str(e)}")
                elif reply_func:
                    reply_func(f"Fehler beim Abrufen der Temperaturverlaufsdaten: {str(e)}")
    
    return user_data.get('status', STATISTICS)

async def handle_temp_callback(update, context):
    """Handler für Temperatur-Callbacks mit optimierter API"""
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
            
            # Gewählten Heizkörper finden
            selected_heater = None
            for heater in heaters:
                if heater.ain == ain:
                    selected_heater = heater
                    break
            
            if not selected_heater:
                await query.edit_message_text("Fehler: Heizkörper nicht gefunden.")
                return
            
            name = selected_heater.name
            tsoll = selected_heater.thermostat.get('tsoll')
            
            # Next-Change Information holen
            next_change_info = stats_manager.get_next_temperature_change(ain)
            
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
            if next_change_info and not next_change_info.get('error') and next_change_info.get('tchange'):
                next_temp = next_change_info['tchange']
                if next_temp is not None:
                    next_temp_display = next_temp / 2 if next_temp > 0 else 0
                    
                    # Zeit der nächsten Änderung holen
                    time_text = ""
                    if next_change_info.get('endperiod'):
                        try:
                            timestamp = int(next_change_info['endperiod'])
                            if timestamp > 0:
                                next_time = datetime.fromtimestamp(timestamp)
                                time_text = f" um {next_time.strftime('%H:%M')}"
                        except (ValueError, OSError):
                            pass
                    
                    message_text += f"🔄 Nächste Änderung: {next_temp_display:.1f}°C{time_text}\n"
            
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
                if heater.ain == ain:
                    heater_name = heater.name
                    break
            
            # Temperatur setzen mit optimierter API
            logger.info(f"Setze Temperatur für {heater_name} (AIN: {ain}) auf {temp_celsius:.1f}°C")
            success = stats_manager.fritz_api.set_temperature(ain, temp_celsius)
            logger.info(f"Temperatur-Setzung Ergebnis: {success}")
            
            if success:
                # Next-Change Information holen
                next_change_info = stats_manager.get_next_temperature_change(ain)
                logger.info(f"Next-Change Info für {ain}: {next_change_info}")
                
                success_message = f"✅ *Temperatur erfolgreich gesetzt!*\n\n"
                success_message += f"🏠 {heater_name}\n"
                success_message += f"🌡️ Neue Zieltemperatur: {temp_celsius:.1f}°C"
                
                if next_change_info and not next_change_info.get('error'):
                    next_temp = next_change_info.get('tchange')
                    logger.info(f"Next-Change tchange: {next_temp}")
                    if next_temp is not None:
                        next_temp_display = next_temp / 2 if next_temp > 0 else 0
                        
                        # Uhrzeit der nächsten Änderung holen
                        time_text = ""
                        if next_change_info.get('endperiod'):
                            try:
                                timestamp = int(next_change_info['endperiod'])
                                if timestamp > 0:
                                    next_time = datetime.fromtimestamp(timestamp)
                                    time_text = f" um {next_time.strftime('%H:%M')}"
                            except (ValueError, OSError):
                                pass
                        
                        success_message += f"\n\n⏰ *Nächste automatische Änderung:* {next_temp_display:.1f}°C{time_text}"
                else:
                    logger.info(f"Next-Change nicht verfügbar oder Fehler: {next_change_info.get('error') if next_change_info else 'None'}")
                
                # Inline-Nachricht entfernen und neue Nachricht senden
                await query.delete_message()
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=success_message,
                    parse_mode='Markdown'
                )
            else:
                # Inline-Nachricht entfernen und Fehlermeldung senden
                await query.delete_message()
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ Fehler beim Setzen der Temperatur für {heater_name}"
                )
        
    except Exception as e:
        logger.error(f"Fehler bei Temperatur-Callback: {e}")
        await query.delete_message()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"❌ Fehler: {str(e)}"
        )

async def handle_window_callback(update, context):
    """Handler für Fenster-Callbacks mit optimierter API"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == 'cancel_window_mode':
            await query.edit_message_text("❌ Fenster-Modus abgebrochen")
            return
        
        # Geräte abrufen
        devices = stats_manager.fritz_api.get_devices(use_cache=True)
        heaters = [d for d in devices if d.thermostat and d.thermostat.get('tsoll') is not None]
        
        if query.data == 'window_disable_all':
            # Alle Fenster-Modi deaktivieren
            success_count = 0
            for heater in heaters:
                if stats_manager.disable_window_open_mode(heater.ain):
                    success_count += 1
            
            await query.edit_message_text(
                f"✅ Fenster-Modus bei {success_count}/{len(heaters)} Heizkörpern deaktiviert"
            )
        
        elif query.data == 'window_all_heaters':
            # Alle Heizkörper für Fenster-Modus anzeigen
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = []
            for heater in heaters:
                status = stats_manager.get_window_open_status(heater.ain)
                status_text = "🟢 Aktiv" if status.get('windowopenactiv') else "🔴 Inaktiv"
                
                keyboard.append([InlineKeyboardButton(
                    f"🪟 {heater.name} ({status_text})",
                    callback_data=f'window_heater_{heater.ain}_{heater.name}'
                )])
            
            keyboard.append([
                InlineKeyboardButton("🚫 Alle deaktivieren", callback_data='window_disable_all'),
                InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_window_mode')
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🪟 **Fenster-Modus - Heizkörper auswählen:**\n\n"
                "Wähle den Heizkörper für den Fenster-Offen-Modus:",
                reply_markup=reply_markup, parse_mode='Markdown'
            )
        
        elif query.data.startswith('window_heater_'):
            # Spezifischen Heizkörper behandeln
            logger.info(f"Window callback data: {query.data}")
            
            # Bessere Extraktion: Entferne "window_heater_" und teile den Rest
            data_part = query.data[len('window_heater_'):]  # "14456 0864968_Küche Heizung"
            
            # Finde den letzten Underscore um Namen von AIN zu trennen
            last_underscore = data_part.rfind('_')
            if last_underscore > 0:
                ain = data_part[:last_underscore]  # "14456 0864968"
                name_part = data_part[last_underscore + 1:]  # "Küche Heizung"
            else:
                ain = data_part  # Kein Name vorhanden
                name_part = ""
            
            logger.info(f"Extrahierte AIN: '{ain}'")
            logger.info(f"Extrahierter Name: '{name_part}'")
            
            # Gerätename aus der Geräteliste holen
            heater_name = "Unbekannt"
            try:
                # Frische Geräte-Daten holen um Cache-Probleme zu vermeiden
                devices = stats_manager.fritz_api.get_devices(use_cache=False)
                logger.info(f"Suche nach AIN '{ain}' in {len(devices)} Geräten")
                
                for device in devices:
                    logger.info(f"Vergleiche mit Gerät: {device.name} (AIN: '{device.ain}')")
                    if device.ain == ain:
                        heater_name = device.name
                        logger.info(f"Gerät gefunden: {heater_name}")
                        break
                
                if heater_name == "Unbekannt":
                    logger.warning(f"Kein Gerät mit AIN '{ain}' gefunden")
                    logger.info(f"Verfügbare AINs: {[d.ain for d in devices if d.thermostat]}")
                    
            except Exception as e:
                logger.error(f"Fehler beim Holen des Gerätenamens: {e}")
            
            logger.info(f"Verwende Name: '{heater_name}'")
            
            # Toggle Fenster-Modus
            current_status = stats_manager.get_window_open_status(ain)
            
            if current_status.get('windowopenactiv'):
                # Deaktivieren
                if stats_manager.disable_window_open_mode(ain):
                    await query.edit_message_text(
                        f"✅ Fenster-Modus für {heater_name} deaktiviert"
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Fehler beim Deaktivieren des Fenster-Modus für {heater_name}"
                    )
            else:
                # Aktivieren mit Standard-Dauer aus Konfiguration
                from lib.config import Config
                config_obj = Config()
                window_config = config_obj.get('window_open', {})
                default_duration = window_config.get('default_duration_minutes', 30)
                
                result = stats_manager.set_window_open_mode(ain, duration_minutes=default_duration)
                
                if result['success']:
                    end_time = result['end_time']
                    await query.edit_message_text(
                        f"✅ Fenster-Modus für {heater_name} aktiviert\n"
                        f"⏰ Bis: {end_time.strftime('%H:%M')} Uhr\n"
                        f"📅 Dauer: {result['duration_minutes']} Minuten"
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Fehler beim Aktivieren des Fenster-Modus für {heater_name}\n"
                        f"Fehler: {result.get('error', 'Unbekannt')}"
                    )
        
        elif query.data.startswith('window_disable_'):
            # Spezifischen Heizkörper deaktivieren
            parts = query.data.split('_', 2)
            if len(parts) >= 2:
                ain = parts[1]
                heater_name = f"Heizkörper {ain}"
                
                # Namen versuchen zu ermitteln
                for heater in heaters:
                    if heater.ain == ain:
                        heater_name = heater.name
                        break
                
                if stats_manager.disable_window_open_mode(ain):
                    await query.edit_message_text(
                        f"✅ Fenster-Modus für {heater_name} deaktiviert"
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Fehler beim Deaktivieren des Fenster-Modus für {heater_name}"
                    )
        
    except Exception as e:
        logger.error(f"Fehler bei Fenster-Callback: {e}")

async def window_open_mode(update, context, user_data, markupList):
    """HKR Fenster-Offen Modus - Hauptfunktion"""
    try:
        chat_id = update.effective_chat.id
        
        # Keyboard am Anfang setzen
        # Wenn markupList[STATISTICS] leer ist (Test-Modus), dynamisch erstellen
        if markupList and STATISTICS in markupList and markupList[STATISTICS]:
            context.user_data['keyboard'] = markupList[STATISTICS]
        else:
            # Dynamisch erstellen für Test-Modus oder wenn markupList leer
            import lib.config
            if hasattr(lib.config, 'ReplyKeyboardMarkup') and lib.config.ReplyKeyboardMarkup:
                context.user_data['keyboard'] = lib.config.ReplyKeyboardMarkup(
                    lib.config.buildKeyboard(tastertur), 
                    resize_keyboard=True
                )
            else:
                context.user_data['keyboard'] = lib.config.buildKeyboard(tastertur)
        
        context.user_data['status'] = STATISTICS
        
        # Konfiguration für Fenster-Offen Modus laden
        from lib.config import Config
        config_obj = Config()
        window_config = config_obj.get('window_open', {})
        default_duration = window_config.get('default_duration_minutes', 30)
        reminder_minutes = window_config.get('reminder_minutes_before', 5)
        
        # Sicherstellen dass Login gültig ist
        if not stats_manager._ensure_login():
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
                    elif reply_func:
                        reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
            return user_data.get('status', STATISTICS)
        
        # Geräte abrufen
        devices = stats_manager.fritz_api.get_devices(use_cache=False)
        if not devices:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Keine Geräte gefunden!",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Keine Geräte gefunden!")
                    elif reply_func:
                        reply_func("❌ Keine Geräte gefunden!")
            return user_data.get('status', STATISTICS)
        
        heaters = [device for device in devices if device.thermostat and device.thermostat.get('tsoll') is not None]
        if not heaters:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Keine Heizkörper gefunden!",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Keine Heizkörper gefunden!")
                    elif reply_func:
                        reply_func("❌ Keine Heizkörper gefunden!")
            return user_data.get('status', STATISTICS)
        
        # Hole alle Fenster-Status-Informationen in einem einzigen API-Aufruf
        window_status_cache = {}
        try:
            device_list_url = f"http://{stats_manager.fritz_api.host}:{stats_manager.fritz_api.port}/webservices/homeautoswitch.lua"
            params = {
                'sid': stats_manager.fritz_api.sid,
                'switchcmd': 'getdevicelistinfos'
            }
            response = stats_manager.fritz_api.session.get(device_list_url, params=params, timeout=10)
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
            name = heater.name
            ain = heater.ain
            thermostat = heater.thermostat
            
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
        
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(f"🪟 *Fenster-Offen Modus*\n\n"
                                            f"Konfiguration: {default_duration} Minuten, Erinnerung {reminder_minutes} Min. vor Ablauf\n\n"
                                            "Wähle einen Heizkörper oder eine Aktion:\n",
                                            parse_mode='Markdown',
                                            reply_markup=reply_markup)
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(f"🪟 *Fenster-Offen Modus*\n\n"
                                    f"Konfiguration: {default_duration} Minuten, Erinnerung {reminder_minutes} Min. vor Ablauf\n\n"
                                    "Wähle einen Heizkörper oder eine Aktion:\n")
                elif reply_func:
                    reply_func(f"🪟 *Fenster-Offen Modus*\n\n"
                                    f"Konfiguration: {default_duration} Minuten, Erinnerung {reminder_minutes} Min. vor Ablauf\n\n"
                                    "Wähle einen Heizkörper oder eine Aktion:\n")
        
        context.user_data['window_mode'] = True
        return user_data.get('status', STATISTICS)
        
    except Exception as e:
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(f"Fehler beim Abrufen der Geräte: {str(e)}",
                                              reply_markup=keyboard_markup)
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(f"Fehler beim Abrufen der Geräte: {str(e)}")
                elif reply_func:
                    reply_func(f"Fehler beim Abrufen der Geräte: {str(e)}")
        return user_data.get('status', STATISTICS)

async def vacation_mode(update, context, user_data, markupList):
    """Schaltet alle Heizkörper in den Urlaubsmodus oder zurück"""
    try:
        bot = context.bot
        chat_id = update.effective_chat.id
        
        # Keyboard am Anfang setzen
        # Wenn markupList[STATISTICS] leer ist (Test-Modus), dynamisch erstellen
        if markupList and STATISTICS in markupList and markupList[STATISTICS]:
            context.user_data['keyboard'] = markupList[STATISTICS]
        else:
            # Dynamisch erstellen für Test-Modus oder wenn markupList leer
            import lib.config
            if hasattr(lib.config, 'ReplyKeyboardMarkup') and lib.config.ReplyKeyboardMarkup:
                context.user_data['keyboard'] = lib.config.ReplyKeyboardMarkup(
                    lib.config.buildKeyboard(tastertur), 
                    resize_keyboard=True
                )
            else:
                context.user_data['keyboard'] = lib.config.buildKeyboard(tastertur)
        
        context.user_data['status'] = STATISTICS
        
        # Import Config für Vorlagennamen
        from lib.config import Config
        config = Config()
        
        # Vorlagennamen aus Konfiguration holen
        vacation_on_name = config.get('templates.vacation_on', 'Urlaubsschaltung AN')
        vacation_off_name = config.get('templates.vacation_off', 'Urlaubsschaltung AUS')
        
        # Sicherstellen dass Login gültig ist
        if not stats_manager._ensure_login():
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
                    elif reply_func:
                        reply_func("❌ Verbindungsfehler: Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
            return user_data.get('status', STATISTICS)
        
        devices = stats_manager.fritz_api.get_devices(use_cache=False)
        
        if not devices:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.")
                    elif reply_func:
                        reply_func("Keine Geräte gefunden oder Verbindung zur FritzBox fehlgeschlagen.")
            return user_data.get('status', STATISTICS)
        
        # Filter nur Heizkörper (Geräte mit Thermostat-Daten)
        heaters = [device for device in devices if device.thermostat and device.thermostat.get('tsoll') is not None]
        
        if not heaters:
            if hasattr(update.message, 'reply_text'):
                if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                    keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                    await update.message.reply_text("Keine Heizkörper gefunden.",
                                                  reply_markup=keyboard_markup)
                else:
                    reply_func = getattr(update.message, 'reply_text', None)
                    if reply_func and asyncio.iscoroutinefunction(reply_func):
                        await reply_func("Keine Heizkörper gefunden.")
                    elif reply_func:
                        reply_func("Keine Heizkörper gefunden.")
            return user_data.get('status', STATISTICS)
        
        # Prüfen ob bereits im Urlaubsmodus (Hilfsfunktion nutzen)
        vacation_status_check = stats_manager.is_vacation_active()
        vacation_active = vacation_status_check['is_active'] if not vacation_status_check['error'] else False
        
        # Cache löschen um aktuelle Daten zu erhalten
        stats_manager.fritz_api.clear_cache()
        
        # Zuerst versuchen, die Vorlagenliste über AHA-Interface zu holen
        template_list = stats_manager.fritz_api.get_template_list_aha()
        
        message = f"🏖️ *FritzBox Urlaubsmodus wird umgeschaltet...*\n\n"
        
        # Debug-Informationen hinzufügen
        if vacation_status_check.get('error'):
            message += f"⚠️ *Status-Prüfung fehlgeschlagen:* {vacation_status_check['error']}\n\n"
        else:
            message += f"📊 *Aktueller Status:* {vacation_status_check['active_count']}/{vacation_status_check['total_count']} Heizkörper im Urlaubsmodus ({vacation_status_check['percentage']:.1f}%)\n\n"
        
        if template_list:
            # XML parsen und Vorlagen extrahieren
            templates = stats_manager.fritz_api.parse_template_xml(template_list)
            
            # Prüfen, ob Urlaubsvorlagen vorhanden sind
            vacation_templates = []
            for template in templates:
                if template['name'] == vacation_on_name or template['name'] == vacation_off_name:
                    vacation_templates.append(template)
            
            if vacation_templates:
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
                    
                    # Verwende applytemplate mit Identifier
                    if off_template:
                        try:
                            # Vorlage mit applytemplate und Identifier anwenden
                            success = stats_manager.fritz_api.apply_template(off_template['identifier'])
                            
                            if success:
                                message += f"✅ *Urlaubsmodus erfolgreich deaktiviert!*\n\n"
                                message += f"🏠 Alle Heizkörper wieder im Normalbetrieb\n"
                                message += f"📅 Zeitplan wieder aktiv\n"
                                
                                # Warten und Status erneut prüfen
                                import time
                                time.sleep(2)  # Kurze Wartezeit damit FritzBox die Änderung übernehmen kann
                                stats_manager.fritz_api.clear_cache()  # Cache löschen
                                new_status = stats_manager.is_vacation_active()
                                if not new_status.get('error') and not new_status['is_active']:
                                    message += f"✅ *Status-Prüfung bestätigt:* Urlaubmodus beendet\n"
                                else:
                                    message += f"⚠️ *Status-Prüfung:* Möglicherweise noch aktiv ({new_status.get('percentage', 0):.1f}%)\n"
                            else:
                                message += f"❌ *Fehler beim Deaktivieren des Urlaubsmodus!*\n\n"
                                message += f"Bitte überprüfen Sie die Verbindung zur FritzBox.\n"
                        except Exception as e:
                            message += f"❌ *Fehler bei der Vorlagenanwendung:*\n{str(e)}\n"
                    else:
                        message += f"❌ *Urlaubs-AUS-Vorlage nicht gefunden!*\n\n"
                        message += f"Erwartete Vorlage: '{vacation_off_name}'\n"
                        message += f"Bitte überprüfen Sie die Konfiguration.\n"
                else:
                    # Urlaubsmodus aktivieren
                    message += f"🏖️ *Urlaubsmodus wird aktiviert...*\n\n"
                    
                    # Verwende applytemplate mit Identifier
                    if on_template:
                        try:
                            # Vorlage mit applytemplate und Identifier anwenden
                            success = stats_manager.fritz_api.apply_template(on_template['identifier'])
                            
                            if success:
                                message += f"✅ *Urlaubsmodus erfolgreich aktiviert!*\n\n"
                                message += f"🏖️ Alle Heizkörper auf Urlaubstemperatur\n"
                                message += f"📅 Zeitplan vorübergehend deaktiviert\n"
                                message += f"🌡️ Urlaubstemperatur: {vacation_status_check.get('vacation_temp', 16.0):.1f}°C\n"
                                
                                # Warten und Status erneut prüfen
                                import time
                                time.sleep(2)  # Kurze Wartezeit damit FritzBox die Änderung übernehmen kann
                                stats_manager.fritz_api.clear_cache()  # Cache löschen
                                new_status = stats_manager.is_vacation_active()
                                if not new_status.get('error') and new_status['is_active']:
                                    message += f"✅ *Status-Prüfung bestätigt:* Urlaubmodus aktiv ({new_status['percentage']:.1f}%)\n"
                                else:
                                    message += f"⚠️ *Status-Prüfung:* Möglicherweise noch nicht voll aktiv ({new_status.get('percentage', 0):.1f}%)\n"
                            else:
                                message += f"❌ *Fehler beim Aktivieren des Urlaubsmodus!*\n\n"
                                message += f"Bitte überprüfen Sie die Verbindung zur FritzBox.\n"
                        except Exception as e:
                            message += f"❌ *Fehler bei der Vorlagenanwendung:*\n{str(e)}\n"
                    else:
                        message += f"❌ *Urlaubs-AN-Vorlage nicht gefunden!*\n\n"
                        message += f"Erwartete Vorlage: '{vacation_on_name}'\n"
                        message += f"Bitte überprüfen Sie die Konfiguration.\n"
            else:
                message += f"❌ *Keine Urlaubs-Vorlagen gefunden!*\n\n"
                message += f"Bitte erstellen Sie zuerst die folgenden Vorlagen in der FritzBox:\n"
                message += f"• '{vacation_on_name}'\n"
                message += f"• '{vacation_off_name}'\n"
        else:
            message += f"❌ *Keine Vorlagen gefunden!*\n\n"
            message += f"Konnte keine Vorlagen von der FritzBox abrufen.\n"
        
        # Nachricht senden
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard_markup)
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(message)
                elif reply_func:
                    reply_func(message)
        
        return user_data.get('status', STATISTICS)
        
    except Exception as e:
        logger.error(f"Fehler bei vacation_mode: {e}")
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                keyboard_markup = get_keyboard_markup(user_data.get('keyboard', []))
                await update.message.reply_text(f"Fehler: {str(e)}", reply_markup=keyboard_markup)
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func(f"Fehler: {str(e)}")
                elif reply_func:
                    reply_func(f"Fehler: {str(e)}")
        return user_data.get('status', STATISTICS)

async def back(update, context, user_data, markupList):
    """Wechselt zurück ins Hauptmenü"""
    try:
        from lib.config import MAIN
        context.user_data['keyboard'] = markupList[MAIN]
        context.user_data['status'] = MAIN
        
        if hasattr(update.message, 'reply_text'):
            if TELEGRAM_AVAILABLE and ReplyKeyboardMarkup:
                await update.message.reply_text('🏠 Zurück zum Hauptmenü', reply_markup=markupList[MAIN])
            else:
                reply_func = getattr(update.message, 'reply_text', None)
                if reply_func and asyncio.iscoroutinefunction(reply_func):
                    await reply_func('🏠 Zurück zum Hauptmenü')
                elif reply_func:
                    reply_func('🏠 Zurück zum Hauptmenü')
        
        return context.user_data.get('status', MAIN)
    except Exception as e:
        logger.error(f"Fehler bei back: {e}")
        return context.user_data.get('status', MAIN)

async def default(update, context, user_data, markupList):
    """Default-Funktion - zeigt Status an"""
    return await status(update, context, user_data, markupList)

# Import time für Timer
import time
