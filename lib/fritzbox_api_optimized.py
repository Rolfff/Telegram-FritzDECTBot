#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import xml.etree.ElementTree as ET
import hashlib
import time
import urllib.parse
import urllib.request
import json
import logging
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from lib.config import Config

# Logger initialisieren
logger = logging.getLogger(__name__)

@dataclass
class DeviceInfo:
    """Struktur für Geräteinformationen"""
    ain: str
    name: str
    manufacturer: str
    productname: str
    fwversion: str
    present: bool
    txbusy: bool
    functionbitmask: int
    device_type: str
    temperature: Optional[Dict] = None
    thermostat: Optional[Dict] = None
    switch: Optional[Dict] = None
    powermeter: Optional[Dict] = None
    battery: Optional[Dict] = None
    alert: Optional[Dict] = None
    button: Optional[List[Dict]] = None
    simpleonoff: Optional[Dict] = None
    levelcontrol: Optional[Dict] = None
    colorcontrol: Optional[Dict] = None
    blind: Optional[Dict] = None

@dataclass
class TemplateInfo:
    """Struktur für Vorlageninformationen"""
    identifier: str
    id: str
    name: str
    functionbitmask: int
    autocreate: bool
    devices: List[str]
    applymask: Dict[str, Any]
    metadata: Optional[Dict] = None
    sub_templates: Optional[List[str]] = None
    triggers: Optional[List[str]] = None
    
    @property
    def is_template(self) -> bool:
        """Prüft ob dies eine einfache Vorlage ist"""
        return (not self.autocreate and 
                len(self.devices) > 0 and 
                not self.is_scenario)
    
    @property
    def is_scenario(self) -> bool:
        """Prüft ob dies ein Szenario ist (mehrere Vorlagen oder Trigger)"""
        return (self.sub_templates is not None and len(self.sub_templates) > 0) or \
               (self.triggers is not None and len(self.triggers) > 0)
    
    @property
    def is_vacation_scenario(self) -> bool:
        """Prüft ob dies ein Urlaubsszenario ist"""
        return ("urlaub" in self.name.lower() or 
                "vacation" in self.name.lower())

