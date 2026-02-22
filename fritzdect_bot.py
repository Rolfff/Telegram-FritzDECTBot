#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import os
from telegram import Update, ReplyKeyboardMarkup
import signal
import sys
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from lib.config import modeList, markupList, LOGIN, MAIN, ADMIN, STATISTICS, AUTOMATION, Config, genMarkupList
from lib.user_database import UserDatabase
from lib.fritzbox_api import FritzBoxAPI

import lib.adminMode as AdminMode
import lib.loginMode as LoginMode
import lib.statistikMode as StatistikMode
import lib.automationMode as AutomationMode

# Konfiguration
config = Config()
db = UserDatabase()

# Textbefehle für MAIN-Status (da modeList[MAIN] = None)
main_textbefehl = {
    'start': 'Bot starten und Login einleiten',
    'help': 'Diese Hilfe anzeigen',
    'letsgo': 'Rechte überprüfen und fortfahren',
    'logout': 'Ausloggen',
    'bye': 'Bot beenden',
    'heizung': 'Alle Heizkörper und deren Temperaturen anzeigen',
    'geraete': 'Alle FritzBox Geräte und deren Temperaturen anzeigen',
    'vacation_mode': 'Schaltet FritzBox-Urlaubsschaltung für alle Heizkörper ein/aus',
    'admin': 'Aktiviert den Admin-Modus (nur Admin)',
    'automation': 'Öffnet den Automation-Modus für Szenarien und Vorlagen'
}

# Global variable for graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nBot wird beendet...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
fritzbox = FritzBoxAPI()

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
modeList[STATISTICS] = StatistikMode
modeList[AUTOMATION] = AutomationMode

# markupList generieren
from lib.config import genMarkupList
markupList = genMarkupList()


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
            if db.user_exists(int(chat_id)) and db.is_user_allowed(int(chat_id)):
                user_data['isAuthenticated'] = True
            else:
                user_data['isAuthenticated'] = False
                if not db.is_user_blocked(int(chat_id)):
                    await update.message.reply_text('Ohh... Deine Berechtigung ist abgelaufen.', reply_markup=markupList[LOGIN])
        except:
            user_data['isAuthenticated'] = False
    
    if not user_data['isAuthenticated']:
        user_data['keyboard'] = markupList[LOGIN]
        user_data['status'] = LOGIN
        return LOGIN
    else:
        if user_data['isAuthenticated'] and user_data['status'] == LOGIN:
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
        if context.user_data['status'] != LOGIN:
            await checkAuthentifizierung(update, context.user_data)
        
        if context.user_data['isAuthenticated'] or context.user_data['status'] == LOGIN:
            funkName=None
            # Suche nach FunktionsName ([1:] entfernt / am Anfang der Zeichenkette)
            if textFromUser.startswith('/') and textFromUser[1:] in classs.tastertur:
                funkName=textFromUser[1:]
            # Suche über Button-Beschriftung
            elif textFromUser in classs.tastertur.values():
                for key, value in classs.tastertur.items():
                    if value == textFromUser:
                        funkName=key
            if funkName is None:
                # Default Funktion versuchen
                try:
                    func = getattr(classs, 'default')
                    #funcRet = await func(context.bot, update, context.user_data, markupList)
                    funcRet = await func(update, context, context.user_data, markupList)
                    context.user_data['status'] = funcRet
                except AttributeError as e:
                    logger.error(f"Default-Funktion nicht gefunden in Klasse {classs.__name__}: {e}")
                    await update.message.reply_text(
                        'Modus: "'+textFromUser+'" wurde leider nicht gefunden.\n'+
                        'Versuche es mal mit /help.\n',
                        reply_markup=markupList[context.user_data['status']])
            else:
                if context.user_data['chatId'] != config.get_admin_chat_id():
                    try:
                        await context.bot.send_message(config.get_admin_chat_id(), text=context.user_data['firstname']+" hat Funktion "+str(classs.__name__)+"."+funkName+" aufgerufen.")
                    except Exception as e:
                        logger.warning(f"Konnte Admin-Benachrichtigung nicht senden: {e}")
                
                func = getattr(classs, str(funkName))
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

async def switchToAutomationModus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wechselt in den Automation-Modus"""
    context.user_data['keyboard'] = markupList[AUTOMATION]
    context.user_data['status'] = AUTOMATION
    await update.message.reply_text("-->AUTOMATIONMODE<--\n\n🤖 Verfügbare Funktionen:\n"
                                  "• Szenarien anzeigen und ausführen\n"
                                  "• Vorlagen anzeigen und anwenden\n"
                                  "• Urlaubs-Szenarien erstellen\n\n"
                                  "💡 Nutze /help für alle Befehle",
                                  reply_markup=context.user_data['keyboard'])
    return context.user_data['status']

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zeigt Hilfe mit allen verfügbaren Befehlen"""
    help_text = """Nutze das Keyboard für Standard-Aktionen.
Weitere Funktionen:"""
    
    if context.user_data['chatId'] == config.get_admin_chat_id():
        help_text += "\n- /admin aktiviert den Admin-Modus"
    
    help_text += "\n- /automation öffnet den Automation-Modus"
    
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
                for key, value in modeList[current_status].textbefehl.items():
                    help_text += f'\n- /{key} {value}'
        except (KeyError, AttributeError, IndexError) as e:
            # Fallback falls etwas schief geht
            help_text += f'\n- Status {current_status}: Keine Hilfe verfügbar'
    
    help_text += "\n \nInvalide Angaben führen zu dieser Ausgabe. Wende dich bei weitern Fragen an den Administrator."
    
    await update.message.reply_text(help_text)

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für unbekannte Textnachrichten - zeigt Hilfe an"""
    await help_command(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für unbekannte Befehle - zeigt Hilfe an"""
    await help_command(update, context)

