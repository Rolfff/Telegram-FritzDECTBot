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
config = config_module.Config()


# Import markupList from config
from lib.config import genMarkupList, LOGIN, MAIN, ADMIN, STATISTICS
markupList = genMarkupList()
# TODO: hier funktioniert die Inigration noch nicht. Es werden nicht alle benötigte Informaationen mit übergeben.
# TODO: Adminmode Testen!!!

# Funktionen hier registrieren für Admin-Mode
# Funktionen Map{ Funk-Name: Tastertur beschriftung}
tastertur = {'status': 'Status',
         'back': 'Zurück'}

# Funktionen Map{Funk-Name, Beschreiung in Help}
textbefehl = {'status': 'Zeigt Grafiken aller Sensoren an',
         'back': 'Wechselt zurück ins Main-Menu'}

async def status(update, context):
    bot = context.bot
    await update.message.reply_text("Test",
                                  reply_markup=context.user_data.get('keyboard'))
    context.user_data['keyboard'] = markupList[STATISTICS]
    context.user_data['status'] = STATISTICS
    return context.user_data['status']

async def back(update, context):
    context.user_data['keyboard'] = markupList[MAIN]
    context.user_data['status'] = MAIN
    return context.user_data['status']

async def default(update, context):
    return await status(update, context)

# Wrapper functions for direct bot calls (update, context signature)
#async def status_wrapper(update, context):
#    return await status(context.bot, update, context.user_data)
 #   return await zurück(context.bot, update, context.user_data)