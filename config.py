"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота (получите у @BotFather)
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID админа (ваш Telegram ID)
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# Username админа для связи (без @)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '')

# Кодовое слово для получения PDF
CODE_WORD = os.getenv('CODE_WORD', 'Антистресс')

# Путь к PDF файлу
PDF_FILE_PATH = os.getenv('PDF_FILE_PATH', 'Blue Playful Coping Skills Checklist Worksheet A4.pdf')

# Путь к базе данных
DATABASE_PATH = os.getenv('DATABASE_PATH', 'users.db')