class OptimizedFritzBoxAPI:
    """
    Optimierte AHA-Schnittstelle für FritzBox mit Performance-Optimierungen
    Basierend auf AVM Home Automation HTTP Interface Documentation
    """
    
    # Function Bitmask Constants
    FUNCTION_HANFUN = 1
    FUNCTION_LIGHT = 4
    FUNCTION_ALARM = 16
    FUNCTION_BUTTON = 32
    FUNCTION_HKR = 64
    FUNCTION_ENERGY = 128
    FUNCTION_TEMPERATURE = 256
    FUNCTION_POWERMETER = 512
    FUNCTION_DECT_REPEATER = 1024
    FUNCTION_MICROPHONE = 2048
    FUNCTION_HANFUN_UNIT = 8192
    FUNCTION_ONOFF = 32768
    FUNCTION_LEVEL = 65536
    FUNCTION_COLOR = 131072
    FUNCTION_BLIND = 262144
    FUNCTION_HUMIDITY = 1048576
    
    def __init__(self, config=None):
        # Verwende übergebene Config oder globale Instanz
        if config is not None:
            self.config = config
        else:
            # Versuche, die globale Config aus dem Bot zu holen
            try:
                import sys
                import os
                # Finde die Konfigurationsdatei aus sys.argv
                config_file = None
                if len(sys.argv) > 1:
                    for i, arg in enumerate(sys.argv):
                        if arg == '-c' and i + 1 < len(sys.argv):
                            config_file = sys.argv[i + 1]
                            break
                
                if config_file and os.path.exists(config_file):
                    self.config = Config(config_file)
                else:
                    self.config = Config()
            except Exception:
                self.config = Config()
        
        self.fritz_config = self.config.get_fritzbox_config()
        
        # Entferne Default-Werte - löse Error aus wenn nicht vorhanden
        self.host = self.fritz_config.get('host')
        self.port = self.fritz_config.get('port')
        self.username = self.fritz_config.get('username')
        self.password = self.fritz_config.get('password')
        
        # Error wenn notwendige Konfiguration fehlt
        if not self.host:
            raise ValueError("FATAL: 'host' nicht in Konfiguration gefunden! Bitte überprüfe deine config.json")
        if not self.username:
            raise ValueError("FATAL: 'username' nicht in Konfiguration gefunden! Bitte überprüfe deine config.json")
        if not self.password:
            raise ValueError("FATAL: 'password' nicht in Konfiguration gefunden! Bitte überprüfe deine config.json")
        if self.port is None:
            raise ValueError("FATAL: 'port' nicht in Konfiguration gefunden! Bitte überprüfe deine config.json")
        self.session = requests.Session()
        self.sid = None
        
        # Performance Caching
        self._device_cache = {}
        self._template_cache = {}
        self._cache_timestamp = {}
        self._cache_lock = threading.Lock()
        self._cache_timeout = 30  # Sekunden
        
        # Connection Pooling für Performance
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Prüft ob Cache noch gültig ist"""
        with self._cache_lock:
            if cache_key not in self._cache_timestamp:
                return False
            return time.time() - self._cache_timestamp[cache_key] < self._cache_timeout
    
    def _update_cache(self, cache_key: str, data: Any) -> None:
        """Aktualisiert den Cache"""
        with self._cache_lock:
            if cache_key == 'devices':
                self._device_cache = data
            elif cache_key == 'templates':
                self._template_cache = data
            self._cache_timestamp[cache_key] = time.time()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Holt Daten aus Cache"""
        with self._cache_lock:
            if cache_key == 'devices':
                return self._device_cache.get('devices') if self._device_cache else None
            elif cache_key == 'templates':
                return self._template_cache.get('templates') if self._template_cache else None
        return None
    
    def _execute_aha_command(self, switchcmd: str, ain: str = None, param: str = None, 
                           endtimestamp: str = None, use_cache: bool = False) -> Optional[Union[str, Dict]]:
        """
        Führt einen AHA-Befehl aus mit optimierter Fehlerbehandlung und Performance
        
        Args:
            switchcmd: AHA-Kommando gemäß Dokumentation
            ain: Geräte-Identifikator (optional)
            param: Zusätzlicher Parameter (optional)
            endtimestamp: Spezieller Parameter für sethkrwindowopen (optional)
            use_cache: Cache verwenden für Leseoperationen
            
        Returns:
            Response als Text oder geparste XML-Daten
        """
        # Cache-Check für Leseoperationen
        if use_cache and switchcmd in ['getdevicelistinfos', 'gettemplatelistinfos']:
            cache_key = 'devices' if switchcmd == 'getdevicelistinfos' else 'templates'
            if self._is_cache_valid(cache_key):
                cached_data = self._get_from_cache(cache_key)
                if cached_data:
                    return cached_data
        
        # Sicherstellen dass Login vorhanden
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        # URL-Parameter vorbereiten
        params = {
            'sid': self.sid,
            'switchcmd': switchcmd
        }
        
        if ain:
            params['ain'] = ain
        if param is not None:
            params['param'] = param
        if endtimestamp is not None:
            params['endtimestamp'] = endtimestamp
        
        # URL basierend auf Dokumentation
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        # Debug-Logging für AHA-Kommando
        logger.info(f"AHA-Kommando: {switchcmd}")
        logger.info(f"URL: {url}")
        logger.info(f"Parameter: {params}")
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            logger.info(f"HTTP Status: {response.status_code}")
            logger.info(f"HTTP Response: {response.text.strip()}")
            response.raise_for_status()
            
            # XML-Antworten speziell behandeln
            if switchcmd in ['getdevicelistinfos', 'gettemplatelistinfos', 'getbasicdevicestats', 
                           'gettriggerlistinfos', 'getcolordefaults', 'getdeviceinfos']:
                xml_data = response.text
                parsed_data = self._parse_xml_response(switchcmd, xml_data)
                
                # Cache aktualisieren
                if use_cache and switchcmd in ['getdevicelistinfos', 'gettemplatelistinfos']:
                    cache_key = 'devices' if switchcmd == 'getdevicelistinfos' else 'templates'
                    self._update_cache(cache_key, parsed_data)
                
                return parsed_data
            else:
                return response.text.strip()
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"AHA Command Error ({switchcmd}): {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected Error ({switchcmd}): {e}")
            return None
    
    def _parse_xml_response(self, command: str, xml_data: str) -> Dict:
        """Parst XML-Antworten gemäß AVM-Dokumentation"""
        try:
            root = ET.fromstring(xml_data)
            
            if command == 'getdevicelistinfos':
                return self._parse_device_list(root)
            elif command == 'gettemplatelistinfos':
                return self._parse_template_list(root)
            elif command == 'getbasicdevicestats':
                return self._parse_device_stats(root)
            elif command == 'gettriggerlistinfos':
                return self._parse_trigger_list(root)
            elif command == 'getcolordefaults':
                return self._parse_color_defaults(root)
            elif command == 'getdeviceinfos':
                return self._parse_single_device(root)
            else:
                return {'xml': xml_data}
                
        except ET.ParseError as e:
            logger.debug(f"XML Parse Error: {e}")
            return {'error': f'XML Parse Error: {e}', 'xml': xml_data}
    
    def _parse_device_list(self, root: ET.Element) -> Dict[str, List[DeviceInfo]]:
        """Parst die Geräteliste gemäß AVM-Dokumentation"""
        devices = []
        
        for device_elem in root.findall('device'):
            device = self._parse_device_element(device_elem)
            devices.append(device)
        
        return {'devices': devices}
    
    def _parse_device_element(self, device_elem: ET.Element) -> DeviceInfo:
        """Parst ein einzelnes Device-Element"""
        ain = device_elem.get('identifier', '')
        name_elem = device_elem.find('name')
        name = name_elem.text if name_elem is not None else 'Unbekannt'
        
        device = DeviceInfo(
            ain=ain,
            name=name,
            manufacturer=device_elem.get('manufacturer', ''),
            productname=device_elem.get('productname', ''),
            fwversion=device_elem.get('fwversion', ''),
            present=device_elem.get('present') == '1',
            txbusy=device_elem.get('txbusy') == '1',
            functionbitmask=int(device_elem.get('functionbitmask', '0')),
            device_type=self._get_device_type_from_mask(int(device_elem.get('functionbitmask', '0')))
        )
        
        # Funktionsspezifische Daten parsen
        device.temperature = self._parse_temperature(device_elem)
        device.thermostat = self._parse_thermostat(device_elem)
        device.switch = self._parse_switch(device_elem)
        device.powermeter = self._parse_powermeter(device_elem)
        device.battery = self._parse_battery(device_elem)
        device.alert = self._parse_alert(device_elem)
        device.button = self._parse_buttons(device_elem)
        device.simpleonoff = self._parse_simpleonoff(device_elem)
        device.levelcontrol = self._parse_levelcontrol(device_elem)
        device.colorcontrol = self._parse_colorcontrol(device_elem)
        device.blind = self._parse_blind(device_elem)
        
        return device
    
    def _get_device_type_from_mask(self, bitmask: int) -> str:
        """Bestimmt den Gerätetyp aus der Function Bitmask"""
        types = []
        if bitmask & self.FUNCTION_HKR:
            types.append('Heizkörperregler')
        if bitmask & self.FUNCTION_POWERMETER:
            types.append('Schaltsteckdose')
        if bitmask & self.FUNCTION_TEMPERATURE:
            types.append('Temperatursensor')
        if bitmask & self.FUNCTION_LIGHT:
            types.append('Lampe')
        if bitmask & self.FUNCTION_ALARM:
            types.append('Alarmsensor')
        if bitmask & self.FUNCTION_BUTTON:
            types.append('Taster')
        if bitmask & self.FUNCTION_BLIND:
            types.append('Rollladen')
        if bitmask & self.FUNCTION_HUMIDITY:
            types.append('Luftfeuchtigkeitssensor')
        
        return ', '.join(types) if types else 'Unbekannt'
    
    def _parse_temperature(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Temperatur-Daten"""
        temp_elem = device_elem.find('temperature')
        if temp_elem is not None:
            return {
                'celsius': temp_elem.get('celsius'),
                'offset': temp_elem.get('offset')
            }
        return None
    
    def _parse_thermostat(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst HKR-Daten gemäß Dokumentation"""
        hkr_elem = device_elem.find('hkr')
        if hkr_elem is not None:
            return {
                'tist': hkr_elem.findtext('tist'),
                'tsoll': hkr_elem.findtext('tsoll'),
                'komfort': hkr_elem.findtext('komfort'),
                'absenk': hkr_elem.findtext('absenk'),
                'lock': hkr_elem.findtext('lock'),
                'devicelock': hkr_elem.findtext('devicelock'),
                'errorcode': hkr_elem.findtext('errorcode'),
                'batterylow': hkr_elem.findtext('batterylow'),
                'battery': hkr_elem.findtext('battery'),
                'windowopenactiv': hkr_elem.findtext('windowopenactiv'),
                'windowopenactiveendtime': hkr_elem.findtext('windowopenactiveendtime'),
                'boostactive': hkr_elem.findtext('boostactive'),
                'boostactiveendtime': hkr_elem.findtext('boostactiveendtime'),
                'adaptiveHeatingActive': hkr_elem.findtext('adaptiveHeatingActive'),
                'adaptiveHeatingRunning': hkr_elem.findtext('adaptiveHeatingRunning'),
                'holidayactive': hkr_elem.findtext('holidayactive'),
                'summeractive': hkr_elem.findtext('summeractive'),
                'nextchange': self._parse_nextchange(hkr_elem)
            }
        return None
    
    def _parse_nextchange(self, hkr_elem: ET.Element) -> Optional[Dict]:
        """Parst nextchange Element"""
        nextchange_elem = hkr_elem.find('nextchange')
        if nextchange_elem is not None:
            return {
                'endperiod': nextchange_elem.findtext('endperiod'),
                'tchange': nextchange_elem.findtext('tchange')
            }
        return None
    
    def _parse_switch(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Switch-Daten"""
        switch_elem = device_elem.find('switch')
        if switch_elem is not None:
            return {
                'state': switch_elem.get('state'),
                'mode': switch_elem.get('mode'),
                'lock': switch_elem.get('lock'),
                'devicelock': switch_elem.get('devicelock')
            }
        return None
    
    def _parse_powermeter(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Powermeter-Daten"""
        powermeter_elem = device_elem.find('powermeter')
        if powermeter_elem is not None:
            return {
                'power': powermeter_elem.get('power'),
                'energy': powermeter_elem.get('energy'),
                'voltage': powermeter_elem.get('voltage')
            }
        return None
    
    def _parse_battery(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Battery-Daten"""
        battery_elem = device_elem.find('battery')
        if battery_elem is not None:
            return {
                'batterylow': device_elem.get('batterylow'),
                'battery': battery_elem.text
            }
        return None
    
    def _parse_alert(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Alert-Daten"""
        alert_elem = device_elem.find('alert')
        if alert_elem is not None:
            return {
                'state': alert_elem.get('state'),
                'lastalertchgtimestamp': alert_elem.get('lastalertchgtimestamp')
            }
        return None
    
    def _parse_buttons(self, device_elem: ET.Element) -> Optional[List[Dict]]:
        """Parst Button-Daten"""
        buttons = []
        for button_elem in device_elem.findall('button'):
            button = {
                'identifier': button_elem.get('identifier'),
                'id': button_elem.get('id'),
                'name': button_elem.find('name').text if button_elem.find('name') is not None else None,
                'lastpressedtimestamp': button_elem.get('lastpressedtimestamp')
            }
            buttons.append(button)
        return buttons if buttons else None
    
    def _parse_simpleonoff(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst SimpleOnOff-Daten"""
        simpleonoff_elem = device_elem.find('simpleonoff')
        if simpleonoff_elem is not None:
            return {
                'state': simpleonoff_elem.get('state')
            }
        return None
    
    def _parse_levelcontrol(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst LevelControl-Daten"""
        levelcontrol_elem = device_elem.find('levelcontrol')
        if levelcontrol_elem is not None:
            return {
                'level': levelcontrol_elem.get('level'),
                'levelpercentage': levelcontrol_elem.get('levelpercentage')
            }
        return None
    
    def _parse_colorcontrol(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst ColorControl-Daten"""
        colorcontrol_elem = device_elem.find('colorcontrol')
        if colorcontrol_elem is not None:
            return {
                'supported_modes': colorcontrol_elem.get('supported_modes'),
                'current_mode': colorcontrol_elem.get('current_mode'),
                'fullcolorsupport': colorcontrol_elem.get('fullcolorsupport'),
                'mapped': colorcontrol_elem.get('mapped'),
                'hue': colorcontrol_elem.find('hue').text if colorcontrol_elem.find('hue') is not None else None,
                'saturation': colorcontrol_elem.find('saturation').text if colorcontrol_elem.find('saturation') is not None else None,
                'unmapped_hue': colorcontrol_elem.find('unmapped_hue').text if colorcontrol_elem.find('unmapped_hue') is not None else None,
                'unmapped_saturation': colorcontrol_elem.find('unmapped_saturation').text if colorcontrol_elem.find('unmapped_saturation') is not None else None,
                'temperature': colorcontrol_elem.find('temperature').text if colorcontrol_elem.find('temperature') is not None else None
            }
        return None
    
    def _parse_blind(self, device_elem: ET.Element) -> Optional[Dict]:
        """Parst Blind-Daten"""
        blind_elem = device_elem.find('blind')
        if blind_elem is not None:
            return {
                'mode': blind_elem.get('mode'),
                'endpositionsset': blind_elem.get('endpositionsset')
            }
        return None
    
    def _parse_template_list(self, root: ET.Element) -> Dict[str, List[TemplateInfo]]:
        """Parst die Vorlagenliste gemäß Dokumentation"""
        templates = []
        
        for template_elem in root.findall('template'):
            template = self._parse_template_element(template_elem)
            templates.append(template)
        
        return {'templates': templates}
    
    def _parse_template_element(self, template_elem: ET.Element) -> TemplateInfo:
        """Parst ein einzelnes Template-Element"""
        identifier = template_elem.get('identifier', '')
        name_elem = template_elem.find('name')
        name = name_elem.text if name_elem is not None else 'Unbekannt'
        
        # Devices parsen
        devices = []
        devices_elem = template_elem.find('devices')
        if devices_elem is not None:
            for device_elem in devices_elem.findall('device'):
                device_ain = device_elem.get('identifier', '')
                if device_ain:
                    devices.append(device_ain)
        
        # ApplyMask parsen
        applymask = {}
        applymask_elem = template_elem.find('applymask')
        if applymask_elem is not None:
            for child in applymask_elem:
                applymask[child.tag] = child.text
        
        # Metadata parsen
        metadata = None
        metadata_elem = template_elem.find('metadata')
        if metadata_elem is not None and metadata_elem.text:
            try:
                metadata = json.loads(metadata_elem.text)
            except json.JSONDecodeError:
                metadata = {'raw': metadata_elem.text}
        
        # SubTemplates parsen
        sub_templates = []
        subtemplates_elem = template_elem.find('sub_templates')
        if subtemplates_elem is not None:
            for sub_elem in subtemplates_elem.findall('template'):
                sub_id = sub_elem.get('identifier', '')
                if sub_id:
                    sub_templates.append(sub_id)
        
        # Triggers parsen
        triggers = []
        triggers_elem = template_elem.find('triggers')
        if triggers_elem is not None:
            for trigger_elem in triggers_elem.findall('trigger'):
                trigger_id = trigger_elem.get('identifier', '')
                if trigger_id:
                    triggers.append(trigger_id)
        
        return TemplateInfo(
            identifier=identifier,
            id=template_elem.get('id', ''),
            name=name,
            functionbitmask=int(template_elem.get('functionbitmask', '0')),
            autocreate=template_elem.get('autocreate') == '1',
            devices=devices,
            applymask=applymask,
            metadata=metadata,
            sub_templates=sub_templates if sub_templates else None,
            triggers=triggers if triggers else None
        )
    
    def _parse_device_stats(self, root: ET.Element) -> Dict:
        """Parst Geräte-Statistiken"""
        stats = {}
        
        for stat_type in ['temperature', 'humidity', 'voltage', 'power', 'energy']:
            stat_elem = root.find(stat_type)
            if stat_elem is not None:
                stats[stat_type] = self._parse_stat_element(stat_elem)
        
        return {'stats': stats}
    
    def _parse_stat_element(self, stat_elem: ET.Element) -> Dict:
        """Parst ein einzelnes Statistik-Element"""
        stats_data = []
        stats_elems = stat_elem.findall('stats')
        
        for stats in stats_elems:
            data = {
                'count': int(stats.get('count', '0')),
                'grid': int(stats.get('grid', '0')),
                'datatime': int(stats.get('datatime', '0')),
                'values': []
            }
            
            if stats.text:
                values = stats.text.strip().split(',')
                for value in values:
                    if value.strip() == '-':
                        data['values'].append(None)
                    else:
                        try:
                            data['values'].append(float(value.strip()))
                        except ValueError:
                            data['values'].append(None)
            
            stats_data.append(data)
        
        return stats_data
    
    def _parse_trigger_list(self, root: ET.Element) -> Dict[str, List[Dict]]:
        """Parst die Trigger-Liste"""
        triggers = []
        
        for trigger_elem in root.findall('trigger'):
            name_elem = trigger_elem.find('name')
            trigger = {
                'identifier': trigger_elem.get('identifier', ''),
                'active': trigger_elem.get('active') == '1',
                'name': name_elem.text if name_elem is not None else 'Unbekannt'
            }
            triggers.append(trigger)
        
        return {'triggers': triggers}
    
    def _parse_color_defaults(self, root: ET.Element) -> Dict:
        """Parst Color Defaults"""
        defaults = {}
        
        hsdefaults_elem = root.find('hsdefaults')
        if hsdefaults_elem is not None:
            defaults['hsdefaults'] = []
            for hs_elem in hsdefaults_elem.findall('hs'):
                hs_data = {
                    'hue_index': int(hs_elem.get('hue_index', '0')),
                    'name': hs_elem.find('name').text if hs_elem.find('name') is not None else '',
                    'colors': []
                }
                
                for color_elem in hs_elem.findall('color'):
                    color_data = {
                        'sat_index': int(color_elem.get('sat_index', '0')),
                        'hue': int(color_elem.get('hue', '0')),
                        'sat': int(color_elem.get('sat', '0')),
                        'val': int(color_elem.get('val', '0'))
                    }
                    hs_data['colors'].append(color_data)
                
                defaults['hsdefaults'].append(hs_data)
        
        temperaturedefaults_elem = root.find('temperaturedefaults')
        if temperaturedefaults_elem is not None:
            defaults['temperaturedefaults'] = []
            for temp_elem in temperaturedefaults_elem.findall('temp'):
                defaults['temperaturedefaults'].append({
                    'value': int(temp_elem.get('value', '0'))
                })
        
        return defaults
    
    def _parse_single_device(self, root: ET.Element) -> Dict:
        """Parst ein einzelnes Gerät (getdeviceinfos)"""
        device_elem = root.find('device')
        if device_elem is not None:
            device = self._parse_device_element(device_elem)
            return {'device': device}
        return {'error': 'No device found'}
    
    # Legacy Login-Methoden (behalten für Kompatibilität)
    def test_credentials(self) -> bool:
        """Testet die Zugangsdaten"""
        try:
            login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
            response = self.session.get(login_url, timeout=10)
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            
            if blocktime > 0:
                logger.debug(f"BlockTime aktiv: {blocktime} Sekunden - FritzBox hat Timer gesetzt")
                time.sleep(blocktime)
                return self._try_pbkdf2_login()
            
            if challenge.startswith("2$"):
                challenge_response = self._calculate_pbkdf2_response(challenge, self.password)
            else:
                challenge_response = self._calculate_md5_response(challenge, self.password)
            
            try:
                sid = self._send_response(self.username, challenge_response)
                if sid != "0000000000000000":
                    self.sid = sid
                    return True
            except Exception:
                pass
            
            return False
                
        except Exception:
            return False
    
    def _calculate_pbkdf2_response(self, challenge: str, password: str) -> str:
        """Berechnet PBKDF2 Response korrekt gemäß AVM-Dokumentation"""
        challenge_parts = challenge.split("$")
        
        if len(challenge_parts) >= 5:
            # Format: 2$iter1$salt1$iter2$salt2
            iter1 = int(challenge_parts[1])
            salt1_hex = challenge_parts[2]
            iter2 = int(challenge_parts[3])
            salt2_hex = challenge_parts[4]
            
            # KORREKT: Hex zu Bytes konvertieren
            salt1 = bytes.fromhex(salt1_hex)
            salt2 = bytes.fromhex(salt2_hex)
            
            # Erste Runde PBKDF2: password + salt1
            hash1 = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt1, iter1)
            
            # Zweite Runde PBKDF2: hash1 + salt2  
            hash2 = hashlib.pbkdf2_hmac('sha256', hash1, salt2, iter2)
            
            # Response gemäß AVM-Dokumentation: salt2$hash2
            return f"{salt2_hex}${hash2.hex()}"
        else:
            # Fallback für altes Format
            iter1 = int(challenge_parts[1])
            salt1_hex = challenge_parts[2]
            iter2 = int(challenge_parts[3])
            salt2_hex = challenge_parts[4]
            
            salt1 = bytes.fromhex(salt1_hex)
            salt2 = bytes.fromhex(salt2_hex)
            
            hash1 = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt1, iter1)
            hash2 = hashlib.pbkdf2_hmac('sha256', hash1, salt2, iter2)
            
            return f"{salt2_hex}${hash2.hex()}"
    
    def _calculate_md5_response(self, challenge: str, password: str) -> str:
        """Berechnet MD5 Response"""
        response = challenge + "-" + password
        response = response.encode("utf_16_le")
        md5_sum = hashlib.md5()
        md5_sum.update(response)
        response = challenge + "-" + md5_sum.hexdigest()
        return response
    
    def _send_response(self, username: str, challenge_response: str) -> str:
        """Sendet Login-Response"""
        login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
        
        post_data_dict = {"username": username, "response": challenge_response}
        post_data = urllib.parse.urlencode(post_data_dict).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        http_request = urllib.request.Request(login_url, post_data, headers)
        http_response = urllib.request.urlopen(http_request)
        
        xml = ET.fromstring(http_response.read())
        return xml.find("SID").text
    
    def login(self) -> bool:
        """Führt Login durch - nutzt AHA-Schnittstelle für maximale Kompatibilität"""
        return self._login_aha_only()
    
    def _login_aha_only(self) -> bool:
        """Login nur über AHA-Schnittstelle mit detailliertem Debug-Logging"""
        try:
            logger.debug("=== AHA-Login gestartet ===")
            logger.debug(f"Host: {self.host}:{self.port}")
            logger.debug(f"Username: {self.username}")
            
            # Zuerst einfache Verbindungstest
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result != 0:
                logger.debug(f"Verbindung zu {self.host}:{self.port} fehlgeschlagen: {result}")
                logger.error("FritzBox nicht erreichbar - Netzwerkverbindung prüfen!")
                return False
            
            logger.debug(f"Verbindung zu {self.host}:{self.port} erfolgreich")
            
            # Zuerst versuchen, ob einfache AHA-Schnittstelle funktioniert
            login_url = f"http://{self.host}:{self.port}/login_sid.lua"
            logger.debug(f"Versuche einfachen Login: {login_url}")
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            sid = xml.find("SID").text
            
            if sid and sid != "0000000000000000":
                self.sid = sid
                logger.debug(f"Einfacher AHA-Login erfolgreich - SID: {sid}")
                return True
            
            # Wenn einfacher Login fehlschlägt, Challenge-Response versuchen
            logger.debug("Einfacher AHA-Login fehlgeschlagen, versuche Challenge-Response...")
            
            # Challenge-Response mit version=2 (PBKDF2) versuchen
            challenge_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
            logger.debug(f"Versuche Challenge-Response: {challenge_url}")
            response = self.session.get(challenge_url, timeout=30)
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            
            logger.debug(f"Challenge erhalten: {challenge}")
            logger.debug(f"BlockTime: {blocktime}")
            
            if blocktime > 0:
                logger.debug(f"BlockTime aktiv: {blocktime} Sekunden - warte...")
                time.sleep(blocktime)
                # Erneut versuchen ohne BlockTime-Check
                return self._login_aha_only()
            
            # Einfache Challenge-Response (ohne komplexe PBKDF2 Berechnung)
            if challenge.startswith("2$"):
                logger.debug("Nutze PBKDF2 Challenge-Response")
                # KORREKTE PBKDF2 Berechnung verwenden
                challenge_response = self._calculate_pbkdf2_response(challenge, self.password)
            else:
                logger.debug("Nutze MD5 Challenge-Response")
                challenge_response = self._calculate_md5_response(challenge, self.password)
            
            logger.debug(f"Berechnete Response: {challenge_response}")
            
            # KEINE URL-Encodierung für die Response - das führt zu Fehlern!
            post_data_dict = {"username": self.username, "response": challenge_response}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            logger.debug(f"Sende POST mit Username: {self.username}")
            logger.debug(f"Response-Length: {len(challenge_response)} Zeichen")
            
            response = self.session.post(challenge_url, data=post_data_dict, headers=headers, timeout=30)
            response.raise_for_status()
            
            xml = ET.fromstring(response.text)
            sid = xml.find("SID").text
            
            logger.debug(f"Login-Antwort SID: {sid}")
            
            if sid and sid != "0000000000000000":
                self.sid = sid
                logger.debug(f"AHA Challenge-Response Login erfolgreich - SID: {sid}")
                # Cache bei neuem Login löschen
                with self._cache_lock:
                    self._cache_timestamp.clear()
                return True
            else:
                logger.debug(f"AHA Challenge-Response Login fehlgeschlagen - SID: {sid}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Netzwerkfehler bei AHA-Login: {e}")
            logger.error("Netzwerkverbindungsproblem - prüfen Sie Verbindung zur FritzBox")
            return False
        except Exception as e:
            logger.debug(f"Unerwarteter Fehler bei AHA-Login: {e}")
            logger.error("Unerwarteter Fehler - prüfen Sie Logs und versuchen Sie erneut")
            return False
    
    def _calculate_simple_pbkdf2_response(self, challenge: str, password: str) -> str:
        """Vereinfachte PBKDF2 Response - KORRIGIERT"""
        try:
            # Extrahiere Challenge-Parameter
            parts = challenge.split('$')
            if len(parts) < 5:
                # Fallback zu MD5 bei ungültiger Challenge
                return self._calculate_md5_response(challenge, password)
            
            # KORREKT: Hex zu Bytes konvertieren
            iter1 = int(parts[1])
            salt1_hex = parts[2]
            iter2 = int(parts[3])
            salt2_hex = parts[4]
            
            salt1 = bytes.fromhex(salt1_hex)
            salt2 = bytes.fromhex(salt2_hex)
            
            # Erste Runde: Password + salt1
            hash1 = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt1, iter1)
            
            # Zweite Runde: hash1 + salt2
            hash2 = hashlib.pbkdf2_hmac('sha256', hash1, salt2, iter2)
            
            # Response gemäß AVM-Dokumentation: salt2$hash2
            return f"{salt2_hex}${hash2.hex()}"
            
        except Exception as e:
            logger.debug(f"Vereinfachte PBKDF2 Berechnung fehlgeschlagen: {e}")
            # Fallback zu MD5
            return self._calculate_md5_response(challenge, password)
    
    def _try_pbkdf2_login(self) -> bool:
        """Versucht PBKDF2 Login (version=2)"""
        try:
            login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            
            if blocktime > 0:
                logger.debug(f"BlockTime aktiv: {blocktime} Sekunden - FritzBox hat Sekundensperre aktiviert")
                logger.debug(f"FritzBox blockiert Login-Versuche für {blocktime} Sekunden")
                logger.debug(f"Warte auf Ende der Sperre und versuche erneut...")
                time.sleep(blocktime)
                # Nach erfolgreichem PBKDF2 Login, True zurückgeben (nicht _login_aha_only)
            if sid and sid != "0000000000000000":
                self.sid = sid
                logger.debug(f"PBKDF2 Login erfolgreich, SID: {sid}")
                # Cache bei neuem Login löschen
                with self._cache_lock:
                    self._cache_timestamp.clear()
                return True
            else:
                logger.debug(f"PBKDF2 Login fehlgeschlagen, SID: {sid}")
                return False
            
            if challenge.startswith("2$"):
                challenge_response = self._calculate_pbkdf2_response(challenge, self.password)
            else:
                challenge_response = self._calculate_md5_response(challenge, self.password)
            
            encoded_username = urllib.parse.quote_plus(self.username, encoding='utf-8')
            encoded_response = urllib.parse.quote_plus(challenge_response, encoding='utf-8')
            
            post_data_dict = {"username": encoded_username, "response": encoded_response}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = self.session.post(login_url, data=post_data_dict, headers=headers, timeout=30)
            response.raise_for_status()
            
            xml = ET.fromstring(response.text)
            sid = xml.find("SID").text
            
            if sid and sid != "0000000000000000":
                self.sid = sid
                logger.debug(f"PBKDF2 Login erfolgreich, SID: {sid}")
                # Cache bei neuem Login löschen
                with self._cache_lock:
                    self._cache_timestamp.clear()
                return True
            else:
                logger.debug(f"PBKDF2 Login fehlgeschlagen, SID: {sid}")
                return False
                
        except Exception as e:
            logger.debug(f"PBKDF2 Login Fehler: {e}")
            return False
    
    def _try_md5_login(self) -> bool:
        """Versucht MD5 Login (version=1)"""
        try:
            login_url = f"http://{self.host}:{self.port}/login_sid.lua"
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            
            if blocktime > 0:
                logger.debug(f"BlockTime aktiv: {blocktime} Sekunden - FritzBox hat Sekundensperre aktiviert")
                logger.info(f"FritzBox blockiert Login-Versuche für {blocktime} Sekunden")
                logger.info(f"Warte auf Ende der Sperre und versuche erneut...")
                time.sleep(blocktime)
                return self._try_md5_login()
            
            # MD5 Response berechnen
            challenge_response = self._calculate_md5_response(challenge, self.password)
            
            encoded_username = urllib.parse.quote_plus(self.username, encoding='utf-8')
            encoded_response = urllib.parse.quote_plus(challenge_response, encoding='utf-8')
            
            post_data_dict = {"username": encoded_username, "response": encoded_response}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = self.session.post(login_url, data=post_data_dict, headers=headers, timeout=30)
            response.raise_for_status()
            
            xml = ET.fromstring(response.text)
            sid = xml.find("SID").text
            
            if sid and sid != "0000000000000000":
                self.sid = sid
                logger.debug(f"MD5 Login erfolgreich, SID: {sid}")
                # Cache bei neuem Login löschen
                with self._cache_lock:
                    self._cache_timestamp.clear()
                return True
            else:
                logger.debug(f"MD5 Login fehlgeschlagen, SID: {sid}")
                return False
                
        except Exception as e:
            logger.debug(f"MD5 Login Fehler: {e}")
            return False
    
    # Optimierte High-Level API-Methoden
    def get_devices(self, use_cache: bool = True) -> List[DeviceInfo]:
        """Holt alle Geräte mit Caching"""
        result = self._execute_aha_command('getdevicelistinfos', use_cache=use_cache)
        if result and 'devices' in result:
            return result['devices']
        return []
    
    def get_templates(self, use_cache: bool = True) -> List[TemplateInfo]:
        """Holt alle Vorlagen mit Caching"""
        result = self._execute_aha_command('gettemplatelistinfos', use_cache=use_cache)
        if result and 'templates' in result:
            return result['templates']
        return []
    
    def get_template_list_aha(self) -> Optional[str]:
        """Legacy-Methode für Kompatibilität - gibt rohe XML-Antwort zurück"""
        result = self._execute_aha_command('gettemplatelistinfos', use_cache=False)
        if result and 'templates' in result:
            # Konvertiere zurück zu XML für Legacy-Kompatibilität
            return self._templates_to_xml(result['templates'])
        return None
    
    def _templates_to_xml(self, templates: List[TemplateInfo]) -> str:
        """Konvertiert TemplateInfo-Liste zurück zu XML für Legacy-Kompatibilität"""
        xml_lines = ['<templatelist>']
        for template in templates:
            xml_lines.append(f'  <template identifier="{template.identifier}" id="{template.id}" functionbitmask="{template.functionbitmask}" autocreate="1">')
            xml_lines.append(f'    <name>{template.name}</name>')
            if template.devices:
                xml_lines.append('    <devices>')
                for device_ain in template.devices:
                    xml_lines.append(f'      <device identifier="{device_ain}" />')
                xml_lines.append('    </devices>')
            if template.applymask:
                xml_lines.append('    <applymask>')
                for key, value in template.applymask.items():
                    xml_lines.append(f'      <{key}>{value}</{key}>')
                xml_lines.append('    </applymask>')
            xml_lines.append('  </template>')
        xml_lines.append('</templatelist>')
        return '\n'.join(xml_lines)
    
    def parse_template_xml(self, xml_string: str) -> List[Dict]:
        """Legacy-Methode - parst XML und gibt einfache Dict-Liste zurück"""
        try:
            root = ET.fromstring(xml_string)
            templates = []
            
            for template_elem in root.findall('template'):
                template_info = self._parse_template_element(template_elem)
                template_dict = {
                    'id': template_info.id,
                    'identifier': template_info.identifier,
                    'name': template_info.name,
                    'functionbitmask': template_info.functionbitmask,
                    'devices': template_info.devices,
                    'applymask': template_info.applymask
                }
                templates.append(template_dict)
            
            return templates
        except ET.ParseError as e:
            logger.debug(f"XML Parse Error in parse_template_xml: {e}")
            return []
    
    def get_device_by_ain(self, ain: str, use_cache: bool = True) -> Optional[DeviceInfo]:
        """Holt ein spezifisches Gerät per AIN"""
        devices = self.get_devices(use_cache=use_cache)
        for device in devices:
            if device.ain == ain:
                return device
        return None
    
    def get_template_by_identifier(self, identifier: str, use_cache: bool = True) -> Optional[TemplateInfo]:
        """Holt eine spezifische Vorlage per Identifier"""
        templates = self.get_templates(use_cache=use_cache)
        for template in templates:
            if template.identifier == identifier:
                return template
        return None
    
    def get_template_by_name(self, name: str, use_cache: bool = True) -> Optional[TemplateInfo]:
        """Holt eine spezifische Vorlage per Name"""
        templates = self.get_templates(use_cache=use_cache)
        for template in templates:
            if template.name == name:
                return template
        return None
    
    def get_template_by_id(self, template_id: str, use_cache: bool = True) -> Optional[TemplateInfo]:
        """Holt eine spezifische Vorlage per ID"""
        templates = self.get_templates(use_cache=use_cache)
        # Normalize template_id by stripping whitespace
        normalized_id = str(template_id).strip()
        for template in templates:
            # Normalize stored template.id as well for robust comparison
            stored_id = str(template.id).strip()
            if stored_id == normalized_id:
                return template
        return None
    
    def get_templates_only(self, use_cache: bool = True) -> List[TemplateInfo]:
        """Holt nur echte Vorlagen (keine Szenarien oder Auto-Create)"""
        templates = self.get_templates(use_cache=use_cache)
        return [t for t in templates if t.is_template]
    
    def get_scenarios_only(self, use_cache: bool = True) -> List[TemplateInfo]:
        """Holt nur Szenarien (Vorlagen mit Sub-Templates oder Triggern)"""
        templates = self.get_templates(use_cache=use_cache)
        return [t for t in templates if t.is_scenario]
    
    def get_vacation_scenarios(self, use_cache: bool = True) -> List[TemplateInfo]:
        """Holt nur Urlaubsszenarien"""
        templates = self.get_templates(use_cache=use_cache)
        return [t for t in templates if t.is_vacation_scenario]
    
    def classify_automation_type(self, template: TemplateInfo) -> str:
        """Klassifiziert den Typ der Automatisierung"""
        if template.is_vacation_scenario:
            return "vacation_scenario"
        elif template.is_scenario:
            return "scenario"
        elif template.is_template:
            return "template"
        elif template.autocreate:
            return "auto_template"
        else:
            return "unknown"
    
    def set_temperature(self, ain: str, temperature: float) -> bool:
        """Setzt HKR-Solltemperatur gemäß Dokumentation"""
        temp_value = int(temperature * 2)  # 0.5°C Schritte
        if temp_value < 16 or temp_value > 56:
            return False
        
        result = self._execute_aha_command('sethkrtsoll', ain=ain, param=str(temp_value))
        return result is not None
    
    def set_window_open_mode(self, ain: str, end_timestamp: int) -> bool:
        """Setzt Fenster-Offen-Modus gemäß Dokumentation"""
        logger.info(f"Setze Fenster-Offen-Modus für AIN {ain} mit Timestamp {end_timestamp}")
        logger.info(f"Endzeit: {datetime.fromtimestamp(end_timestamp)}")
        
        result = self._execute_aha_command('sethkrwindowopen', ain=ain, endtimestamp=str(end_timestamp))
        logger.info(f"AHA-Kommando Ergebnis: {result}")
        
        return result is not None
    
    def disable_window_open_mode(self, ain: str) -> bool:
        """Deaktiviert Fenster-Offen-Modus"""
        return self.set_window_open_mode(ain, 0)
    
    def apply_template(self, template_identifier: str) -> bool:
        """Wendet Vorlage an gemäß Dokumentation"""
        result = self._execute_aha_command('applytemplate', ain=template_identifier)
        return result is not None
    
    def set_switch_on(self, ain: str) -> bool:
        """Schaltet Gerät ein"""
        result = self._execute_aha_command('setswitchon', ain=ain)
        return result is not None
    
    def set_switch_off(self, ain: str) -> bool:
        """Schaltet Gerät aus"""
        result = self._execute_aha_command('setswitchoff', ain=ain)
        return result is not None
    
    def toggle_switch(self, ain: str) -> bool:
        """Toggelt Schaltzustand"""
        result = self._execute_aha_command('setswitchtoggle', ain=ain)
        return result is not None
    
    def get_device_stats(self, ain: str) -> Optional[Dict]:
        """Holt Geräte-Statistiken"""
        return self._execute_aha_command('getbasicdevicestats', ain=ain)
    
    def get_temperature(self, ain: str) -> Optional[float]:
        """Holt aktuelle Temperatur"""
        result = self._execute_aha_command('gettemperature', ain=ain)
        if result and result != 'inval':
            try:
                return float(result) / 10  # 0.1°C
            except ValueError:
                return None
        return None
    
    def get_hkr_target_temp(self, ain: str) -> Optional[float]:
        """Holt HKR-Solltemperatur"""
        result = self._execute_aha_command('gethkrtsoll', ain=ain)
        if result and result not in ['inval', '253', '254']:
            try:
                return float(result) / 2  # 0.5°C
            except ValueError:
                return None
        return None
    
    def clear_cache(self) -> None:
        """Löscht alle Caches"""
        with self._cache_lock:
            self._device_cache.clear()
            self._template_cache.clear()
            self._cache_timestamp.clear()
    
    def login_with_fallback(self) -> bool:
        """Führt Login durch mit MD5 und PBKDF2 Fallback (nur für Notfälle)"""
        try:
            # Zuerst einfache Verbindungstest
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result != 0:
                logger.debug(f"Verbindung zu {self.host}:{self.port} fehlgeschlagen: {result}")
                logger.error("FritzBox nicht erreichbar - Netzwerkverbindung prüfen!")
                return False
            
            logger.debug(f"Verbindung zu {self.host}:{self.port} erfolgreich")
            
            # Zuerst PBKDF2 (version=2) versuchen
            if self._try_pbkdf2_login():
                return True
            
            logger.debug("PBKDF2 Login fehlgeschlagen, versuche MD5...")
            # Fallback zu MD5 (version=1)
            if self._try_md5_login():
                return True
            
            # Alle Login-Methoden fehlgeschlagen
            logger.error("Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
            logger.error("MÖGLICHE URSACHEN:")
            logger.error("  1. Falsche Zugangsdaten (Benutzername/Passwort)")
            logger.error("  2. FritzBox hat Sekundensperre aktiv (warten Sie einige Minuten)")
            logger.error("  3. Netzwerkverbindungsprobleme")
            logger.error("  4. FritzBox antwortet nicht (Neustart prüfen)")
            return False
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Netzwerkfehler bei login: {e}")
            logger.error("Netzwerkverbindungsproblem - prüfen Sie Verbindung zur FritzBox")
            return False
        except Exception as e:
            logger.debug(f"Unerwarteter Fehler bei login: {e}")
            logger.error("Unerwarteter Fehler - prüfen Sie Logs und versuchen Sie erneut")
            return False
