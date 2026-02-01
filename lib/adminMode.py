#!/usr/bin/python3
# -*- coding: utf-8 -*-
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


# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'nextRequest': 'nächster Request',
         'displayUsers': 'Zeige alle User',
         'deleteUsers': 'Lösche User',
         'quit': 'Verlasse AdminMode'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'nextRequest': 'Zeigt den nächsten User-Request an',
         'displayUsers': 'Zeigt alle User',
         'deleteUsers': 'Lösche User',
         'help': 'Zeigt diesen Text an',
         'quit': 'Verlasse AdminMode'}

async def displayUsers(bot, update, user_data, markupList):
    userDB = UserDatabase()
    try:
        # userList() methode existiert möglicherweise nicht, wir verwenden eine alternative
        users = "User list functionality not yet implemented"
        await update.message.reply_text("Hier die Liste aller aktiven User \n \n" + users,
            reply_markup=user_data['keyboard'])
    except Exception as e:
        await update.message.reply_text(f"Fehler beim Abrufen der User-Liste: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

async def deleteUsers(bot, update, user_data, markupList):
    # todo: muss weiteren Workflow schreiben
    userDB = UserDatabase()
    try:
        users = "User list functionality not yet implemented"
        user_data['keyboard'] = markupList[ADMIN]
        user_data['status'] = ADMIN
        await update.message.reply_text("Bitte wähle den zu löschenden User aus in dem du einen dessen Nummer schickst: \n \n" + users,
            reply_markup=user_data['keyboard'])
    except Exception as e:
        await update.message.reply_text(f"Fehler: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

async def quit(bot, update, user_data, markupList):
    user_data['keyboard'] = markupList[MAIN]
    await update.message.reply_text("EXIT --ADMINMODE--",
            reply_markup=user_data['keyboard'])
    user_data['status'] = MAIN
    return user_data['status']

async def nextRequest(bot, update, user_data, markupList):
    userDB = UserDatabase()
    try:
        # getNextRequest() methode existiert möglicherweise nicht
        nextRequest = {'chatID': None, 'firstname': 'No', 'lastname': 'Request'}
        if nextRequest['chatID'] is not None:
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = nextRequest
            await update.message.reply_text("Request "+str(nextRequest['chatID'])+": "+str(nextRequest['firstname'])+" "+str(nextRequest['lastname']),
                reply_markup=user_data['keyboard'])
        else:
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = nextRequest
            await update.message.reply_text("No request.",
                reply_markup=user_data['keyboard'])
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



async def help(bot, update, user_data, markupList):
    text=''
    for key, value in textbefehl.items():
        text = text + '- /' + key + ' ' + value + '\n'
            
    await update.message.reply_text(
                'Nutze das Keyboard für Admin-Aktionen: \n'+
                 str(text)+' ',
                reply_markup=user_data['keyboard'])
    return user_data['status']
    
async def default(bot, update, user_data, markupList):
    return await help(bot, update, user_data, markupList)
