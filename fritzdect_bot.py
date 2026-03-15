#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import os
# Telegram Importe mit Fallback für Tests
try:
    from telegram import Update, ReplyKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Update = None
    ReplyKeyboardMarkup = None
    print("WARNING: telegram module nicht gefunden - Bot läuft im Test-Modus")

import signal
import sys
import asyncio
# Telegram.ext Import mit Fallback
try:
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
    TELEGRAM_EXT_AVAILABLE = True
except ImportError:
    TELEGRAM_EXT_AVAILABLE = False
    Application = None
    CommandHandler = None
    MessageHandler = None
    filters = None
    ContextTypes = None
    ConversationHandler = None
    CallbackQueryHandler = None
    print("WARNING: telegram.ext module nicht gefunden - Bot läuft im Test-Modus")
from lib.config import modeList, markupList, LOGIN, MAIN, ADMIN, STATISTICS, AUTOMATION, SETTINGS, Config, genMarkupList
from lib.user_database import UserDatabase
from lib.fritzbox_api_optimized import OptimizedFritzBoxAPI

import lib.adminMode as AdminMode
import lib.loginMode as LoginMode
import lib.statistikMode_optimized as StatistikModeOptimized
import lib.settingsMode as SettingsMode
import lib.automationMode_optimized as AutomationModeOptimized

# Konfiguration
config = Config()
db = UserDatabase()

# LoginMode die globale Datenbank-Instanz setzen
LoginMode.set_database(db)
# AdminMode die globale Datenbank-Instanz setzen
AdminMode.set_database(db)
# SettingsMode die globale Datenbank-Instanz setzen
SettingsMode.set_database(db)

# Textbefehle für MAIN-Status (da modeList[MAIN] = None)
main_textbefehl = {
    'start': 'Bot starten und Login einleiten',
    'help': 'Diese Hilfe anzeigen',
    'logout': 'Ausloggen',
    'heizung': 'Alle Heizkörper und deren Temperaturen anzeigen',
    'set_temp': 'Temperatur der Heizungen setzen',
    'temp_history': 'Temp.-Verlauf der Heizungen anzeigen',
    'automation': 'Öffnet den Automation-Modus für Szenarien und Vorlagen',
    'einstellungen': 'Öffnet die Einstellungen für Sprache und Benachrichtigungen'
}

# Globale variable for graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nBot wird beendet...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Nur bei Verfügbarkeit der Telegram-Module initialisieren
if TELEGRAM_AVAILABLE and TELEGRAM_EXT_AVAILABLE:
    fritzbox = OptimizedFritzBoxAPI()

    # Logging
    logging.basicConfig(**config.get_logging_config())
    logger = logging.getLogger(__name__)
    logger.info("=== Bot gestartet - Logging aktiviert ===")
    logger.info(f"Logging-Level: {config.get('logging.level')}")
    
    # Modi Klassennamen zu den Statusen (Index 0=MAIN, 1=LOGIN, 2=ADMIN, usw.)
    # Hinweis: Die Indizes müssen mit den Werten von ConversationHandler.states übereinstimmen
    from lib.config import modeList
    modeList[LOGIN] = LoginMode
    modeList[ADMIN] = AdminMode
    modeList[STATISTICS] = StatistikModeOptimized  # Optimierte Version verwenden!
    modeList[AUTOMATION] = AutomationModeOptimized  # Optimierte Version verwenden!
    modeList[SETTINGS] = SettingsMode
    
    # markupList generieren
    from lib.config import genMarkupList
    markupList = genMarkupList()
    
    # Weitere Importe nur bei Verfügbarkeit
    import lib.adminMode as AdminMode
    import lib.loginMode as LoginMode
    import lib.statistikMode_optimized as StatistikModeOptimized
    import lib.automationMode_optimized as AutomationModeOptimized
else:
    print("WARNING: Telegram-Module nicht verfügbar - Bot wird nicht gestartet")
    sys.exit(1)


def initializeChatData(message, user_data):
    """Initialisiert die Chat-Daten"""
    user_data['langCode'] = str(message.from_user.language_code) if message.from_user.language_code else 'de'
    user_data['chatId'] = str(message.chat.id)
    user_data['firstname'] = str(message.from_user.first_name) if message.from_user.first_name else ''
    user_data['lastname'] = str(message.from_user.last_name) if message.from_user.last_name else ''
    user_data['keyboard'] = markupList[LOGIN]
    user_data['status'] = LOGIN
    user_data['userRequest'] = None
    
    # Prüfen ob Admin (immer erlaubt)
    if user_data['chatId'] == config.get_admin_chat_id():
        user_data['isAuthenticated'] = True
    else:
        # Für andere Benutzer initial auf False setzen, wird in checkAuthentifizierung geprüft
        user_data['isAuthenticated'] = False
    
    logger.info(f'chatID:{user_data["chatId"]} Username: {user_data["firstname"]} {user_data["lastname"]}')

