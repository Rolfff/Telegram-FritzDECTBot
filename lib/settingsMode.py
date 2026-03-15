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
tastertur = {'language': 'Sprache ändern',
         'notifications': 'Benachrichtigungen',
         'back': 'Zurück'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'language': 'Ändert die Sprache des Bots',
         'notifications': 'Konfiguriert Benachrichtigungseinstellungen',
         'back': 'Wechselt zurück ins Main-Menu'}


async def default(update, context, user_data, markupList):
    """Default-Funktion für Settings-Mode"""
    """Wechselt in den Settings-Modus"""
    context.user_data['keyboard'] = markupList[SETTINGS]
    context.user_data['status'] = SETTINGS
    await update.message.reply_text("-->SETTINGSMODE<--\n\n⚙️ Verfügbare Funktionen:\n"
                                  "• Sprache ändern (🇩🇪🇬🇧🇷🇺🇫🇷🇪🇸)\n"
                                  "• Benachrichtigungen konfigurieren\n"
                                  "• Persönliche Einstellungen anpassen\n\n"
                                  "💡 Nutze /help für alle Befehle",
                                  reply_markup=context.user_data['keyboard'])
    return context.user_data['status']


async def language(update, context, user_data, markupList):
    """Zeigt Sprachauswahl mit Inline-Buttons"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
    
    try:
        chat_id = user_data['chatId']
        current_language = db.get_user_language(chat_id)
        
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
        current_lang_name = language_names.get(current_language, f'🌐 {current_language}')
        
        await update.message.reply_text(
            f"🌍 **Spracheinstellungen**\n\n"
            f"Aktuelle Sprache: {current_lang_name}\n\n"
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
        chat_id = user_data['chatId']
        
        # Aktuelle Benachrichtigungseinstellungen holen
        user_info = db.fetch_one(f"""
            SELECT notifyVacationMode, notifyDoorPowerMeter, notifyDoorFrontDoor 
            FROM {db.table_name} 
            WHERE chatID = ?
        """, (chat_id,))
        
        if user_info:
            vacation_mode, door_power_meter, door_front_door = user_info
        else:
            # Standardwerte wenn nicht gefunden
            vacation_mode = door_power_meter = door_front_door = 1
        
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
            "🔔 **Benachrichtigungseinstellungen**\n\n"
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
        "🔙 **Zurück zum Hauptmenü**",
        reply_markup=markupList[MAIN]
    )
    return MAIN





async def handle_settings_callback(update, context, user_data, markupList):
    """Verarbeitet Callbacks von Inline-Buttons im Settings-Mode"""
    global db
    if db is None:
        await update.callback_query.answer("❌ Datenbank nicht verfügbar.")
        return user_data['status']
    
    query = update.callback_query
    await query.answer()  # Callback bestätigen
    
    try:
        callback_data = query.data
        chat_id = int(callback_data.split('_')[-1])  # Chat-ID extrahieren
        
        if callback_data.startswith('set_language_'):
            # Sprache ändern
            language = callback_data.split('_')[2]
            db.update_user_language(chat_id, language)
            
            language_names = {
                'de': '🇩🇪 Deutsch',
                'en': '🇬🇧 English',
                'ru': '🇷🇺 Русский', 
                'fr': '🇫🇷 Français',
                'es': '🇪🇸 Español'
            }
            
            await query.edit_message_text(
                f"✅ **Sprache geändert!**\n\n"
                f"Neue Sprache: {language_names.get(language, f'🌐 {language}')}\n\n"
                f"Die Änderung wird beim nächsten Login vollständig wirksam."
            )
            
        elif callback_data.startswith('toggle_vacation_'):
            # Urlaubsschaltung umschalten
            current_value = db.fetch_one(f"SELECT notifyVacationMode FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            new_value = 0 if current_value and current_value[0] == 1 else 1
            db.update_notification_setting(chat_id, 'notifyVacationMode', new_value)
            
            status_text = "aktiviert" if new_value == 1 else "deaktiviert"
            await query.edit_message_text(
                f"🏖️ **Urlaubsschaltung {status_text}!**\n\n"
                f"Du wirst {'jetzt' if new_value == 1 else 'nicht mehr'} über Urlaubsschaltungen benachrichtigt."
            )
            
        elif callback_data.startswith('toggle_power_'):
            # Tür-Stromzähler umschalten
            current_value = db.fetch_one(f"SELECT notifyDoorPowerMeter FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            new_value = 0 if current_value and current_value[0] == 1 else 1
            db.update_notification_setting(chat_id, 'notifyDoorPowerMeter', new_value)
            
            status_text = "aktiviert" if new_value == 1 else "deaktiviert"
            await query.edit_message_text(
                f"⚡ **Tür-Stromzähler {status_text}!**\n\n"
                f"Du wirst {'jetzt' if new_value == 1 else 'nicht mehr'} über Tür-Stromzähler-Ereignisse benachrichtigt."
            )
            
        elif callback_data.startswith('toggle_door_'):
            # Haustür umschalten
            current_value = db.fetch_one(f"SELECT notifyDoorFrontDoor FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            new_value = 0 if current_value and current_value[0] == 1 else 1
            db.update_notification_setting(chat_id, 'notifyDoorFrontDoor', new_value)
            
            status_text = "aktiviert" if new_value == 1 else "deaktiviert"
            await query.edit_message_text(
                f"🚪 **Haustür-Benachrichtigungen {status_text}!**\n\n"
                f"Du wirst {'jetzt' if new_value == 1 else 'nicht mehr'} über Haustür-Ereignisse benachrichtigt."
            )
            
        elif callback_data.startswith('cancel_language_'):
            # Sprachänderung abbrechen
            await query.edit_message_text("❌ **Sprachänderung abgebrochen**")
            
        elif callback_data.startswith('back_settings_'):
            # Zurück zu den Einstellungen
            await query.edit_message_text("🔙 **Zurück zu den Einstellungen**")
            
    except Exception as e:
        await query.edit_message_text(f"❌ Fehler: {str(e)}")
    
    return user_data['status']
