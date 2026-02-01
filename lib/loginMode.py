#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import importlib.util
import sys
from telegram.ext import ConversationHandler

def load_module(name, filepath):
    """Load a module from file path using importlib"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), filepath))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Load configuration and database modules
config_module = load_module("config", "config.py")
config = config_module.Config()
user_database_module = load_module("user_database", "user_database.py")
db = user_database_module.UserDatabase()

# Import Konstanten aus config
LOGIN, MAIN, ADMIN = config_module.LOGIN, config_module.MAIN, config_module.ADMIN


# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'login': 'Login',
         'bye': 'Bye'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'login': 'Um alle Funktionen zu nutzen, musst du dich einloggen',
         'bye': 'Schließt die aktuelle Sitzung'}

async def default(bot, update, user_data, markupList):
    return await login(bot, update, user_data, markupList)

async def login(bot, update, user_data, markupList):
    """Login-Verarbeitung"""
    password = update.message.text
    chat_id = update.effective_chat.id
    
    # Prüfen ob Benutzer geblockt ist
    if db.is_user_blocked(chat_id):
        block_days = config.get_block_duration_days()
        await update.message.reply_text(
            f"Du bist für {block_days} Tage geblockt wegen zu vieler fehlgeschlagener Login-Versuche."
        )
        await bye(bot, update, user_data, markupList)
        return LOGIN

    if password == "Login" or password == "/login":
        await update.message.reply_text(
            "Bitte gib dein Passwort ein",
            reply_markup=user_data['keyboard']
        )
        return user_data['status']
    
    if password == config.get_telegram_password():
        # Erfolgreicher Login - fehlgeschlagene Versuche zurücksetzen
        db.reset_failed_attempts(chat_id)
        
        if str(chat_id) == config.get_admin_chat_id():
            db.add_user(chat_id, update.effective_user.first_name, is_admin=1)
            await update.message.reply_text(
                "Admin-Login erfolgreich!",
                reply_markup= markupList[MAIN]
            )
        else:
            db.add_user(chat_id, update.effective_user.first_name)
            await update.message.reply_text(
                "Login erfolgreich!",
                reply_markup= markupList[MAIN]
            )
            try:
                await bot.send_message(config.get_admin_chat_id(),text='Request: '+user_data['firstname']+' '+user_data['lastname']+' möchte auf dein Licht im Zimmer zugreifen. Möchtest du in den Admin-Modus wechseln?')
                await bot.send_message(config.get_admin_chat_id(),text='Antworte: /admin')
                await bot.send_message(user_data['chatId'],text='Der Admin wurde benachrichtigt.')
            except Exception as e:
                print(f"Failed to notify admin: {e}")
                await bot.send_message(user_data['chatId'],text='Der Admin konnte nicht benachrichtigt werden. Bitte überprüfe die Bot Konfiguration.')
            await update.message.reply_text(
                'Falls der Admin nicht schnell genug reagiert, gib das Passwort bitte noch einmal ein um den Admin an die Freigebe zu erinnern.',
                reply_markup=markupList[LOGIN])
        user_data['keyboard'] = markupList[LOGIN]
        user_data['status'] = LOGIN
        return user_data['status'] 
    else:
        # Fehlgeschlagener Login-Versuch aufzeichnen
        is_blocked = db.record_failed_attempt(chat_id)
        max_attempts = config.get_max_failed_attempts()
        
        if is_blocked:
            block_days = config.get_block_duration_days()
            await update.message.reply_text(
                f"Zu viele fehlgeschlagene Login-Versuche! Du bist für {block_days} Tage geblockt."
            )
        else:
            await update.message.reply_text(
                f"Falsches Passwort! ({max_attempts - db.get_failed_attempts(chat_id)} Versuche übrig)"
            )
        return LOGIN

async def bye(bot, update, user_data, markupList):
    """Beendet die Konversation"""
    if 'isAuthenticated' in user_data:
        del user_data['isAuthenticated']
        del user_data['status']
        del user_data['keyboard'] 

    await update.message.reply_text("bye")
    
    user_data.clear()
    return ConversationHandler.END

