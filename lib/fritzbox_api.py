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
                # TR-064 funktioniert ohne Login - wir können direkt Geräte abrufen
                return True
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
