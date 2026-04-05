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
    'grant_access': 'Zugriff verlängern',
    'back': 'Zurück'
}

# Text-Befehle (für /help)
textbefehl = {
    'nextRequest': 'Zeigt den nächsten User-Request an',
    'displayUsers': 'Zeigt alle registrierten Benutzer',
    'deleteUsers': 'Löscht einen Benutzer aus der Datenbank',
    'show_config': 'Zeigt die aktuelle Bot-Konfiguration',
    'grant_access': 'Verlängert den Zugriff eines Benutzers',
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
                r'custom_days_.*',
                r'extend_access_.*',
                r'extend_days_.*',
                r'extend_custom_.*',
                r'refresh_user_list',
                r'cancel_extend_access'
            ],
            'handler': AdminMode.handle_request_callback
        }
    
    @staticmethod
    async def default(update, context, user_data, markupList):
        """Standard-Funktion für AdminMode"""
        # Prüfen ob auf benutzerdefinierte Tage gewartet wird
        if user_data.get('waiting_for_custom_days'):
            return await AdminMode.handle_custom_days(update, context, user_data, markupList)
        
        # Prüfen ob auf benutzerdefinierte Verlängerungstage gewartet wird
        if user_data.get('waiting_for_extend_days'):
            return await AdminMode.handle_extend_days(update, context, user_data, markupList)
        
        # Prüfen ob auf User-Löschung gewartet wird
        if user_data.get('deleteUserList'):
            return await AdminMode.handle_delete_user(update, context, user_data, markupList)
        
        # Prüfen ob Abbruch-Befehle für benutzerdefinierte Eingabe
        message_text = update.message.text.strip().lower() if update.message else ""
        if message_text in ['abbruch', 'abbrechen', 'cancel', 'stop', 'exit']:
            user_data['extend_access_chat_id'] = None
            user_data['waiting_for_extend_days'] = None
            await update.message.reply_text("❌ Eingabe abgebrochen", reply_markup=user_data['keyboard'])
            return context.user_data['status']
        
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
            "• Zugriff verlängern - Verlängert den Zugriff eines Benutzers\n\n"
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
        """Zeigt Benutzerliste zur Zugriffverlängerung mit Inline-Tastatur"""
        logger.info(f"grant_access aufgerufen mit Text: {update.message.text}")
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar. Bitte kontaktiere den Admin.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
        
        try:
            # Alle Benutzer abrufen, die Zugriff haben oder hatten
            all_users = db.get_all_users()
            
            if not all_users:
                await update.message.reply_text("📋 **Keine Benutzer gefunden**", reply_markup=user_data['keyboard'])
                return context.user_data['status']
            
            # Inline-Tastatur für Benutzerauswahl erstellen
            keyboard = []
            for user in all_users:
                chat_id, firstname, lastname, is_admin, allowed_to, failed_attempts, blocked_until, *rest = user
                name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
                
                # Status-Emoji basierend auf Zugriff
                if is_admin:
                    status_emoji = "👑"
                elif allowed_to:
                    try:
                        allowed_until = DT.datetime.strptime(allowed_to, '%Y-%m-%d %H:%M:%S.%f')
                        if DT.datetime.now() < allowed_until:
                            status_emoji = "✅"
                        else:
                            status_emoji = "⏳"
                    except:
                        status_emoji = "⏳"
                else:
                    status_emoji = "❌"
                
                # Button-Text erstellen
                button_text = f"{status_emoji} {name} (ID: {chat_id})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f'extend_access_{chat_id}')])
            
            # Zusätzliche Optionen
            keyboard.extend([
                [InlineKeyboardButton("🔄 Liste aktualisieren", callback_data='refresh_user_list')],
                [InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_extend_access')]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔧 **Zugriff verlängern:**\n\n"
                "Wähle einen Benutzer aus, dessen Zugriff du verlängern möchtest:\n\n"
                "👑 Admin | ✅ Aktiv | ⏳ Wartend/Abgelaufen | ❌ Kein Zugriff",
                reply_markup=reply_markup
            )
            
            # Im Admin-Mode bleiben
            context.user_data['status'] = ADMIN
            context.user_data['keyboard'] = markupList[ADMIN]
            return ADMIN
            
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
        # Sicherstellen, dass dies ein Callback-Query ist
        if not hasattr(update, 'callback_query'):
            logger.error(f"handle_request_callback ohne Callback-Query aufgerufen. Update-Typ: {type(update)}")
            return context.user_data['status']
        
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        logger.info(f"Admin callback received: {callback_data}")
        
        # Datenbank-Instanz holen
        db = AdminMode.db
        
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
            
            elif callback_data.startswith('extend_access_'):
                chat_id = int(callback_data.split('_')[2])
                logger.info(f"extend_access callback erhalten: chat_id={chat_id}")
                return await AdminMode._handle_extend_access(update, context, user_data, markupList, chat_id)
            
            elif callback_data == 'refresh_user_list':
                return await AdminMode._refresh_user_list(update, context, user_data, markupList)
            
            elif callback_data == 'cancel_extend_access':
                logger.info(f"cancel_extend_access callback erhalten")
                return await AdminMode._cancel_extend_access(update, context, user_data, markupList)
            
            elif callback_data.startswith('extend_days_'):
                chat_id = int(callback_data.split('_')[2])
                days = int(callback_data.split('_')[3])
                logger.info(f"extend_days callback erhalten: chat_id={chat_id}, days={days}")
                return await AdminMode._extend_access_days(update, context, user_data, markupList, chat_id, days)
            
            elif callback_data.startswith('extend_custom_'):
                chat_id = int(callback_data.split('_')[2])
                logger.info(f"extend_custom callback erhalten: chat_id={chat_id}")
                return await AdminMode._extend_access_custom(update, context, user_data, markupList, chat_id)
            
            else:
                logger.warning(f"Unbekannter Callback: {callback_data}")
                try:
                    await query.edit_message_text(
                        "❌ Unbekannte Aktion",
                        reply_markup=user_data['keyboard']
                    )
                except Exception as edit_error:
                    logger.error(f"Fehler beim Editieren der Nachricht: {edit_error}")
                    await query.answer("❌ Fehler bei der Aktion", show_alert=True)
                
        except Exception as e:
            logger.error(f"Fehler in Callback-Handler: {e}")
            logger.error(f"Update-Typ: {type(update)}")
            logger.error(f"Callback-Data: {callback_data}")
            try:
                await query.answer("❌ Fehler bei der Aktion", show_alert=True)
            except Exception as answer_error:
                logger.error(f"Fehler beim Answer: {answer_error}")
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
                
                # Callback beantworten und Nachricht bearbeiten
                await query.answer()
                await query.edit_message_text(
                    f'✅ Zugriff für Benutzer {chat_id} bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr gewährt.',
                    reply_markup=user_data['keyboard']
                )
            except Exception as e:
                logger.error(f"Fehler bei der Genehmigung: {str(e)}")
                try:
                    await query.answer()
                    await query.edit_message_text(
                        f'❌ Fehler bei der Genehmigung: {str(e)}',
                        reply_markup=user_data['keyboard']
                    )
                except Exception as answer_error:
                    logger.error(f"Fehler beim Answer: {answer_error}")
        else:
            try:
                await query.answer()
                await query.edit_message_text(
                    '❌ Datenbank nicht verfügbar.',
                    reply_markup=user_data['keyboard']
                )
            except Exception as e:
                logger.error(f"Fehler bei Datenbankzugriff: {e}")
                try:
                    await query.answer()
                except Exception as answer_error:
                    logger.error(f"Fehler beim Answer: {answer_error}")
        
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
        
        return context.user_data['status']
    
    @staticmethod
    async def _handle_extend_access(update, context, user_data, markupList, chat_id):
        """Zeigt Optionen zur Zugriffverlängerung für einen bestimmten Benutzer"""
        query = update.callback_query
        global db
        
        if db is None:
            await query.answer("❌ Datenbank nicht verfügbar", show_alert=True)
            return context.user_data['status']
        
        try:
            # Benutzer-Info abrufen
            user_info = db.fetch_one(f"SELECT firstname, lastname, allowedToDatetime FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if not user_info:
                await query.answer("❌ Benutzer nicht gefunden", show_alert=True)
                return context.user_data['status']
            
            firstname, lastname, allowed_to = user_info
            name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            
            # Aktuellen Status anzeigen
            status_text = ""
            if allowed_to:
                try:
                    allowed_until = DT.datetime.strptime(allowed_to, '%Y-%m-%d %H:%M:%S.%f')
                    if DT.datetime.now() < allowed_until:
                        days_remaining = (allowed_until - DT.datetime.now()).days
                        status_text = f"Aktiver Zugriff bis {allowed_until.strftime('%d.%m.%Y %H:%M')} (noch {days_remaining} Tage)"
                    else:
                        status_text = f"Zugriff abgelaufen am {allowed_until.strftime('%d.%m.%Y %H:%M')}"
                except:
                    status_text = "Ungültiges Datumsformat"
            else:
                status_text = "Kein Zugriff gewährt"
            
            # Inline-Tastatur für Verlängerungsoptionen
            keyboard = [
                [
                    InlineKeyboardButton("✅ 7 Tage", callback_data=f'extend_days_{chat_id}_7'),
                    InlineKeyboardButton("✅ 30 Tage", callback_data=f'extend_days_{chat_id}_30')
                ],
                [
                    InlineKeyboardButton("⚙️ Benutzerdefiniert", callback_data=f'extend_custom_{chat_id}'),
                    InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_extend_access')
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🔧 **Zugriff verlängern für:**\n\n"
                f"👤 {name} (ID: {chat_id})\n"
                f"📅 Status: {status_text}\n\n"
                f"Wähle die Verlängerungsdauer:",
                reply_markup=reply_markup
            )
            
            return context.user_data['status']
            
        except Exception as e:
            logger.error(f"Fehler bei Zugriffverlängerung: {e}")
            await query.answer("❌ Fehler bei der Aktion", show_alert=True)
            return context.user_data['status']
    
    @staticmethod
    async def _refresh_user_list(update, context, user_data, markupList):
        """Aktualisiert die Benutzerliste"""
        query = update.callback_query
        
        # Zuerst Callback beantworten
        await query.answer()
        
        # Benutzerliste direkt anzeigen (ohne grant_access aufzurufen)
        return await AdminMode._show_user_list_callback(update, context, user_data, markupList)
    
    @staticmethod
    async def _show_user_list_callback(update, context, user_data, markupList):
        """Zeigt Benutzerliste für Callback-Updates an"""
        global db
        if db is None:
            await query.answer("❌ Datenbank nicht verfügbar.", show_alert=True)
            return context.user_data['status']
        
        try:
            # Alle Benutzer abrufen, die Zugriff haben oder hatten
            all_users = db.get_all_users()
            
            if not all_users:
                await update.message.reply_text("📋 **Keine Benutzer gefunden**", reply_markup=user_data['keyboard'])
                return context.user_data['status']
            
            # Inline-Tastatur für Benutzerauswahl erstellen
            keyboard = []
            for user in all_users:
                chat_id, firstname, lastname, is_admin, allowed_to, failed_attempts, blocked_until, *rest = user
                name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
                
                # Status-Emoji basierend auf allowedToDatetime
                if allowed_to:
                    try:
                        allowed_until = DT.datetime.strptime(allowed_to, '%Y-%m-%d %H:%M:%S.%f')
                        if DT.datetime.now() < allowed_until:
                            status_emoji = "✅"
                        else:
                            status_emoji = "⏳"
                    except:
                        status_emoji = "⏳"
                else:
                    status_emoji = "❌"
                
                # Button-Text erstellen
                button_text = f"{status_emoji} {name} (ID: {chat_id})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f'extend_access_{chat_id}')])
            
            # Zusätzliche Optionen
            keyboard.extend([
                [InlineKeyboardButton("🔄 Liste aktualisieren", callback_data='refresh_user_list')],
                [InlineKeyboardButton("❌ Abbrechen", callback_data='cancel_extend_access')]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Neue Nachricht senden (nicht bearbeiten)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🔧 **Zugriff verlängern:**\n\n"
                     "Wähle einen Benutzer aus, dessen Zugriff du verlängern möchtest:\n\n"
                     "👑 Admin | ✅ Aktiv | ⏳ Wartend/Abgelaufen | ❌ Kein Zugriff",
                reply_markup=reply_markup
            )
            
            return context.user_data['status']
            
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Benutzerliste: {e}")
            await query.answer("❌ Fehler beim Laden der Benutzerliste", show_alert=True)
            return context.user_data['status']
    
    @staticmethod
    async def _cancel_extend_access(update, context, user_data, markupList):
        """Bricht die Zugriffverlängerung ab"""
        query = update.callback_query
        logger.info(f"_cancel_extend_access aufgerufen")
        
        # Zuerst Callback beantworten
        await query.answer()
        
        # Dann Nachricht bearbeiten (ohne ReplyKeyboardMarkup)
        await query.edit_message_text(
            "❌ Zugriffverlängerung abgebrochen"
        )
        
        return context.user_data['status']
    
    @staticmethod
    async def _extend_access_days(update, context, user_data, markupList, chat_id, days):
        """Verlängert den Zugriff für einen Benutzer um eine bestimmte Anzahl von Tagen"""
        query = update.callback_query
        logger.info(f"_extend_access_days aufgerufen: chat_id={chat_id}, days={days}")
        global db
        
        if db is None:
            await query.answer("❌ Datenbank nicht verfügbar", show_alert=True)
            return context.user_data['status']
        
        try:
            # Zugriff verlängern
            allowed_until = db.grant_access(chat_id, days)
            
            # Benutzer-Info für Benachrichtigung
            user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if user_info:
                firstname, lastname = user_info
                name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            else:
                name = f"Benutzer {chat_id}"
            
            # Benachrichtigung an den Benutzer senden
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'✅ **Zugriff verlängert!**\n\n'
                         f'📅 Dein Zugriff wurde bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr verlängert.\n\n'
                         f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
                )
            except Exception as e:
                logger.error(f"Failed to notify user about access extension: {e}")
            
            # Bestätigung an Admin
            await query.edit_message_text(
                f'✅ **Zugriff verlängert!**\n\n'
                f'👤 {name} (ID: {chat_id})\n'
                f'📅 Bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr\n'
                f'⏰ Um {days} Tage verlängert',
                reply_markup=user_data['keyboard']
            )
            
            return context.user_data['status']
            
        except Exception as e:
            logger.error(f"Fehler bei Zugriffverlängerung: {e}")
            await query.answer("❌ Fehler bei der Verlängerung", show_alert=True)
            return context.user_data['status']
    
    @staticmethod
    async def _extend_access_custom(update, context, user_data, markupList, chat_id):
        """Fordert Admin auf, benutzerdefinierte Tage einzugeben"""
        query = update.callback_query
        logger.info(f"_extend_access_custom aufgerufen: chat_id={chat_id}")
        
        # User-Info für spätere Verwendung speichern
        user_data['extend_access_chat_id'] = chat_id
        user_data['waiting_for_extend_days'] = True
        
        # Zuerst Callback beantworten
        await query.answer()
        
        # Dann Nachricht bearbeiten (ohne Tastatur, um Inline-Konflikt zu vermeiden)
        await query.edit_message_text(
            '⏳ **Benutzerdefinierte Verlängerung**\n\n'
            'Bitte gib die Anzahl der Tage ein, um die der Zugriff verlängert werden soll.\n\n'
            'Beispiele: 7, 30, 365\n'
            'Zum Abbrechen: abbruch oder abbrechen'
        )
        
        return context.user_data['status']
    
    @staticmethod
    async def handle_extend_days(update, context, user_data, markupList):
        """Verarbeitet benutzerdefinierte Tage für Zugriffverlängerung"""
        logger.info(f"handle_extend_days aufgerufen mit Nachricht: {update.message.text}")
        
        # Sicherstellen, dass dies eine normale Nachricht ist (kein Callback)
        if hasattr(update, 'callback_query'):
            logger.error("handle_extend_days mit Callback-Query aufgerufen - das sollte nicht passieren!")
            return context.user_data['status']
        
        global db
        if db is None:
            await update.message.reply_text("❌ Datenbank nicht verfügbar.", reply_markup=user_data['keyboard'])
            return context.user_data['status']
        
        try:
            # Tage aus der Nachricht extrahieren
            message_text = update.message.text.strip()
            
            try:
                days = int(message_text)
                if days <= 0:
                    await update.message.reply_text("❌ Bitte gib eine positive Zahl größer als 0 ein.", reply_markup=user_data['keyboard'])
                    return context.user_data['status']
            except ValueError:
                await update.message.reply_text("❌ Bitte gib eine gültige positive Zahl ein (z.B. 7, 30, 365).", reply_markup=user_data['keyboard'])
                return context.user_data['status']
            
            # Chat-ID aus den user_data holen
            chat_id = user_data.get('extend_access_chat_id')
            if not chat_id:
                await update.message.reply_text("❌ Fehler: Keine Benutzer-ID gefunden.", reply_markup=user_data['keyboard'])
                return context.user_data['status']
            
            # Zugriff verlängern
            allowed_until = db.grant_access(chat_id, days)
            
            # Benutzer-Info für Benachrichtigung
            user_info = db.fetch_one(f"SELECT firstname, lastname FROM {db.table_name} WHERE chatID = ?", (chat_id,))
            if user_info:
                firstname, lastname = user_info
                name = f"{firstname or 'Unbekannt'} {lastname or ''}".strip()
            else:
                name = f"Benutzer {chat_id}"
            
            # Benachrichtigung an den Benutzer senden
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'✅ **Zugriff verlängert!**\n\n'
                         f'📅 Dein Zugriff wurde bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr verlängert.\n\n'
                         f'Viel Spaß mit dem FritzDECT-Bot! 🤖'
                )
            except Exception as e:
                logger.error(f"Failed to notify user about access extension: {e}")
            
            # Bestätigung an Admin
            await update.message.reply_text(
                f'✅ **Zugriff verlängert!**\n\n'
                f'👤 {name} (ID: {chat_id})\n'
                f'📅 Bis zum {allowed_until.strftime("%d.%m.%Y %H:%M")} Uhr\n'
                f'⏰ Um {days} Tage verlängert',
                reply_markup=user_data['keyboard']
            )
            
            # Status zurücksetzen
            user_data['extend_access_chat_id'] = None
            user_data['waiting_for_extend_days'] = None
            
            return context.user_data['status']
            
        except Exception as e:
            await update.message.reply_text(f'❌ Fehler: {str(e)}', reply_markup=user_data['keyboard'])
            return context.user_data['status']

# Datenbank-Instanz setzen
def init_database(database_instance):
    """Initialisiert die Datenbank-Instanz"""
    AdminMode.set_database(database_instance)