async def checkAuthentifizierung(update, user_data):
    """Überprüft die Authentifizierung"""
    chat_id = user_data['chatId']
    
    # Admin immer erlauben
    if chat_id == config.get_admin_chat_id():
        user_data['isAuthenticated'] = True
        # Admin zur Datenbank hinzufügen falls nicht vorhanden
        try:
            db.add_user(int(chat_id), user_data['firstname'], is_admin=1)
        except:
            pass  # Admin existiert wahrscheinlich schon
    else:
        # Prüfen ob Benutzer in Datenbank und nicht geblockt
        try:
            # Prüfen ob User gerade freigeschaltet wurde (hat Zugriff aber Status ist noch LOGIN)
            was_just_granted = (db.user_exists(int(chat_id)) and 
                              db.is_access_granted(int(chat_id)) and 
                              user_data.get('status') == LOGIN)
            
            if db.user_exists(int(chat_id)) and (db.is_user_allowed(int(chat_id)) or db.is_access_granted(int(chat_id))):
                user_data['isAuthenticated'] = True
                # Wenn User gerade freigeschaltet wurde, automatisch in MAIN wechseln
                if was_just_granted:
                    user_data['keyboard'] = markupList[MAIN]
                    user_data['status'] = MAIN
                    await update.message.reply_text(
                        '🎉 **Willkommen im FritzDECT-Bot!**\n\n'
                        'Dein Zugriff wurde erfolgreich aktiviert.\n'
                        'Du kannst jetzt alle Funktionen nutzen.\n\n'
                        '💡 Nutze /help für eine Übersicht aller Befehle.',
                        reply_markup=markupList[MAIN]
                    )
            else:
                user_data['isAuthenticated'] = False
                if not db.is_user_blocked(int(chat_id)):
                    await update.message.reply_text('Ohh... Deine Berechtigung ist abgelaufen.', reply_markup=markupList[LOGIN])
        except:
            user_data['isAuthenticated'] = False
    
    # Status nur anpassen wenn nicht bereits auf MAIN gesetzt (z.B. nach Freischaltung)
    if not user_data['isAuthenticated']:
        user_data['keyboard'] = markupList[LOGIN]
        user_data['status'] = LOGIN
        return LOGIN
    elif user_data['isAuthenticated'] and user_data['status'] == LOGIN:
        # Nur wechseln wenn nicht bereits durch Freischaltung auf MAIN gesetzt
        if 'was_just_granted' not in locals() or not was_just_granted:
            user_data['keyboard'] = markupList[MAIN]
            user_data['status'] = MAIN

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Beendet die Konversation"""
    if 'choice' in context.user_data:
        del context.user_data['choice']

    await update.message.reply_text("bye")
    
    context.user_data.clear()
    return ConversationHandler.END

async def selectModeFunc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wählt die passende Funktion basierend auf dem Modus aus der modeList"""
    if modeList[context.user_data['status']] is None:
        await update.message.reply_text(
                'Interner Error: Keine Klasse gefunden in modeList an Stelle "'+str(context.user_data['status'])+'".\n',
                reply_markup=ReplyKeyboardMarkup(context.user_data['keyboard'], one_time_keyboard=True))
        return context.user_data['status']
    else:
        classs = modeList[context.user_data['status']]
        
        textFromUser = update.message.text
        
        # Authentifizierung prüfen für alle Modi außer LOGIN
        if context.user_data['status'] != LOGIN:
            await checkAuthentifizierung(update, context.user_data)
            # Wenn Status durch checkAuthentifizierung geändert wurde (z.B. nach Freischaltung)
            if context.user_data['status'] == MAIN and context.user_data.get('isAuthenticated'):
                # User wurde gerade freigeschaltet, zeige Hauptmenü
                return MAIN
            elif context.user_data['status'] == LOGIN:
                # User wurde nicht authentifiziert, bleibe im LOGIN
                return LOGIN
        
        # Bei LOGIN-Status immer die Login-Funktion aufrufen
        if context.user_data['status'] == LOGIN:
            # Default Funktion (login) aufrufen
            try:
                func = getattr(classs, 'default')
                # Korrekte Parameter-Reihenfolge: (update, context, user_data, markupList)
                funcRet = await func(update, context, context.user_data, markupList)
                context.user_data['status'] = funcRet
                return funcRet
            except AttributeError as e:
                logger.error(f"Default-Funktion nicht gefunden in Klasse {classs.__name__}: {e}")
                await update.message.reply_text(
                    'Interner Fehler im Login-Modus.\n',
                    reply_markup=markupList[context.user_data['status']])
                return context.user_data['status']
        if context.user_data['status'] == MAIN:
            # Hauptmenü anzeigen
            await help_command(update, context)
            return context.user_data['status']

        if context.user_data['isAuthenticated'] and context.user_data['status'] != LOGIN:
            funkName=None
            # Normale Behandlung für andere Modi (MAIN hat keine Klasse)
            # Suche nach FunktionsName ([1:] entfernt / am Anfang der Zeichenkette)
            if textFromUser.startswith('/') and textFromUser[1:] in classs.tastertur:
                funkName=textFromUser[1:]
            # Suche über Button-Beschriftung
            elif textFromUser in classs.tastertur.values():
                    for key, value in classs.tastertur.items():
                        if value == textFromUser:
                            funkName=key
            if funkName is None:
                # Default Funktion versuchen (nur für Nicht-MAIN Modi)
                    try:
                        func = getattr(classs, 'default')
                        # Korrekte Parameter-Reihenfolge: (update, context, user_data, markupList)
                        funcRet = await func(update, context, context.user_data, markupList)
                        context.user_data['status'] = funcRet
                    except AttributeError as e:
                        logger.error(f"Default-Funktion nicht gefunden in Klasse {classs.__name__}: {e}")
                        await update.message.reply_text(
                            'Modus: "'+textFromUser+'" wurde leider nicht gefunden.\n'+
                            'Versuche es mal mit /help.\n',
                            reply_markup=markupList[context.user_data['status']])
            else:
                # Normale Funktionsausführung für andere Modi
                if context.user_data['chatId'] != config.get_admin_chat_id():
                    try:
                        await context.bot.send_message(config.get_admin_chat_id(), text=context.user_data['firstname']+" hat Funktion "+str(classs.__name__)+"."+funkName+" aufgerufen.")
                    except Exception as e:
                        logger.warning(f"Konnte Admin-Benachrichtigung nicht senden: {e}")
                
                func = getattr(classs, str(funkName))
                # Korrekte Parameter-Reihenfolge: (update, context, user_data, markupList)
                funcRet = await func(update, context, context.user_data, markupList)
                context.user_data['status'] = funcRet
    return context.user_data['status']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Startfunktion"""
    # Chat-Daten initialisieren
    initializeChatData(update.message, context.user_data)
    
    await update.message.reply_text(
        f"Hi {update.message.from_user.first_name}! "
    )
    
    # Authentifizierung prüfen
    await checkAuthentifizierung(update, context.user_data)
    
    if context.user_data['isAuthenticated']:
        await update.message.reply_text("Willkommen zurück ;P",
            reply_markup=markupList[context.user_data['status']])
        return context.user_data['status']
    else:
        await update.message.reply_text(
            "Bitte melde dich mit dem Passwort an um fortzufahren:",
            reply_markup=markupList[LOGIN]
        )
        return LOGIN

async def switchToAdminModus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['chatId'] == config.get_admin_chat_id():
        context.user_data['keyboard'] = markupList[ADMIN]
        context.user_data['status'] = ADMIN
        await update.message.reply_text("-->ADMINMODE<--",
                                  reply_markup=context.user_data['keyboard'])
        return context.user_data['status']
    else:
        await update.message.reply_text('Sorry, du hast leider keine Admin-Rechte.')

   

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt Hilfe mit allen verfügbaren Befehlen"""
    # Debug: Logge den Aufruf
    logger.info(f"help_command aufgerufen für Status: {context.user_data.get('status', MAIN)}")
    
    help_text = """Nutze das Keyboard für Standard-Aktionen.
Weitere Funktionen:"""
    help_text += "\n- /help zeigt diesen Text an"
    if context.user_data['chatId'] == config.get_admin_chat_id():
        help_text += "\n- /admin aktiviert den Admin-Modus"
    
    # Textbefehle für aktuellen Status anzeigen
    current_status = context.user_data.get('status', MAIN)
    
    if current_status == MAIN:
        # MAIN-Status hat keine Klasse, aber unsere main_textbefehl Map
        for key, value in main_textbefehl.items():
            help_text += f'\n- /{key} {value}'
    else:
        # Andere Modi haben Klassen mit textbefehl Maps
        try:
            if modeList[current_status] is not None:
                logger.debug(f"Suche textbefehl in modeList[{current_status}]")
                for key, value in modeList[current_status].textbefehl.items():
                    help_text += f'\n- /{key} {value}'
                    logger.debug(f"Gefunden: {key} = {value}")
        except (KeyError, AttributeError, IndexError) as e:
            # Fallback falls etwas schief geht
            logger.error(f"Fehler in help_command: {e}")
            help_text += f'\n- Status {current_status}: Keine Hilfe verfügbar'
    
    help_text += "\n \nInvalide Angaben führen zu dieser Ausgabe. Wande dich bei weitern Fragen an den Administrator."
    
    logger.debug(f"Sende Hilfe-Text: {help_text[:100]}...")
    await update.message.reply_text(help_text)

