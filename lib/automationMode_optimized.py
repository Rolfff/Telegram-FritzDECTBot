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
            
            scenarios_text = "Verfügbare Szenarien und Vorlagen:\n\n"
            
            # Echte Szenarien (mit Sub-Templates oder Triggern)
            scenarios = fritz_api.get_scenarios_only(use_cache=True)
            if scenarios:
                scenarios_text += "Szenarien (mehrere Vorlagen kombiniert):\n"
                for scenario in scenarios:
                    scenarios_text += f"  {scenario.name} (ID: {scenario.id})\n"
                    
                    # Sub-Templates anzeigen
                    if scenario.sub_templates:
                        scenarios_text += f"    Enthält {len(scenario.sub_templates)} Vorlage(n)\n"
                    
                    # Trigger anzeigen
                    if scenario.triggers:
                        scenarios_text += f"    Mit {len(scenario.triggers)} Trigger(n)\n"
                    
                    # Geräte-Info anzeigen
                    if scenario.devices:
                        device_names = []
                        for dev in scenario.devices[:3]:  # Max 3 Geräte anzeigen
                            if hasattr(dev, 'name'):
                                device_names.append(f"{dev.name}")
                            else:
                                device_names.append(f"{dev}")  # Falls dev ein String ist
                        if len(scenario.devices) > 3:
                            device_names.append(f"+{len(scenario.devices)-3} weitere")
                        scenarios_text += f"    Geräte: {', '.join(device_names)}\n"
                    scenarios_text += "\n"
            else:
                scenarios_text += "Szenarien: Keine echten Szenarien gefunden\n\n"
            
            # Echte Vorlagen (einzelne Konfigurationen)
            templates = fritz_api.get_templates_only(use_cache=True)
            if templates:
                scenarios_text += "Vorlagen (einzelne Konfigurationen):\n"
                for template in templates:
                    scenarios_text += f"  {template.name} (ID: {template.id})\n"
                    
                    # Geräte-Info anzeigen
                    if template.devices:
                        device_names = []
                        for dev in template.devices[:3]:  # Max 3 Geräte anzeigen
                            if hasattr(dev, 'name'):
                                device_names.append(f"{dev.name}")
                            else:
                                device_names.append(f"{dev}")  # Falls dev ein String ist
                        if len(template.devices) > 3:
                            device_names.append(f"+{len(template.devices)-3} weitere")
                        scenarios_text += f"    Geräte: {', '.join(device_names)}\n"
                    
                    # ApplyMask anzeigen
                    if template.applymask:
                        masks = []
                        for mask_type in ['hkr_temperature', 'hkr_holidays', 'hkr_time_table', 
                                         'relay_manual', 'relay_automatic', 'level', 'color']:
                            if mask_type in template.applymask:
                                masks.append(mask_type.replace('_', ' ').title())
                        if masks:
                            scenarios_text += f"    Funktionen: {', '.join(masks)}\n"
                    scenarios_text += "\n"
            else:
                scenarios_text += "Vorlagen: Keine benutzerdefinierten Vorlagen gefunden\n\n"
            
            # Urlaubsszenarien (spezielle Szenarien)
            vacation_scenarios = fritz_api.get_vacation_scenarios(use_cache=True)
            if vacation_scenarios:
                scenarios_text += "Urlaubsszenarien:\n"
                for vac_scenario in vacation_scenarios:
                    scenarios_text += f"  {vac_scenario.name} (ID: {vac_scenario.id})\n"
                scenarios_text += "\n"
            
            # Spezielle Szenarien (Urlaub etc.)
            scenarios_text += "System-Szenarien:\n"
            scenarios_text += "  Urlaub aktivieren\n"
            scenarios_text += "  Urlaub deaktivieren\n"
            
            scenarios_text += "\nNutze /executeScenario um Szenarien auszuführen"
            scenarios_text += "\nNutze /applyTemplate um Vorlagen anzuwenden"
            
            await update.message.reply_text(scenarios_text,
                reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Szenarien: {e}")
            await update.message.reply_text(f"Fehler: {str(e)}",
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
            
            # Nur echte Vorlagen (keine Szenarien oder Auto-Create)
            templates = fritz_api.get_templates_only(use_cache=True)
            
            if templates:
                for template in templates:
                    templates_text += f"  {template.name}\n"
                    templates_text += f"    ID: {template.id}\n"
                    templates_text += f"    Identifier: {template.identifier}\n"
                    templates_text += f"    Geräte: {len(template.devices)}\n"
                    
                    # ApplyMask anzeigen
                    if template.applymask:
                        masks = []
                        for mask_type in ['hkr_temperature', 'hkr_holidays', 'hkr_time_table', 
                                       'relay_manual', 'relay_automatic', 'level', 'color']:
                            if mask_type in template.applymask:
                                masks.append(mask_type.replace('_', ' ').title())
                        
                        if masks:
                            templates_text += f"    Funktionen: {', '.join(masks)}\n"
                
                templates_text += f"\nInsgesamt {len(templates)} Vorlage(n) gefunden\n"
                templates_text += "Nutze /applyTemplate um eine Vorlage anzuwenden"
            else:
                templates_text += "Keine benutzerdefinierten Vorlagen gefunden.\n\n"
                templates_text += "Tipp: Erstelle Vorlagen in der FritzBox-Weboberfläche\n"
                templates_text += "Szenarien werden unter /listScenarios angezeigt"
            
            await update.message.reply_text(templates_text,
                reply_markup=user_data['keyboard'])
                
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Vorlagen: {e}")
            await update.message.reply_text(f"Fehler: {str(e)}",
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
                # Inline-Keyboard für Szenario-Auswahl dynamisch erstellen
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                
                keyboard = []
                
                # Echte Szenarien (mit Sub-Templates oder Triggern)
                scenarios = fritz_api.get_scenarios_only(use_cache=True)
                if scenarios:
                    keyboard.append([InlineKeyboardButton("Echte Szenarien:", 
                                                           callback_data='no_action')])
                    for scenario in scenarios:
                        # Szenario-Typ bestimmen
                        scenario_type = fritz_api.classify_automation_type(scenario)
                        icon = "  " if scenario_type == "scenario" else "  "
                        safe_name = scenario.name.replace(' ', '_').replace('(', '').replace(')', '')
                        keyboard.append([InlineKeyboardButton(f"{icon} {scenario.name}", 
                                                           callback_data=f'execute_scenario_{scenario.id}_{safe_name}')])
                    keyboard.append([InlineKeyboardButton("", callback_data='no_action')])  # Trennlinie
                
                # Echte Vorlagen (einzelne Konfigurationen)
                templates = fritz_api.get_templates_only(use_cache=True)
                if templates:
                    keyboard.append([InlineKeyboardButton("Verfügbare Vorlagen:", 
                                                           callback_data='no_action')])
                    for template in templates:
                        # Template-Name für Callback sicher machen
                        safe_name = template.name.replace(' ', '_').replace('(', '').replace(')', '')
                        keyboard.append([InlineKeyboardButton(f"  {template.name}", 
                                                           callback_data=f'execute_template_{template.id}_{safe_name}')])
                    keyboard.append([InlineKeyboardButton("", callback_data='no_action')])  # Trennlinie
                
                # Spezielle Szenarien hinzufügen
                keyboard.append([InlineKeyboardButton("Urlaub aktivieren", 
                                                       callback_data='execute_scenario_Urlaub aktivieren')])
                keyboard.append([InlineKeyboardButton("Urlaub deaktivieren", 
                                                       callback_data='execute_scenario_Urlaub deaktivieren')])
                keyboard.append([InlineKeyboardButton("Abbrechen", callback_data='cancel_scenario')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🎯 **Szenario auswählen:**\n\n"
                    "Wähle das Szenario oder die Vorlage, die du ausführen möchtest:",
                    reply_markup=reply_markup, parse_mode='Markdown')
                return user_data['status']
            
            # Befehls-Text extrahieren
            scenario_text = text.replace('/executeScenario ', '').strip()
            
            if not scenario_text or scenario_text == "Szenario ausführen":
                # Inline-Keyboard für Szenario-Auswahl dynamisch erstellen
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                
                keyboard = []
                
                # Vorlagen dynamisch aus der FritzBox laden
                templates = fritz_api.get_templates(use_cache=True)
                if templates:
                    # Nicht automatisch erstellte Vorlagen filtern
                    user_templates = [t for t in templates if not t.autocreate]
                    
                    if user_templates:
                        keyboard.append([InlineKeyboardButton("🏠 **Vorlagen aus der FritzBox:**", 
                                                               callback_data='no_action')])
                        for template in user_templates:
                            # Template-Name für Callback sicher machen
                            safe_name = template.name.replace(' ', '_').replace('(', '').replace(')', '')
                            keyboard.append([InlineKeyboardButton(f"🔧 {template.name}", 
                                                               callback_data=f'execute_template_{template.id}_{safe_name}')])
                        keyboard.append([InlineKeyboardButton("", callback_data='no_action')])  # Trennlinie
                
                # Spezielle Szenarien hinzufügen
                keyboard.append([InlineKeyboardButton("�️ Urlaub aktivieren", 
                                                       callback_data='execute_scenario_Urlaub aktivieren')])
                keyboard.append([InlineKeyboardButton("🏠 Urlaub deaktivieren", 
                                                       callback_data='execute_scenario_Urlaub deaktivieren')])
                keyboard.append([InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_scenario')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🎯 **Szenario auswählen:**\n\n"
                    "Wähle das Szenario oder die Vorlage, die du ausführen möchtest:",
                    reply_markup=reply_markup, parse_mode='Markdown')
                return user_data['status']
            
            # Szenario/Vorlage ausführen
            stats_manager = self._get_stats_manager()
            
            # Prüfen ob es eine Vorlage ist - zuerst ohne Cache für aktuelle Daten
            template = fritz_api.get_template_by_name(scenario_text, use_cache=False)
            if not template:
                # Fallback mit Cache
                template = fritz_api.get_template_by_name(scenario_text, use_cache=True)
            
            if template:
                # Vorlage ausführen
                success = fritz_api.apply_template(template.identifier)
                if success:
                    await update.message.reply_text(f"✅ Vorlage '{template.name}' erfolgreich ausgeführt",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"❌ Fehler beim Ausführen der Vorlage '{template.name}'",
                        reply_markup=user_data['keyboard'])
            elif "Urlaub aktivieren" in scenario_text:
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
                await update.message.reply_text("❌ Unbekanntes Szenario oder Vorlage",
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
            
            # Vorlage anwenden mit optimierter API - zuerst ohne Cache für aktuelle Daten
            template = fritz_api.get_template_by_name(template_text, use_cache=False)
            if not template:
                # Fallback mit Cache
                template = fritz_api.get_template_by_name(template_text, use_cache=True)
            
            if template:
                success = fritz_api.apply_template(template.identifier)
                
                if success:
                    await update.message.reply_text(f"** Vorlage '{template_text}' erfolgreich angewendet",
                        reply_markup=user_data['keyboard'])
                else:
                    await update.message.reply_text(f"** Fehler beim Anwenden der Vorlage '{template_text}'",
                        reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text(f"** Vorlage '{template_text}' nicht gefunden",
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
            if callback_data.startswith('execute_template_'):
                # Template-ID und Name für dynamische Vorlagen-Ausführung extrahieren
                parts = callback_data.replace('execute_template_', '').split('_', 1)
                if len(parts) >= 2:
                    template_id = parts[0].strip()  # Strip whitespace
                    template_safe_name = parts[1]
                    
                    logger.info(f"Looking for template with ID: '{template_id}'")
                    
                    fritz_api = self._get_fritz_api()
                    # Try without cache first to ensure we have fresh data
                    template = fritz_api.get_template_by_id(template_id, use_cache=False)
                    
                    if not template:
                        # Fallback: try with cache
                        template = fritz_api.get_template_by_id(template_id, use_cache=True)
                        logger.warning(f"Template {template_id} not found without cache, trying with cache")
                    
                    if template:
                        logger.info(f"Found template: {template.name} (ID: {template.id})")
                        success = fritz_api.apply_template(template.identifier)
                        
                        if success:
                            await query.edit_message_text(f"✅ Vorlage '{template.name}' erfolgreich ausgeführt",
                                                        reply_markup=None)
                        else:
                            await query.edit_message_text(f"❌ Fehler beim Ausführen der Vorlage '{template.name}'",
                                                        reply_markup=None)
                    else:
                        # Debug: list available template IDs
                        templates = fritz_api.get_templates(use_cache=False)
                        available_ids = [f"{t.id} ({t.name})" for t in templates[:5]]
                        logger.error(f"Template {template_id} not found. Available IDs: {available_ids}")
                        await query.edit_message_text(f"❌ Vorlage nicht gefunden: {template_id}\n\nVerfügbare IDs: {', '.join(available_ids)}",
                                                    reply_markup=None)
                else:
                    await query.edit_message_text("❌ Ungültiges Template-Format",
                                                reply_markup=None)
                    
            elif callback_data.startswith('execute_scenario_'):
                # Szenario-ID und Name extrahieren
                parts = callback_data.replace('execute_scenario_', '').split('_', 1)
                if len(parts) >= 2:
                    scenario_id = parts[0].strip()
                    scenario_safe_name = parts[1]
                    
                    logger.info(f"Looking for scenario with ID: '{scenario_id}'")
                    
                    fritz_api = self._get_fritz_api()
                    # Zuerst ohne Cache suchen
                    scenario = fritz_api.get_template_by_id(scenario_id, use_cache=False)
                    
                    if not scenario:
                        # Fallback mit Cache
                        scenario = fritz_api.get_template_by_id(scenario_id, use_cache=True)
                        logger.warning(f"Scenario {scenario_id} not found without cache, trying with cache")
                    
                    if scenario:
                        scenario_type = fritz_api.classify_automation_type(scenario)
                        logger.info(f"Found scenario: {scenario.name} (Type: {scenario_type})")
                        
                        if scenario_type == "scenario":
                            # Echtes Szenario mit Sub-Templates ausführen
                            success = self._execute_real_scenario(scenario, fritz_api)
                            if success:
                                await query.edit_message_text(f"Szenario '{scenario.name}' erfolgreich ausgeführt",
                                                            reply_markup=None)
                            else:
                                await query.edit_message_text(f"Fehler beim Ausführen des Szenarios '{scenario.name}'",
                                                            reply_markup=None)
                        elif scenario_type == "vacation_scenario":
                            # Urlaubsszenario über stats_manager ausführen
                            stats_manager = self._get_stats_manager()
                            result = stats_manager.apply_vacation_template(active=True)
                            if result['success']:
                                await query.edit_message_text(f"Szenario '{scenario.name}' erfolgreich ausgeführt",
                                                            reply_markup=None)
                            else:
                                await query.edit_message_text(f"Fehler: {result['error']}",
                                                            reply_markup=None)
                        else:
                            # Als Vorlage behandeln
                            success = fritz_api.apply_template(scenario.identifier)
                            if success:
                                await query.edit_message_text(f"Vorlage '{scenario.name}' erfolgreich ausgeführt",
                                                            reply_markup=None)
                            else:
                                await query.edit_message_text(f"Fehler beim Ausführen der Vorlage '{scenario.name}'",
                                                            reply_markup=None)
                    else:
                        # Debug: list available scenario IDs
                        scenarios = fritz_api.get_scenarios_only(use_cache=False)
                        available_ids = [f"{s.id} ({s.name})" for s in scenarios[:5]]
                        logger.error(f"Scenario {scenario_id} not found. Available IDs: {available_ids}")
                        await query.edit_message_text(f"Szenario nicht gefunden: {scenario_id}\n\nVerfügbare Szenarien: {', '.join(available_ids)}",
                                                    reply_markup=None)
                else:
                    # Spezielle Szenarien (Urlaub etc.)
                    scenario_text = callback_data.replace('execute_scenario_', '')
                    stats_manager = self._get_stats_manager()
                    
                    if "Urlaub aktivieren" in scenario_text:
                        result = stats_manager.apply_vacation_template(active=True)
                        if result['success']:
                            await query.edit_message_text("Szenario 'Urlaub aktivieren' erfolgreich ausgeführt",
                                                        reply_markup=None)
                        else:
                            await query.edit_message_text(f"Fehler: {result['error']}",
                                                        reply_markup=None)
                    elif "Urlaub deaktivieren" in scenario_text:
                        result = stats_manager.apply_vacation_template(active=False)
                        if result['success']:
                            await query.edit_message_text("Szenario 'Urlaub deaktivieren' erfolgreich ausgeführt",
                                                        reply_markup=None)
                        else:
                            await query.edit_message_text(f"Fehler: {result['error']}",
                                                        reply_markup=None)
                    else:
                        await query.edit_message_text("Unbekanntes Szenario",
                                                    reply_markup=None)
                    
            elif callback_data.startswith('apply_template_'):
                # Template-ID und Name extrahieren
                parts = callback_data.replace('apply_template_', '').split('_', 1)
                if len(parts) >= 2:
                    template_id = parts[0].strip()  # Strip whitespace
                    template_name = parts[1]
                    
                    logger.info(f"Looking for template to apply with ID: '{template_id}'")
                    
                    fritz_api = self._get_fritz_api()
                    # Try without cache first to ensure we have fresh data
                    template = fritz_api.get_template_by_id(template_id, use_cache=False)
                    
                    if not template:
                        # Fallback: try with cache
                        template = fritz_api.get_template_by_id(template_id, use_cache=True)
                        logger.warning(f"Template {template_id} not found without cache, trying with cache")
                    
                    if template:
                        logger.info(f"Found template to apply: {template.name} (ID: {template.id})")
                        success = fritz_api.apply_template(template.identifier)
                        
                        if success:
                            await query.edit_message_text(f"** Vorlage '{template_name}' erfolgreich angewendet",
                                                        reply_markup=None)
                        else:
                            await query.edit_message_text(f"** Fehler beim Anwenden der Vorlage '{template_name}'",
                                                        reply_markup=None)
                    else:
                        # Debug: list available template IDs
                        templates = fritz_api.get_templates(use_cache=False)
                        available_ids = [f"{t.id} ({t.name})" for t in templates[:5]]
                        logger.error(f"Template {template_id} not found for apply. Available IDs: {available_ids}")
                        await query.edit_message_text(f"** Vorlage nicht gefunden: {template_id}\n\nVerfügbare IDs: {', '.join(available_ids)}",
                                                    reply_markup=None)
                else:
                    await query.edit_message_text("** Ungültiges Template-Format",
                                                reply_markup=None)
                    
            elif callback_data == 'cancel_scenario' or callback_data == 'cancel_template' or callback_data == 'no_action':
                if callback_data == 'no_action':
                    # Keine Aktion für Header-Buttons
                    await query.answer("Keine Aktion")
                else:
                    await query.edit_message_text("❌ Aktion abgebrochen",
                                                reply_markup=None)
                
        except Exception as e:
            logger.error(f"Fehler in handle_scenario_callback: {e}")
            await query.edit_message_text(f"❌ Fehler: {str(e)}",
                                        reply_markup=None)
        
        return user_data['status']
    
    def _execute_real_scenario(self, scenario: 'TemplateInfo', fritz_api: 'OptimizedFritzBoxAPI') -> bool:
        """Führt ein echtes Szenario mit Sub-Templates aus"""
        try:
            logger.info(f"Executing real scenario: {scenario.name}")
            
            # Sub-Templates ausführen
            if scenario.sub_templates:
                for sub_template_id in scenario.sub_templates:
                    sub_template = fritz_api.get_template_by_id(sub_template_id, use_cache=False)
                    if sub_template:
                        logger.info(f"Executing sub-template: {sub_template.name}")
                        success = fritz_api.apply_template(sub_template.identifier)
                        if not success:
                            logger.error(f"Failed to execute sub-template: {sub_template.name}")
                            return False
                    else:
                        logger.error(f"Sub-template not found: {sub_template_id}")
                        return False
            
            # Trigger aktivieren (falls vorhanden)
            if scenario.triggers:
                for trigger_id in scenario.triggers:
                    logger.info(f"Activating trigger: {trigger_id}")
                    # Hier könnte Trigger-Logik implementiert werden
                    # Für jetzt nur loggen
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing real scenario {scenario.name}: {e}")
            return False
    
    def get_callback_handlers(self):
        """Gibt Callback-Handler für Inline-Keyboards zurück - Framework-konform"""
        return {
            'patterns': [
                r'execute_template_.*',  # Für dynamische Vorlagen-Ausführung
                r'execute_scenario_.*',  # Für spezielle Szenarien (Urlaub etc.)
                r'apply_template_.*',    # Für Vorlagen-Anwendung
                r'cancel_scenario',       # Für Abbruch
                r'cancel_template',       # Für Abbruch
                r'no_action'              # Für Header-Buttons ohne Aktion
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
