#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import xml.etree.ElementTree as ET
import hashlib
import time
import urllib.parse
import urllib.request
from lib.config import Config

class LoginState:
    def __init__(self, challenge: str, blocktime: int):
        self.challenge = challenge
        self.blocktime = blocktime
        self.is_pbkdf2 = challenge.startswith("2$")

class FritzBoxAPI:
    def __init__(self):
        self.config = Config()
        self.fritz_config = self.config.get_fritzbox_config()
        self.host = self.fritz_config.get('host', '192.168.178.1')
        self.port = self.fritz_config.get('port', 80)
        self.username = self.fritz_config.get('username', '')
        self.password = self.fritz_config.get('password', '')
        self.session = requests.Session()
        self.sid = None
        
    
    def test_credentials(self):
        """Testet die Zugangsdaten mit einem einfachen Login"""
        # Session zurücksetzen
        self.session = requests.Session()
        
        # Test mit version=2 (PBKDF2) wie im AVM-Beispiel
        try:
            login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
            response = self.session.get(login_url, timeout=10)
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            
            if blocktime > 0:
                return False
            
            # Challenge-Response berechnen - IMMER mit version=2 prüfen
            if challenge.startswith("2$"):
                challenge_response = self.calculate_pbkdf2_response(challenge, self.password)
            else:
                challenge_response = self.calculate_md5_response(challenge, self.password)
            
            # Login versuchen
            try:
                sid = self.send_response(self.username, challenge_response)
                
                if sid != "0000000000000000":
                    self.sid = sid
                    return True
                    
            except Exception as e:
                pass
            
            return False
                
        except Exception as e:
            return False
    
    def get_login_state(self):
        """ Get login state from FRITZ!Box using login_sid.lua?version=2 """
        login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
        
        try:
            response = self.session.get(login_url, timeout=10)
            response.raise_for_status()
            xml = ET.fromstring(response.text)
            challenge = xml.find("Challenge").text
            blocktime = int(xml.find("BlockTime").text)
            return LoginState(challenge, blocktime)
        except requests.exceptions.RequestException as e:
            raise Exception(f"Verbindungsfehler: {str(e)}")
        except ET.ParseError as e:
            raise Exception(f"XML Parse Fehler: {str(e)} - Response: {response.text[:100]}")
        except Exception as e:
            raise Exception(f"Fehler beim Abrufen des Login-Status: {str(e)}")
    
    def calculate_pbkdf2_response(self, challenge: str, password: str) -> str:
        """ Calculate the response for a given challenge via PBKDF2 """
        challenge_parts = challenge.split("$")
        # Extract all necessary values encoded into the challenge
        iter1 = int(challenge_parts[1])
        salt1 = bytes.fromhex(challenge_parts[2])
        iter2 = int(challenge_parts[3])
        salt2 = bytes.fromhex(challenge_parts[4])
        # Hash twice, once with static salt...
        hash1 = hashlib.pbkdf2_hmac("sha256", password.encode('utf-8'), salt1, iter1)
        # Once with dynamic salt.
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
        return f"{challenge_parts[4]}${hash2.hex()}"
    
    def calculate_md5_response(self, challenge: str, password: str) -> str:
        """ Calculate the response for a challenge using legacy MD5 - AVM官方实现 """
        response = challenge + "-" + password
        # the legacy response needs utf_16_le encoding
        response = response.encode("utf_16_le")
        md5_sum = hashlib.md5()
        md5_sum.update(response)
        response = challenge + "-" + md5_sum.hexdigest()
        return response
    
    def get_config_info(self):
        """Gibt Konfigurationsinformationen für Debugging zurück"""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password_set': bool(self.password),
            'config_keys': list(self.fritz_config.keys()) if self.fritz_config else []
        }
    
    def login_tr064(self):
        """Login über TR-064 API für FRITZ!OS 7.57+"""
        try:
            # TR-064 Login URL für neuere FritzBox-Versionen
            login_url = f"http://{self.host}:49000/tr64desc.xml"
            
            print(f"DEBUG: Prüfe TR-064 Verfügbarkeit mit: {login_url}")
            response = self.session.get(login_url, timeout=30)
            
            if response.status_code == 200:
                print(f"DEBUG: TR-064 verfügbar für FRITZ!OS 7.57")
                
                # Jetzt eigentlichen Login durchführen mit Challenge-Response
                login_sid_url = f"http://{self.host}:49000/login_sid.lua"
                
                # Zuerst Challenge holen
                challenge_response = self.session.get(f"http://{self.host}:49000/login_sid.lua", timeout=30)
                if challenge_response.status_code == 200:
                    xml = ET.fromstring(challenge_response.text)
                    challenge = xml.find("Challenge").text
                    
                    # Challenge-Response berechnen
                    if challenge.startswith("2$"):
                        response_value = self.calculate_pbkdf2_response(challenge, self.password)
                    else:
                        response_value = self.calculate_md5_response(challenge, self.password)
                    
                    params = {
                        'username': self.username,
                        'response': response_value
                    }
                    
                    print(f"DEBUG: Führe TR-064 Login durch mit: {login_sid_url}")
                    login_response = self.session.post(login_sid_url, data=params, timeout=30)
                    
                    if login_response.status_code == 200:
                        xml = ET.fromstring(login_response.text)
                        sid = xml.find("SID").text
                        
                        if sid and sid != "0000000000000000":
                            self.sid = sid
                            print(f"DEBUG: TR-064 Login erfolgreich, SID: {sid}")
                            return True
                        else:
                            print(f"DEBUG: TR-064 Login fehlgeschlagen: {sid}")
                            return False
                    else:
                        print(f"DEBUG: TR-064 Login POST fehlgeschlagen: {login_response.status_code}")
                        return False
                else:
                    print(f"DEBUG: TR-064 Challenge holen fehlgeschlagen: {challenge_response.status_code}")
                    return False
            else:
                print(f"DEBUG: TR-064 nicht verfügbar, Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"DEBUG: TR-064 Fehler: {str(e)}")
            return False
    
    def get_devices_tr064(self):
        """Geräte über TR-064 API für FRITZ!OS 7.57+ abrufen"""
        try:
            # Methode 1: AVM Webservice API auf Port 49000
            device_url = f"http://{self.host}:49000/webservices/homeautoswitch.lua"
            
            params = {
                'switchcmd': 'getdevicelistinfos',
                'sid': '0000000000000000'
            }
            
            print(f"DEBUG: Rufe Geräte über AVM Webservice API für FRITZ!OS 7.57 ab...")
            response = self.session.get(device_url, params=params, timeout=30)
            
            if response.status_code == 200:
                print(f"DEBUG: AVM Webservice Response erhalten: {response.text[:200]}...")
                return self.parse_avm_devices(response.text)
            else:
                print(f"DEBUG: AVM Webservice Status: {response.status_code}")
            
            # Methode 2: Original HomeAutomation API auf Port 80 ohne Login
            device_url = f"http://{self.host}:80/webservices/homeautoswitch.lua"
            
            print(f"DEBUG: Versuche Original HomeAutomation API auf Port 80 ohne Login...")
            response = self.session.get(device_url, params=params, timeout=30)
            
            if response.status_code == 200:
                print(f"DEBUG: Original API Response erhalten: {response.text[:200]}...")
                return self.parse_avm_devices(response.text)
            else:
                print(f"DEBUG: Original API Status: {response.status_code}")
                # Versuche alternative Methode
                return self.get_devices_tr064_alternative()
                
        except Exception as e:
            print(f"DEBUG: HomeAutomation API Fehler: {str(e)}")
            return []
    
    def parse_avm_devices(self, xml_data):
        """AVM Webservice Geräte-XML parsen"""
        try:
            root = ET.fromstring(xml_data)
            devices = []
            
            # AVM Webservice hat die gleiche Struktur wie die Original API
            for device in root.findall('device'):
                device_info = {
                    'ain': device.get('identifier'),
                    'name': device.get('name'),
                    'manufacturer': device.get('manufacturer'),
                    'productname': device.get('productname'),
                    'fwversion': device.get('fwversion'),
                    'present': device.get('present') == '1',
                    'txbusy': device.get('txbusy') == '1'
                }
                
                # Thermostat-spezifische Informationen
                temp = device.find('temperature')
                if temp is not None:
                    device_info['temperature'] = {
                        'celsius': temp.get('celsius'),
                        'offset': temp.get('offset')
                    }
                
                hkr = device.find('hkr')
                if hkr is not None:
                    device_info['thermostat'] = {
                        'tist': hkr.get('tist'),  # Ist-Temperatur
                        'tsoll': hkr.get('tsoll'),  # Soll-Temperatur
                        'komfort': hkr.get('komfort'),
                        'absenk': hkr.get('absenk'),
                        'lock': hkr.get('lock'),
                        'devicelock': hkr.get('devicelock'),
                        'errorcode': hkr.get('errorcode'),
                        'batterylow': hkr.get('batterylow')
                    }
                
                devices.append(device_info)
            
            return devices
            
        except Exception as e:
            print(f"DEBUG: AVM Webservice Parse-Fehler: {str(e)}")
            return []
    
    def get_devices_tr064_alternative(self):
        """Alternative Methode für Geräteabruf bei FRITZ!OS 7.57+"""
        try:
            # Alternative URL für neuere FritzBoxen
            device_url = f"http://{self.host}:49000/upnp/control/wancommonifconfig1"
            
            soap_headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '"urn:dslforum-org:service:WANCommonIFConfig:1#GetTotalBytesReceived"'
            }
            
            soap_body = '''<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:GetTotalBytesReceived xmlns:u="urn:dslforum-org:service:WANCommonIFConfig:1"/>
</s:Body>
</s:Envelope>'''
            
            print(f"DEBUG: Versuche alternative TR-064 Methode...")
            response = self.session.post(device_url, data=soap_body, headers=soap_headers, timeout=30)
            
            if response.status_code == 200:
                print(f"DEBUG: Alternative TR-064 Methode funktioniert")
                # Hier könnten wir versuchen, über eine andere API die Geräte zu bekommen
                return []
            else:
                print(f"DEBUG: Alternative TR-064 Methode fehlgeschlagen: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"DEBUG: Alternative TR-064 Fehler: {str(e)}")
            return []
    
    def parse_tr064_devices(self, xml_data):
        """TR-064 Geräte-XML parsen"""
        try:
            root = ET.fromstring(xml_data)
            devices = []
            
            # TR-064 hat eine andere XML-Struktur
            for device in root.findall('.//device'):
                device_info = {
                    'ain': device.get('id', ''),
                    'name': device.get('name', 'Unbekannt'),
                    'manufacturer': device.get('manufacturer', ''),
                    'present': device.get('present', '0') == '1'
                }
                
                # Temperatur-Daten suchen
                temp_elem = device.find('.//temperature')
                if temp_elem is not None:
                    device_info['temperature'] = {
                        'celsius': temp_elem.get('celsius', '0'),
                        'offset': temp_elem.get('offset', '0')
                    }
                
                # Thermostat-Daten suchen
                hkr_elem = device.find('.//hkr')
                if hkr_elem is not None:
                    device_info['thermostat'] = {
                        'tist': hkr_elem.get('tist', '0'),
                        'tsoll': hkr_elem.get('tsoll', '0'),
                        'komfort': hkr_elem.get('komfort', '0'),
                        'absenk': hkr_elem.get('absenk', '0'),
                        'batterylow': hkr_elem.get('batterylow', '0')
                    }
                
                devices.append(device_info)
            
            return devices
            
        except Exception as e:
            print(f"DEBUG: TR-064 Parse-Fehler: {str(e)}")
            return []
    
    def login(self):
        """Meldet sich an der FritzBox an für FRITZ!OS 7.57"""
        # Für FRITZ!OS 7.57 ist eine Anmeldung erforderlich
        # Nur erreichbare Endpoints basierend auf Connection-Test verwenden
        working_endpoints = self.test_connection()
        
        # Baue Login-URLs basierend auf erreichbaren Endpoints
        endpoints = []
        for endpoint in working_endpoints:
            if "https://" in endpoint:
                endpoints.extend([
                    f"{endpoint}/login_sid.lua?version=2",
                    f"{endpoint}/login_sid.lua"
                ])
            else:
                endpoints.extend([
                    f"{endpoint}/login_sid.lua?version=2",
                    f"{endpoint}/login_sid.lua"
                ])
        
        # Fallback zu Standard-Endpoints falls keine gefunden
        if not endpoints:
            endpoints = [
                f"http://{self.host}:80/login_sid.lua?version=2",
                f"http://{self.host}:80/login_sid.lua"
            ]
        
        for login_url in endpoints:
            try:
                response = self.session.get(login_url, timeout=30, verify=False)
                response.raise_for_status()
                xml = ET.fromstring(response.text)
                challenge = xml.find("Challenge").text
                blocktime = int(xml.find("BlockTime").text)
                
                if blocktime > 0:
                    time.sleep(blocktime)
                    continue
                
                # Für FRITZ!OS 7.57 wird oft PBKDF2 verwendet
                if challenge.startswith("2$"):
                    challenge_response = self.calculate_pbkdf2_response(challenge, self.password)
                else:
                    challenge_response = self.calculate_md5_response(challenge, self.password)
                
                # Username und Response für URL-encoding vorbereiten
                encoded_username = urllib.parse.quote_plus(self.username, encoding='utf-8')
                encoded_response = urllib.parse.quote_plus(challenge_response, encoding='utf-8')
                
                post_data_dict = {"username": encoded_username, "response": encoded_response}
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                
                response = self.session.post(login_url, data=post_data_dict, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                
                xml = ET.fromstring(response.text)
                sid = xml.find("SID").text
                
                if sid != "0000000000000000":
                    self.sid = sid
                    return True
                else:
                    continue
                    
            except Exception as e:
                continue
        
        raise Exception("Alle Login-Methoden fehlgeschlagen - überprüfen Sie Zugangsdaten und Erreichbarkeit")
    
    def send_response(self, username: str, challenge_response: str) -> str:
        """ Send the response and return the parsed sid. raises an Exception on error - AVM官方实现 """
        login_url = f"http://{self.host}:{self.port}/login_sid.lua?version=2"
        
        # Build response params - AVM官方方式
        post_data_dict = {"username": username, "response": challenge_response}
        post_data = urllib.parse.urlencode(post_data_dict).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # Send response - AVM官方方式
        http_request = urllib.request.Request(login_url, post_data, headers)
        http_response = urllib.request.urlopen(http_request)
        
        # Parse SID from resulting XML.
        xml = ET.fromstring(http_response.read())
        return xml.find("SID").text
    
    def get_devices_aha(self):
        """Geräte über AHA-Interface (AHAI) für FRITZ!OS 7.57+ abrufen"""
        try:
            # AHA-Interface URL - funktioniert oft ohne Login auf neueren FritzBoxen
            aha_url = f"http://{self.host}:49000/aha_dev_info.xml"
            
            print(f"DEBUG: Versuche AHA-Interface: {aha_url}")
            response = self.session.get(aha_url, timeout=30)
            
            if response.status_code == 200:
                print(f"DEBUG: AHA-Interface Response erhalten: {response.text[:200]}...")
                return self.parse_aha_devices(response.text)
            else:
                print(f"DEBUG: AHA-Interface Status: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"DEBUG: AHA-Interface Fehler: {str(e)}")
            return []
    
    def parse_aha_devices(self, xml_data):
        """AHA-Interface Geräte-XML parsen"""
        try:
            root = ET.fromstring(xml_data)
            devices = []
            
            # AHA-Interface hat eine andere XML-Struktur
            for device in root.findall('.//device'):
                device_info = {
                    'ain': device.get('id', device.get('identifier', '')),
                    'name': device.get('name', 'Unbekannt'),
                    'manufacturer': device.get('manufacturer', 'AVM'),
                    'productname': device.get('productname', ''),
                    'fwversion': device.get('fwversion', ''),
                    'present': device.get('present', '1') == '1',
                    'function': device.get('function', '')
                }
                
                # Temperatur-Daten suchen
                temp_elem = device.find('.//temperature')
                if temp_elem is not None:
                    device_info['temperature'] = {
                        'celsius': temp_elem.get('celsius', '0'),
                        'offset': temp_elem.get('offset', '0')
                    }
                
                # Thermostat-Daten suchen
                hkr_elem = device.find('.//hkr')
                if hkr_elem is not None:
                    device_info['thermostat'] = {
                        'tist': hkr_elem.get('tist', '0'),
                        'tsoll': hkr_elem.get('tsoll', '0'),
                        'komfort': hkr_elem.get('komfort', '0'),
                        'absenk': hkr_elem.get('absenk', '0'),
                        'batterylow': hkr_elem.get('batterylow', '0')
                    }
                
                # PowerMeter-Daten suchen
                power_elem = device.find('.//powermeter')
                if power_elem is not None:
                    device_info['powermeter'] = {
                        'power': power_elem.get('power', '0'),
                        'energy': power_elem.get('energy', '0'),
                        'voltage': power_elem.get('voltage', '0')
                    }
                
                devices.append(device_info)
            
            return devices
            
        except Exception as e:
            print(f"DEBUG: AHA-Interface Parse-Fehler: {str(e)}")
            return []
    
    def test_connection(self):
        """Testet verschiedene Ports und Endpunkte der FritzBox"""
        ports_to_test = [80, 443, 49000]
        working_endpoints = []
        
        for port in ports_to_test:
            try:
                # Teste basic connectivity
                test_url = f"http://{self.host}:{port}/"
                response = self.session.get(test_url, timeout=5)
                if response.status_code in [200, 302]:
                    working_endpoints.append(f"http://{self.host}:{port}")
                
                # Teste HTTPS
                if port == 443:
                    https_url = f"https://{self.host}:{port}/"
                    response = self.session.get(https_url, timeout=5, verify=False)
                    if response.status_code in [200, 302]:
                        working_endpoints.append(f"https://{self.host}:{port}")
                        
            except Exception as e:
                pass
        
        return working_endpoints
    
    def get_devices(self):
        """Ruft alle Geräte von der FritzBox ab"""
        # Login mit den konfigurierten Zugangsdaten
        if not self.test_credentials():
            return []
        
        # Geräte über HomeAutomation API abrufen
        device_list_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua?sid={self.sid}&switchcmd=getdevicelistinfos"
        
        try:
            response = self.session.get(device_list_url, timeout=30)
            response.raise_for_status()
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                devices = []
                for device in root.findall('device'):
                    device_info = {
                        'ain': device.get('identifier'),
                        'name': device.find('name').text if device.find('name') is not None else 'Unbekannt',
                        'manufacturer': device.get('manufacturer'),
                        'productname': device.get('productname'),
                        'fwversion': device.get('fwversion'),
                        'present': device.get('present') == '1',
                        'txbusy': device.get('txbusy') == '1'
                    }
                    
                    # Thermostat-spezifische Informationen
                    temp = device.find('temperature')
                    if temp is not None:
                        device_info['temperature'] = {
                            'celsius': temp.get('celsius'),
                            'offset': temp.get('offset')
                        }
                    
                    hkr = device.find('hkr')
                    if hkr is not None:
                        device_info['thermostat'] = {
                            'tist': hkr.find('tist').text if hkr.find('tist') is not None else None,  # Ist-Temperatur
                            'tsoll': hkr.find('tsoll').text if hkr.find('tsoll') is not None else None,  # Soll-Temperatur
                            'komfort': hkr.find('komfort').text if hkr.find('komfort') is not None else None,
                            'absenk': hkr.find('absenk').text if hkr.find('absenk') is not None else None,
                            'lock': hkr.find('lock').text if hkr.find('lock') is not None else None,
                            'devicelock': hkr.find('devicelock').text if hkr.find('devicelock') is not None else None,
                            'errorcode': hkr.find('errorcode').text if hkr.find('errorcode') is not None else None,
                            'batterylow': hkr.find('batterylow').text if hkr.find('batterylow') is not None else None
                        }
                    
                    devices.append(device_info)
                
                return devices
            else:
                return []
                
        except requests.exceptions.RequestException as e:
            return []
        except ET.ParseError as e:
            return []
        except Exception as e:
            return []
    
    def set_temperature(self, ain, temperature):
        """Setzt die Temperatur für ein Gerät"""
        # Zuerst sicherstellen, dass wir eingeloggt sind
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        # Temperatur in 0.5 Schritten (16 = 8°C, 25 = 12.5°C, etc.)
        temp_value = int(temperature * 2)
        
        set_temp_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        params = {
            'sid': self.sid,
            'ain': ain,
            'switchcmd': 'sethkrtsoll',
            'param': temp_value
        }
        
        try:
            response = self.session.get(set_temp_url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.status_code == 200
                
        except requests.exceptions.RequestException as e:
            return False
        except Exception as e:
            return False
    
    def get_device_name(self, ain):
        """Holt den Gerätenamen für eine AIN"""
        devices = self.get_devices()
        for device in devices:
            if device['ain'] == ain:
                return device['name']
        return ain
    
    def set_vacation_mode(self, ain, start_date, end_date, active=True):
        """Setzt den Urlaubsmodus für ein Gerät über die FritzBox API"""
        # Zuerst sicherstellen, dass wir eingeloggt sind
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        # URL für Urlaubsschaltung mit Szenario
        vacation_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        if active:
            # Urlaubsszenario erstellen/aktivieren
            params = {
                'sid': self.sid,
                'ain': ain,
                'switchcmd': 'sethkrholiday',
                'param': f'{start_date},{end_date}'  # Format: TT.MM.JJJJ,TT.MM.JJJJ
            }
        else:
            # Urlaubsszenario deaktivieren
            params = {
                'sid': self.sid,
                'ain': ain,
                'switchcmd': 'sethkrholiday',
                'param': ''  # Leerer Parameter deaktiviert das Szenario
            }
        
        try:
            response = self.session.get(vacation_url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            return False
        except Exception as e:
            return False
    
    def create_vacation_template(self, template_name, active=True):
        """Erstellt eine FritzBox-Urlaubsvorlage gemäß AVM-Dokumentation"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        if active:
            # Vorlage 1: Urlaubsschaltung aktivieren (1.1. - 31.12.)
            params = {
                'sid': self.sid,
                'switchcmd': 'sethkrholiday',
                'param': '01.01.,00:00,31.12.,23:00'  # Format laut AVM-Doku
            }
            
            print(f"=== FritzBox Urlaubsvorlage erstellen (aktiv) ===")
            print(f"Vorlage: {template_name}")
            print(f"Parameter: {params['param']}")
            
        else:
            # Vorlage 2: Urlaubsschaltung deaktivieren (keine Zeiträume)
            params = {
                'sid': self.sid,
                'switchcmd': 'sethkrholiday',
                'param': ''  # Leere Parameter löschen alle Urlaubszeiträume
            }
            
            print(f"=== FritzBox Urlaubsvorlage erstellen (deaktiv) ===")
            print(f"Vorlage: {template_name}")
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            print(f"URL: {url}")
            print(f"Params: {params}")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                response_text = response.text.strip()
                if response_text == "OK" or response_text == "" or "error" not in response_text.lower():
                    print(f"✅ Urlaubsvorlage '{template_name}' erfolgreich erstellt")
                    return True
                else:
                    print(f"❌ Fehler in Antwort: {response_text}")
                    return False
            else:
                print(f"❌ HTTP-Fehler: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Exception bei Urlaubsvorlage: {e}")
            return False
    
    def apply_vacation_template(self, template_id):
        """Wendet eine erstellte Urlaubsvorlage an"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': self.sid,
            'switchcmd': 'applytemplate',
            'param': template_id
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            print(f"Vorlage anwenden - Status: {response.status_code}")
            print(f"Vorlage anwenden - Response: {response.text}")
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Fehler beim Anwenden der Vorlage: {e}")
            return False
    
    def get_basic_device_stats(self, ain):
        """Ruft grundlegende Gerätestatistiken über getbasicdevicestats ab
        
        Args:
            ain (str): Die AIN des Geräts (erforderlich)
            
        Returns:
            dict: Geparste Statistikdaten oder None bei Fehler
        """
        # Zuerst sicherstellen, dass wir eingeloggt sind
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        if not ain:
            print("AIN ist erforderlich für getbasicdevicestats")
            return None
        
        stats_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        params = {
            'sid': self.sid,
            'switchcmd': 'getbasicdevicestats',
            'ain': ain
        }
        
        try:
            response = self.session.get(stats_url, params=params, timeout=30)
            response.raise_for_status()
            
            if response.status_code == 200:
                return self.parse_basic_device_stats(response.text, ain)
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Fehler bei getbasicdevicestats: {e}")
            return None
        except Exception as e:
            print(f"Allgemeiner Fehler bei getbasicdevicestats: {e}")
            return None
    
    def parse_basic_device_stats(self, xml_data, ain):
        """Parst die XML-Antwort von getbasicdevicestats"""
        try:
            import datetime
            import re
            
            # Debug: Zeige die XML-Struktur
            print(f"DEBUG XML-Struktur: {xml_data[:200]}...")
            
            # Die XML-Antwort ist oft nicht wohlgeformt, wir verwenden Regex zum Parsen
            device_stats = {}
            
            # Stats-Attribute extrahieren
            stats_pattern = r'<stats[^>]*count="(\d+)"[^>]*grid="(\d+)"[^>]*datatime="(\d+)"'
            stats_match = re.search(stats_pattern, xml_data)
            
            if stats_match:
                device_stats['count'] = int(stats_match.group(1))
                device_stats['grid'] = int(stats_match.group(2))
                device_stats['datatime'] = datetime.datetime.fromtimestamp(int(stats_match.group(3)))
            
            # Datenpunkte extrahieren (alles zwischen > und <)
            data_pattern = r'<stats[^>]*>([^<]*)</stats>'
            data_match = re.search(data_pattern, xml_data)
            
            if data_match:
                data_text = data_match.group(1).strip()
                data_points = []
                for item in data_text.split(","):
                    try:
                        data_points.append(int(item))
                    except ValueError:
                        data_points.append(None)  # Fehlende Daten
                device_stats["data"] = data_points
            
            return device_stats
            
        except Exception as e:
            print(f"Fehler beim Parsen der Stats-Daten: {e}")
            return {}
    
    def get_temperature_history(self, ain, hours=24):
        """Holt die Temperaturhistorie für ein Gerät und bereitet sie auf
        
        Args:
            ain (str): Die AIN des Geräts
            hours (int): Anzahl der Stunden für die Analyse (Standard: 24)
            
        Returns:
            dict: Aufbereitete Temperaturdaten mit Statistiken
        """
        stats = self.get_basic_device_stats(ain)
        if not stats:
            return None
        
        # Daten aufbereiten
        data_points = stats.get('data', [])
        grid_seconds = stats.get('grid', 900)  # Standard: 15 Minuten
        datatime = stats.get('datatime')
        
        # Filtere None-Werte
        valid_data = [x for x in data_points if x is not None]
        
        if not valid_data:
            return None
        
        # Temperaturen umrechnen (FritzBox speichert oft als °C * 2)
        temperatures = []
        for temp in valid_data:
            # Bei den Testdaten sehen wir Werte wie 215, 210, etc. -> das sind °C * 10
            if temp > 100:  # Wahrscheinlich *10 gespeichert
                temperatures.append(temp / 10)
            else:
                temperatures.append(temp)
        
        # Statistiken berechnen
        result = {
            'ain': ain,
            'device_name': self.get_device_name(ain),
            'total_points': len(data_points),
            'valid_points': len(valid_data),
            'grid_seconds': grid_seconds,
            'last_update': datatime,
            'temperatures_celsius': temperatures,
            'min_temp': min(temperatures),
            'max_temp': max(temperatures),
            'avg_temp': sum(temperatures) / len(temperatures),
            'current_temp': temperatures[-1] if temperatures else None,
            'time_range_hours': len(valid_data) * grid_seconds / 3600
        }
        
        return result

    def apply_template_direct_on_devices(self, template_name, activate=True):
        """Wendet eine Vorlage direkt auf die konfigurierten Geräte an"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        # Zuerst die Vorlagenliste holen
        template_list = self.get_template_list_aha()
        if not template_list:
            return False
        
        # Finde die spezifische Vorlage und extrahiere Geräte-IDs
        import re
        template_pattern = rf'<template[^>]*><name>{re.escape(template_name)}</name>.*?</template>'
        template_match = re.search(template_pattern, template_list, re.DOTALL)
        
        if not template_match:
            print(f"❌ Vorlage '{template_name}' nicht gefunden")
            return False
        
        template_xml = template_match.group(0)
        
        # Extrahiere Geräte-IDs
        device_pattern = r'<device identifier="([^"]*)"'
        device_ids = re.findall(device_pattern, template_xml)
        
        if not device_ids:
            print(f"❌ Keine Geräte in Vorlage '{template_name}' gefunden")
            return False
        
        print(f"🔍 Vorlage '{template_name}' - Geräte: {device_ids}")
        
        success_count = 0
        
        for device_id in device_ids:
            try:
                if activate:
                    # Urlaub aktivieren - Versuche verschiedene Methoden
                    methods = [
                        # Methode 1: sethkrholiday mit ganzjährigem Zeitraum
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrholiday',
                            'ain': device_id,
                            'param': '01.01.,00:00,31.12.,23:00'
                        },
                        
                        # Methode 2: sethkrholidayactive
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrholidayactive',
                            'ain': device_id,
                            'param': '1'
                        },
                        
                        # Methode 3: sethkrtsoll auf niedrige Temperatur (16°C)
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrtsoll',
                            'ain': device_id,
                            'param': '32'  # 16°C
                        }
                    ]
                else:
                    # Urlaub deaktivieren
                    methods = [
                        # Methode 1: sethkrholiday leer
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrholiday',
                            'ain': device_id,
                            'param': ''
                        },
                        
                        # Methode 2: sethkrholidayactive ausschalten
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrholidayactive',
                            'ain': device_id,
                            'param': '0'
                        },
                        
                        # Methode 3: sethkrtsoll auf normale Temperatur (20°C)
                        {
                            'sid': self.sid,
                            'switchcmd': 'sethkrtsoll',
                            'ain': device_id,
                            'param': '40'  # 20°C
                        }
                    ]
                
                for i, params in enumerate(methods):
                    response = self.session.get(url, params=params, timeout=10)
                    
                    print(f"Gerät {device_id} - Methode {i+1}: {params['switchcmd']} - Status {response.status_code}")
                    
                    if response.status_code == 200:
                        success_count += 1
                        print(f"✅ Gerät {device_id} erfolgreich (Methode {i+1})")
                        break
                        
            except Exception as e:
                print(f"❌ Exception bei Gerät {device_id}: {e}")
                continue
        
        print(f"Ergebnis: {success_count}/{len(device_ids)} Geräte erfolgreich")
        return success_count > 0
    
    def parse_template_xml(self, xml_content):
        """Parst die XML-Vorlagenliste und extrahiert relevante Informationen"""
        import re
        
        templates = []
        
        # Extrahiere Template-Informationen mit Regex
        template_pattern = r'<template[^>]*identifier="([^"]*)"[^>]*id="([^"]*)"[^>]*><name>([^<]*)</name>'
        
        matches = re.findall(template_pattern, xml_content)
        
        for match in matches:
            template_id, template_id_num, template_name = match
            templates.append({
                'identifier': template_id,
                'id': template_id_num,
                'name': template_name.strip()
            })
        
        return templates
    
    def get_template_list_aha(self):
        """Holt die Vorlagenliste über das AHA-HTTP-Interface"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        # Versuche beide möglichen Befehle
        commands = [
            ('gettemplatelist', ''),
            ('gettemplatelistinfos', '')
        ]
        
        for cmd, param in commands:
            try:
                params = {
                    'sid': self.sid,
                    'switchcmd': cmd
                }
                if param:
                    params['param'] = param
                
                response = self.session.get(url, params=params, timeout=10)
                
                print(f"{cmd}: Status {response.status_code}")
                print(f"Response: {response.text}")
                
                if response.status_code == 200 and response.text.strip():
                    return response.text.strip()
                    
            except Exception as e:
                print(f"Fehler bei {cmd}: {e}")
                continue
        
        return None
    
    def create_vacation_scenarios(self):
        """Erstellt Szenarien für manuelle Urlaubsvorlagen"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        # Szenario 1: Urlaub aktivieren
        scenario1_params = {
            'sid': self.sid,
            'switchcmd': 'createscenario',
            'param': 'Urlaub aktivieren,Urlaubsschaltung'
        }
        
        # Szenario 2: Urlaub deaktivieren
        scenario2_params = {
            'sid': self.sid,
            'switchcmd': 'createscenario',
            'param': 'Urlaub deaktivieren,Urlaubsschaltung aus'
        }
        
        scenarios_created = 0
        
        try:
            # Beide Szenarien erstellen
            for name, params in [("Urlaub aktivieren", scenario1_params), ("Urlaub deaktivieren", scenario2_params)]:
                response = self.session.get(url, params=params, timeout=10)
                print(f"Szenario '{name}' - Status: {response.status_code}")
                if response.status_code == 200:
                    scenarios_created += 1
                    print(f"✅ {name} erstellt")
            
            return scenarios_created == 2
            
        except Exception as e:
            print(f"❌ Fehler bei Szenarien: {e}")
            return False
    
    def apply_vacation_scenario(self, active=True):
        """Wendet Urlaubsszenario an"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return False
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        scenario_name = "Urlaub aktivieren" if active else "Urlaub deaktivieren"
        params = {
            'sid': self.sid,
            'switchcmd': 'applyscenario',
            'param': scenario_name
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            print(f"Szenario '{scenario_name}' - Status: {response.status_code}")
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Fehler bei Szenario: {e}")
            return False
    
    def get_vacation_template_info(self):
        """Holt Informationen über die aktuelle Urlaubsvorlage"""
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': self.sid,
            'switchcmd': 'gethkrholiday'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            print(f"gethkrholiday Status: {response.status_code}")
            print(f"gethkrholiday Response: {response.text}")
            
            if response.status_code == 200:
                return response.text.strip()
            return None
            
        except Exception as e:
            print(f"Fehler bei gethkrholiday: {e}")
            return None
    
    def get_vacation_status(self, ain):
        """Prüft den Urlaubsstatus für ein Gerät"""
        # Zuerst sicherstellen, dass wir eingeloggt sind
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        # URL für Urlaubstatus
        vacation_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': self.sid,
            'ain': ain,
            'switchcmd': 'gethkrholidayactive'
        }
        
        try:
            response = self.session.get(vacation_url, params=params, timeout=10)
            response.raise_for_status()
            
            if response.status_code == 200:
                # Antwort ist normalerweise "1" für aktiv, "0" für inaktiv
                return response.text.strip() == "1"
            return None
            
        except requests.exceptions.RequestException as e:
            return None
        except Exception as e:
            return None
    
    def get_timer_info(self, ain):
        """Holt Timer-Informationen für ein Gerät (nächste Schaltzeiten)"""
        # Zuerst sicherstellen, dass wir eingeloggt sind
        if not self.sid or self.sid == "0000000000000000":
            if not self.login():
                return None
        
        # URL für Timer-Informationen
        timer_url = f"http://{self.host}:{self.port}/webservices/homeautoswitch.lua"
        
        params = {
            'sid': self.sid,
            'ain': ain,
            'switchcmd': 'gettimer'
        }
        
        try:
            response = self.session.get(timer_url, params=params, timeout=10)
            response.raise_for_status()
            
            if response.status_code == 200:
                # Timer-XML parsen
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                timer_info = []
                for timer in root.findall('timer'):
                    timer_data = {
                        'weekday': timer.get('weekday'),
                        'hour': timer.get('hour'),
                        'minute': timer.get('minute'),
                        'temp': timer.get('temp'),
                        'active': timer.get('active', '1') == '1'
                    }
                    timer_info.append(timer_data)
                
                return timer_info
            return None
            
        except requests.exceptions.RequestException as e:
            return None
        except Exception as e:
            return None
    
    def get_next_timer_change(self, ain, current_temp=None):
        """Berechnet die nächste Temperaturänderung basierend auf dem Timer"""
        import datetime
        
        timer_info = self.get_timer_info(ain)
        if not timer_info:
            return None
        
        now = datetime.datetime.now()
        current_weekday = str(now.weekday())  # 0=Montag, 6=Sonntag
        current_time = now.time()
        
        next_change = None
        min_diff = float('inf')
        
        # Zuerst nach heutigen Timern suchen
        for timer in timer_info:
            if not timer['active']:
                continue
                
            try:
                timer_hour = int(timer['hour'])
                timer_minute = int(timer['minute'])
                timer_time = datetime.time(timer_hour, timer_minute)
                
                # Prüfen, ob der Timer heute noch aktiv wird
                if timer['weekday'] == current_weekday and timer_time > current_time:
                    timer_datetime = datetime.datetime.combine(now.date(), timer_time)
                    diff = (timer_datetime - now).total_seconds()
                    if diff < min_diff:
                        min_diff = diff
                        next_change = {
                            'time': timer_time,
                            'temp': float(timer['temp']) / 2,  # FritzBox speichert in 0.5°C Schritten
                            'datetime': timer_datetime,
                            'is_today': True
                        }
                        
            except (ValueError, TypeError):
                continue
        
        # Wenn heute nichts gefunden, nach morgen suchen
        if next_change is None:
            tomorrow = now + datetime.timedelta(days=1)
            tomorrow_weekday = str(tomorrow.weekday())
            
            for timer in timer_info:
                if not timer['active']:
                    continue
                    
                try:
                    timer_hour = int(timer['hour'])
                    timer_minute = int(timer['minute'])
                    timer_time = datetime.time(timer_hour, timer_minute)
                    
                    # Prüfen, ob der Timer morgen aktiv wird
                    if timer['weekday'] == tomorrow_weekday:
                        timer_datetime = datetime.datetime.combine(tomorrow.date(), timer_time)
                        diff = (timer_datetime - now).total_seconds()
                        if diff < min_diff:
                            min_diff = diff
                            next_change = {
                                'time': timer_time,
                                'temp': float(timer['temp']) / 2,
                                'datetime': timer_datetime,
                                'is_today': False
                            }
                            
                except (ValueError, TypeError):
                    continue
        
        return next_change
