#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Optional
from lib.fritzbox_api_optimized import OptimizedFritzBoxAPI, TemplateInfo
from lib.statistikMode_optimized import stats_manager

# Logger initialisieren
logger = logging.getLogger(__name__)

# Tastatur-Befehle
tastertur = {
    'listScenarios': 'Szenarien anzeigen',
    'listTemplates': 'Vorlagen anzeigen',
    'executeScenario': 'Szenario ausführen',
    'applyTemplate': 'Vorlage anwenden',
    'quit': 'Verlasse AutomationMode'
}

# Funktionen Map
textbefehl = {
    'listScenarios': 'Zeigt alle verfügbaren Szenarien an',
    'listTemplates': 'Zeigt alle verfügbaren Vorlagen an',
    'executeScenario': 'Führt ein ausgewähltes Szenario aus',
    'applyTemplate': 'Wendet eine ausgewählte Vorlage an',
    'help': 'Zeigt diesen Text an',
    'quit': 'Verlasse AutomationMode'
}

class OptimizedAutomationManager:
    """Optimierter Automation-Manager mit performanter AHA-Schnittstelle"""
    
    def __init__(self):
        self.fritz_api = OptimizedFritzBoxAPI()
        self.stats_manager = stats_manager
    
    async def list_scenarios(self, update, context, user_data, markupList):
        """Zeigt alle verfügbaren Szenarien mit optimierter API"""
        try:
            # Login prüfen
            if not self.fritz_api.login():
                await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            scenarios_text = "📋 **Verfügbare Szenarien:**\n\n"
            scenarios_found = []
            
            # Vorlagen als Szenarien interpretieren (optimiert mit Cache)
            templates = self.fritz_api.get_templates(use_cache=True)
            if templates:
                scenarios_text += "🏠 **Vorlagen (als Szenarien verwendbar):**\n"
                for template in templates:
                    # Nur Szenarien anzeigen (mit sub_templates)
                    if template.sub_templates:
                        scenarios_found.append(f"• {template.name} (ID: {template.id})")
            
            # Manuelles Urlaubs-Szenario
            scenarios_text += "\n🏖️ **Urlaubs-Szenarien:**\n"
            scenarios_text += "• Urlaub aktivieren\n"
            scenarios_text += "• Urlaub deaktivieren\n"
            scenarios_found.extend(["Urlaub aktivieren", "Urlaub deaktivieren"])
            
            if scenarios_found:
                scenarios_text += "\n" + "\n".join(scenarios_found)
                scenarios_text += "\n\n💡 Nutze /executeScenario um ein Szenario auszuführen"
            else:
                scenarios_text += "Keine Szenarien gefunden.\n\n"
                scenarios_text += "💡 Tipp: Erstelle zuerst Urlaubs-Szenarien mit /createVacationScenario"
            
            await update.message.reply_text(scenarios_text,
                reply_markup=user_data['keyboard'], parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Szenarien: {e}")
            await update.message.reply_text(f"❌ Fehler beim Abrufen der Szenarien: {str(e)}",
                reply_markup=user_data['keyboard'])
        
        return user_data['status']
    
    async def list_templates(self, update, context, user_data, markupList):
        """Zeigt alle verfügbaren Vorlagen mit optimierter API"""
        try:
            # Login prüfen
            if not self.fritz_api.login():
                await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            templates_text = "📋 **Verfügbare Vorlagen:**\n\n"
            
            # Vorlagen mit Cache abrufen
            templates = self.fritz_api.get_templates(use_cache=True)
            
            if templates:
                # Nicht automatisch erstellte Vorlagen filtern
                user_templates = [t for t in templates if not t.autocreate]
                
                if user_templates:
                    for template in user_templates:
                        templates_text += f"🏠 **{template.name}**\n"
                        templates_text += f"   ID: {template.id}\n"
                        templates_text += f"   Identifier: {template.identifier}\n"
                        templates_text += f"   Geräte: {len(template.devices)}\n"
                        
                        # ApplyMask anzeigen
                        if template.applymask:
                            masks = []
                            for mask_type in ['hkr_temperature', 'hkr_holidays', 'hkr_time_table', 
                                           'relay_manual', 'relay_automatic', 'level', 'color']:
                                if mask_type in template.applymask:
                                    masks.append(mask_type.replace('_', ' ').title())
                            
                            if masks:
                                templates_text += f"   Funktionen: {', '.join(masks)}\n"
                        
                        templates_text += "\n"
                    
                    templates_text += f"💡 Insgesamt {len(user_templates)} Vorlage(n) gefunden\n"
                    templates_text += "💡 Nutze /applyTemplate um eine Vorlage anzuwenden"
                else:
                    templates_text += "Keine benutzerdefinierten Vorlagen gefunden.\n\n"
                    templates_text += "💡 Automatisch erstellte Vorlagen werden ausgeblendet.\n"
                    templates_text += "💡 Erstelle Vorlagen in der FritzBox-Weboberfläche"
            else:
                templates_text += "Konnte keine Vorlagen abrufen.\n\n"
                templates_text += "💡 Überprüfe die Verbindung zur FritzBox"
            
            await update.message.reply_text(templates_text,
                reply_markup=user_data['keyboard'], parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Vorlagen: {e}")
            await update.message.reply_text(f"❌ Fehler beim Abrufen der Vorlagen: {str(e)}",
                reply_markup=user_data['keyboard'])
        
        return user_data['status']
    
    async def execute_scenario(self, update, context, user_data, markupList):
        """Führt ein ausgewähltes Szenario mit optimierter API aus"""
        try:
            # Login prüfen
            if not self.fritz_api.login():
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
            
            # Befehls-Text extrahieren
            scenario_text = text.replace('/executeScenario ', '').strip()
            
            if not scenario_text or scenario_text == "Szenario ausführen":
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
            
            # Szenario ausführen mit optimiertem Manager
            if "Urlaub aktivieren" in scenario_text:
                result = self.stats_manager.apply_vacation_template(active=True)
                if result['success']:
                    await update.message.reply_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt",
                        reply_markup=user_data['keyboard'])
                else:
                    error_msg = result.get('error', 'Unbekannter Fehler')
                    await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios: {error_msg}",
                        reply_markup=user_data['keyboard'])
            elif "Urlaub deaktivieren" in scenario_text:
                result = self.stats_manager.apply_vacation_template(active=False)
                if result['success']:
                    await update.message.reply_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt",
                        reply_markup=user_data['keyboard'])
                else:
                    error_msg = result.get('error', 'Unbekannter Fehler')
                    await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios: {error_msg}",
                        reply_markup=user_data['keyboard'])
            else:
                # Versuche Vorlage als Szenario auszuführen
                template = self.fritz_api.get_template_by_name(scenario_text, use_cache=True)
                if template:
                    success = self.fritz_api.apply_template(template.identifier)
                    if success:
                        await update.message.reply_text(f"✅ Szenario '{scenario_text}' erfolgreich ausgeführt",
                            reply_markup=user_data['keyboard'])
                    else:
                        await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios",
                            reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Unbekanntes Szenario: {scenario_text}\n\n"
                        "💡 Nutze /listScenarios um verfügbare Szenarien zu sehen",
                        reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler bei der Szenario-Ausführung: {e}")
            await update.message.reply_text(f"❌ Fehler bei der Szenario-Ausführung: {str(e)}",
                reply_markup=user_data['keyboard'])
        
        return user_data['status']
    
    async def apply_template(self, update, context, user_data, markupList):
        """Wendet eine ausgewählte Vorlage mit optimierter API an"""
        try:
            # Login prüfen
            if not self.fritz_api.login():
                await update.message.reply_text("❌ Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            # Text der Vorlage extrahieren
            text = update.message.text
            
            # Prüfen ob es ein Button-Klick ist
            if text == "Vorlage anwenden":
                # Vorlagen mit Cache abrufen und Inline-Keyboard erstellen
                templates = self.fritz_api.get_templates(use_cache=True)
                user_templates = [t for t in templates if not t.autocreate]
                
                if user_templates:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    
                    keyboard = []
                    for template in user_templates:
                        keyboard.append([InlineKeyboardButton(f"🏠 {template.name}", 
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
                    "Es sind keine benutzerdefinierten Vorlagen in der FritzBox konfiguriert.\n"
                    "Bitte erstelle zuerst Vorlagen in der FritzBox-Weboberfläche.",
                    reply_markup=reply_markup, parse_mode='Markdown')
                return user_data['status']
            
            # Befehls-Text extrahieren
            template_text = text.replace('/applyTemplate ', '').strip()
            
            if not template_text or template_text == "Vorlage anwenden":
                # Vorlagen mit Cache abrufen und Inline-Keyboard erstellen
                templates = self.fritz_api.get_templates(use_cache=True)
                user_templates = [t for t in templates if not t.autocreate]
                
                if user_templates:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    
                    keyboard = []
                    for template in user_templates:
                        keyboard.append([InlineKeyboardButton(f"🏠 {template.name}", 
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
                    "Es sind keine benutzerdefinierten Vorlagen in der FritzBox konfiguriert.\n"
                    "Bitte erstelle zuerst Vorlagen in der FritzBox-Weboberfläche.",
                    reply_markup=reply_markup, parse_mode='Markdown')
                return user_data['status']
            
            # Vorlage anwenden mit optimierter API
            template = self.fritz_api.get_template_by_name(template_text, use_cache=True)
            if template:
                success = self.fritz_api.apply_template(template.identifier)
                
                if success:
                    await update.message.reply_text(f"✅ Vorlage '{template_text}' erfolgreich angewendet",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Fehler beim Anwenden der Vorlage '{template_text}'\n\n"
                        "💡 Überprüfe die Vorlagenkonfiguration in der FritzBox",
                        reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text(f"❌ Vorlage '{template_text}' nicht gefunden\n\n"
                    "💡 Nutze /listTemplates um verfügbare Vorlagen zu sehen",
                    reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Anwenden der Vorlage: {e}")
            await update.message.reply_text(f"❌ Fehler beim Anwenden der Vorlage: {str(e)}",
                reply_markup=user_data['keyboard'])
        
        return user_data['status']
    
    async def handle_scenario_callback(self, update, context):
        """Handler für Szenario-Callback-Buttons mit optimierter API"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('execute_scenario_'):
            scenario_name = query.data.replace('execute_scenario_', '', 1)
            
            try:
                # Login prüfen
                if not self.fritz_api.login():
                    await query.edit_message_text("❌ Fehler: Login bei FritzBox fehlgeschlagen")
                    return
                
                # Szenario ausführen mit optimiertem Manager
                if "Urlaub aktivieren" in scenario_name:
                    result = self.stats_manager.apply_vacation_template(active=True)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt")
                    else:
                        error_msg = result.get('error', 'Unbekannter Fehler')
                        await query.edit_message_text(f"❌ Fehler beim Ausführen des Szenarios: {error_msg}")
                elif "Urlaub deaktivieren" in scenario_name:
                    result = self.stats_manager.apply_vacation_template(active=False)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt")
                    else:
                        error_msg = result.get('error', 'Unbekannter Fehler')
                        await query.edit_message_text(f"❌ Fehler beim Ausführen des Szenarios: {error_msg}")
                else:
                    await query.edit_message_text(f"❌ Unbekanntes Szenario: {scenario_name}")
                    
            except Exception as e:
                logger.error(f"Fehler bei der Szenario-Ausführung: {e}")
                await query.edit_message_text(f"❌ Fehler bei der Szenario-Ausführung: {str(e)}")
        
        elif query.data == 'cancel_scenario':
            await query.edit_message_text("❌ Szenario-Ausführung abgebrochen")
        
        elif query.data.startswith('apply_template_'):
            # Vorlagen-ID und Name extrahieren
            parts = query.data.split('_', 2)
            logger.debug(f"Callback-Data: {query.data}")
            logger.debug(f"Parts nach Split: {parts}")
            
            if len(parts) >= 3:
                template_id = parts[1]
                template_name = parts[2]
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
                # Login prüfen
                if not self.fritz_api.login():
                    await query.edit_message_text("❌ Fehler: Login bei FritzBox fehlgeschlagen\n\n"
                                            "💡 Bitte überprüfe:\n"
                                            "• FritzBox ist erreichbar\n"
                                            "• Zugangsdaten sind korrekt\n"
                                            "• Keine andere Session aktiv")
                    return
                
                # Vorlage mit optimierter API suchen
                template = self.fritz_api.get_template_by_id(template_id, use_cache=True)
                if template:
                    template_name = template.name
                    logger.debug(f"Vorlage gefunden: {template_name}")
                else:
                    logger.warning(f"Vorlage mit ID {template_id} nicht gefunden")
                
                # Vorlage anwenden
                if template:
                    success = self.fritz_api.apply_template(template.identifier)
                    
                    if success:
                        await query.edit_message_text(f"✅ Vorlage '{template_name}' erfolgreich angewendet")
                    else:
                        await query.edit_message_text(f"❌ Fehler beim Anwenden der Vorlage '{template_name}'")
                else:
                    await query.edit_message_text(f"❌ Vorlage mit ID {template_id} nicht gefunden")
                    
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
    
    async def quit(self, update, context, user_data, markupList):
        """Verlässt den Automation Mode"""
        user_data['keyboard'] = markupList['MAIN']  # Annahme: MAIN ist der richtige Key
        await update.message.reply_text("EXIT --AUTOMATIONMODE--",
                reply_markup=user_data['keyboard'])
        user_data['status'] = 'MAIN'  # Annahme: MAIN ist der richtige Status
        return user_data['status']
    
    async def help(self, update, context, user_data, markupList):
        """Zeigt die Hilfe für den Automation Mode an"""
        text = '🤖 **Automation Mode - Hilfe:**\n\n'
        for key, value in textbefehl.items():
            text = text + '- /' + key + ' ' + value + '\n'
        
        text += '\n💡 **Tipp:** Mit diesen Befehlen kannst du FritzBox-Szenarien und Vorlagen verwalten'
        text += '\n🚀 **Performance:** Alle Operationen nutzen Caching für schnellere Antworten'
            
        await update.message.reply_text(text,
                    reply_markup=user_data['keyboard'], parse_mode='Markdown')
        return user_data['status']
    
    def clear_cache(self):
        """Löscht alle Caches"""
        self.fritz_api.clear_cache()
        self.stats_manager.clear_cache()

# Globale Instanz
automation_manager = OptimizedAutomationManager()

# Legacy-Funktionen für Kompatibilität
async def listScenarios(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.list_scenarios(update, context, user_data, markupList)

async def listTemplates(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.list_templates(update, context, user_data, markupList)

async def executeScenario(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.execute_scenario(update, context, user_data, markupList)

async def applyTemplate(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.apply_template(update, context, user_data, markupList)

async def handle_scenario_callback(update, context):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.handle_scenario_callback(update, context)

async def quit(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.quit(update, context, user_data, markupList)

async def help(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.help(update, context, user_data, markupList)
