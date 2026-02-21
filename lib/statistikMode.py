#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import importlib.util
import sys

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


# Import markupList from config
from lib.config import genMarkupList, LOGIN, MAIN, ADMIN, STATISTICS, Config
# markupList wird zur Laufzeit generiert, nicht beim Import
markupList = None
# TODO: Gruppen-funktionen beachten (Absenk-/Komfortemperatur, Zeitplan edit)???
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
         'back': 'Zurueck'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'status': 'Zeigt Ziel- und Ist-Temperatur aller Heizkörper an',
         'set_temp': 'Setzt die Temperatur für einen Heizkörper',
         'temp_history': 'Zeigt Temperaturverlauf aller Heizungen der letzten 24 Stunden als Graphik an',
         'vacation_mode': 'Schaltet FritzBox-Urlaubsschaltung für alle Heizkörper ein/aus',
         'back': 'Wechselt zurück ins Main-Menu'}

async def status(update, context, markupList):
    bot = context.bot
    
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
        
        for heater in heaters:
            name = heater.get('name', 'Unbekannt')
            thermostat = heater['thermostat']
            
            # Temperaturen umrechnen (Werte sind in 0.5°C Schritten)
            tist_value = thermostat.get('tist')
            tsoll_value = thermostat.get('tsoll')
            
            # None-Werte behandeln - wenn keine Temperatur verfügbar, zeige "N/A"
            if tist_value is not None and tsoll_value is not None:
                current_temp = int(tist_value) / 2
                target_temp = int(tsoll_value) / 2
                
                # Status-Emoji basierend auf Temperaturdifferenz
                if abs(current_temp - target_temp) < 0.5:
                    status_emoji = "✅"
                elif current_temp < target_temp:
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
                
                message += f"{status_emoji}{vacation_icon} *{name}*\n"
                message += f"   Aktuell: {current_temp:.1f}°C\n"
                message += f"   Ziel: {target_temp:.1f}°C\n"
            else:
                message += f"❓ *{name}*\n"
                message += f"   Aktuell: N/A\n"
                message += f"   Ziel: N/A\n"
            
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

async def set_temp(update, context, markupList):
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
            
            if tist is not None and tsoll is not None:
                current_temp = int(tist) / 2
                target_temp = int(tsoll) / 2
                temp_info = f" ({current_temp:.1f}°C → {target_temp:.1f}°C)"
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

async def vacation_mode(update, context, markupList):
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

async def temp_history(update, context, markupList):
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
            
            # X-Achse formatieren
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
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
            
            await query.edit_message_text(f"🌡️ *Temperatur für {name} wählen:*\n\n"
                                        f"Aktuelle Zieltemperatur: {current_target:.1f}°C\n"
                                        f"Wähle die neue Zieltemperatur:",
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
                # Timer-Informationen für die nächste Temperaturänderung holen
                next_change = fritz.get_next_timer_change(ain, temp_celsius)
                
                success_message = f"✅ *Temperatur erfolgreich gesetzt!*\n\n"
                success_message += f"🏠 {heater_name}\n"
                success_message += f"🌡️ Neue Zieltemperatur: {temp_celsius:.1f}°C"
                
                if next_change:
                    time_str = next_change['time'].strftime("%H:%M")
                    next_temp = next_change['temp']
                    
                    if next_change.get('is_today', True):
                        success_message += f"\n\n⏰ *Gültig bis:* {time_str} Uhr"
                        success_message += f"\n🔄 *Anschließend:* {next_temp:.1f}°C (gemäß Zeitplan)"
                    else:
                        # Nächste Änderung ist morgen
                        tomorrow_name = next_change['datetime'].strftime("%A")
                        success_message += f"\n\n⏰ *Gültig bis morgen, {tomorrow_name} {time_str} Uhr*"
                        success_message += f"\n🔄 *Anschließend:* {next_temp:.1f}°C (gemäß Zeitplan)"
                else:
                    success_message += f"\n\nℹ️ Keine weiteren Zeitplanänderungen gefunden"
                
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

async def back(update, context, markupList):
    context.user_data['keyboard'] = markupList[MAIN]
    context.user_data['status'] = MAIN
    await update.message.reply_text('Zurück zum Hauptmenü', reply_markup=markupList[MAIN])
    return context.user_data['status']

async def default(update, context, markupList):
    return await status(update, context, markupList)

# Wrapper functions for direct bot calls (update, context signature)
#async def status_wrapper(update, context):
#    return await status(context.bot, update, context.user_data)
 #   return await zurück(context.bot, update, context.user_data)