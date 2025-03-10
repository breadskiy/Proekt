import logging
import sqlite3
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8144970525:AAFbfkIvEL7_Wzeefl0TfoegnmFZR_Xxypg"  
DB_NAME = "jokes.db"

class JokeBot:
    def __init__(self, token):
        self.application = ApplicationBuilder().token(token).build()
        self.last_joke_id = None  # Переменная для хранения ID последнего показанного анекдота
        self.init_db()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("joke", self.get_joke))  # Команда для вывода анекдота
        self.application.add_handler(CommandHandler("top", self.top_jokes))  # Команда для отображения топ-3 анекдотов
        self.application.add_handler(CallbackQueryHandler(self.rate_joke))  # Обработчик для оценки анекдота
        self.application.add_handler(CallbackQueryHandler(self.next_joke, pattern="^next_joke$"))  # Обработчик для кнопки "Далее"
        logger.info("Обработчики зарегистрированы")

    def init_db(self):
        """Инициализация базы данных и добавление анекдотов с вычислением средней оценки"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Проверяем, существуют ли таблицы, и создаем их только если они не существуют
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS joke_ratings (
                joke_id INTEGER,
                rating INTEGER,
                PRIMARY KEY (joke_id, rating),
                FOREIGN KEY (joke_id) REFERENCES jokes(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS joke_statistics (
                joke_id INTEGER PRIMARY KEY,
                average_rating REAL DEFAULT 0.0,
                rating_count INTEGER DEFAULT 0,
                FOREIGN KEY (joke_id) REFERENCES jokes(id)
            )
            """
        )

        conn.commit()

        # Добавляем 3 анекдота в базу данных (если их ещё нет)
        jokes = [
            ("У чукчи спрашивают: Чья космонавтика самая лучшая в мире?\n- НАСА, - гордо ответил чукча."),
            ("В дверь кто-то вежливо постучал ногой.\n- Безруков! - догадался Штирлиц."),
            ("В Американском аэропорту мужчина уложил на пол тысячу человек криком: \"АЛЛА, Я В БАР!\""),
            ("Шел мужик вдоль реки, видит — медведь загорает. Сел рядом с ним и загорел."),
            ("Поймали инопланетяне русского, француза и немца, заперли каждого в замкнутую комнату 2 на 2 метра, дали каждому два титановых шарика и сказали:\n"
            "- Кто за день придумает с этими шариками то, что нас удивит, того отпустим, а остальнах на опыты отправим!\n"
            "Через день заходят к французу! Тот стоит посреди комнаты и виртуозно жонглирует шариками!\n"
            "- Что ж, француз, ты нас удивил, если те двое ничего не придумали, мы тебя отпустим!\n"
            "Заходят к немцу! Тот виртуозно жонглирует титановыми шариками при этом отбивая чечетку!\n"
            "- Ну, немец, удивил! Сейчас посмотрим, что там русский придумал и отпустим тебя!\n"
            "Инопланетянин заходит к русскому, а тот плачет, его инопланетянин спрашивает: русский ты чего плачешь?\n"
            "- я шарики потерял!"),
            ("Приходит улитка в бар\nПросит налить воды\nБармен наливает\nНа следующий день опять приходит\nОпять просит воды\nИ так месяц\n"
            "И бармен спрашивает\nНу у меня же тут полно алкогольных напитков\nПочему берешь только воду?\n"
            "А улитка говорит\nМужик давай потом у меня дом горит"),
            ("Лежит мужик на рельсах, плачет и смеётся. Подходит к нему девушка и спрашивает:\n"
            "— Мужчина, что с вами?\n— Мне поезд ногу переехал.\n— А что смеётесь тогда?!\n"
            "— А всё-таки классную подножку я ему поставил!"),
            ("Мужик едет на встречу, опаздывает, нервничает, не может найти место припарковаться.\n"
            "Поднимает лицо к небу и говорит:\n— Господи, помоги мне найти место для парковки. Я тогда брошу пить и буду каждое воскресенье ходить в церковь!\n"
            "Вдруг чудесным образом появляется свободное местечко. Мужик снова обращается к небу:\n— А, всё, не надо. Нашёл!")
        ]

        # Добавляем анекдоты в базу данных, если они еще не существуют
        for joke in jokes:
            cursor.execute("SELECT id FROM jokes WHERE text = ?", (joke,))
            if cursor.fetchone() is None:  # Если анекдот не существует, добавляем его
                cursor.execute("INSERT INTO jokes (text) VALUES (?)", (joke,))
        conn.commit()

        # Инициализируем таблицу статистики для анекдотов, если они ещё не добавлены
        cursor.execute("SELECT id FROM jokes")
        joke_ids = cursor.fetchall()
        for joke_id in joke_ids:
            cursor.execute("INSERT OR IGNORE INTO joke_statistics (joke_id) VALUES (?)", (joke_id[0],))
        conn.commit()

        conn.close()
        logger.info("База данных успешно инициализирована и анекдоты добавлены (если их ещё нет).")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.message.chat_id
            logger.info(f"Команда /start получена от {chat_id}")

            # Список стикеров
            sticker_list = [
                "CAACAgIAAxkBAAEN56JnvzRf_m0_q_txpeo_ZkURU2QjIAACMCkAArb06EgaNeEGV2utizYE",
                "CAACAgIAAxkBAAEN56BnvzRaH0hXVUOPm22VwouDkx5ojAACzyoAAvEXGUgu9UECMJaoxjYE",
                "CAACAgIAAxkBAAEN555nvzRHSRI2DbwCFWAJ9-IExJCOzQACfDEAAvrjwEkOkbWwvM-KQjYE",
                "CAACAgIAAxkBAAEN55xnvzQ1eJ2D7yMf35mGdBOyvxlrQwACYAEAAntOKhCBfNndRmRpczYE",
                "CAACAgIAAxkBAAEN55pnvzQvV2rJDHbKkDvHonvy0EGJoAAC1iIAAprjoUoM9JWryQKMtjYE"
            ]

            # Выбираем случайный стикер из списка
            random_sticker = random.choice(sticker_list)

            # Отправляем стикер и приветственное сообщение
            await update.message.reply_sticker(random_sticker)
            await update.message.reply_text(
                "Привет! Я бот с анекдотами. Напиши /joke, чтобы получить случайный анекдот."
            )
            logger.info(f"Приветственное сообщение отправлено пользователю с chat_id: {chat_id}")

    async def get_joke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод случайного анекдота, исключая последний показанный"""
        
        # Проверяем, если обновление от кнопки
        if update.callback_query:
            chat_id = update.callback_query.message.chat_id
            user_name = update.callback_query.from_user.username
        else:
            chat_id = update.message.chat_id
            user_name = update.message.from_user.username

        logger.info(f"Пользователь {user_name} с chat_id {chat_id} запросил анекдот")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Получаем все ID анекдотов
        cursor.execute("SELECT id FROM jokes")
        all_jokes = cursor.fetchall()
        conn.close()

        # Выбираем случайный анекдот, который не равен последнему показанному
        available_jokes = [joke[0] for joke in all_jokes if joke[0] != self.last_joke_id]

        if available_jokes:
            # Выбираем случайный анекдот из доступных
            next_joke_id = random.choice(available_jokes)

            # Получаем текст анекдота по его ID
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM jokes WHERE id = ?", (next_joke_id,))
            joke = cursor.fetchone()
            conn.close()

            if joke:
                # Обновляем ID последнего показанного анекдота
                self.last_joke_id = next_joke_id
                logger.info(f"Анекдот с ID {next_joke_id} был отправлен пользователю {user_name}")
                
                # Получаем текущую среднюю оценку
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT average_rating FROM joke_statistics WHERE joke_id = ?", (next_joke_id,))
                avg_rating = cursor.fetchone()[0]
                conn.close()

                # Создаем кнопки для оценки и для получения следующего анекдота
                keyboard = [
                    [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)],
                    [InlineKeyboardButton("Далее", callback_data="next_joke")]  # Кнопка для получения следующего анекдота
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем анекдот без лишнего повторения слова "анекдот"
                if update.callback_query:
                    await update.callback_query.message.edit_text(f"{joke[0]}\n\nСредняя оценка: {avg_rating:.2f}\n\nПожалуйста, оцените:", reply_markup=reply_markup)
                else:
                    await update.message.reply_text(f"{joke[0]}\n\nСредняя оценка: {avg_rating:.2f}\n\nПожалуйста, оцените:", reply_markup=reply_markup)
        else:
            logger.warning(f"Пользователь {user_name} с chat_id {chat_id} не получил новый анекдот, так как в базе нет других анекдотов")
            if update.callback_query:
                await update.callback_query.message.edit_text("Нет других анекдотов в базе.")
            else:
                await update.message.reply_text("Нет других анекдотов в базе.")


    async def top_jokes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выводит топ 3 анекдотов с наивысшей средней оценкой"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Получаем топ 3 анекдота с наивысшими средними оценками
        cursor.execute(
            """
            SELECT j.text, js.average_rating, js.rating_count
            FROM joke_statistics js
            JOIN jokes j ON js.joke_id = j.id
            ORDER BY js.average_rating DESC
            LIMIT 3
            """
        )
        top_jokes = cursor.fetchall()
        conn.close()

        if top_jokes:
            medal_icons = ["🥇", "🥈", "🥉"]
            top_message = "Топ 3 анекдота:\n\n"
            
            # Формируем строку для вывода топ 3 анекдотов с медалями
            for index, (joke_text, avg_rating, rating_count) in enumerate(top_jokes):
                medal = medal_icons[index]
                top_message += f"{medal} Анекдот: {joke_text}\nОценка: {avg_rating:.2f} (Оценок: {rating_count})\n\n"
            
            await update.message.reply_text(top_message)
        else:
            await update.message.reply_text("Топ анекдотов пустой или не найдено оценок.")


    async def rate_joke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик оценки анекдота"""
        query = update.callback_query
        user_name = query.from_user.username
        joke_id = self.last_joke_id

        if query.data == "next_joke":
            # Если это кнопка "Далее", переходим к следующему анекдоту
            await self.next_joke(update, context)
        else:
            try:
                rating = int(query.data)
                logger.info(f"Пользователь {user_name} оценил анекдот с ID {joke_id} на {rating}")

                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()

                # Проверка, существует ли уже такая оценка для этого анекдота
                cursor.execute("SELECT * FROM joke_ratings WHERE joke_id = ? AND rating = ?", (joke_id, rating))
                existing_rating = cursor.fetchone()

                if existing_rating:
                    logger.info(f"Оценка {rating} для анекдота с ID {joke_id} уже существует. Обновляем статистику.")
                else:
                    # Вставляем новую оценку, если её еще нет
                    cursor.execute("INSERT INTO joke_ratings (joke_id, rating) VALUES (?, ?)", (joke_id, rating))
                
                conn.commit()

                # Обновление статистики анекдота
                cursor.execute("SELECT rating_count, average_rating FROM joke_statistics WHERE joke_id = ?", (joke_id,))
                rating_count, avg_rating = cursor.fetchone()

                new_rating_count = rating_count + 1
                new_avg_rating = ((avg_rating * rating_count) + rating) / new_rating_count

                cursor.execute(
                    "UPDATE joke_statistics SET average_rating = ?, rating_count = ? WHERE joke_id = ?",
                    (new_avg_rating, new_rating_count, joke_id)
                )
                conn.commit()

                cursor.execute("SELECT average_rating, rating_count FROM joke_statistics WHERE joke_id = ?", (joke_id,))
                new_avg_rating, new_rating_count = cursor.fetchone()

                conn.close()

                # Создаем кнопку "Далее" для получения следующего анекдота
                keyboard = [[InlineKeyboardButton("Далее", callback_data="next_joke")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем новое сообщение с благодарностью за отзыв и кнопкой "Далее"
                await query.message.edit_text(
                    f"Анекдот:\n{query.message.text}\n\n"
                    f"Спасибо за вашу оценку! Средняя оценка: {new_avg_rating:.2f}\n"
                    f"Оценок: {new_rating_count}",
                    reply_markup=reply_markup
                )

            except ValueError:
                logger.error(f"Не удалось преобразовать данные {query.data} в целое число")



    async def next_joke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик для кнопки 'Далее', отправляющий новый анекдот в новом сообщении"""
        
        query = update.callback_query
        await query.answer()  # Закрываем всплывающее уведомление Telegram

        # Получаем новый анекдот и отправляем его в новое сообщение
        await self.get_joke(update, context)  # Просто вызываем функцию отправки нового анекдота


    def run(self):
        try:
            logger.info("Запуск polling")
            self.application.run_polling()
            logger.info("Бот успешно запущен и слушает обновления")
        except Exception as e:
            logger.error(f"Ошибка при запуске: {e}")

def run_bot():
    bot = JokeBot(TOKEN)
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")


if __name__ == "__main__":
    run_bot()


