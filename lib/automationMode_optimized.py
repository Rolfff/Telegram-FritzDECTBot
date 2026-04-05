#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Optional
from lib.fritzbox_api_optimized import OptimizedFritzBoxAPI, TemplateInfo
from lib.statistikMode_optimized import stats_manager
# Importiere Konstanten
from lib.config import AUTOMATION

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
            
            scenarios_text = "📋 Verfügbare Szenarien:\n\n"
            scenarios_found = []
            
            # Vorlagen als Szenarien interpretieren (optimiert mit Cache)
            templates = self.fritz_api.get_templates(use_cache=True)
            if templates:
                scenarios_text += "🏠 Vorlagen (als Szenarien verwendbar):\n"
                for template in templates:
                    # Nur Szenarien anzeigen (mit sub_templates)
                    if template.sub_templates:
                        scenarios_found.append(f"• {template.name} (ID: {template.id})")
            
            # Manuelles Urlaubs-Szenario
            scenarios_text += "\n🏖️ Urlaubs-Szenarien:\n"
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
                reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Szenarien: {e}")
            await update.message.reply_text(f"❌ Fehler: {str(e)}",
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
            
            templates_text = "📋 Verfügbare Vorlagen:\n\n"
            
            # Vorlagen mit Cache abrufen
            templates = self.fritz_api.get_templates(use_cache=True)
            
            if templates:
                # Nicht automatisch erstellte Vorlagen filtern
                user_templates = [t for t in templates if not t.autocreate]
                
                if user_templates:
                    for template in user_templates:
                        templates_text += f"🏠 {template.name}\n"
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
                    
                    templates_text += f"💡 Insgesamt {len(user_templates)} Vorlage(n) gefunden\n"
                    templates_text += "💡 Nutze /applyTemplate um eine Vorlage anzuwenden"
                else:
                    templates_text += "Keine benutzerdefinierten Vorlagen gefunden.\n\n"
                    templates_text += "💡 Automatisch erstellte Vorlagen werden ausgeblendet.\n"
                    templates_text += "💡 Erstelle Vorlagen in der FritzBox-Weboberfläche"
            
            await update.message.reply_text(templates_text,
                reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Vorlagen: {e}")
            await update.message.reply_text(f"❌ Fehler: {str(e)}",
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
                    "🎯 Szenario auswählen:\n\n"
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
                    "🎯 Szenario auswählen:\n\n"
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
                    await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios: {result['error']}",
                        reply_markup=user_data['keyboard'])
            elif "Urlaub deaktivieren" in scenario_text:
                result = self.stats_manager.apply_vacation_template(active=False)
                if result['success']:
                    await update.message.reply_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios: {result['error']}",
                        reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("❌ Unbekanntes Szenario",
                    reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler bei Szenario-Ausführung: {e}")
            await update.message.reply_text(f"❌ Fehler: {str(e)}",
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
            
            # Text des Befehls extrahieren
            text = update.message.text
            
            # Prüfen ob es ein Button-Klick ist
            if text == "Vorlage anwenden":
                # Inline-Keyboard für Vorlagen-Auswahl erstellen
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                
                keyboard = []
                for template in user_templates:
                    keyboard.append([InlineKeyboardButton(f"🏠 {template.name}", 
                                                       callback_data=f'apply_template_{template["id"]}_{template["name"]}')])
                    
                keyboard.append([InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_template')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🎯 Vorlage auswählen:\n\n"
                    "Wähle die Vorlage, die du anwenden möchtest:",
                    reply_markup=reply_markup, parse_mode='Markdown')
                return user_data['status']
            
            # Befehls-Text extrahieren
            template_text = text.replace('/applyTemplate ', '').strip()
            
            if not template_text or template_text == "Vorlage anwenden":
                await update.message.reply_text("❌ Keine Vorlage angegeben",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            # Vorlage anwenden mit optimierter API
            template = self.fritz_api.get_template_by_name(template_text, use_cache=True)
            if template:
                success = self.fritz_api.apply_template(template.identifier)
                
                if success:
                    await update.message.reply_text(f"✅ Vorlage '{template_text}' erfolgreich angewendet",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Fehler beim Anwenden der Vorlage '{template_text}'",
                        reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text(f"❌ Vorlage '{template_text}' nicht gefunden",
                    reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Anwenden der Vorlage: {e}")
            await update.message.reply_text(f"❌ Fehler: {str(e)}",
                reply_markup=user_data['keyboard'])
        return user_data['status']
    
    async def quit(self, update, context, user_data, markupList):
        """Verlässt den Automation-Modus"""
        user_data['keyboard'] = markupList[MAIN]
        user_data['status'] = MAIN
        await update.message.reply_text("🔙 Zurück zum Hauptmenü",
            reply_markup=markupList[MAIN])
        return MAIN
    
    async def default(self, update, context, user_data, markupList):
        """Default-Funktion für Automation-Modus"""
        help_text = "🤖 Automation-Modus\n\n"
        help_text += "Verfügbare Befehle:\n"
        for key, value in textbefehl.items():
            help_text += f"• /{key} - {value}\n"
        help_text += "\n💡 Nutze /help für detaillierte Hilfe"
        
        await update.message.reply_text(help_text, reply_markup=user_data.get('keyboard'))
        return user_data.get('status', AUTOMATION)
    
    async def default(self, update, context, user_data, markupList):
        """Default-Funktion für Automation-Modus"""
        help_text = "🤖 Automation-Modus\n\n"
        help_text += "Verfügbare Befehle:\n"
        for key, value in textbefehl.items():
            help_text += f"• /{key} - {value}\n"
        help_text += "\n💡 Nutze /help für detaillierte Hilfe"
        
        await update.message.reply_text(help_text, reply_markup=user_data.get('keyboard'))
        return user_data.get('status', AUTOMATION)
    
    async def help(self, update, context, user_data, markupList):
        """Zeigt Hilfe für Automation-Modus"""
        help_text = ""
        for key, value in textbefehl.items():
            help_text += f"- /{key} {value}\n"
        
    
    async def default(self, update, context, user_data, markupList):
        """Default-Funktion für Automation-Modus"""
        help_text = "🤖 Automation-Modus\n\n"
        help_text += "Verfügbare Befehle:\n"
        for key, value in textbefehl.items():
            help_text += f"• /{key} - {value}\n"
        help_text += "\n💡 Nutze /help für detaillierte Hilfe"
        
        await update.message.reply_text(help_text, reply_markup=user_data.get('keyboard'))
        return user_data.get('status', AUTOMATION)
    
    async def handle_scenario_callback(self, update, context, user_data, markupList):
        """Handler für Szenario-Callback-Buttons mit optimierter API"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        try:
            if callback_data.startswith('execute_scenario_'):
                scenario_text = callback_data.replace('execute_scenario_', '')
                
                if "Urlaub aktivieren" in scenario_text:
                    result = self.stats_manager.apply_vacation_template(active=True)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt")
                    else:
                        await query.edit_message_text(f"❌ Fehler: {result['error']}")
                elif "Urlaub deaktivieren" in scenario_text:
                    result = self.stats_manager.apply_vacation_template(active=False)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt")
                    else:
                        await query.edit_message_text(f"❌ Fehler: {result['error']}")
                else:
                    await query.edit_message_text("❌ Unbekanntes Szenario")
                    
            elif callback_data.startswith('apply_template_'):
                # Template-ID und Name extrahieren
                parts = callback_data.replace('apply_template_', '').split('_', 1)
                if len(parts) >= 2:
                    template_id = parts[0]
                    template_name = parts[1]
                    
                    template = self.fritz_api.get_template_by_id(template_id, use_cache=True)
                    if template:
                        success = self.fritz_api.apply_template(template.identifier)
                        
                        if success:
                            await query.edit_message_text(f"✅ Vorlage '{template_name}' erfolgreich angewendet")
                        else:
                            await query.edit_message_text(f"❌ Fehler beim Anwenden der Vorlage '{template_name}'")
                    else:
                        await query.edit_message_text(f"❌ Vorlage nicht gefunden: {template_id}")
                else:
                    await query.edit_message_text("❌ Ungültiges Template-Format")
                    
            elif callback_data == 'cancel_scenario' or callback_data == 'cancel_template':
                await query.edit_message_text("❌ Aktion abgebrochen")
                
        except Exception as e:
            logger.error(f"Fehler in handle_scenario_callback: {e}")
            await query.edit_message_text(f"❌ Fehler: {str(e)}")
        
        return context.user_data.get('status', MAIN)
    
    def get_callback_handlers(self):
        """Gibt Callback-Handler für Inline-Keyboards zurück"""
        return {
            'handler': self.handle_scenario_callback,
            'patterns': [
                r'execute_scenario_.*',
                r'apply_template_.*',
                r'cancel_scenario',
                r'cancel_template'
            ]
        }

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

async def quit(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.quit(update, context, user_data, markupList)

async def help(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.help(update, context, user_data, markupList)

async def handle_scenario_callback(update, context):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.handle_scenario_callback(update, context)

# Klasse für Kompatibilität mit fritzdect_bot.py
class AutomationModeOptimized:
    """Wrapper-Klasse für Kompatibilität mit dem Bot-Framework"""
    
    # Tastatur-Befehle und Textbefehle für Kompatibilität
    tastertur = tastertur
    textbefehl = textbefehl
    
    @staticmethod
    async def default(update, context, user_data, markupList):
        """Default-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.default(update, context, user_data, markupList)
    
    @staticmethod
    async def listScenarios(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.list_scenarios(update, context, user_data, markupList)
    
    @staticmethod
    async def listTemplates(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.list_templates(update, context, user_data, markupList)
    
    @staticmethod
    async def executeScenario(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.execute_scenario(update, context, user_data, markupList)
    
    @staticmethod
    async def applyTemplate(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.apply_template(update, context, user_data, markupList)
    
    @staticmethod
    async def quit(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.quit(update, context, user_data, markupList)
    
    @staticmethod
    async def help(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.help(update, context, user_data, markupList)
    
    @staticmethod
    def get_callback_handlers():
        """Gibt Callback-Handler für Inline-Keyboards zurück"""
        return automation_manager.get_callback_handlers()
    
    @staticmethod
    async def handle_scenario_callback(update, context, user_data, markupList):
        """Handler für Szenario-Callbacks - delegiert zur globalen Instanz"""
        return await automation_manager.handle_scenario_callback(update, context, user_data, markupList)
