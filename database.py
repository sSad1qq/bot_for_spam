"""
Модуль для работы с базой данных пользователей воронки "Антистресс"
"""
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict
import config


class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Создание таблицы пользователей, если её нет"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                added_date TEXT NOT NULL,
                status TEXT DEFAULT 'file_sent',
                contact_provided INTEGER DEFAULT 0,
                contact_name TEXT,
                contact_phone TEXT,
                last_message_time TEXT,
                warmup_1_sent INTEGER DEFAULT 0,
                warmup_2_sent INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: Optional[str] = None, 
                 first_name: Optional[str] = None, last_name: Optional[str] = None) -> bool:
        """
        Добавление пользователя в базу данных
        
        Args:
            user_id: ID пользователя в Telegram
            username: Username пользователя
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            True если пользователь добавлен, False если уже существует
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже пользователь в базе
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            conn.close()
            return False
        
        # Добавляем нового пользователя
        added_date = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO users (
                user_id, username, first_name, last_name, added_date, 
                status, last_message_time
            )
            VALUES (?, ?, ?, ?, ?, 'file_sent', ?)
        ''', (user_id, username, first_name, last_name, added_date, added_date))
        
        conn.commit()
        conn.close()
        return True
    
    def is_user_exists(self, user_id: int) -> bool:
        """
        Проверка существования пользователя в базе
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True если пользователь существует, иначе False
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone() is not None
        
        conn.close()
        return result
    
    def update_user_status(self, user_id: int, status: str, update_time: bool = True):
        """
        Обновление статуса пользователя
        
        Args:
            user_id: ID пользователя
            status: Новый статус (file_sent, offer_sent, contact_provided)
            update_time: Обновлять ли время последнего сообщения
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if update_time:
            current_time = datetime.now().isoformat()
            cursor.execute('''
                UPDATE users 
                SET status = ?, last_message_time = ?
                WHERE user_id = ?
            ''', (status, current_time, user_id))
        else:
            cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (status, user_id))
        
        conn.commit()
        conn.close()
    
    def save_contact(self, user_id: int, name: str, phone: str):
        """
        Сохранение контактных данных пользователя
        
        Args:
            user_id: ID пользователя
            name: Имя для связи
            phone: Номер телефона
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET contact_provided = 1, contact_name = ?, contact_phone = ?, status = 'contact_provided'
            WHERE user_id = ?
        ''', (name, phone, user_id))
        
        conn.commit()
        conn.close()
    
    def mark_warmup_sent(self, user_id: int, warmup_number: int):
        """
        Отметить, что догревающее сообщение отправлено
        
        Args:
            user_id: ID пользователя
            warmup_number: Номер догрева (1 или 2)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        column = f'warmup_{warmup_number}_sent'
        current_time = datetime.now().isoformat()
        
        cursor.execute(f'''
            UPDATE users 
            SET {column} = 1, last_message_time = ?
            WHERE user_id = ?
        ''', (current_time, user_id))
        
        conn.commit()
        conn.close()
    
    def get_users_for_warmup(self, hours: int, warmup_number: int) -> List[Dict]:
        """
        Получить пользователей для догрева
        
        Args:
            hours: Количество часов с последнего сообщения
            warmup_number: Номер догрева (1 или 2)
            
        Returns:
            Список пользователей, которым нужно отправить догрев
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        warmup_column = f'warmup_{warmup_number}_sent'
        
        cursor.execute(f'''
            SELECT user_id, username, first_name 
            FROM users 
            WHERE status = 'offer_sent'
            AND contact_provided = 0 
            AND {warmup_column} = 0
            AND datetime(last_message_time, '+{hours} hours') <= datetime('now', 'localtime')
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2]
            })
        
        conn.close()
        return users
    
    def get_all_users(self) -> List[int]:
        """
        Получение списка всех пользователей
        
        Returns:
            Список ID всех пользователей
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return users
    
    def get_users_without_contact(self) -> List[int]:
        """
        Получение пользователей, которые не оставили контакт
        
        Returns:
            Список ID пользователей без контакта
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE contact_provided = 0')
        users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return users
    
    def get_users_with_contact(self) -> List[int]:
        """
        Получение пользователей, которые оставили контакт
        
        Returns:
            Список ID пользователей с контактом
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE contact_provided = 1')
        users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return users
    
    def get_user_count(self) -> int:
        """
        Получение общего количества пользователей
        
        Returns:
            Количество пользователей в базе
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_contact_count(self) -> int:
        """
        Получение количества пользователей с контактами
        
        Returns:
            Количество пользователей, оставивших контакт
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE contact_provided = 1')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """
        Получить информацию о пользователе
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с информацией или None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, first_name, contact_name, contact_phone, 
                   status, added_date, contact_provided
            FROM users 
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'contact_name': row[3],
                'contact_phone': row[4],
                'status': row[5],
                'added_date': row[6],
                'contact_provided': row[7]
            }
        return None
