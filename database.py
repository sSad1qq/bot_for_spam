"""
Модуль для работы с базой данных пользователей
"""
import sqlite3
from datetime import datetime
from typing import List, Optional
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
                is_subscribed INTEGER DEFAULT 1
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
        added_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, added_date, is_subscribed)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (user_id, username, first_name, last_name, added_date))
        
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
    
    def get_all_subscribers(self) -> List[int]:
        """
        Получение списка всех подписанных пользователей
        
        Returns:
            Список ID пользователей
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE is_subscribed = 1')
        subscribers = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return subscribers
    
    def unsubscribe_user(self, user_id: int) -> bool:
        """
        Отписка пользователя от рассылки
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True если операция успешна
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET is_subscribed = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True
    
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
    
    def get_subscriber_count(self) -> int:
        """
        Получение количества подписчиков
        
        Returns:
            Количество активных подписчиков
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_subscribed = 1')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count

