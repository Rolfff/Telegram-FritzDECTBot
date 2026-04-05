# Telegram Importe mit Fallback für Tests
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    TELEGRAM_AVAILABLE = False
    print("WARNING: telegram module nicht gefunden - SettingsMode läuft im Test-Modus")

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

# Importiere Konstanten
from lib.config import SETTINGS, MAIN

# Globale Datenbank-Instanz
db = None

def set_database(database_instance):
    """Setzt die globale Datenbank-Instanz"""
    global db
    db = database_instance


def get_callback_handlers():
    """Gibt die Callback-Handler-Konfiguration für SettingsMode zurück"""
    return {
        'patterns': [
            r'set_language_.*',
            r'toggle_vacation_.*',
            r'toggle_power_.*',
            r'toggle_door_.*',
            r'cancel_language_.*',
            r'back_settings_.*'
        ],
        'handler': SettingsMode.handle_settings_callback
    }


# Funktionen hier registrieren für Settings-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {
    'language': 'Sprache ändern',
    'notifications': 'Benachrichtigungen',
    'back': 'Zurück'
}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {
    'language': 'Ändert die Sprache des Bots',
    'notifications': 'Konfiguriert Benachrichtigungseinstellungen',
    'back': 'Wechselt zurück ins Main-Menu'
}


async def default(update, context, user_data, markupList):
    """Default-Funktion für Settings-Mode"""
    """Wechselt in den Settings-Modus"""
    context.user_data['keyboard'] = markupList[SETTINGS]
    context.user_data['status'] = SETTINGS
    await update.message.reply_text("-->SETTINGSMODE<--\n\n⚙️ Verfügbare Funktionen:\n"
                                  "• Sprache ändern (🇩🇪🇬🇧🇷🇺🇫🇷🇪🇸)\n"
                                  "• Benachrichtigungen konfigurieren\n"
                                  "• Zurück zum Hauptmenü", reply_markup=markupList[SETTINGS])
    return context.user_data['status']


