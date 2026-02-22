#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import importlib.util
import sys
import datetime as DT


def load_module(name, filepath):
    """Load a module from file path using importlib"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), filepath))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Load configuration and database modules
config_module = load_module("config", "config.py")
user_database_module = load_module("user_database", "user_database.py")
from user_database import UserDatabase
from lib.fritzbox_api import FritzBoxAPI

# Import Konstanten aus config
LOGIN, MAIN, ADMIN, STATISTICS, AUTOMATION = config_module.LOGIN, config_module.MAIN, config_module.ADMIN, config_module.STATISTICS, config_module.AUTOMATION

# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'listScenarios': 'Szenarien anzeigen',
         'listTemplates': 'Vorlagen anzeigen',
         'executeScenario': 'Szenario ausführen',
         'applyTemplate': 'Vorlage anwenden',
         'quit': 'Verlasse AutomationMode'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'listScenarios': 'Zeigt alle verfügbaren Szenarien an',
         'listTemplates': 'Zeigt alle verfügbaren Vorlagen an',
         'executeScenario': 'Führt ein ausgewähltes Szenario aus',
         'applyTemplate': 'Wendet eine ausgewählte Vorlage an',
         'help': 'Zeigt diesen Text an',
         'quit': 'Verlasse AutomationMode'}

async def listScenarios(update, context, user_data, markupList):
    """Zeigt alle verfügbaren Szenarien der FritzBox an"""
    try:
        fritzbox = FritzBoxAPI()
        
        # Login versuchen
        if not fritzbox.login():
            await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                reply_markup=user_data['keyboard'])
            return user_data['status']
        
        # Szenarien-Informationen abrufen
        scenarios_text = "📋 **Verfügbare Szenarien:**\n\n"
        
        # Versuche verschiedene Methoden um Szenarien zu bekommen
        scenarios_found = []
        
        # Methode 1: Vorlage als Szenario-Liste interpretieren
        template_list = fritzbox.get_template_list_aha()
        if template_list:
            scenarios_text += "🏠 **Vorlagen (als Szenarien verwendbar):**\n"
            templates = fritzbox.parse_template_xml(template_list)
            for template in templates:
                scenarios_found.append(f"• {template['name']} (ID: {template['id']})")
        
        # Methode 2: Manuelles Urlaubs-Szenario
        scenarios_text += "\n🏖️ **Urlaubs-Szenarien:**\n"
        scenarios_text += "• Urlaub aktivieren\n"
        scenarios_text += "• Urlaub deaktivieren\n"
        scenarios_found.extend(["Urlaub aktivieren", "Urlaub deaktivieren"])
        
        if scenarios_found:
            scenarios_text += "\n" + "\n".join(scenarios_found)
            scenarios_text += "\n\n💡 Nutze /executeScenario um ein Szenario auszuführen"
        else:
            scenarios_text += "Keine Szenarien gefunden.\n\n💡 Tipp: Erstelle zuerst Urlaubs-Szenarien mit /createVacationScenario"
        
        await update.message.reply_text(scenarios_text,
            reply_markup=user_data['keyboard'], parse_mode='Markdown')
            
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler beim Abrufen der Szenarien: {str(e)}",
            reply_markup=user_data['keyboard'])
    
    return user_data['status']

async def listTemplates(update, context, user_data, markupList):
    """Zeigt alle verfügbaren Vorlagen der FritzBox an"""
    try:
        fritzbox = FritzBoxAPI()
        
        # Login versuchen
        if not fritzbox.login():
            await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                reply_markup=user_data['keyboard'])
            return user_data['status']
        
        templates_text = "📋 **Verfügbare Vorlagen:**\n\n"
        
        # Vorlagen-Liste abrufen
        template_list = fritzbox.get_template_list_aha()
        if template_list:
            templates = fritzbox.parse_template_xml(template_list)
            
            if templates:
                for template in templates:
                    templates_text += f"🏠 **{template['name']}**\n"
                    templates_text += f"   ID: {template['id']}\n"
                    templates_text += f"   Identifier: {template['identifier']}\n\n"
                
                templates_text += f"💡 Insgesamt {len(templates)} Vorlage(n) gefunden\n"
                templates_text += "💡 Nutze /applyTemplate um eine Vorlage anzuwenden"
            else:
                templates_text += "Keine Vorlagen in der FritzBox gefunden.\n\n"
                templates_text += "💡 Tipp: Erstelle zuerst Vorlagen in der FritzBox-Weboberfläche"
        else:
            templates_text += "Konnte keine Vorlagen abrufen.\n\n"
            templates_text += "💡 Überprüfe die Verbindung zur FritzBox"
        
        await update.message.reply_text(templates_text,
            reply_markup=user_data['keyboard'], parse_mode='Markdown')
            
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler beim Abrufen der Vorlagen: {str(e)}",
            reply_markup=user_data['keyboard'])
    
    return user_data['status']

async def executeScenario(update, context, user_data, markupList):
    """Führt ein ausgewähltes Szenario aus"""
    try:
        fritzbox = FritzBoxAPI()
        
        # Login versuchen
        if not fritzbox.login():
            await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                reply_markup=user_data['keyboard'])
            return user_data['status']
        
        # Text des Szenarios extrahieren
        text = update.message.text
        
        # Prüfen ob es ein Button-Klick ist
        if text == "Szenario ausführen":
            # Inline-Keyboard für Szenario-Auswahl erstellen
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [InlineKeyboardButton("🏖️ Urlaub aktivieren", callback_data='execute_scenario_Urlaub aktivieren')],
                [InlineKeyboardButton("🏠 Urlaub deaktivieren", callback_data='execute_scenario_Urlaub deaktivieren')],
                [InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_scenario')]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 **Szenario auswählen:**\n\n"
                "Wähle das Szenario, das du ausführen möchtest:",
                reply_markup=reply_markup, parse_mode='Markdown')
            return user_data['status']
        
        # Befehls-Text extrahieren (entfernt /executeScenario am Anfang)
        scenario_text = text.replace('/executeScenario ', '').strip()
        
        if not scenario_text or scenario_text == "Szenario ausführen":
            # Inline-Keyboard für Szenario-Auswahl erstellen
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [InlineKeyboardButton("�️ Urlaub aktivieren", callback_data='execute_scenario_Urlaub aktivieren')],
                [InlineKeyboardButton("🏠 Urlaub deaktivieren", callback_data='execute_scenario_Urlaub deaktivieren')],
                [InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_scenario')]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 **Szenario auswählen:**\n\n"
                "Wähle das Szenario, das du ausführen möchtest:",
                reply_markup=reply_markup, parse_mode='Markdown')
            return user_data['status']
        
        # Szenario ausführen
        if "Urlaub aktivieren" in scenario_text:
            success = fritzbox.apply_vacation_scenario(active=True)
            if success:
                await update.message.reply_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt",
                    reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("❌ Fehler beim Ausführen des Szenarios",
                    reply_markup=user_data['keyboard'])
        elif "Urlaub deaktivieren" in scenario_text:
            success = fritzbox.apply_vacation_scenario(active=False)
            if success:
                await update.message.reply_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt",
                    reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("❌ Fehler beim Ausführen des Szenarios",
                    reply_markup=user_data['keyboard'])
        else:
            await update.message.reply_text(f"❌ Unbekanntes Szenario: {scenario_text}\n\n"
                "💡 Nutze /listScenarios um verfügbare Szenarien zu sehen",
                reply_markup=user_data['keyboard'])
                
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler bei der Szenario-Ausführung: {str(e)}",
            reply_markup=user_data['keyboard'])
    
    return user_data['status']

async def applyTemplate(update, context, user_data, markupList):
    """Wendet eine ausgewählte Vorlage an"""
    try:
        fritzbox = FritzBoxAPI()
        
        # Login versuchen
        if not fritzbox.login():
            await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                reply_markup=user_data['keyboard'])
            return user_data['status']
        
        # Text der Vorlage extrahieren
        text = update.message.text
        
        # Prüfen ob es ein Button-Klick ist
        if text == "Vorlage anwenden":
            # Vorlagen abrufen und Inline-Keyboard erstellen
            template_list = fritzbox.get_template_list_aha()
            if template_list:
                templates = fritzbox.parse_template_xml(template_list)
                if templates:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    
                    keyboard = []
                    for template in templates:
                        keyboard.append([InlineKeyboardButton(f"🏠 {template['name']}", 
                                                       callback_data=f'apply_template_{template["id"]}_{template["name"]}')])
                    
                    keyboard.append([InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_template')])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        "🎯 **Vorlage auswählen:**\n\n"
                        "Wähle die Vorlage, die du anwenden möchtest:",
                        reply_markup=reply_markup, parse_mode='Markdown')
                    return user_data['status']
            
            # Keine Vorlagen gefunden
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [[InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_template')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 **Keine Vorlagen gefunden:**\n\n"
                "Es sind keine Vorlagen in der FritzBox konfiguriert.\n"
                "Bitte erstelle zuerst Vorlagen in der FritzBox-Weboberfläche.",
                reply_markup=reply_markup, parse_mode='Markdown')
            return user_data['status']
        
        # Befehls-Text extrahieren (entfernt /applyTemplate am Anfang)
        template_text = text.replace('/applyTemplate ', '').strip()
        
        if not template_text or template_text == "Vorlage anwenden":
            # Vorlagen abrufen und Inline-Keyboard erstellen
            template_list = fritzbox.get_template_list_aha()
            if template_list:
                templates = fritzbox.parse_template_xml(template_list)
                if templates:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    
                    keyboard = []
                    for template in templates:
                        keyboard.append([InlineKeyboardButton(f"🏠 {template['name']}", 
                                                       callback_data=f'apply_template_{template["id"]}_{template["name"]}')])
                    
                    keyboard.append([InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_template')])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        "🎯 **Vorlage auswählen:**\n\n"
                        "Wähle die Vorlage, die du anwenden möchtest:",
                        reply_markup=reply_markup, parse_mode='Markdown')
                    return user_data['status']
            
            # Keine Vorlagen gefunden
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [[InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_template')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 **Keine Vorlagen gefunden:**\n\n"
                "Es sind keine Vorlagen in der FritzBox konfiguriert.\n"
                "Bitte erstelle zuerst Vorlagen in der FritzBox-Weboberfläche.",
                reply_markup=reply_markup, parse_mode='Markdown')
            return user_data['status']
        
        # Vorlage anwenden
        success = fritzbox.apply_template_direct_on_devices(template_text, activate=True)
        
        if success:
            await update.message.reply_text(f"✅ Vorlage '{template_text}' erfolgreich angewendet",
                reply_markup=user_data['keyboard'])
        else:
            await update.message.reply_text(f"❌ Fehler beim Anwenden der Vorlage '{template_text}'\n\n"
                "💡 Überprüfe den Vorlagennamen mit /listTemplates",
                reply_markup=user_data['keyboard'])
                
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler beim Anwenden der Vorlage: {str(e)}",
            reply_markup=user_data['keyboard'])
    
    return user_data['status']

# Callback-Handler für Inline-Buttons
async def handle_scenario_callback(update, context):
    """Handler für Szenario-Callback-Buttons"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('execute_scenario_'):
        # Szenario-Name extrahieren
        scenario_name = query.data.replace('execute_scenario_', '', 1)
        
        try:
            fritzbox = FritzBoxAPI()
            
            # Login versuchen
            if not fritzbox.login():
                await query.edit_message_text("❌ Fehler: Login bei FritzBox fehlgeschlagen")
                return
            
            # Szenario ausführen
            if "Urlaub aktivieren" in scenario_name:
                success = fritzbox.apply_vacation_scenario(active=True)
                if success:
                    await query.edit_message_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt")
                else:
                    await query.edit_message_text("❌ Fehler beim Ausführen des Szenarios")
            elif "Urlaub deaktivieren" in scenario_name:
                success = fritzbox.apply_vacation_scenario(active=False)
                if success:
                    await query.edit_message_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt")
                else:
                    await query.edit_message_text("❌ Fehler beim Ausführen des Szenarios")
            else:
                await query.edit_message_text(f"❌ Unbekanntes Szenario: {scenario_name}")
                
        except Exception as e:
            await query.edit_message_text(f"❌ Fehler bei der Szenario-Ausführung: {str(e)}")
    
    elif query.data == 'cancel_scenario':
        await query.edit_message_text("❌ Szenario-Ausführung abgebrochen")
    
    elif query.data.startswith('apply_template_'):
        # Vorlagen-ID und Name extrahieren
        parts = query.data.split('_', 2)
        logger.debug(f"Callback-Data: {query.data}")
        logger.debug(f"Parts nach Split: {parts}")
        
        if len(parts) >= 3:
            template_id = parts[1]  # Korrekt: parts[1] enthält die ID
            template_name = parts[2]  # parts[2] enthält den Namen
            logger.debug(f"Extrahiert - ID: {template_id}, Name: {template_name}")
        elif len(parts) == 2:
            template_id = parts[1]
            template_name = ''
            logger.debug(f"Nur ID extrahiert: {template_id}")
        else:
            template_id = ''
            template_name = ''
            logger.debug("Keine ID extrahiert")
        
        try:
            fritzbox = FritzBoxAPI()
            
            # Login versuchen
            if not fritzbox.login():
                await query.edit_message_text("❌ Fehler: Login bei FritzBox fehlgeschlagen\n\n"
                                        "💡 Bitte überprüfe:\n"
                                        "• FritzBox ist erreichbar\n"
                                        "• Zugangsdaten sind korrekt\n"
                                        "• Keine andere Session aktiv")
                return
            
            # Finde den vollständigen Vorlagennamen anhand der ID
            template_list = fritzbox.get_template_list_aha()
            if template_list:
                templates = fritzbox.parse_template_xml(template_list)
                if templates:
                    # Debug: Alle verfügbaren Vorlagen anzeigen
                    available_ids = [t['id'] for t in templates]
                    logger.debug(f"Verfügbare Vorlagen-IDs: {available_ids}")
                    logger.debug(f"Suche nach ID: {template_id}")
                    
                    for template in templates:
                        if template['id'] == template_id:
                            template_name = template['name']
                            logger.debug(f"Vorlage gefunden: {template_name}")
                            break
                    else:
                        logger.warning(f"Vorlage mit ID {template_id} nicht gefunden")
                else:
                    logger.warning("Keine Vorlagen geparst")
            else:
                logger.warning("Keine Vorlagen-Liste erhalten")
            
            # Vorlage anwenden
            success = fritzbox.apply_template_direct_on_devices(template_name, activate=True)
            
            if success:
                await query.edit_message_text(f"✅ Vorlage '{template_name}' erfolgreich angewendet")
            else:
                await query.edit_message_text(f"❌ Fehler beim Anwenden der Vorlage '{template_name}'")
                
        except Exception as e:
            error_msg = str(e)
            if "Login" in error_msg or "Authentifizierung" in error_msg:
                await query.edit_message_text("❌ Login-Fehler bei FritzBox\n\n"
                                        "💡 Mögliche Ursachen:\n"
                                        "• FritzBox nicht erreichbar\n"
                                        "• Falsche Zugangsdaten\n"
                                        "• Session abgelaufen\n\n"
                                        f"Details: {error_msg}")
            else:
                await query.edit_message_text(f"❌ Fehler beim Anwenden der Vorlage: {error_msg}")
    
    elif query.data == 'cancel_template':
        await query.edit_message_text("❌ Vorlagen-Anwendung abgebrochen")

async def quit(update, context, user_data, markupList):
    """Verlässt den Automation Mode"""
    user_data['keyboard'] = markupList[MAIN]
    await update.message.reply_text("EXIT --AUTOMATIONMODE--",
            reply_markup=user_data['keyboard'])
    user_data['status'] = MAIN
    return user_data['status']

async def help(update, context, user_data, markupList):
    """Zeigt die Hilfe für den Automation Mode an"""
    text = '🤖 **Automation Mode - Hilfe:**\n\n'
    for key, value in textbefehl.items():
        text = text + '- /' + key + ' ' + value + '\n'
    
    text += '\n💡 **Tipp:** Mit diesen Befehlen kannst du FritzBox-Szenarien und Vorlagen verwalten'
            
    await update.message.reply_text(text,
                reply_markup=user_data['keyboard'], parse_mode='Markdown')
    return user_data['status']
    
async def default(update, context, user_data, markupList):
    """Standard-Funktion für unbekannte Befehle"""
    return await help(update, context, user_data, markupList)
