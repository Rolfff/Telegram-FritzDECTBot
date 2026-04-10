#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Optional
from lib.fritzbox_api_optimized import OptimizedFritzBoxAPI, TemplateInfo
# Importiere Konstanten
from lib.config import AUTOMATION, MAIN

# Logger initialisieren
logger = logging.getLogger(__name__)

# Tastatur-Befehle
tastertur = {
    'listScenarios': 'Szenarien anzeigen',
    'listTemplates': 'Vorlagen anzeigen',
    'executeScenario': 'Szenario ausführen',
    'applyTemplate': 'Vorlage anwenden',
    'back': 'Zurück'
}

# Funktionen Map
textbefehl = {
    'listScenarios': 'Zeigt alle verfügbaren Szenarien an',
    'listTemplates': 'Zeigt alle verfügbaren Vorlagen an',
    'executeScenario': 'Führt ein ausgewähltes Szenario aus',
    'applyTemplate': 'Wendet eine ausgewählte Vorlage an',
    'back': 'Wechselt zurück ins Main-Menu'
}

class OptimizedAutomationManager:
    """Optimierter Automation-Manager mit performanter AHA-Schnittstelle"""
    
    def __init__(self):
        self.fritz_api = None
        self.stats_manager = None
    
    def _get_stats_manager(self):
        """Lazy initialization of stats_manager"""
        if self.stats_manager is None:
            from lib.statistikMode_optimized import stats_manager
            self.stats_manager = stats_manager
        return self.stats_manager
    
    def _get_fritz_api(self):
        """Lazy initialization of fritz_api"""
        if self.fritz_api is None:
            self.fritz_api = OptimizedFritzBoxAPI()
        return self.fritz_api
    
    async def list_scenarios(self, update, context, user_data, markupList):
        """Zeigt alle verfügbaren Szenarien mit optimierter API"""
        try:
            # Login prüfen
            fritz_api = self._get_fritz_api()
            if not fritz_api.login():
                await update.message.reply_text("Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            scenarios_text = "Verfügbare Szenarien:\n\n"
            scenarios_found = []
            
            # Vorlagen als Szenarien interpretieren (optimiert mit Cache)
            templates = fritz_api.get_templates(use_cache=True)
            if templates:
                scenarios_text += "Vorlagen (als Szenarien verwendbar):\n"
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
            fritz_api = self._get_fritz_api()
            if not fritz_api.login():
                await update.message.reply_text("Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            templates_text = "Verfügbare Vorlagen:\n\n"
            
            # Vorlagen mit Cache abrufen
            templates = fritz_api.get_templates(use_cache=True)
            
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
            fritz_api = self._get_fritz_api()
            if not fritz_api.login():
                await update.message.reply_text("Fehler: Login bei FritzBox fehlgeschlagen",
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
            stats_manager = self._get_stats_manager()
            if "Urlaub aktivieren" in scenario_text:
                result = stats_manager.apply_vacation_template(active=True)
                if result['success']:
                    await update.message.reply_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Fehler beim Ausführen des Szenarios: {result['error']}",
                        reply_markup=user_data['keyboard'])
            elif "Urlaub deaktivieren" in scenario_text:
                result = stats_manager.apply_vacation_template(active=False)
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
            fritz_api = self._get_fritz_api()
            if not fritz_api.login():
                await update.message.reply_text("Fehler: Login bei FritzBox fehlgeschlagen",
                    reply_markup=user_data['keyboard'])
                return user_data['status']
            
            # Text des Befehls extrahieren
            text = update.message.text
            
            # Prüfen ob es ein Button-Klick ist
            if text == "Vorlage anwenden":
                # Inline-Keyboard für Vorlagen-Auswahl erstellen
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                
                # Vorlagen abrufen
                templates = fritz_api.get_templates(use_cache=True)
                user_templates = [t for t in templates if not t.autocreate] if templates else []
                
                keyboard = []
                for template in user_templates:
                    keyboard.append([InlineKeyboardButton(f"🏠 {template.name}", 
                                                       callback_data=f'apply_template_{template.id}_{template.name}')])
                    
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
            template = fritz_api.get_template_by_name(template_text, use_cache=True)
            if template:
                success = fritz_api.apply_template(template.identifier)
                
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
    
    async def back(self, update, context, user_data, markupList):
        """Wechselt zurück ins Main-Menu"""
        context.user_data['keyboard'] = markupList[MAIN]
        context.user_data['status'] = MAIN
        
        await update.message.reply_text(
            "🔙 Zurück zum Hauptmenü",
            reply_markup=context.user_data['keyboard']
        )
        return MAIN
    
    async def default(self, update, context, user_data, markupList):
        """Default-Funktion für Automation-Modus - Framework-konform"""
        context.user_data['keyboard'] = markupList[AUTOMATION]
        context.user_data['status'] = AUTOMATION
        
        help_text = "🤖 **Automation-Modus**\n\n"
        help_text += "Verfügbare Funktionen:\n"
        for key, value in textbefehl.items():
            help_text += f"• {value}\n"
        help_text += "\n💡 Nutze /help für alle Befehle"
        
        await update.message.reply_text(help_text, reply_markup=context.user_data['keyboard'])
        return context.user_data['status']
    
    async def help(self, update, context, user_data, markupList):
        """Zeigt Hilfe für Automation-Modus"""
        help_text = "🤖 **Automation-Modus - Hilfe**\n\n"
        help_text += "Verfügbare Befehle:\n"
        for key, value in textbefehl.items():
            help_text += f"- /{key} {value}\n"
        
        await update.message.reply_text(help_text, reply_markup=user_data['keyboard'])
        return user_data['status']
    
    async def handle_scenario_callback(self, update, context, user_data, markupList):
        """Handler für Szenario-Callback-Buttons mit optimierter API - Framework-konform"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        try:
            if callback_data.startswith('execute_scenario_'):
                scenario_text = callback_data.replace('execute_scenario_', '')
                
                if "Urlaub aktivieren" in scenario_text:
                    stats_manager = self._get_stats_manager()
                    result = stats_manager.apply_vacation_template(active=True)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub aktivieren' erfolgreich ausgeführt",
                                                    reply_markup=user_data['keyboard'])
                    else:
                        await query.edit_message_text(f"❌ Fehler: {result['error']}",
                                                    reply_markup=user_data['keyboard'])
                elif "Urlaub deaktivieren" in scenario_text:
                    result = stats_manager.apply_vacation_template(active=False)
                    if result['success']:
                        await query.edit_message_text("✅ Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt",
                                                    reply_markup=user_data['keyboard'])
                    else:
                        await query.edit_message_text(f"❌ Fehler: {result['error']}",
                                                    reply_markup=user_data['keyboard'])
                else:
                    await query.edit_message_text("❌ Unbekanntes Szenario",
                                                reply_markup=user_data['keyboard'])
                    
            elif callback_data.startswith('apply_template_'):
                # Template-ID und Name extrahieren
                parts = callback_data.replace('apply_template_', '').split('_', 1)
                if len(parts) >= 2:
                    template_id = parts[0]
                    template_name = parts[1]
                    
                    fritz_api = self._get_fritz_api()
                    template = fritz_api.get_template_by_id(template_id, use_cache=True)
                    if template:
                        success = fritz_api.apply_template(template.identifier)
                        
                        if success:
                            await query.edit_message_text(f"✅ Vorlage '{template_name}' erfolgreich angewendet",
                                                        reply_markup=user_data['keyboard'])
                        else:
                            await query.edit_message_text(f"❌ Fehler beim Anwenden der Vorlage '{template_name}'",
                                                        reply_markup=user_data['keyboard'])
                    else:
                        await query.edit_message_text(f"❌ Vorlage nicht gefunden: {template_id}",
                                                    reply_markup=user_data['keyboard'])
                else:
                    await query.edit_message_text("❌ Ungültiges Template-Format",
                                                reply_markup=user_data['keyboard'])
                    
            elif callback_data == 'cancel_scenario' or callback_data == 'cancel_template':
                await query.edit_message_text("❌ Aktion abgebrochen",
                                            reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler in handle_scenario_callback: {e}")
            await query.edit_message_text(f"❌ Fehler: {str(e)}",
                                        reply_markup=user_data['keyboard'])
        
        return user_data['status']
    
    def get_callback_handlers(self):
        """Gibt Callback-Handler für Inline-Keyboards zurück - Framework-konform"""
        return {
            'patterns': [
                r'execute_scenario_.*',
                r'apply_template_.*',
                r'cancel_scenario',
                r'cancel_template'
            ],
            'handler': self.handle_scenario_callback
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

async def back(update, context, user_data, markupList):
    """Legacy-Funktion - verwendet optimierten Manager"""
    return await automation_manager.back(update, context, user_data, markupList)

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
    async def back(update, context, user_data, markupList):
        """Legacy-Funktion - delegiert zur globalen Instanz"""
        return await automation_manager.back(update, context, user_data, markupList)
    
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
