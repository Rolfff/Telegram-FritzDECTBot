#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import datetime as DT
from sqlite3 import Error
from lib.config import Config

class UserDatabase:
    def __init__(self):
        self.config = Config()
        self.db_config = self.config.get_database_config()
        self.db_path = self.db_config.get('path', 'database/userdata.db')
        self.table_name = self.db_config.get('table', 'users')
        
        # Existenz der Datenbank überprüfen und ggf. diese anlegen
        if not os.path.exists(self.db_path):
            print(f"Datenbank {self.db_path} nicht vorhanden - Datenbank wird angelegt.")
            self.create_database()
        else:
            # Prüfen ob Migration benötigt wird
            self.migrate_database()
    
    def execute(self, sql, params=None):
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            connection.commit()
        except Error as e:
            print(f"{str(e)} SQL-Query: {sql}")
        finally:
            connection.close()
    
    def fetch_one(self, sql, params=None):
        """Führt eine SQL-Abfrage aus und gibt einen Datensatz zurück"""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            result = cursor.fetchone()
            return result
        except Error as e:
            print(f"Fehler bei fetch_one: {e} SQL-Query: {sql}")
            return None
        finally:
            connection.close()
    
    def create_database(self):
        # Verzeichnis erstellen falls nicht vorhanden
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Tabelle erzeugen
        sql = f"""CREATE TABLE {self.table_name} (
            chatID INTEGER NOT NULL,
            firstname TEXT DEFAULT NULL,
            lastname TEXT DEFAULT NULL,
            isAdmin INTEGER NOT NULL DEFAULT 0,
            allowedToDatetime DATE NOT NULL,
            failedAttempts INTEGER NOT NULL DEFAULT 0,
            blockedUntil DATE DEFAULT NULL,
            notifyVacationMode INTEGER NOT NULL DEFAULT 1,
            notifyDoorPowerMeter INTEGER NOT NULL DEFAULT 1,
            notifyDoorFrontDoor INTEGER NOT NULL DEFAULT 1,
            language_code TEXT DEFAULT 'en',
            PRIMARY KEY(chatID)
        );"""
        self.execute(sql)
        
        sql = f"CREATE INDEX index_{self.table_name} ON {self.table_name} (chatID);"
        self.execute(sql)
        self.execute("PRAGMA auto_vacuum = FULL;")
    
    def migrate_database(self):
        """Prüft und migriert die Datenbank auf die aktuelle Schema-Version"""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        
        try:
            # Prüfen welche Spalten existieren
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Fehlende Spalten hinzufügen
            if 'failedAttempts' not in columns:
                print("Füge Spalte 'failedAttempts' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN failedAttempts INTEGER NOT NULL DEFAULT 0")
                connection.commit()
            
            if 'blockedUntil' not in columns:
                print("Füge Spalte 'blockedUntil' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN blockedUntil DATE DEFAULT NULL")
                connection.commit()
            
            # Neue Benachrichtigungs-Spalten hinzufügen
            if 'notifyVacationMode' not in columns:
                print("Füge Spalte 'notifyVacationMode' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN notifyVacationMode INTEGER NOT NULL DEFAULT 1")
                connection.commit()
            
            if 'notifyDoorPowerMeter' not in columns:
                print("Füge Spalte 'notifyDoorPowerMeter' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN notifyDoorPowerMeter INTEGER NOT NULL DEFAULT 1")
                connection.commit()
            
            if 'notifyDoorFrontDoor' not in columns:
                print("Füge Spalte 'notifyDoorFrontDoor' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN notifyDoorFrontDoor INTEGER NOT NULL DEFAULT 1")
                connection.commit()
            
            # Spracheinstellung hinzufügen
            if 'language_code' not in columns:
                print("Füge Spalte 'language_code' hinzu...")
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN language_code TEXT DEFAULT 'en'")
                connection.commit()
                
        except Error as e:
            print(f"Fehler bei Datenbank-Migration: {e}")
        finally:
            connection.close()
    
    def add_user(self, chat_id, firstname=None, lastname=None, is_admin=0, language_code='en'):
        """Fügt einen neuen Benutzer hinzu"""
        allowed_until = DT.datetime.now() + DT.timedelta(hours=-1)
        sql = f"""INSERT OR REPLACE INTO {self.table_name} 
                 (chatID, firstname, lastname, isAdmin, allowedToDatetime, failedAttempts, blockedUntil, language_code) 
                 VALUES (?, ?, ?, ?, ?, 0, NULL, ?)"""
        self.execute(sql, (chat_id, firstname, lastname, is_admin, allowed_until, language_code))
    
    def update_user_language(self, chat_id, language_code):
        """Aktualisiert die Spracheinstellung eines Benutzers"""
        sql = f"UPDATE {self.table_name} SET language_code = ? WHERE chatID = ?"
        self.execute(sql, (language_code, chat_id))
    
    def get_user_language(self, chat_id):
        """Gibt die Spracheinstellung eines Benutzers zurück"""
        sql = f"SELECT language_code FROM {self.table_name} WHERE chatID = ?"
        result = self.fetch_one(sql, (chat_id,))
        return result[0] if result else 'en'
    
    def is_user_blocked(self, chat_id):
        """Prüft ob Benutzer geblockt ist"""
        sql = f"SELECT blockedUntil FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            if result and result[0]:
                blocked_until = DT.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S.%f')
                check_blocked = DT.datetime.now() < blocked_until
                if check_blocked == False:
                    # Versuche reset
                    update_sql = f"UPDATE {self.table_name} SET failedAttempts = ?, blockedUntil = ? WHERE chatID = ?"
                    cursor.execute(update_sql, (0,None, chat_id))
                    connection.commit()
                return check_blocked
            return False
        except Error as e:
            print(f"Fehler bei Block-Prüfung: {e}")
            return False
        finally:
            connection.close()
    
    def record_failed_attempt(self, chat_id):
        """Zeichnet einen fehlgeschlagenen Login-Versuch auf"""
        max_attempts = self.config.get_max_failed_attempts()
        block_days = self.config.get_block_duration_days()
        
        # Zuerst prüfen ob Benutzer existiert
        if not self.user_exists(chat_id):
            self.add_user(chat_id)
            return False
        
        # Aktuelle Versuche holen
        sql = f"SELECT failedAttempts FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            if result:
                new_attempts = result[0] + 1
                
                if new_attempts >= max_attempts:
                    # Benutzer blockieren
                    blocked_until = DT.datetime.now() + DT.timedelta(days=block_days)
                    update_sql = f"""UPDATE {self.table_name} 
                                   SET failedAttempts = ?, blockedUntil = ? 
                                   WHERE chatID = ?"""
                    cursor.execute(update_sql, (new_attempts, blocked_until, chat_id))
                    connection.commit()
                    return True
                else:
                    # Versuche erhöhen
                    update_sql = f"UPDATE {self.table_name} SET failedAttempts = ? WHERE chatID = ?"
                    cursor.execute(update_sql, (new_attempts, chat_id))
                    connection.commit()
        except Error as e:
            print(f"Fehler bei Aufzeichnung fehlgeschlagener Versuche: {e}")
        finally:
            connection.close()
        
        return False
    
    def reset_failed_attempts(self, chat_id):
        """Setzt fehlgeschlagene Versuche zurück"""
        sql = f"UPDATE {self.table_name} SET failedAttempts = 0, blockedUntil = NULL WHERE chatID = ?"
        self.execute(sql, (chat_id,))
    
    def user_exists(self, chat_id):
        """Prüft ob Benutzer existiert"""
        sql = f"SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE chatID = ?)"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            return cursor.fetchone()[0] == 1
        except Error as e:
            print(f"Fehler bei Existenz-Prüfung: {e}")
            return False
        finally:
            connection.close()
    
    def get_failed_attempts(self, chat_id):
        """Gibt Anzahl fehlgeschlagener Versuche zurück"""
        sql = f"SELECT failedAttempts FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
        except Error as e:
            print(f"Fehler bei Abfrage fehlgeschlagener Versuche: {e}")
            return 0
        finally:
            connection.close()
    
    def is_user_allowed(self, chat_id):
        """Prüft ob Benutzer Zugriff hat"""
        # Zuerst prüfen ob Benutzer geblockt ist
        if self.is_user_blocked(chat_id):
            return False
        
        sql = f"SELECT allowedToDatetime FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            if result:
                allowed_until = DT.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S.%f')
                return DT.datetime.now() < allowed_until
            return False
        except Error as e:
            print(f"Fehler bei Prüfung Benutzerzugriff: {e}")
            return False
        finally:
            connection.close()
    
    def is_admin(self, chat_id):
        """Prüft ob Benutzer Admin ist"""
        sql = f"SELECT isAdmin FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            return result and result[0] == 1
        except Error as e:
            print(f"Fehler bei Admin-Prüfung: {e}")
            return False
        finally:
            connection.close()
    
    def get_notification_settings(self, chat_id):
        """Gibt die Benachrichtigungseinstellungen für einen Benutzer zurück"""
        sql = f"SELECT notifyVacationMode, notifyDoorPowerMeter, notifyDoorFrontDoor FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'notifyVacationMode': bool(result[0]),
                    'notifyDoorPowerMeter': bool(result[1]),
                    'notifyDoorFrontDoor': bool(result[2])
                }
            # Standardwerte zurückgeben wenn Benutzer nicht gefunden
            return {
                'notifyVacationMode': True,
                'notifyDoorPowerMeter': True,
                'notifyDoorFrontDoor': True
            }
        except Error as e:
            print(f"Fehler bei Abfrage Benachrichtigungseinstellungen: {e}")
            return {
                'notifyVacationMode': True,
                'notifyDoorPowerMeter': True,
                'notifyDoorFrontDoor': True
            }
        finally:
            connection.close()
    
    def update_notification_setting(self, chat_id, setting, value):
        """Aktualisiert eine einzelne Benachrichtigungseinstellung"""
        valid_settings = ['notifyVacationMode', 'notifyDoorPowerMeter', 'notifyDoorFrontDoor']
        if setting not in valid_settings:
            raise ValueError(f"Ungültige Einstellung: {setting}")
        
        sql = f"UPDATE {self.table_name} SET {setting} = ? WHERE chatID = ?"
        self.execute(sql, (int(value), chat_id))
    
    def update_all_notification_settings(self, chat_id, vacation_mode, door_power_meter, door_front_door):
        """Aktualisiert alle Benachrichtigungseinstellungen"""
        sql = f"""UPDATE {self.table_name} 
                 SET notifyVacationMode = ?, notifyDoorPowerMeter = ?, notifyDoorFrontDoor = ? 
                 WHERE chatID = ?"""
        self.execute(sql, (int(vacation_mode), int(door_power_meter), int(door_front_door), chat_id))
    
    def grant_access(self, chat_id, days=30):
        """Gewährt einem Benutzer Zugriff für eine bestimmte Anzahl von Tagen"""
        allowed_until = DT.datetime.now() + DT.timedelta(days=days)
        sql = f"UPDATE {self.table_name} SET allowedToDatetime = ? WHERE chatID = ?"
        self.execute(sql, (allowed_until, chat_id))
        return allowed_until
    
    def is_access_granted(self, chat_id):
        """Prüft ob einem Benutzer Zugriff gewährt wurde (nach Admin-Freigabe)"""
        sql = f"SELECT allowedToDatetime FROM {self.table_name} WHERE chatID = ?"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, (chat_id,))
            result = cursor.fetchone()
            if result:
                allowed_until = DT.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S.%f')
                return DT.datetime.now() < allowed_until
            return False
        except Error as e:
            print(f"Fehler bei Prüfung des Zugriffs: {e}")
            return False
        finally:
            connection.close()
    
    def extend_access(self, chat_id, d=0):
        """Verlängert den Zugriff eines Benutzers"""
        allowed_until = DT.datetime.now() + DT.timedelta(days=d)
        sql = f"UPDATE {self.table_name} SET allowedToDatetime = ? WHERE chatID = ?"
        self.execute(sql, (allowed_until, chat_id))
    
    def get_pending_requests(self):
        """Gibt alle User zurück, die auf Freigabe warten"""
        sql = f"""SELECT chatID, firstname, lastname FROM {self.table_name} 
                  WHERE allowedToDatetime < ? AND isAdmin = 0 
                  ORDER BY allowedToDatetime DESC"""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            # User mit allowedToDatetime in der Vergangenheit sind wartend
            now = DT.datetime.now()
            cursor.execute(sql, (now,))
            return cursor.fetchall()
        except Error as e:
            print(f"Fehler beim Abrufen der wartenden Anfragen: {e}")
            return []
        finally:
            connection.close()
    
    def get_all_users(self):
        """Gibt alle Benutzer zurück"""
        sql = f"SELECT * FROM {self.table_name}"
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        except Error as e:
            print(f"Fehler beim Abrufen aller Benutzer: {e}")
            return []
        finally:
            connection.close()

    
