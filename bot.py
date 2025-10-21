"""
Telegram бот - воронка "Антистресс"
"""
import logging
import os
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError

import config
import config_timing
from database import Database
import messages

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = (
        f"Здравствуйте, {user.first_name}! 👋\n\n"
        f"Рады приветствовать вас в программе поддержки от Эталона!\n\n"
        f"📚 Мы подготовили для вас полезные материалы по управлению стрессом "
        f"и тревожностью в период подготовки к экзаменам.\n\n"
        f"🔑 Чтобы получить материалы, напишите кодовое слово.\n\n"
        f"После этого вы получите доступ к файлу с практическими инструментами "
        f"и специальное предложение от нашего психолога."
    )
    
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n\n"
        "Введите кодовое слово **Антистресс**, чтобы получить полезные материалы."
    )
    
    await update.message.reply_text(help_text)


async def check_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка ID пользователя"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    user_info = db.get_user_info(user_id)
    
    message = (
        f"🆔 Ваша информация:\n\n"
        f"ID: {user_id}\n"
        f"Username: @{username or 'не указан'}\n"
        f"Имя: {update.effective_user.first_name}\n\n"
        f"ADMIN_ID в боте: {config.ADMIN_ID}\n"
        f"Вы админ: {'✅ ДА' if user_id == config.ADMIN_ID else '❌ НЕТ'}\n\n"
    )
    
    if user_info:
        message += (
            f"Статус в воронке: {user_info['status']}\n"
            f"Контакт предоставлен: {'✅ ДА' if user_info['contact_provided'] else '❌ НЕТ'}"
        )
    else:
        message += "Вы ещё не в базе. Введите кодовое слово **Антистресс**."
    
    await update.message.reply_text(message)


async def send_offer_delayed(application, user_id: int, delay: int = 60):
    """Отправка предложения консультации через заданную задержку"""
    await asyncio.sleep(delay)
    
    logger.info(f"Отправка предложения консультации пользователю {user_id}")
    
    try:
        # Проверяем, не оставил ли пользователь уже контакт
        user_info = db.get_user_info(user_id)
        if user_info and user_info['contact_provided']:
            logger.info(f"Пользователь {user_id} уже оставил контакт, пропускаем")
            return
        
        await application.bot.send_message(
            chat_id=user_id,
            text=messages.OFFER_MESSAGE
        )
        
        # Обновляем last_message_time - первый догрев будет через 1 минуту после предложения
        db.update_user_status(user_id, 'offer_sent', update_time=True)
        logger.info(f"Предложение отправлено пользователю {user_id}")
        
    except TelegramError as e:
        logger.error(f"Не удалось отправить предложение пользователю {user_id}: {e}")


