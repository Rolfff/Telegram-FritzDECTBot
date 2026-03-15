# Telegram Importe mit Fallback für Tests
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    TELEGRAM_AVAILABLE = False
    print("WARNING: telegram module nicht gefunden - AdminMode läuft im Test-Modus")

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

# Import Konstanten aus config
LOGIN, MAIN, ADMIN, STATISTICS = config_module.LOGIN, config_module.MAIN, config_module.ADMIN, config_module.STATISTICS

# Globale Variable für Datenbank - wird von fritzdect_bot.py gesetzt
db = None

def set_database(database_instance):
    """Setzt die globale Datenbank-Instanz"""
    global db
    db = database_instance


# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'nextRequest': 'nächster Request',
         'displayUsers': 'Zeige alle User',
         'deleteUsers': 'Lösche User',
         'show_config': 'Konfig anezigen',
         'quit': 'Verlasse AdminMode'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'nextRequest': 'Zeigt den nächsten User-Request an',
         'displayUsers': 'Zeigt alle User',
         'deleteUsers': 'Löscht User',
         'show_config': 'Zeigt die aktuelle Konfiguration an',
         'help': 'Zeigt diesen Text an',
         'quit': 'Verlasse AdminMode'}

async def displayUsers(update, context, user_data, markupList):
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
        
    try:
        # Hole alle Benutzer
        all_users = db.get_all_users()
        
        if all_users:
            users_text = "📋 **Alle Benutzer:**\n\n"
            for user in all_users:
                chat_id, firstname, lastname, is_admin, allowed_to, failed_attempts, blocked_until = user[:7]
                status = "👑 Admin" if is_admin else "👤 User"
                
                # Datetime-Strings konvertieren für Vergleiche
                try:
                    if blocked_until and isinstance(blocked_until, str):
                        blocked_until_dt = DT.datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        blocked_until_dt = blocked_until
                    
                    if allowed_to and isinstance(allowed_to, str):
                        allowed_to_dt = DT.datetime.strptime(allowed_to, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        allowed_to_dt = allowed_to
                except (ValueError, TypeError):
                    # Bei Fehlern mit None weitermachen
                    blocked_until_dt = None
                    allowed_to_dt = None
                
                # Status und Freischalt-Datum bestimmen
                access_info = ""
                if blocked_until_dt and DT.datetime.now() < blocked_until_dt:
                    status += " 🚫 Geblockt"
                    access_info = f"Geblockt bis {blocked_until_dt.strftime('%d.%m.%Y %H:%M')}"
                elif allowed_to_dt and DT.datetime.now() < allowed_to_dt:
                    status += " ✅ Aktiv"
                    access_info = f"Freigegeben bis {allowed_to_dt.strftime('%d.%m.%Y %H:%M')}"
                else:
                    status += " ⏳ Wartend"
                    access_info = "Wartet auf Freigabe"
                
                users_text += f"{status}: {firstname or 'Unbekannt'} {lastname or ''} (ID: {chat_id})\n"
                users_text += f"   📅 {access_info}\n\n"
            
            await update.message.reply_text(users_text, reply_markup=user_data['keyboard'])
        else:
            await update.message.reply_text("📋 **Keine Benutzer in der Datenbank**", reply_markup=user_data['keyboard'])
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen der User-Liste: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

async def deleteUsers(update, context, user_data, markupList):
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
        
    try:
        # Hole alle Benutzer für die Auswahl
        all_users = db.get_all_users()
        
        if all_users:
            users_text = "🗑️ **Zu löschende Benutzer auswählen:**\n\n"
            for i, user in enumerate(all_users, 1):
                chat_id, firstname, lastname, is_admin, allowed_to, failed_attempts, blocked_until = user[:7]
                status = "👑 Admin" if is_admin else "👤 User"
                
                # Datetime-Strings konvertieren für Vergleiche
                try:
                    if blocked_until and isinstance(blocked_until, str):
                        blocked_until_dt = DT.datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        blocked_until_dt = blocked_until
                    
                    if allowed_to and isinstance(allowed_to, str):
                        allowed_to_dt = DT.datetime.strptime(allowed_to, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        allowed_to_dt = allowed_to
                except (ValueError, TypeError):
                    # Bei Fehlern mit None weitermachen
                    blocked_until_dt = None
                    allowed_to_dt = None
                
                # Status und Freischalt-Datum bestimmen
                access_info = ""
                if blocked_until_dt and DT.datetime.now() < blocked_until_dt:
                    status += " 🚫 Geblockt"
                    access_info = f"Geblockt bis {blocked_until_dt.strftime('%d.%m.%Y %H:%M')}"
                elif allowed_to_dt and DT.datetime.now() < allowed_to_dt:
                    status += " ✅ Aktiv"
                    access_info = f"Freigegeben bis {allowed_to_dt.strftime('%d.%m.%Y %H:%M')}"
                else:
                    status += " ⏳ Wartend"
                    access_info = "Wartet auf Freigabe"
                
                users_text += f"{i}. {status}: {firstname or 'Unbekannt'} {lastname or ''} (ID: {chat_id})\n"
                users_text += f"   📅 {access_info}\n"
            
            users_text += f"\nBitte sende die Nummer des zu löschenden Benutzers (0-{len(all_users)}).\n"
            users_text += f"0 = Abbrechen\n"
            
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['deleteUserList'] = all_users
            await update.message.reply_text(users_text, reply_markup=user_data['keyboard'])
        else:
            await update.message.reply_text("📋 **Keine Benutzer zum Löschen vorhanden**", reply_markup=user_data['keyboard'])
    except Exception as e:
        await update.message.reply_text(f"Fehler: {str(e)}", reply_markup=user_data['keyboard'])
    return user_data['status']

async def quit(update, context, user_data, markupList):
    user_data['keyboard'] = markupList[MAIN]
    await update.message.reply_text("EXIT --ADMINMODE--",
            reply_markup=user_data['keyboard'])
    user_data['status'] = MAIN
    return user_data['status']

async def nextRequest(update, context, user_data, markupList):
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
        
    try:
        # Hole alle wartenden Anfragen
        pending_requests = db.get_pending_requests()
        
        if pending_requests:
            # Nimm die neueste Anfrage (erste in der Liste)
            next_request = pending_requests[0]
            chat_id, firstname, lastname = next_request
            
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = {
                'chatID': chat_id,
                'firstname': firstname or 'Unbekannt',
                'lastname': lastname or ''
            }
            
            # Inline-Buttons für Aktionen erstellen
            keyboard = [
                [
                    InlineKeyboardButton("✅ Zulassen", callback_data=f'approve_request_{chat_id}'),
                    InlineKeyboardButton("❌ Ablehnen", callback_data=f'reject_request_{chat_id}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔐 **Zugriffsanfrage:**\n\n"
                f"👤 {firstname or 'Unbekannt'} {lastname or ''}\n"
                f"🆔 Chat-ID: {chat_id}\n\n"
                f"Bitte wähle eine Aktion:",
                reply_markup=reply_markup
            )
        else:
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = None
            await update.message.reply_text(
                "✅ **Keine wartenden Anfragen**\n\n"
                "Alle Benutzer haben bereits Zugriff oder es liegen keine Anfragen vor.",
                reply_markup=user_data['keyboard']
            )
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen des Requests: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

def allowUser(bot, update, user_data):
    user_data['keyboard'] = getMarkupList(user_data)[GETDAYS]
    user_data['status'] = GETDAYS
    nextRequest = user_data['userRequest']
    update.message.reply_text("Wieviel Tage soll "+str(nextRequest['firstname'])+" zugriff auf die Lampe haben? Bitte gebe eine natürliche Zahl ein oder /quit .",
        reply_markup=user_data['keyboard'])
    return user_data['status']

def updateUser(bot, update, user_data):
    text = update.message.text
    print(str(text))
    user_data['keyboard'] = getMarkupList(user_data)[ADMIN]
    user_data['status'] = ADMIN
    nextRequest = user_data['userRequest']
    try:
        days_ = int(text)
        userDB = UserDatabase()
        userDB.extend_access(nextRequest['chatID'],days_)
        allowed_until = DT.datetime.now() + DT.timedelta(days=d)
        update.message.reply_text("User: "+str(nextRequest['firstname'])+" "+str(nextRequest['lastname'])+ " erlaubt bis "+str(allowed_until)+".",
            reply_markup=user_data['keyboard'])
        bot.send_message(nextRequest['chatID'],text="Der Admin hat dir bis zum "+str(allowed_until)+" eingeräumt den Bot zu nutzen. Bitte schreibe mir /letsgo !")
    except ValueError as e:
        update.message.reply_text("Error "+str(e)+" User: "+str(nextRequest['firstname'])+" "+str(nextRequest['lastname'])+ " nicht freigegeben. Bitte versuche es nochmal.",
            reply_markup=user_data['keyboard'])
    except Exception as e:
        update.message.reply_text("Error "+str(e)+" User: "+str(nextRequest['firstname'])+" "+str(nextRequest['lastname'])+ " nicht freigegeben. Bitte versuche es nochmal.",
            reply_markup=user_data['keyboard'])
    finally:
        user_data['userRequest'] = None
        return user_data['status']



async def help(update, context, user_data, markupList):
    text=''
    for key, value in textbefehl.items():
        text = text + '- /' + key + ' ' + value + '\n'
            
    await update.message.reply_text(
                'Nutze das Keyboard für Admin-Aktionen: \n'+
                 str(text)+' ',
                reply_markup=user_data['keyboard'])
    return user_data['status']

async def handle_request_callback(update, context, user_data, markupList):
    """Verarbeitet Callbacks von Inline-Buttons für User-Anfragen"""
    global db
    if db is None:
        await update.callback_query.answer("❌ Datenbank nicht verfügbar.")
        return user_data['status']
    
    query = update.callback_query
    await query.answer()  # Callback bestätigen
    
    try:
        callback_data = query.data
        print(f"DEBUG: Callback erhalten: {callback_data}")
        
        if callback_data.startswith('approve_request_'):
            # Chat-ID extrahieren
            chat_id = int(callback_data.split('_')[2])
            
            # User-Informationen holen
            user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if user_info:
                firstname, lastname = user_info
                user_name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            else:
                user_name = f"User {chat_id}"
            
            # Speichere die Chat-ID für die nächste Eingabe
            user_data['pending_approval_chat_id'] = chat_id
            user_data['pending_approval_name'] = user_name
            
            # Frage nach der Anzahl der Tage
            keyboard = [
                [InlineKeyboardButton("7 Tage", callback_data=f'grant_days_{chat_id}_7'),
                 InlineKeyboardButton("30 Tage", callback_data=f'grant_days_{chat_id}_30')],
                [InlineKeyboardButton("90 Tage", callback_data=f'grant_days_{chat_id}_90'),
                 InlineKeyboardButton("365 Tage", callback_data=f'grant_days_{chat_id}_365')],
                [InlineKeyboardButton("⚙️ Benutzerdefiniert", callback_data=f'custom_days_{chat_id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🔐 **Zugriff gewähren für:**\n\n"
                f"👤 {user_name}\n"
                f"🆔 Chat-ID: {chat_id}\n\n"
                f"📅 Wähle die Dauer des Zugriffs:",
                reply_markup=reply_markup
            )
            
        elif callback_data.startswith('reject_request_'):
            # Chat-ID extrahieren
            chat_id = int(callback_data.split('_')[2])
            
            # User-Informationen holen
            user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if user_info:
                firstname, lastname = user_info
                user_name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            else:
                user_name = f"User {chat_id}"
            
            # User aus Datenbank löschen
            db.execute(f"DELETE FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            
            # Bestätigung senden
            await query.edit_message_text(
                f"❌ **Anfrage abgelehnt**\n\n"
                f"👤 {user_name}\n"
                f"🆔 Chat-ID: {chat_id}\n\n"
                f"Der Benutzer wurde aus der Datenbank entfernt.\n"
                f"Er kann sich erneut anmelden, wenn er möchte."
            )
            
        elif callback_data.startswith('grant_days_'):
            # Chat-ID und Tage extrahieren
            parts = callback_data.split('_')
            chat_id = int(parts[2])
            days = int(parts[3])
            
            # Zugriff gewähren
            allowed_until = db.grant_access(chat_id, days)
            
            # User-Informationen holen
            user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if user_info:
                firstname, lastname = user_info
                user_name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            else:
                user_name = f"User {chat_id}"
            
            # Benachrichtigung an den Benutzer senden
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'✅ **Zugriff gewährt!**\n\n'
                        f'📅 Du kannst den Bot jetzt bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr nutzen.\n\n'
                        f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
                )
            except Exception as e:
                print(f"Failed to notify user about access grant: {e}")
            
            # Bestätigung an Admin
            await query.edit_message_text(
                f"✅ **Zugriff gewährt**\n\n"
                f"👤 {user_name}\n"
                f"🆔 Chat-ID: {chat_id}\n"
                f"📅 Bis zum: {allowed_until.strftime('%d.%m.%Y %H:%M')} Uhr\n\n"
                f"Der Benutzer wurde benachrichtigt."
            )
            
        elif callback_data.startswith('custom_days_'):
            # Chat-ID extrahieren
            chat_id = int(callback_data.split('_')[2])
            
            # Speichere für benutzerdefinierte Eingabe
            user_data['custom_days_chat_id'] = chat_id
            user_data['waiting_for_custom_days'] = True
            
            await query.edit_message_text(
                f"⚙️ **Benutzerdefinierte Dauer**\n\n"
                f"Bitte sende die Anzahl der Tage als Zahl (z.B. 14, 60, 180):"
            )
            
    except Exception as e:
        print(f"Fehler bei Callback-Verarbeitung: {e}")
        await query.edit_message_text(f"❌ Fehler: {str(e)}")
    
    return user_data['status']

async def handle_custom_days(update, context, user_data, markupList):
    """Verarbeitet benutzerdefinierte Tage-Eingabe"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar.")
        return user_data['status']
    
    try:
        # Prüfen ob auf benutzerdefinierte Tage gewartet wird
        if not user_data.get('waiting_for_custom_days'):
            return user_data['status']
        
        chat_id = user_data.get('custom_days_chat_id')
        if not chat_id:
            await update.message.reply_text("❌ Fehler: Chat-ID nicht gefunden.")
            return user_data['status']
        
        # Tage aus der Nachricht extrahieren
        message_text = update.message.text.strip()
        try:
            days = int(message_text)
            if days <= 0 or days > 3650:  # Max 10 Jahre
                await update.message.reply_text("❌ Ungültige Anzahl von Tagen! Bitte eine Zahl zwischen 1 und 3650 eingeben.")
                return user_data['status']
        except ValueError:
            await update.message.reply_text("❌ Ungültige Eingabe! Bitte eine ganze Zahl eingeben (z.B. 14, 60, 180).")
            return user_data['status']
        
        # Zugriff gewähren
        allowed_until = db.grant_access(chat_id, days)
        
        # User-Informationen holen
        user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
        if user_info:
            firstname, lastname = user_info
            user_name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
        else:
            user_name = f"User {chat_id}"
        
        # Benachrichtigung an den Benutzer senden
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'✅ **Zugriff gewährt!**\n\n'
                    f'📅 Du kannst den Bot jetzt bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr nutzen.\n\n'
                    f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
            )
        except Exception as e:
            print(f"Failed to notify user about access grant: {e}")
        
        # Bestätigung an Admin
        await update.message.reply_text(
            f"✅ **Zugriff gewährt**\n\n"
            f"👤 {user_name}\n"
            f"🆔 Chat-ID: {chat_id}\n"
            f"📅 Bis zum: {allowed_until.strftime('%d.%m.%Y %H:%M')} Uhr\n\n"
            f"Der Benutzer wurde benachrichtigt.",
            reply_markup=markupList[ADMIN]
        )
        
        # Status zurücksetzen
        user_data['custom_days_chat_id'] = None
        user_data['waiting_for_custom_days'] = False
        
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler: {str(e)}")
    
    return user_data['status']

async def handle_delete_user(update, context, user_data, markupList):
    """Verarbeitet die User-Löschung nach Nummer-Eingabe"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar.")
        return user_data['status']
    
    try:
        delete_user_list = user_data.get('deleteUserList')
        if not delete_user_list:
            await update.message.reply_text("❌ Fehler: Keine User-Liste zum Löschen vorhanden.")
            return user_data['status']
        
        # Nummer aus der Nachricht extrahieren
        message_text = update.message.text.strip()
        try:
            user_number = int(message_text)
            
            # Abbrechen wenn 0 eingegeben wurde
            if user_number == 0:
                user_data['deleteUserList'] = None
                await update.message.reply_text(
                    "❌ **Löschvorgang abgebrochen**\n\nKein Benutzer wurde gelöscht.",
                    reply_markup=user_data['keyboard']
                )
                return user_data['status']
            
            # Validierung der Nummer
            if user_number < 1 or user_number > len(delete_user_list):
                await update.message.reply_text(
                    f"❌ Ungültige Nummer! Bitte eine Zahl zwischen 0 und {len(delete_user_list)} eingeben.\n"
                    f"0 = Abbrechen",
                    reply_markup=user_data['keyboard']
                )
                return user_data['status']
        except ValueError:
            await update.message.reply_text(
                f"❌ Ungültige Eingabe! Bitte eine ganze Zahl zwischen 0 und {len(delete_user_list)} eingeben.\n"
                f"0 = Abbrechen",
                reply_markup=user_data['keyboard']
            )
            return user_data['status']
        
        # User-Informationen holen
        user_to_delete = delete_user_list[user_number - 1]
        chat_id, firstname, lastname, is_admin, allowed_to, failed_attempts, blocked_until = user_to_delete[:7]
        user_name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
        
        # Admin kann nicht gelöscht werden
        if is_admin:
            await update.message.reply_text(
                "❌ Admin-Benutzer können nicht gelöscht werden!",
                reply_markup=markupList[ADMIN]
            )
            # Status zurücksetzen
            user_data['deleteUserList'] = None
            return user_data['status']
        
        # User aus Datenbank löschen
        db.execute(f"DELETE FROM {db.table_name} WHERE chatID = ?", (chat_id,))
        
        # Bestätigung senden
        await update.message.reply_text(
            f"🗑️ **Benutzer gelöscht**\n\n"
            f"👤 {user_name}\n"
            f"🆔 Chat-ID: {chat_id}\n\n"
            f"Der Benutzer wurde aus der Datenbank entfernt.",
            reply_markup=markupList[ADMIN]
        )
        
        # Status zurücksetzen
        user_data['deleteUserList'] = None
        
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler: {str(e)}")
    
    return user_data['status']

async def show_config(update, context, user_data, markupList):
    """Zeigt die aktuelle Konfiguration an"""
    try:
        # Konfiguration aus der globalen config_module laden
        config = config_module.Config()
        
        # Sensible Daten maskieren
        telegram_token = config.get_telegram_token()
        telegram_password = config.get_telegram_password()
        fritzbox_password = config.get_fritzbox_config().get('password', '')
        
        # Token und Passwort maskieren (nur erste 3 Zeichen zeigen, rest mit ***)
        masked_token = telegram_token[:3] + '***' if telegram_token else 'Nicht gesetzt'
        masked_password = telegram_password[:3] + '***' if telegram_password else 'Nicht gesetzt'
        masked_fritzbox_password = fritzbox_password[:3] + '***' if fritzbox_password else 'Nicht gesetzt'
        
        # Konfiguration formatieren
        config_text = f"⚙️ **Aktuelle Konfiguration:**\n\n"
        config_text += f"🤖 **Telegram:**\n"
        config_text += f"├─ Token: {masked_token}\n"
        config_text += f"├─ Admin Chat-ID: {config.get_admin_chat_id()}\n"
        config_text += f"└─ Passwort: {masked_password}\n\n"
        
        config_text += f"🌐 **FritzBox:**\n"
        config_text += f"├─ Host: {config.get_fritzbox_config().get('host', 'Nicht gesetzt')}\n"
        config_text += f"├─ Port: {config.get_fritzbox_config().get('port', 'Nicht gesetzt')}\n"
        config_text += f"├─ Username: {config.get_fritzbox_config().get('username', 'Nicht gesetzt')}\n"
        config_text += f"└─ Passwort: {masked_fritzbox_password}\n\n"
        
        config_text += f"🏠 **Templates:**\n"
        config_text += f"├─ Urlaub AN: {config.get('templates.vacation_on', 'Nicht gesetzt')}\n"
        config_text += f"├─ Urlaub AUS: {config.get('templates.vacation_off', 'Nicht gesetzt')}\n"
        config_text += f"└─ Urlaub Temperatur: {config.get('templates.vacation_temperature', 'Nicht gesetzt')}°C\n\n"
        
        config_text += f"🪟 **Fenster-Öffnung:**\n"
        config_text += f"├─ Standard Dauer: {config.get('window_open.default_duration_minutes', 'Nicht gesetzt')} Minuten\n"
        config_text += f"├─ Erinnerung vor: {config.get('window_open.reminder_minutes_before', 'Nicht gesetzt')} Minuten\n"
        config_text += f"└─ Max Dauer: {config.get('window_open.max_duration_hours', 'Nicht gesetzt')} Stunden\n\n"
        
        config_text += f"💾 **Datenbank:**\n"
        config_text += f"├─ Pfad: {config.get_database_config().get('path', 'Nicht gesetzt')}\n"
        config_text += f"└─ Tabelle: {config.get_database_config().get('table', 'Nicht gesetzt')}\n\n"
        
        config_text += f"📝 **Logging:**\n"
        config_text += f"├─ Level: {config.get_logging_config().get('level', 'Nicht gesetzt')}\n"
        config_text += f"└─ Format: {config.get_logging_config().get('format', 'Nicht gesetzt')}\n\n"
        
        config_text += f"🔒 **Sicherheit:**\n"
        config_text += f"├─ Max Fehlversuche: {config.get_max_failed_attempts()}\n"
        config_text += f"└─ Blockdauer: {config.get_block_duration_days()} Tage\n\n"
        
        config_text += f"📊 **Statistik:**\n"
        config_text += f"├─ Anzahl Benutzer: {len(db.get_all_users()) if db else 'N/A'}\n"
        config_text += f"└─ Wartende Anfragen: {len(db.get_pending_requests()) if db else 'N/A'}"
        
        await update.message.reply_text(config_text, reply_markup=user_data['keyboard'])
        
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler beim Laden der Konfiguration: {str(e)}", 
                                      reply_markup=user_data['keyboard'])
    
    return user_data['status']

async def grant_access(update, context, user_data, markupList):
    """Gewährt einem Benutzer Zugriff"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
        
    try:
        # Erwarte: /grant_access chat_id tage
        message_text = update.message.text.strip()
        parts = message_text.split()
        
        if len(parts) < 3:
            await update.message.reply_text(
                '❌ Falsches Format! Benutze: /grant_access chat_id tage\n'
                f'Beispiel: /grant_access 123456789 30'
            )
            return user_data['status']
        
        chat_id = parts[1]
        try:
            days = int(parts[2])
        except ValueError:
            await update.message.reply_text(
                '❌ Ungültige Anzahl von Tagen! Muss eine ganze Zahl sein.'
            )
            return user_data['status']
        
        # Prüfen ob Benutzer existiert
        if not db.user_exists(int(chat_id)):
            await update.message.reply_text(
                f'❌ Benutzer mit ID {chat_id} existiert nicht.'
            )
            return user_data['status']
        
        # Zugriff gewähren
        allowed_until = db.grant_access(int(chat_id), days)
        
        # Benachrichtigung an den Benutzer senden
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=f'✅ **Zugriff gewährt!**\n\n'
                    f'📅 Du kannst den Bot jetzt bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr nutzen.\n\n'
                    f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
            )
        except Exception as e:
            print(f"Failed to notify user about access grant: {e}")
        
        # Bestätigung an Admin senden
        await update.message.reply_text(
            f'✅ Zugriff für Benutzer {chat_id} bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr gewährt.'
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Fehler: {str(e)}')
    
    return user_data['status']

async def default(update, context, user_data, markupList):
    """Default-Funktion für AdminMode"""
    global db
    if db is None:
        await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.")
        return user_data['status']
    
    # Prüfen ob auf benutzerdefinierte Tage gewartet wird
    if user_data.get('waiting_for_custom_days'):
        return await handle_custom_days(update, context, user_data, markupList)
    
    # Prüfen ob auf User-Löschung gewartet wird
    if user_data.get('deleteUserList'):
        return await handle_delete_user(update, context, user_data, markupList)
    
    # Ansonsten Hilfe anzeigen
    return await help(update, context, user_data, markupList)


def get_callback_handlers():
    """Gibt die Callback-Handler-Konfiguration für AdminMode zurück"""
    return {
        'patterns': [
            r'approve_request_.*',
            r'reject_request_.*',
            r'grant_days_.*',
            r'custom_days_.*'
        ],
        'handler': AdminMode.handle_request_callback
    }