async def async_main():
    """Asynchronous main function"""
    # Prüfen ob Telegram-Module verfügbar sind
    if not TELEGRAM_AVAILABLE or not TELEGRAM_EXT_AVAILABLE:
        print("ERROR: Telegram-Module nicht verfügbar - Bot kann nicht gestartet werden")
        return
    
    token = config.get_telegram_token()
    if not token:
        print("Bot-Token nicht in config.json gefunden!")
        return
    
    application = Application.builder().token(token).build()
    
    autoStatesHandler={
            MAIN: [
                MessageHandler(filters.Regex('^(Temperatur setzen)$'), lambda update, context: StatistikModeOptimized.set_temp(update, context, context.user_data, markupList)),
                CommandHandler('set_temp', lambda update, context: StatistikModeOptimized.set_temp(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Temp\\.-Verlauf)$'), lambda update, context: StatistikModeOptimized.temp_history(update, context, context.user_data, markupList)),
                CommandHandler('temp_history', lambda update, context: StatistikModeOptimized.temp_history(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Logout)$'), done),
                CommandHandler('logout', done),
                MessageHandler(filters.Regex('^(Heizung)$'), lambda update, context: StatistikModeOptimized.status(update, context, context.user_data, markupList)),
                CommandHandler('heizung', lambda update, context: StatistikModeOptimized.status(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Automation)$'), lambda update, context: AutomationModeOptimized.default(update, context, context.user_data, markupList)),
                CommandHandler('automation', lambda update, context: AutomationModeOptimized.default(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Einstellungen)$'), lambda update, context: SettingsMode.default(update, context, context.user_data, markupList)),
                CommandHandler('einstellungen',  lambda update, context: SettingsMode.default(update, context, context.user_data, markupList)),
            ] if TELEGRAM_AVAILABLE and TELEGRAM_EXT_AVAILABLE else []
        }
    
    for x in range(len(modeList)):
        
        #Gegen none testen
        if modeList[x] is not None:
            #print(str(x)+"="+str(modeList[x]))
            autoStates=[]
            for value in modeList[x].tastertur.values():
               autoStates.extend([MessageHandler(filters.Regex('^'+str(value)+'$'),
                                   selectModeFunc)])
            for key in modeList[x].textbefehl.keys():
               autoStates.extend([CommandHandler(str(key),
                                   selectModeFunc)])
            # /admin Befehl für alle Modi hinzufügen (Berechtigung wird in switchToAdminModus geprüft)
            autoStates.extend([CommandHandler('admin', switchToAdminModus)])
            # /help Befehl für alle Modi hinzufügen - überflüssig, wird global gehandelt
            # autoStates.extend([CommandHandler('help', help_command)])
            #selectModeFunc nur für Modi mit Klassen registrieren (nicht für MAIN)
            autoStates.extend([MessageHandler(filters.TEXT & ~filters.COMMAND, selectModeFunc)])
            autoStatesHandler[x]=autoStates

    
    # ConversationHandler für die Zustandsverwaltung
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),MessageHandler(filters.TEXT, start)],
        states=autoStatesHandler,
        fallbacks=[CommandHandler("help", help_command), CommandHandler("logout", done)],
    )
    
    application.add_handler(conv_handler)
    
    # Help command handler
    application.add_handler(CommandHandler("help", help_command))
    
    # Fallback für unbekannte Textnachrichten
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, help_command))
    
    # Callback handler für Inline-Keyboards
    logger.info("Registriere Callback-Handler...")
    
    # Dynamische Callback-Handler registrieren
    callback_configs = [
        (STATISTICS, StatistikModeOptimized),
        (AUTOMATION, AutomationModeOptimized),
        (SETTINGS, SettingsMode),
        (ADMIN, AdminMode)
    ]
    
    for mode, module in callback_configs:
        if hasattr(module, 'get_callback_handlers'):
            config = module.get_callback_handlers()
            handler = config['handler']
            for pattern in config['patterns']:
                application.add_handler(CallbackQueryHandler(
                    lambda update, context, h=handler: h(update, context, context.user_data, markupList), 
                    pattern=pattern
                ))
                logger.info(f"Callback-Handler registriert für Pattern: {pattern}")
    
    print("Bot wird gestartet...")
    
    # Start the bot with shutdown handling
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        print("Bot wird heruntergefahren...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main():
    """Hauptfunktion"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nBot beendet.")
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == '__main__':
    main()