#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import importlib.util
import sys

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

def displayUsers(bot, update, user_data, markupList):
    userDB = UserDatabase()
    try:
        # userList() methode existiert möglicherweise nicht, wir verwenden eine alternative
        users = "User list functionality not yet implemented"
        update.message.reply_text("Hier die Liste aller aktiven User \n \n" + users,
            reply_markup=user_data['keyboard'])
    except Exception as e:
        update.message.reply_text(f"Fehler beim Abrufen der User-Liste: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

def deleteUsers(bot, update, user_data, markupList):
    # todo: muss weiteren Workflow schreiben
    userDB = UserDatabase()
    try:
        users = "User list functionality not yet implemented"
        user_data['keyboard'] = markupList[ADMIN]
        user_data['status'] = ADMIN
        update.message.reply_text("Bitte wähle den zu löschenden User aus in dem du einen dessen Nummer schickst: \n \n" + users,
            reply_markup=user_data['keyboard'])
    except Exception as e:
        update.message.reply_text(f"Fehler: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

def quit(bot, update, user_data, markupList):
    user_data['keyboard'] = markupList[MAIN]
    update.message.reply_text("EXIT --ADMINMODE--",
            reply_markup=user_data['keyboard'])
    user_data['status'] = MAIN
    return user_data['status']

def nextRequest(bot, update, user_data, markupList):
    userDB = UserDatabase()
    try:
        # getNextRequest() methode existiert möglicherweise nicht
        nextRequest = {'chatID': None, 'firstname': 'No', 'lastname': 'Request'}
        if nextRequest['chatID'] is not None:
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = nextRequest
            update.message.reply_text("Request "+str(nextRequest['chatID'])+": "+str(nextRequest['firstname'])+" "+str(nextRequest['lastname']),
                reply_markup=user_data['keyboard'])
        else:
            user_data['keyboard'] = markupList[ADMIN]
            user_data['status'] = ADMIN
            user_data['userRequest'] = nextRequest
            update.message.reply_text("No request.",
                reply_markup=user_data['keyboard'])
    except Exception as e:
        update.message.reply_text(f"Fehler beim Abrufen des Requests: {str(e)}",
            reply_markup=user_data['keyboard'])
    return user_data['status']

def help(bot, update, user_data, markupList):
    text=''
    for key, value in textbefehl.items():
        text = text + '- /' + key + ' ' + value + '\n'
            
    update.message.reply_text(
                'Nutze das Keyboard für Admin-Aktionen: \n'+
                 str(text)+' ',
                reply_markup=user_data['keyboard'])
    return user_data['status']
    
def default(bot, update, user_data, markupList):
    return help(bot, update, user_data, markupList)