async def handle_antistress_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кодового слова Антистресс"""
    user = update.effective_user
    user_id = user.id
    
    # Проверяем, существует ли PDF файл
    if not os.path.exists(config.PDF_FILE_PATH):
        await update.message.reply_text(
            "❌ Извините, файл пока недоступен. Обратитесь к администратору."
        )
        logger.error(f"PDF файл не найден: {config.PDF_FILE_PATH}")
        return
    
    # Проверяем, новый ли это пользователь
    is_new_user = db.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if not is_new_user:
        await update.message.reply_text(
            "Вы уже получали материалы! Если у вас остались вопросы, напишите администратору."
        )
        return
    
    # Отправляем приветственное сообщение
    await update.message.reply_text(messages.WELCOME_MESSAGE)
    
    # Отправляем PDF файл
    try:
        with open(config.PDF_FILE_PATH, 'rb') as pdf_file:
            await update.message.reply_document(document=pdf_file)
        
        logger.info(f"Новый пользователь добавлен: {user_id} (@{user.username})")
        
        # Запускаем отложенную отправку предложения консультации
        asyncio.create_task(send_offer_delayed(context.application, user_id, delay=config_timing.OFFER_DELAY_SECONDS))
        logger.info(f"Запланирована отправка предложения через {config_timing.OFFER_DELAY_SECONDS} сек для {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке файла. Попробуйте позже."
        )


def validate_phone_number(phone: str) -> bool:
    """
    Проверка корректности номера телефона
    
    Args:
        phone: Номер телефона (уже очищенный от символов)
        
    Returns:
        True если номер валидный
    """
    # Удаляем + в начале если есть
    clean_phone = phone.lstrip('+')
    
    # Проверяем, что это только цифры
    if not clean_phone.isdigit():
        return False
    
    # Проверяем длину (10-12 цифр)
    if len(clean_phone) < 10 or len(clean_phone) > 12:
        return False
    
    # Если начинается с 7 или 8, должно быть 11 цифр
    if clean_phone[0] in ['7', '8']:
        return len(clean_phone) == 11
    
    return True


def extract_contact_info(text: str) -> tuple:
    """
    Извлечение имени и телефона из текста
    
    Returns:
        (name, phone) или (None, None) если не найдено
        (None, 'invalid') если формат номера неправильный
    """
    # Ищем номер телефона (различные форматы)
    phone_patterns = [
        r'\+?7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 (xxx) xxx-xx-xx
        r'\+?\d{10,12}',  # Просто цифры (10-12 символов)
        r'8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # 8 (xxx) xxx-xx-xx
    ]
    
    phone = None
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group().strip()
            # Удаляем телефон из текста, чтобы извлечь имя
            text = text.replace(match.group(), '').strip()
            break
    
    if not phone:
        return None, None
    
    # Очищаем телефон от лишних символов
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Проверяем корректность номера
    if not validate_phone_number(clean_phone):
        return None, 'invalid'
    
    # Имя - это то, что осталось после удаления телефона
    # Очищаем от лишних символов и пробелов
    name = re.sub(r'[^\w\s\-А-Яа-яЁёA-Za-z]', '', text).strip()
    
    if not name:
        return None, clean_phone
    
    return name, clean_phone


async def handle_contact_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка контакта от пользователя"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли пользователь в базе
    user_info = db.get_user_info(user_id)
    if not user_info:
        return False
    
    # Проверяем, получил ли пользователь предложение консультации
    if user_info['status'] == 'file_sent':
        # Предложение еще не отправлено - игнорируем сообщение
        return False
    
    # Если уже оставил контакт, пропускаем
    if user_info['contact_provided']:
        return False
    
    # Обработка контакта через Telegram Contact
    if update.message.contact:
        phone = update.message.contact.phone_number
        name = update.message.contact.first_name or update.effective_user.first_name
        
        db.save_contact(user_id, name, phone)
        
        # Отправляем благодарность
        await update.message.reply_text(messages.THANK_YOU_MESSAGE)
        
        # Уведомляем админа
        await notify_admin_about_contact(context, user_id, name, phone, update.effective_user.username)
        
        logger.info(f"Получен контакт от {user_id}: {name}, {phone}")
        return True
    
    # Обработка текстового сообщения с именем и телефоном
    if update.message.text:
        name, phone = extract_contact_info(update.message.text)
        
        # Проверка на неправильный формат номера
        if phone == 'invalid':
            await update.message.reply_text(
                "❌ Неправильный формат номера телефона.\n\n"
                "Пожалуйста, укажите номер в одном из форматов:\n"
                "• +79991234567\n"
                "• 89991234567\n"
                "• 79991234567\n\n"
                "Например: Иван Петров +79991234567"
            )
            return False
        
        if name and phone:
            db.save_contact(user_id, name, phone)
            
            # Отправляем благодарность
            await update.message.reply_text(messages.THANK_YOU_MESSAGE)
            
            # Уведомляем админа
            await notify_admin_about_contact(context, user_id, name, phone, update.effective_user.username)
            
            logger.info(f"Получен контакт от {user_id}: {name}, {phone}")
            return True
    
    return False


async def notify_admin_about_contact(context, user_id, name, phone, username):
    """Отправка уведомления админу о новом контакте"""
    if not config.ADMIN_ID:
        return
    
    try:
        notification = messages.ADMIN_NOTIFICATION.format(
            name=name,
            phone=phone,
            user_id=user_id,
            username=username or 'не указан',
            date=datetime.now().strftime('%d.%m.%Y %H:%M')
        )
        
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=notification
        )
    except TelegramError as e:
        logger.error(f"Не удалось уведомить админа: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    message_text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Проверяем кодовое слово (нечувствительно к регистру)
    if message_text.lower() == config.CODE_WORD.lower():
        await handle_antistress_code(update, context)
        return
    
    # Проверяем, есть ли пользователь в базе
    user_info = db.get_user_info(user_id)
    
    # Если пользователь уже в базе, пытаемся обработать как контакт
    if user_info:
        # Проверяем, получил ли пользователь предложение консультации
        if user_info['status'] == 'file_sent':
            # Предложение еще не отправлено - не обрабатываем сообщения
            return
        
        contact_handled = await handle_contact_message(update, context)
        
        if not contact_handled:
            # Если контакт уже предоставлен
            if user_info['contact_provided']:
                await update.message.reply_text(
                    "Спасибо! Мы уже получили ваши контакты и скоро свяжемся с вами.\n\n"
                    "Если у вас есть вопросы, можете написать администратору."
                )
            else:
                # Контакт еще не предоставлен, даем подсказку
                await update.message.reply_text(
                    "Пожалуйста, отправьте ваше имя и номер телефона для консультации.\n\n"
                    "📝 Формат: Имя Фамилия +79991234567\n"
                    "Например: Иван Петров +79991234567"
                )
    else:
        # Пользователь не в базе - неверное кодовое слово
        await update.message.reply_text(
            "❌ Неверное кодовое слово.\n\n"
            "Пожалуйста, введите правильное кодовое слово, чтобы получить доступ к материалам.\n\n"
            "Если вы не знаете кодовое слово, обратитесь к организатору программы."
        )


async def check_warmup_users(application):
    """Фоновая задача для проверки и отправки догревающих сообщений"""
    while True:
        try:
            logger.info("Проверка пользователей для догрева...")
            
            # Первый догрев
            users_for_warmup1 = db.get_users_for_warmup(hours=config_timing.WARMUP_1_HOURS, warmup_number=1)
            logger.info(f"Найдено {len(users_for_warmup1)} пользователей для первого догрева")
            
            for user in users_for_warmup1:
                try:
                    await application.bot.send_message(
                        chat_id=user['user_id'],
                        text=messages.WARMUP_1_MESSAGE
                    )
                    db.mark_warmup_sent(user['user_id'], 1)
                    logger.info(f"Первый догрев отправлен пользователю {user['user_id']}")
                except TelegramError as e:
                    logger.error(f"Ошибка отправки первого догрева {user['user_id']}: {e}")
            
            # Второй догрев
            users_for_warmup2 = db.get_users_for_warmup(hours=config_timing.WARMUP_2_HOURS, warmup_number=2)
            logger.info(f"Найдено {len(users_for_warmup2)} пользователей для второго догрева")
            
            for user in users_for_warmup2:
                try:
                    await application.bot.send_message(
                        chat_id=user['user_id'],
                        text=messages.WARMUP_2_MESSAGE
                    )
                    db.mark_warmup_sent(user['user_id'], 2)
                    logger.info(f"Второй догрев отправлен пользователю {user['user_id']}")
                except TelegramError as e:
                    logger.error(f"Ошибка отправки второго догрева {user['user_id']}: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче догрева: {e}")
        
        # Проверяем с интервалом из конфига
        await asyncio.sleep(config_timing.CHECK_INTERVAL_SECONDS)


# ===== КОМАНДЫ АДМИНИСТРАТОРА =====

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика по воронке"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    total_users = db.get_user_count()
    with_contact = db.get_contact_count()
    without_contact = total_users - with_contact
    
    stats_text = (
        f"📊 Статистика воронки \"Антистресс\":\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Оставили контакт: {with_contact}\n"
        f"⏳ Без контакта: {without_contact}\n"
        f"📈 Конверсия: {round(with_contact / total_users * 100, 1) if total_users > 0 else 0}%"
    )
    
    await update.message.reply_text(stats_text)


async def broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка всем пользователям"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /broadcast_all <текст сообщения>\n"
            "Отправит сообщение ВСЕМ пользователям воронки"
        )
        return
    
    message_text = ' '.join(context.args)
    users = db.get_all_users()
    
    await send_broadcast(update, context, users, message_text, "всем пользователям")


async def broadcast_without_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка пользователям без контакта"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /broadcast_no_contact <текст сообщения>\n"
            "Отправит сообщение только тем, кто НЕ оставил контакт"
        )
        return
    
    message_text = ' '.join(context.args)
    users = db.get_users_without_contact()
    
    await send_broadcast(update, context, users, message_text, "пользователям без контакта")


async def broadcast_with_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка пользователям с контактом"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /broadcast_with_contact <текст сообщения>\n"
            "Отправит сообщение только тем, кто оставил контакт"
        )
        return
    
    message_text = ' '.join(context.args)
    users = db.get_users_with_contact()
    
    await send_broadcast(update, context, users, message_text, "пользователям с контактом")


async def send_broadcast(update, context, users, message_text, description):
    """Общая функция для рассылки"""
    if not users:
        await update.message.reply_text(f"Нет {description} для рассылки.")
        return
    
    await update.message.reply_text(f"📤 Начинаю рассылку {len(users)} {description}...")
    
    success_count = 0
    fail_count = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            success_count += 1
        except TelegramError as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            fail_count += 1
    
    result_text = (
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}"
    )
    
    await update.message.reply_text(result_text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")


def main():
    """Запуск бота"""
    # Проверка наличия токена
    if not config.BOT_TOKEN:
        logger.error("Не указан BOT_TOKEN в файле .env!")
        return
    
    # Создание приложения
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", check_id))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast_all", broadcast_all))
    application.add_handler(CommandHandler("broadcast_no_contact", broadcast_without_contact))
    application.add_handler(CommandHandler("broadcast_with_contact", broadcast_with_contact))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Обработчик контактов
    application.add_handler(MessageHandler(
        filters.CONTACT,
        handle_contact_message
    ))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Функция для запуска фоновой задачи после инициализации
    async def post_init(application: Application) -> None:
        """Запускается после инициализации приложения"""
        asyncio.create_task(check_warmup_users(application))
        logger.info("Фоновая задача для догревов запущена")
    
    # Регистрируем функцию post_init
    application.post_init = post_init
    
    # Запуск бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
