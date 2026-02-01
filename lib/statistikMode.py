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
# TODO: Temperaturverlauf anzeigen lassen. Gruppen-funktionen beachten (Absenk-/Komfortemperatur, Zeitplan edit)??? Urlaub modus an und aus schalten.
# TODO: Adminmode Testen!!!

# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'status': 'Status',
         'set_temp': 'Temperatur setzen',
         'back': 'Zurueck'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'status': 'Zeigt Ziel- und Ist-Temperatur aller Heizkörper an',
         'set_temp': 'Setzt die Temperatur für einen Heizkörper',
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
        
        message = "🌡️ *Status aller Heizkörper:*\n\n"
        
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
                
                message += f"{status_emoji} *{name}*\n"
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
                await query.edit_message_text(f"✅ *Temperatur erfolgreich gesetzt!*\n\n"
                                            f"🏠 {heater_name}\n"
                                            f"🌡️ Neue Zieltemperatur: {temp_celsius:.1f}°C",
                                            parse_mode='Markdown')
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