async def async_main():
    """Asynchronous main function"""
    token = config.get_telegram_token()
    if not token:
        print("Bot-Token nicht in config.json gefunden!")
        return
    
    application = Application.builder().token(token).build()
    
    autoStatesHandler={
#            LOGIN: [
#                MessageHandler(filters.Regex('^(Login)$'), getPasswort),
#                CommandHandler('Login', getPasswort),
#                MessageHandler(filters.Regex('^(Bye)$'), done),
#                MessageHandler(filters.TEXT & ~filters.COMMAND, login),
#                MessageHandler(filters.COMMAND, unknown_command),
#            ],
            MAIN: [
                MessageHandler(filters.Regex('^(Geräte)$'), done),
                CommandHandler('geraete', done),
                MessageHandler(filters.Regex('^(Temperatur)$'), lambda update, context: StatistikMode.set_temp(update, context, context.user_data, markupList)),
                CommandHandler('temperatur', lambda update, context: StatistikMode.set_temp(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Temp\\.-Verlauf)$'), lambda update, context: StatistikMode.temp_history(update, context, context.user_data, markupList)),
                CommandHandler('temp_history', lambda update, context: StatistikMode.temp_history(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Logout)$'), done),
                CommandHandler('logout', done),
#TODO pers. Config zb Batterien anzeigen, PushNoti bei Änderungen von anderen, Absenk temp bei Urlaub...                MessageHandler(filters.Regex('^(Einstellungen)$'), lambda update, context: ConfigMode.status(update, context, context.user_data, markupList)),
#                CommandHandler('Einstellungen', lambda update, context: ConfigMode.status(update, context, context.user_data, markupList)),
                MessageHandler(filters.Regex('^(Heizung)$'), lambda update, context: StatistikMode.status(update, context, context.user_data, markupList)),
                CommandHandler('Heizung', lambda update, context: StatistikMode.status(update, context, context.user_data, markupList)),
                CommandHandler('admin', switchToAdminModus),
                CommandHandler('automation', switchToAutomationModus),
                MessageHandler(filters.Regex('^(Automation)$'), switchToAutomationModus),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message),
                MessageHandler(filters.COMMAND, unknown_command),
            ]
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
            # /automation Befehl für alle Modi hinzufügen
            autoStates.extend([CommandHandler('automation', switchToAutomationModus)])
            autoStates.extend([CommandHandler('help', help_command)])
            autoStates.extend([MessageHandler(filters.TEXT, selectModeFunc)])
            autoStatesHandler[x]=autoStates

    
    # ConversationHandler für die Zustandsverwaltung
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),MessageHandler(filters.TEXT, start)],
        states=autoStatesHandler,
        fallbacks=[CommandHandler("logout", done)],
    )
    
    application.add_handler(conv_handler)
    
    # Help command handler
    application.add_handler(CommandHandler("help", help_command))
    
    # Fallback für unbekannte Befehle
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Callback handler für Inline-Keyboards
    logger.info("Registriere Callback-Handler...")
    
    # Handler für Temperatur-Callbacks
    application.add_handler(CallbackQueryHandler(StatistikMode.handle_temp_callback, pattern=r'select_heater_.*'))
    application.add_handler(CallbackQueryHandler(StatistikMode.handle_temp_callback, pattern=r'cancel_temp_set'))
    
    # Handler für Automation Mode Callbacks
    application.add_handler(CallbackQueryHandler(AutomationMode.handle_scenario_callback, pattern=r'execute_scenario_.*'))
    application.add_handler(CallbackQueryHandler(AutomationMode.handle_scenario_callback, pattern=r'apply_template_.*'))
    application.add_handler(CallbackQueryHandler(AutomationMode.handle_scenario_callback, pattern=r'cancel_scenario'))
    application.add_handler(CallbackQueryHandler(AutomationMode.handle_scenario_callback, pattern=r'cancel_template'))
    
    # Handler für Fenster-Callbacks mit allen möglichen Patterns
    window_patterns = [
        r'cancel_window_mode',
        r'window_disable_all', 
        r'window_all_heaters',
        r'window_heater_.*',
        r'window_disable_.*'
    ]
    
    for pattern in window_patterns:
        application.add_handler(CallbackQueryHandler(StatistikMode.handle_window_callback, pattern=pattern))
        logger.info(f"Callback-Handler registriert für Pattern: {pattern}")
    
    # Fallback-Handler für alle anderen Callbacks
    application.add_handler(CallbackQueryHandler(StatistikMode.handle_window_callback))
    logger.info("Fallback Callback-Handler registriert")
    
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