"""
Telegram бот для отправки PDF файлов и рассылки
"""
import logging
import os
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
from database import Database

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
    
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        f"Я бот для отправки специальных материалов.\n"
        f"Введите кодовое слово, чтобы получить доступ к материалам."
    )
    
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/unsubscribe - Отписаться от рассылки\n\n"
        "Введите кодовое слово, чтобы получить PDF файл и подписаться на рассылку."
    )
    
    await update.message.reply_text(help_text)


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /unsubscribe"""
    user_id = update.effective_user.id
    
    if db.is_user_exists(user_id):
        db.unsubscribe_user(user_id)
        await update.message.reply_text(
            "✅ Вы успешно отписались от рассылки.\n"
            "Вы можете снова подписаться, введя кодовое слово."
        )
    else:
        await update.message.reply_text(
            "Вы ещё не подписаны на рассылку."
        )


async def check_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка ID пользователя"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    message = (
        f"🆔 Ваша информация:\n\n"
        f"ID: {user_id}\n"
        f"Username: @{username or 'не указан'}\n"
        f"Имя: {update.effective_user.first_name}\n\n"
        f"ADMIN_ID в боте: {config.ADMIN_ID}\n"
        f"Вы админ: {'✅ ДА' if user_id == config.ADMIN_ID else '❌ НЕТ'}"
    )
    
    await update.message.reply_text(message)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats - только для админа"""
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    total_users = db.get_user_count()
    subscribers = db.get_subscriber_count()
    
    stats_text = (
        f"📊 Статистика бота:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных подписчиков: {subscribers}\n"
        f"❌ Отписавшихся: {total_users - subscribers}"
    )
    
    await update.message.reply_text(stats_text)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /broadcast - рассылка сообщения всем подписчикам
    Только для админа
    
    Использование: /broadcast <текст сообщения>
    """
    user_id = update.effective_user.id
    
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Получаем текст сообщения после команды
    if not context.args:
        await update.message.reply_text(
            "Использование: /broadcast <текст сообщения>\n"
            "Например: /broadcast Привет всем! Это тестовое сообщение."
        )
        return
    
    message_text = ' '.join(context.args)
    subscribers = db.get_all_subscribers()
    
    if not subscribers:
        await update.message.reply_text("Нет подписчиков для рассылки.")
        return
    
    # Отправка сообщения
    success_count = 0
    fail_count = 0
    
    await update.message.reply_text(f"Начинаю рассылку {len(subscribers)} подписчикам...")
    
    for subscriber_id in subscribers:
        try:
            await context.bot.send_message(
                chat_id=subscriber_id,
                text=message_text
            )
            success_count += 1
        except TelegramError as e:
            logger.error(f"Не удалось отправить сообщение пользователю {subscriber_id}: {e}")
            fail_count += 1
    
    result_text = (
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}"
    )
    
    await update.message.reply_text(result_text)


async def handle_admin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик медиа-файлов от админа
    Показывает кнопки для подтверждения рассылки
    """
    user_id = update.effective_user.id
    
    logger.info(f"Получено медиа от пользователя {user_id}, ADMIN_ID={config.ADMIN_ID}")
    
    if user_id != config.ADMIN_ID:
        logger.info(f"Пользователь {user_id} не является админом, пропускаем")
        return
    
    logger.info("Админ отправил медиа, показываем кнопки подтверждения")
    
    # Сохраняем информацию о сообщении для последующей рассылки
    context.user_data['broadcast_message'] = update.message.message_id
    context.user_data['broadcast_chat'] = update.message.chat_id
    
    # Создаем кнопки для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, разослать", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Нет", callback_data="broadcast_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    subscriber_count = db.get_subscriber_count()
    
    await update.message.reply_text(
        f"📤 Разослать это сообщение {subscriber_count} подписчикам?",
        reply_markup=reply_markup
    )


