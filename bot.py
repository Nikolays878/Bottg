import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, CommandStart
import random

# === Конфигурация ===
API_TOKEN = "7957463475:AAG8iS8WWpgE93WpnqMXMLbHn0GmZLnvx1U"
GROUP_CHAT_ID = -1002283722483
ADMIN_ID = 6759225861  # Ваш Telegram ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === БД ===
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    pubg_nick TEXT,
    pubg_id TEXT,
    age TEXT,
    city TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS banned (
    user_id INTEGER PRIMARY KEY
)
""")
conn.commit()

# === Машины состояний ===
class Form(StatesGroup):
    pubg_nick = State()
    pubg_id = State()
    age = State()
    city = State()

class GameStates(StatesGroup):
    guessing = State()

# === Утилиты ===
def format_description(data):
    return (
        f"<b>Описание:</b>\n"
        f"<b>Ник PUBG:</b> <code>{data[2]}</code>\n"
        f"<b>ID PUBG:</b> <code>{data[3]}</code>\n"
        f"<b>Возраст:</b> {data[4]}\n"
        f"<b>Город:</b> {data[5]}\n"
        f"<b>Telegram:</b> @{data[1]}"
    )

def is_banned(user_id):
    cursor.execute("SELECT 1 FROM banned WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# === Команды регистрации ===
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if is_banned(message.from_user.id):
        return await message.answer("Ты забанен.")
    cursor.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,))
    if cursor.fetchone():
        return await message.answer("Ты уже заполнил описание.")
    await message.answer("Привет! Введи PUBG ник:")
    await state.set_state(Form.pubg_nick)

@dp.message(Form.pubg_nick)
async def get_nick(message: Message, state: FSMContext):
    await state.update_data(pubg_nick=message.text)
    await message.answer("Теперь введи PUBG ID:")
    await state.set_state(Form.pubg_id)

@dp.message(Form.pubg_id)
async def get_id(message: Message, state: FSMContext):
    await state.update_data(pubg_id=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def get_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Из какого ты города?")
    await state.set_state(Form.city)

@dp.message(Form.city)
async def get_city(message: Message, state: FSMContext):
    data = await state.get_data()

    # Получаем данные, введенные пользователем
    pubg_nick = data.get("pubg_nick", "Не указан")
    pubg_id = data.get("pubg_id", "Не указан")
    age = data.get("age", "Не указан")
    city = message.text.strip()  # Получаем текст сообщения как город

    # Если город не был введен, устанавливаем значение по умолчанию
    if not city:
        city = "Не указан"

    user_id = message.from_user.id
    username = message.from_user.username or f"id_{user_id}"

    # Сохраняем данные в БД
    cursor.execute(
        "INSERT INTO users (user_id, username, pubg_nick, pubg_id, age, city) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, pubg_nick, pubg_id, age, city)
    )
    conn.commit()
    await state.clear()

    # Формируем описание пользователя
    description = format_description((user_id, username, pubg_nick, pubg_id, age, city))

    # Отправляем описание в группу
    await bot.send_message(GROUP_CHAT_ID, description, parse_mode="HTML")

    # Создаём ссылку для приглашения
    invite_link = await bot.create_chat_invite_link(chat_id=GROUP_CHAT_ID, member_limit=1)
    await message.answer("Описание сохранено! Вот ссылка:\n" + invite_link.invite_link)

# === Команды описаний ===
@dp.message(lambda m: m.text and m.text.lower() == "описание")
async def handle_description(message: Message):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if user:
        await message.reply(format_description(user), parse_mode="HTML")
    else:
        await message.reply("Ты ещё не заполнял описание.")

@dp.message(lambda m: m.text and m.text.lower().startswith("описание @"))
async def handle_target_description(message: Message):
    username = message.text.split("@")[-1].strip()
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    if user:
        await message.reply(format_description(user), parse_mode="HTML")
    else:
        await message.reply("Пользователь не найден.")

# === Администрирование ===
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.reply("/users — все\n/ban ID\n/unban ID")

@dp.message(Command("users"))
async def list_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    text = "\n".join([f"{u[1]} | {u[2]} | {u[4]} лет" for u in users])
    await message.reply(text or "Нет данных.")

@dp.message(lambda m: m.text.startswith("/ban"))
async def ban_user(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Пример: /ban 123456")
    uid = int(parts[1])
    cursor.execute("INSERT OR IGNORE INTO banned(user_id) VALUES (?)", (uid,))
    conn.commit()
    await message.reply(f"Пользователь {uid} забанен.")

@dp.message(lambda m: m.text.startswith("/unban"))
async def unban_user(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Пример: /unban 123456")
    uid = int(parts[1])
    cursor.execute("DELETE FROM banned WHERE user_id=?", (uid,))
    conn.commit()
    await message.reply(f"Пользователь {uid} разбанен.")

# === Игровая команда ===
@dp.message(Command("mute"))
async def mute_user(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("Пример: Мут 3часа")
    
    user_name = parts[1]
    duration = parts[2] if len(parts) > 2 else None
    await message.reply(f"Пользователь {user_name} замучен на {duration}")

@dp.message(Command("ban"))
async def ban_user(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("Пример: Бан @username")

    user_name = parts[1]
    await message.reply(f"Пользователь {user_name} забанен.")

@dp.message(Command("guess"))
async def start_game(message: Message, state: FSMContext):
    secret = random.randint(1, 10)
    await state.set_state(GameStates.guessing)
    await state.update_data(secret=secret)
    await message.reply("Я загадал число от 1 до 10. Угадай!")

@dp.message(GameStates.guessing)
async def process_guess(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        guess = int(message.text)
    except ValueError:
        return await message.reply("Нужно число.")
    if guess == data["secret"]:
        await message.reply("Правильно! Ты угадал!")
        await state.clear()
    else:
        await message.reply("Неверно, попробуй ещё.")

# === Запуск с повторными попытками ===
async def run_bot():
    retries = 5  # Количество попыток повторного подключения
    for attempt in range(retries):
        try:
            print("Бот запущен.")
            await dp.start_polling(bot)
            break  # Выход из цикла при успешном запуске
        except Exception as e:
            print(f"Ошибка при подключении: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(5)  # Задержка перед повторной попыткой
            else:
                print("Не удалось подключиться после нескольких попыток.")
                raise e  # Прекращаем выполнение, если попытки исчерпаны

# === Основная точка входа ===
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_bot())
