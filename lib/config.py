#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Konfigurationsdatei {self.config_file} nicht gefunden!")
            return {}
        except json.JSONDecodeError as e:
            print(f"Fehler beim Lesen der Konfigurationsdatei: {e}")
            return {}
    
    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_telegram_token(self):
        return self.get('telegram.token')
    
    def get_admin_chat_id(self):
        return self.get('telegram.admin_chat_id')
    
    def get_telegram_password(self):
        return self.get('telegram.password')
    
    def get_fritzbox_config(self):
        return self.get('fritzbox', {})
    
    def get_database_config(self):
        return self.get('database', {})
    
    def get_logging_config(self):
        return self.get('logging', {'level': 'INFO', 'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'})
    
    def get_security_config(self):
        return self.get('security', {'max_failed_attempts': 5, 'block_duration_days': 2})
    
    def get_max_failed_attempts(self):
        return self.get('security.max_failed_attempts', 5)
    
    def get_block_duration_days(self):
        return self.get('security.block_duration_days', 2)

# Konstanten für Bot-Zustände
MAIN, LOGIN, ADMIN, STATISTICS, AUTOMATION, SETTINGS = range(6)

# Modi werden in fritzdect_bot.py gesetzt
modeList = [None, None, None, None, None, None]

# Tastatur-Layouts
reply_keyboard_main = [['Temperatur setzen', 'Temp.-Verlauf', 'Heizung'],['Automation','Einstellungen','Logout']]

def genMarkupList():
    """Generiert die MarkupList für alle Modi"""
    try:
        from telegram import ReplyKeyboardMarkup
    except ImportError:
        # Fallback für Tests ohne Telegram
        ReplyKeyboardMarkup = None
    
    markupList = {}
    for i in range(len(modeList)):
        if modeList[i] != None:
            if ReplyKeyboardMarkup:
                markupList[i] = ReplyKeyboardMarkup(buildKeyboard(modeList[i]), one_time_keyboard=False, resize_keyboard=True)
            else:
                # Fallback: Leere Liste
                markupList[i] = []
        else:
            if ReplyKeyboardMarkup:
                markupList[i] = ReplyKeyboardMarkup(reply_keyboard_main, one_time_keyboard=False, resize_keyboard=True)
            else:
                markupList[i] = []
    return markupList

def getMarkupList(status):
    """Gibt die MarkupList für einen bestimmten Status zurück"""
    try:
        from telegram import ReplyKeyboardMarkup
    except ImportError:
        # Fallback für Tests ohne Telegram
        ReplyKeyboardMarkup = None
    
    if modeList[status] != None:
        if ReplyKeyboardMarkup:
            return ReplyKeyboardMarkup(buildKeyboard(modeList[status]), one_time_keyboard=False, resize_keyboard=True)
        else:
            return []
    return []

def buildKeyboard(classs):
    """Erstellt eine Tastatur aus den Variablen 'tastertur' einer Klasse"""
    temp=[]
    reply_keyboard=[]
    i=0
    
    # Fallback für tastertur Attribut
    if hasattr(classs, 'tastertur'):
        tastertur_values = classs.tastertur.values()
    else:
        # Standard-Tastatur wenn tastertur nicht vorhanden
        tastertur_values = ['Hilfe', 'Zurück']
    
    for v in tastertur_values:
        temp.append(v)
        i=i+1
        if i % 3 == 0:
            reply_keyboard.append(temp)
            temp=[]
    reply_keyboard.append(temp)
    return reply_keyboard

# markupList wird in fritzdect_bot.py generiert
markupList = None