async def handle_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки подтверждения рассылки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"Нажата кнопка: {query.data} пользователем {user_id}")
    
    if user_id != config.ADMIN_ID:
        logger.warning(f"Попытка доступа не админа: {user_id}")
        await query.edit_message_text("У вас нет доступа к этой функции.")
        return
    
    if query.data == "broadcast_cancel":
        logger.info("Рассылка отменена админом")
        await query.edit_message_text("❌ Рассылка отменена.")
        # Очищаем сохраненные данные
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_chat', None)
        return
    
    if query.data == "broadcast_confirm":
        # Получаем сохраненное сообщение
        message_id = context.user_data.get('broadcast_message')
        chat_id = context.user_data.get('broadcast_chat')
        
        logger.info(f"Подтверждена рассылка. Message ID: {message_id}, Chat ID: {chat_id}")
        
        if not message_id or not chat_id:
            logger.error(f"Сообщение не найдено! message_id={message_id}, chat_id={chat_id}")
            await query.edit_message_text("❌ Ошибка: сообщение не найдено.")
            return
        
        subscribers = db.get_all_subscribers()
        logger.info(f"Получено {len(subscribers)} подписчиков для рассылки")
        
        if not subscribers:
            await query.edit_message_text("❌ Нет подписчиков для рассылки.")
            return
        
        # Обновляем сообщение
        await query.edit_message_text(f"📤 Начинаю рассылку {len(subscribers)} подписчикам...")
        
        success_count = 0
        fail_count = 0
        
        for subscriber_id in subscribers:
            try:
                logger.info(f"Отправка подписчику {subscriber_id}...")
                # Копируем сохраненное сообщение всем подписчикам
                await context.bot.copy_message(
                    chat_id=subscriber_id,
                    from_chat_id=chat_id,
                    message_id=message_id
                )
                success_count += 1
                logger.info(f"✓ Успешно отправлено {subscriber_id}")
            except TelegramError as e:
                logger.error(f"✗ Не удалось отправить сообщение пользователю {subscriber_id}: {e}")
                fail_count += 1
        
        result_text = (
            f"✅ Рассылка завершена!\n\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {fail_count}"
        )
        
        logger.info(f"Рассылка завершена. Успешно: {success_count}, Ошибок: {fail_count}")
        await query.edit_message_text(result_text)
        
        # Очищаем сохраненные данные
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_chat', None)




async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text.strip()
    
    # Проверяем кодовое слово
    if message_text.lower() == config.CODE_WORD.lower():
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
        
        # Отправляем PDF файл
        try:
            with open(config.PDF_FILE_PATH, 'rb') as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    caption="✅ Вот ваш файл! Вы также подписаны на нашу рассылку."
                )
            
            if is_new_user:
                logger.info(f"Новый пользователь добавлен: {user_id} (@{user.username})")
                
                # Уведомляем админа о новом пользователе
                if config.ADMIN_ID:
                    try:
                        admin_notification = (
                            f"🆕 Новый пользователь!\n\n"
                            f"ID: {user_id}\n"
                            f"Имя: {user.first_name or 'Не указано'}\n"
                            f"Username: @{user.username or 'Не указано'}\n"
                            f"Всего подписчиков: {db.get_subscriber_count()}"
                        )
                        await context.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=admin_notification
                        )
                    except TelegramError as e:
                        logger.error(f"Не удалось уведомить админа: {e}")
            else:
                logger.info(f"Существующий пользователь повторно ввёл код: {user_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке файла. Попробуйте позже."
            )
    else:
        # Если сообщение не кодовое слово и не от админа
        if user_id != config.ADMIN_ID:
            await update.message.reply_text(
                "🤔 Неверное кодовое слово. Попробуйте ещё раз или используйте /help."
            )


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
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("id", check_id))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    # Обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(handle_broadcast_callback))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Обработчик медиа-сообщений от админа для рассылки
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL | filters.VOICE | filters.VIDEO_NOTE) & ~filters.COMMAND,
        handle_admin_media
    ))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

