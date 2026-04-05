import logging
import datetime as DT
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from lib.config import ADMIN, MAIN

# Globale Variable für Datenbank
db = None

logger = logging.getLogger(__name__)

def set_database(database_instance):
    """Setzt die globale Datenbank-Instanz"""
    global db
    db = database_instance

# Tastatur-Befehle (Button-Texte)
tastertur = {
    'nextRequest': 'Nächster Request',
    'displayUsers': 'Zeige alle User',
    'deleteUsers': 'Lösche User',
    'show_config': 'Konfig anzeigen',
    'grant_access': 'Zugriff gewähren',
    'back': 'Zurück'
}

# Text-Befehle (für /help)
textbefehl = {
    'nextRequest': 'Zeigt den nächsten User-Request an',
    'displayUsers': 'Zeigt alle registrierten Benutzer',
    'deleteUsers': 'Löscht einen Benutzer aus der Datenbank',
    'show_config': 'Zeigt die aktuelle Bot-Konfiguration',
    'grant_access': 'Gewährt einem Benutzer Zugriff für bestimmte Tage',
    'back': 'Kehrt zum Hauptmenü zurück'
}

# Hilfe-Funktion entfernt - wird von fritzdect_bot.py gehandelt

class AdminMode:
    """AdminMode Klasse mit allen Admin-Funktionen"""
    
    # Klassenvariablen für Kompatibilität
    tastertur = tastertur
    textbefehl = textbefehl
    db = None
    
    @classmethod
    def set_database(cls, database_instance):
        """Setzt die Datenbank-Instanz"""
        cls.db = database_instance
    
    @staticmethod
    def get_callback_handlers():
        """Gibt die Callback-Handler-Konfiguration zurück"""
        return {
            'patterns': [
                r'approve_request_.*',
                r'reject_request_.*',
                r'grant_days_.*',
                r'custom_days_.*'
            ],
            'handler': AdminMode.handle_request_callback
        }
    
    @staticmethod
    async def default(update, context, user_data, markupList):
        """Standard-Funktion für AdminMode"""
        # Prüfen ob auf benutzerdefinierte Tage gewartet wird
        if user_data.get('waiting_for_custom_days'):
            return await AdminMode.handle_custom_days(update, context, user_data, markupList)
        
        # Prüfen ob auf User-Löschung gewartet wird
        if user_data.get('deleteUserList'):
            return await AdminMode.handle_delete_user(update, context, user_data, markupList)
        
        # Ansonsten Hilfe anzeigen
        return await AdminMode.help(update, context, user_data, markupList)
    
    @staticmethod
    async def help(update, context, user_data, markupList):
        """Zeigt die Admin-Hilfe an"""
        help_text = (
            "🔧 **Admin-Modus Hilfe:**\n\n"
            "Verfügbare Funktionen:\n"
            "• Nächster Request - Zeigt nächsten Zugriffsanfrage\n"
            "• Zeige alle User - Listet alle registrierten Benutzer\n"
            "• Lösche User - Entfernt einen Benutzer\n"
            "• Konfig anzeigen - Zeigt Bot-Konfiguration\n"
            "• Zugriff gewähren - Manuelle Zugriffsgewährung\n\n"
            "💡 Nutze /help für alle Befehle"
        )
        
        # Sicherstellen, dass wir im Admin-Mode bleiben
        context.user_data['status'] = ADMIN
        context.user_data['keyboard'] = markupList[ADMIN]
        
        await update.message.reply_text(help_text, reply_markup=user_data['keyboard'])
        return ADMIN
    
    
    @staticmethod
    async def nextRequest(update, context, user_data, markupList):
        """Nächsten User-Request anzeigen"""
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
            
        try:
            # Hole alle wartenden Anfragen
            pending_requests = db.get_pending_requests()
            
            if pending_requests:
                # Nimm die neueste Anfrage (erste in der Liste)
                next_request = pending_requests[0]
                chat_id, firstname, lastname = next_request
                
                context.user_data['keyboard'] = markupList[ADMIN]
                context.user_data['status'] = ADMIN
                user_data['userRequest'] = {
                    'chatID': chat_id,
                    'firstname': firstname or 'Unbekannt',
                    'lastname': lastname or ''
                }
                
                # Inline-Buttons für Aktionen erstellen
                keyboard = [
                    [
                        InlineKeyboardButton("✅ 7 Tage", callback_data=f'grant_days_{chat_id}_7'),
                        InlineKeyboardButton("✅ 30 Tage", callback_data=f'grant_days_{chat_id}_30')
                    ],
                    [
                        InlineKeyboardButton("⚙️ Benutzerdefiniert", callback_data=f'custom_days_{chat_id}'),
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
                context.user_data['keyboard'] = markupList[ADMIN]
                context.user_data['status'] = ADMIN
                user_data['userRequest'] = None
                await update.message.reply_text(
                    "✅ **Keine wartenden Anfragen**\n\n"
                    "Alle Benutzer haben bereits Zugriff oder es liegen keine Anfragen vor.",
                    reply_markup=user_data['keyboard']
                )
        except Exception as e:
            await update.message.reply_text(f"Fehler beim Abrufen des Requests: {str(e)}",
                reply_markup=user_data['keyboard'])
        return context.user_data['status']
    
    @staticmethod
    async def show_config(update, context, user_data, markupList):
        """Konfiguration anzeigen"""
        global db
        logger = logging.getLogger(__name__)
        logger.debug("AdminMode.show_config aufgerufen")
        
        config_text = (
            "⚙️ **Bot-Konfiguration:**\\n\\n"
            f"📊 **Datenbank:** {'✅ Aktiv' if AdminMode.db else '❌ Inaktiv'}\\n"
            f"🔐 **Admin-Modus:** ✅ Aktiv\\n"
            f"🤖 **Bot-Status:** ✅ Online\\n"
            f"📅 **Server-Zeit:** {DT.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\\n\\n"
            "*Weitere Details folgen...*"
        )
        
        # Sicherstellen, dass wir im Admin-Mode bleiben
        context.user_data['status'] = ADMIN
        context.user_data['keyboard'] = markupList[ADMIN]
        
        await update.message.reply_text(config_text, reply_markup=user_data['keyboard'])
        return context.user_data['status']
    
    @staticmethod
    async def displayUsers(update, context, user_data, markupList):
        """Zeigt alle Benutzer an"""
        from lib.config import ADMIN
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
            
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
                
                # Sicherstellen, dass wir im Admin-Mode bleiben
                context.user_data['status'] = ADMIN
                context.user_data['keyboard'] = markupList[ADMIN]
                
                await update.message.reply_text(users_text, reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("📋 **Keine Benutzer in der Datenbank**", reply_markup=user_data['keyboard'])
                
        except Exception as e:
            await update.message.reply_text(f"Fehler beim Abrufen der User-Liste: {str(e)}",
                reply_markup=user_data['keyboard'])
        return ADMIN
    
    @staticmethod
    async def deleteUsers(update, context, user_data, markupList):
        """Löscht Benutzer"""
        from lib.config import ADMIN
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
            
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
                                                  
                context.user_data['keyboard'] = markupList[ADMIN]
                context.user_data['status'] = ADMIN
                user_data['deleteUserList'] = all_users
                await update.message.reply_text(users_text, reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("📋 **Keine Benutzer zum Löschen vorhanden**", reply_markup=user_data['keyboard'])
                
        except Exception as e:
            await update.message.reply_text(f"Fehler: {str(e)}", reply_markup=user_data['keyboard'])
        return context.user_data['status']
    
    @staticmethod
    async def allowUser(update, context, user_data, markupList):
        """Erlaubt einem Benutzer den Zugriff für bestimmte Tage"""
        from lib.config import GETDAYS
        user_data['keyboard'] = markupList[GETDAYS]
        context.user_data['status'] = GETDAYS
        nextRequest = user_data['userRequest']
        await update.message.reply_text("Wieviel Tage soll "+str(nextRequest['firstname'])+" zugriff auf die Lampe haben? Bitte gebe eine natürliche Zahl ein oder /quit .",
            reply_markup=user_data['keyboard'])
        return context.user_data['status']

    @staticmethod
    async def updateUser(update, context, user_data, markupList):
        """Aktualisiert Benutzerdaten"""
        text = update.message.text
        print(str(text))
        from lib.config import ADMIN
        user_data['keyboard'] = markupList[ADMIN]
        context.user_data['status'] = ADMIN
        return context.user_data['status']

    @staticmethod
    async def handle_custom_days(update, context, user_data, markupList):
        """Behandelt benutzerdefinierte Tage"""
        from lib.config import ADMIN
        try:
            days = int(update.message.text)
            if days <= 0:
                await update.message.reply_text("❌ Bitte gib eine positive Zahl ein.", reply_markup=user_data['keyboard'])
                return context.user_data['status']
            
            # User-Request aus user_data holen
            custom_days_chat_id = user_data.get('custom_days_chat_id')
            if custom_days_chat_id:
                chat_id = custom_days_chat_id
                
                # Zugriff gewähren
                if AdminMode.db:
                    AdminMode.db.extend_access(chat_id, days)
                    await update.message.reply_text(f"✅ Benutzer {chat_id} wurde für {days} Tage freigegeben!", reply_markup=user_data['keyboard'])
                    
                    # Status zurücksetzen und im Admin-Mode bleiben
                    user_data['waiting_for_custom_days'] = False
                    user_data['custom_days_chat_id'] = None
                    context.user_data['status'] = ADMIN
                    context.user_data['keyboard'] = markupList[ADMIN]
                else:
                    await update.message.reply_text("❌ Datenbank nicht verfügbar.", reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text("❌ Keine Chat-ID gefunden.", reply_markup=user_data['keyboard'])
                
        except ValueError:
            await update.message.reply_text("❌ Bitte gib eine gültige Zahl ein.", reply_markup=user_data['keyboard'])
        except Exception as e:
            await update.message.reply_text(f"❌ Fehler: {str(e)}", reply_markup=user_data['keyboard'])
        
        return context.user_data['status']

    @staticmethod
    async def handle_delete_user(update, context, user_data, markupList):
        """Behandelt User-Löschung"""
        try:
            user_input = update.message.text.strip()
            if user_input == '0':
                await update.message.reply_text("❌ Löschung abgebrochen.", reply_markup=user_data['keyboard'])
                user_data['deleteUserList'] = None
                # Sicherstellen, dass wir im Admin-Mode bleiben
                context.user_data['status'] = ADMIN
                context.user_data['keyboard'] = markupList[ADMIN]
                return context.user_data['status']
            
            user_number = int(user_input)
            delete_list = user_data.get('deleteUserList', [])
            
            if 1 <= user_number <= len(delete_list):
                user_to_delete = delete_list[user_number - 1]
                chat_id = user_to_delete[0]
                firstname = user_to_delete[1] or 'Unbekannt'
                lastname = user_to_delete[2] or ''
                
                # User löschen
                if AdminMode.db:
                    AdminMode.db.delete_user(chat_id)
                    await update.message.reply_text(f"✅ {firstname} {lastname} wurde gelöscht!", reply_markup=user_data['keyboard'])
                    user_data['deleteUserList'] = None
                else:
                    await update.message.reply_text("❌ Datenbank nicht verfügbar.", reply_markup=user_data['keyboard'])
            else:
                await update.message.reply_text(f"❌ Ungültige Nummer. Bitte wähle 1-{len(delete_list)} oder 0 zum Abbrechen.", reply_markup=user_data['keyboard'])
                
        except ValueError:
            await update.message.reply_text("❌ Bitte gib eine gültige Nummer ein.", reply_markup=user_data['keyboard'])
        except Exception as e:
            await update.message.reply_text(f"❌ Fehler: {str(e)}", reply_markup=user_data['keyboard'])
        
        # Immer im Admin-Mode bleiben
        context.user_data['status'] = ADMIN
        context.user_data['keyboard'] = markupList[ADMIN]
        return context.user_data['status']
    
    @staticmethod
    async def grant_access(update, context, user_data, markupList):
        """Gewährt einem Benutzer Zugriff für bestimmte Tage"""
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
        
        try:
            # Erwarte: /grant_access chat_id tage
            message_text = update.message.text.strip()
            parts = message_text.split()
            
            if len(parts) < 3:
                await update.message.reply_text(
                    '❌ Falsches Format! Benutze: /grant_access chat_id tage\n'
                    f'Beispiel: /grant_access 123456789 30'
                )
                return context.user_data['status']
            
            chat_id = parts[1]
            try:
                days = int(parts[2])
            except ValueError:
                await update.message.reply_text(
                    '❌ Ungültige Anzahl von Tagen! Muss eine ganze Zahl sein.'
                )
                return context.user_data['status']
            
            # Prüfen ob Benutzer existiert
            if not db.user_exists(int(chat_id)):
                await update.message.reply_text(
                    f'❌ Benutzer mit ID {chat_id} existiert nicht.'
                )
                return context.user_data['status']
            
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
                logger.error(f"Failed to notify user about access grant: {e}")
            
            # Bestätigung an Admin senden und im Admin-Mode bleiben
            context.user_data['status'] = ADMIN
            context.user_data['keyboard'] = markupList[ADMIN]
            
            await update.message.reply_text(
                f'✅ Zugriff für Benutzer {chat_id} bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr gewährt.',
                reply_markup=user_data['keyboard']
            )
            
        except Exception as e:
            await update.message.reply_text(f'❌ Fehler: {str(e)}', reply_markup=user_data['keyboard'])
        
        return context.user_data['status']
    
    @staticmethod
    async def back(update, context, user_data, markupList):
        """Zurück zum Hauptmenü"""
        from lib.config import MAIN
        context.user_data['keyboard'] = markupList[MAIN]
        context.user_data['status'] = MAIN
        
        await update.message.reply_text(
            "🏠 Zurück zum Hauptmenü",
            reply_markup=user_data['keyboard']
        )
        return context.user_data['status']
    
    @staticmethod
    async def handle_request_callback(update, context, user_data, markupList):
        """Handler für Request-Callbacks von Inline-Buttons"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        logger.info(f"Admin callback received: {callback_data}")
        
        try:
            if callback_data.startswith('approve_request_'):
                chat_id = int(callback_data.split('_')[2])
                return await AdminMode._approve_request(update, context, user_data, markupList, chat_id)
            
            elif callback_data.startswith('reject_request_'):
                chat_id = int(callback_data.split('_')[2])
                return await AdminMode._reject_request(update, context, user_data, markupList, chat_id)
            
            elif callback_data.startswith('grant_days_'):
                chat_id = int(callback_data.split('_')[2])
                days = int(callback_data.split('_')[3])
                return await AdminMode._grant_days(update, context, user_data, markupList, chat_id, days)
            
            elif callback_data.startswith('custom_days_'):
                chat_id = int(callback_data.split('_')[2])
                return await AdminMode._request_custom_days(update, context, user_data, markupList, chat_id)
            
            else:
                logger.warning(f"Unbekannter Callback: {callback_data}")
                await query.edit_message_text(
                    "❌ Unbekannte Aktion",
                    reply_markup=user_data['keyboard']
                )
        
        except Exception as e:
            logger.error(f"Fehler in Callback-Handler: {e}")
            await query.answer("❌ Fehler bei der Aktion", show_alert=True)
        
        return context.user_data['status']
    
    @staticmethod
    async def _approve_request(update, context, user_data, markupList, chat_id):
        """Genehmigt einen User-Request"""
        query = update.callback_query
        
        if AdminMode.db:
            try:
                # Standard-Zugriff für 30 Tage gewähren
                allowed_until = AdminMode.db.grant_access(chat_id, 30)
                
                # User benachrichtigen
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f'✅ **Zugriff gewährt!**\n\n'
                               f'📅 Du kannst den Bot jetzt bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr nutzen.\n\n'
                               f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {chat_id}: {e}")
                
                await query.edit_message_text(
                    f'✅ Zugriff für Benutzer {chat_id} bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr gewährt.',
                    reply_markup=user_data['keyboard']
                )
            except Exception as e:
                await query.edit_message_text(
                    f'❌ Fehler bei der Genehmigung: {str(e)}',
                    reply_markup=user_data['keyboard']
                )
        else:
            await query.edit_message_text(
                '❌ Datenbank nicht verfügbar.',
                reply_markup=user_data['keyboard']
            )
        
        return context.user_data['status']
    
    @staticmethod
    async def _reject_request(update, context, user_data, markupList, chat_id):
        """Lehnt einen User-Request ab"""
        query = update.callback_query
        
        if AdminMode.db:
            try:
                AdminMode.db.delete_request(chat_id)
                
                # User benachrichtigen
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text='❌ **Zugriff abgelehnt**\n\n'
                               'Deine Anfrage wurde leider abgelehnt.\n'
                               'Bitte kontaktiere den Admin für weitere Informationen.'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {chat_id}: {e}")
                
                await query.edit_message_text(
                    f'❌ Anfrage von Benutzer {chat_id} abgelehnt.',
                    reply_markup=user_data['keyboard']
                )
            except Exception as e:
                await query.edit_message_text(
                    f'❌ Fehler bei der Ablehnung: {str(e)}',
                    reply_markup=user_data['keyboard']
                )
        else:
            await query.edit_message_text(
                '❌ Datenbank nicht verfügbar.',
                reply_markup=user_data['keyboard']
            )
        
        return context.user_data['status']
    
    @staticmethod
    async def _grant_days(update, context, user_data, markupList, chat_id, days):
        """Gewährt Zugriff für bestimmte Tage"""
        query = update.callback_query
        
        if AdminMode.db:
            try:
                allowed_until = AdminMode.db.grant_access(chat_id, days)
                
                # User benachrichtigen
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f'✅ **Zugriff gewährt!**\n\n'
                               f'📅 Du kannst den Bot jetzt bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr nutzen.\n\n'
                               f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {chat_id}: {e}")
                
                await query.edit_message_text(
                    f'✅ Zugriff für Benutzer {chat_id} für {days} Tage gewährt.',
                    reply_markup=user_data['keyboard']
                )
            except Exception as e:
                await query.edit_message_text(
                    f'❌ Fehler: {str(e)}',
                    reply_markup=user_data['keyboard']
                )
        else:
            await query.edit_message_text(
                '❌ Datenbank nicht verfügbar.',
                reply_markup=user_data['keyboard']
            )
        
        return context.user_data['status']
    
    @staticmethod
    async def _request_custom_days(update, context, user_data, markupList, chat_id):
        """Fordert Benutzer auf, benutzerdefinierte Tage einzugeben"""
        query = update.callback_query
        
        # User-Info für spätere Verwendung speichern
        user_data['custom_days_chat_id'] = chat_id
        user_data['waiting_for_custom_days'] = True
        
        await query.edit_message_text(
            '⏳ **Benutzerdefinierte Tage**\n\n'
            'Bitte gib die Anzahl der Tage ein, für die der Zugriff gewährt werden soll:',
            reply_markup=user_data['keyboard']
        )
        
        return context.user_data['status']

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

# Datenbank-Instanz setzen
def init_database(database_instance):
    """Initialisiert die Datenbank-Instanz"""
    AdminMode.set_database(database_instance)