async def language(update, context, user_data, markupList):
    """Zeigt Sprachauswahl mit Inline-Buttons"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
    
    try:
        chat_id = int(user_data['chatId'])  # Sicherstellen, dass es ein Integer ist
        current_language = db.get_user_language(chat_id)
        print(f"DEBUG: Loading language for chat_id: {chat_id}, current language: {current_language}")
        
        # Sprach-Optionen mit Flag-Emojis
        keyboard = [
            [InlineKeyboardButton("🇩🇪 Deutsch", callback_data=f'set_language_de_{chat_id}')],
            [InlineKeyboardButton("🇬🇧 English", callback_data=f'set_language_en_{chat_id}')],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data=f'set_language_ru_{chat_id}')],
            [InlineKeyboardButton("🇫🇷 Français", callback_data=f'set_language_fr_{chat_id}')],
            [InlineKeyboardButton("🇪🇸 Español", callback_data=f'set_language_es_{chat_id}')],
            [InlineKeyboardButton("❌ Abbrechen", callback_data=f'cancel_language_{chat_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Aktuelle Sprache anzeigen
        language_names = {
            'de': '🇩🇪 Deutsch',
            'en': '🇬🇧 English', 
            'ru': '🇷🇺 Русский',
            'fr': '🇫🇷 Français',
            'es': '🇪🇸 Español'
        }
        
        current_display = language_names.get(current_language, f"🌐 {current_language.upper()}")
        print(f"DEBUG: Current language display: {current_display}")
        
        await update.message.reply_text(
            f"🌐 Spracheinstellungen\n\n"
            f"Aktuelle Sprache: {current_display}\n\n"
            f"Wähle eine neue Sprache:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler: {str(e)}", reply_markup=user_data['keyboard'])
    
    return user_data['status']


async def notifications(update, context, user_data, markupList):
    """Zeigt Benachrichtigungseinstellungen"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
    
    try:
        chat_id = int(user_data['chatId'])  # Sicherstellen, dass es ein Integer ist
        print(f"DEBUG: Loading notifications for chat_id: {chat_id}")
        
        # Aktuelle Benachrichtigungseinstellungen holen
        notification_settings = db.get_notification_settings(chat_id)
        print(f"DEBUG: Notification settings from DB: {notification_settings}")
        
        if notification_settings:
            vacation_mode = notification_settings.get('notifyVacationMode', True)
            door_power_meter = notification_settings.get('notifyDoorPowerMeter', True)
            door_front_door = notification_settings.get('notifyDoorFrontDoor', True)
        else:
            # Standardwerte wenn nicht gefunden
            vacation_mode = door_power_meter = door_front_door = True
            print("DEBUG: Using default notification settings")
        
        print(f"DEBUG: Final values - Vacation: {vacation_mode}, Power: {door_power_meter}, Door: {door_front_door}")
        
        # Inline-Buttons für Benachrichtigungen
        keyboard = []
        
        # Urlaubsschaltung
        vacation_text = "✅ Aktiv" if vacation_mode else "❌ Inaktiv"
        keyboard.append([InlineKeyboardButton(
            f"🏖️ Urlaubsschaltung: {vacation_text}", 
            callback_data=f'toggle_vacation_{chat_id}'
        )])
        
        # Tür-Stromzähler
        power_text = "✅ Aktiv" if door_power_meter else "❌ Inaktiv"
        keyboard.append([InlineKeyboardButton(
            f"⚡ Tür-Stromzähler: {power_text}", 
            callback_data=f'toggle_power_{chat_id}'
        )])
        
        # Haustür
        door_text = "✅ Aktiv" if door_front_door else "❌ Inaktiv"
        keyboard.append([InlineKeyboardButton(
            f"🚪 Haustür: {door_text}", 
            callback_data=f'toggle_door_{chat_id}'
        )])
        
        # Zurück-Button
        keyboard.append([InlineKeyboardButton("🔙 Zurück", callback_data=f'back_settings_{chat_id}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔔 Benachrichtigungseinstellungen\n\n"
            "Wähle aus, welche Benachrichtigungen du erhalten möchtest:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler: {str(e)}", reply_markup=user_data['keyboard'])
    
    return user_data['status']


async def back(update, context, user_data, markupList):
    """Wechselt zurück ins Main-Menu"""
    user_data['keyboard'] = markupList[MAIN]
    user_data['status'] = MAIN
    await update.message.reply_text(
            "🔙 Zurück zum Hauptmenü",
            reply_markup=markupList[MAIN]
        ) 
    return MAIN





async def handle_settings_callback(update, context, user_data, markupList):
    """Verarbeitet Callbacks von Inline-Buttons im Settings-Mode"""
    global db
    if db is None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Datenbank nicht verfügbar")
        return user_data['status']
    
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = update.effective_user.id
    
    try:
        if callback_data.startswith('set_language_'):
            # Sprache setzen
            lang = callback_data.replace('set_language_', '')
            print(f"DEBUG: Raw callback_data: {callback_data}")
            print(f"DEBUG: Extracted lang: '{lang}'")
            
            # Stelle sicher, dass nur der Sprachcode verwendet wird (falls zusätzliche Daten anhängen)
            lang = lang.split('_')[0]  # Nur den Teil vor dem ersten Unterstrich verwenden
            print(f"DEBUG: Cleaned lang: '{lang}'")
            print(f"DEBUG: Database instance: {db}")
            print(f"DEBUG: User ID: {user_id}")
            
            if db is None:
                print("ERROR: Database instance is None!")
                await query.edit_message_text("❌ Datenbank nicht verfügbar")
                return user_data['status']
            
            success = db.update_user_language(user_id, lang)
            print(f"DEBUG: Language update result: {success}")
            
            # Debug: Überprüfen ob die Änderung in der DB ankam
            db.debug_user_settings(user_id)
            
            if success:
                lang_names = {'de': 'Deutsch', 'en': 'English', 'fr': 'Français', 'es': 'Español'}
                display_name = lang_names.get(lang, lang.upper())
                await query.edit_message_text(
                    f"✅ Sprache geändert zu {display_name}"
                )
            else:
                await query.edit_message_text("❌ Sprachänderung fehlgeschlagen")
                
        elif callback_data.startswith('toggle_vacation_'):
            # Urlaub-Benachrichtigungen umschalten
            enabled = callback_data.endswith('_on')
            print(f"DEBUG: Setting vacation notifications for user {user_id} to {enabled}")
            print(f"DEBUG: Database instance: {db}")
            
            if db is None:
                print("ERROR: Database instance is None!")
                await query.edit_message_text("❌ Datenbank nicht verfügbar")
                return user_data['status']
            
            success = db.update_notification_setting(user_id, 'notifyVacationMode', enabled)
            print(f"DEBUG: Vacation notification update result: {success}")
            
            # Debug: Überprüfen ob die Änderung in der DB ankam
            db.debug_user_settings(user_id)
            
            if success:
                status = "aktiviert" if enabled else "deaktiviert"
                await query.edit_message_text(f"✅ Urlaub-Benachrichtigungen {status}")
            else:
                await query.edit_message_text("❌ Einstellung konnte nicht gespeichert werden")
                
        elif callback_data.startswith('toggle_power_'):
            # Stromausfall-Benachrichtigungen umschalten
            enabled = callback_data.endswith('_on')
            print(f"DEBUG: Setting power notifications for user {user_id} to {enabled}")
            print(f"DEBUG: Database instance: {db}")
            
            if db is None:
                print("ERROR: Database instance is None!")
                await query.edit_message_text("❌ Datenbank nicht verfügbar")
                return user_data['status']
            
            success = db.update_notification_setting(user_id, 'notifyDoorPowerMeter', enabled)
            print(f"DEBUG: Power notification update result: {success}")
            
            # Debug: Überprüfen ob die Änderung in der DB ankam
            db.debug_user_settings(user_id)
            
            if success:
                status = "aktiviert" if enabled else "deaktiviert"
                await query.edit_message_text(f"✅ Stromausfall-Benachrichtigungen {status}")
            else:
                await query.edit_message_text("❌ Einstellung konnte nicht gespeichert werden")
                
        elif callback_data.startswith('toggle_door_'):
            # Tür-Öffnungs-Benachrichtigungen umschalten
            enabled = callback_data.endswith('_on')
            print(f"DEBUG: Setting door notifications for user {user_id} to {enabled}")
            print(f"DEBUG: Database instance: {db}")
            
            if db is None:
                print("ERROR: Database instance is None!")
                await query.edit_message_text("❌ Datenbank nicht verfügbar")
                return user_data['status']
            
            success = db.update_notification_setting(user_id, 'notifyDoorFrontDoor', enabled)
            print(f"DEBUG: Door notification update result: {success}")
            
            # Debug: Überprüfen ob die Änderung in der DB ankam
            db.debug_user_settings(user_id)
            
            if success:
                status = "aktiviert" if enabled else "deaktiviert"
                await query.edit_message_text(f"✅ Tür-Öffnungs-Benachrichtigungen {status}")
            else:
                await query.edit_message_text("❌ Einstellung konnte nicht gespeichert werden")
                
        elif callback_data.startswith('cancel_language_'):
            await query.edit_message_text("❌ Sprachänderung abgebrochen")
                
        elif callback_data.startswith('back_settings_'):
            # Zurück zu den Einstellungen
            await query.edit_message_text("🔙 Zurück zu den Einstellungen")
               
    except Exception as e:
        await query.edit_message_text(f"❌ Fehler: {str(e)}")
                        
    return user_data['status']

# Klasse für Kompatibilität mit fritzdect_bot.py
class SettingsMode:
    """Wrapper-Klasse für Kompatibilität mit dem Bot-Framework"""
    
    # Tastatur-Befehle und Textbefehle für Kompatibilität
    tastertur = tastertur
    textbefehl = textbefehl
    
    @staticmethod
    async def default(update, context, user_data, markupList):
        """Default-Funktion - delegiert zur globalen Funktion"""
        return await default(update, context, user_data, markupList)
    
    @staticmethod
    async def language(update, context, user_data, markupList):
        """Sprache ändern - delegiert zur globalen Funktion"""
        return await language(update, context, user_data, markupList)
    
    @staticmethod
    async def notifications(update, context, user_data, markupList):
        """Benachrichtigungen - delegiert zur globalen Funktion"""
        return await notifications(update, context, user_data, markupList)
    
    @staticmethod
    async def back(update, context, user_data, markupList):
        """Zurück - delegiert zur globalen Funktion"""
        return await back(update, context, user_data, markupList)
    
    @staticmethod
    def get_callback_handlers():
        """Gibt Callback-Handler für Inline-Keyboards zurück"""
        return get_callback_handlers()
    
    @staticmethod
    async def handle_settings_callback(update, context, user_data, markupList):
        """Handler für Settings-Callbacks - delegiert zur globalen Funktion"""
        return await handle_settings_callback(update, context, user_data, markupList)
