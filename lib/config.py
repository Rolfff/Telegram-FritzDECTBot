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
MAIN, LOGIN, ADMIN = range(3)


