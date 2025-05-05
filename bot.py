import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, CommandStart
from aiohttp import web

API_TOKEN = os.getenv("API_TOKEN")  # API токен будет храниться в переменной окружения
GROUP_CHAT_ID = -1002368509151  # Заменить на ID вашей группы

logging.basicConfig(level=logging.INFO)

# Создание бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_descriptions = {}

class Form(StatesGroup):
    pubg_nick = State()
    pubg_id = State()
    age = State()
    city = State()

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer("Привет! Чтобы вступить в группу, заполни описание.\nВведи PUBG ник:")
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
    await state.update_data(city=message.text)
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or f"id_{user_id}"

    user_descriptions[user_id] = {
        "pubg_nick": data["pubg_nick"],
        "pubg_id": data["pubg_id"],
        "age": data["age"],
        "city": data["city"],
        "username": f"@{username}"
    }

    await state.clear()

    # Создание временной инвайт-ссылки
    invite_link = await bot.create_chat_invite_link(
        chat_id=GROUP_CHAT_ID,
        member_limit=1,
        creates_join_request=False
    )

    await message.answer(
        "Отлично! Описание сохранено.\nВот ссылка для вступления в группу:\n" + invite_link.invite_link,
        parse_mode="HTML"
    )

# В группе: обработка команды "описание"
@dp.message(lambda message: message.text.lower() == "описание")
async def handle_description(message: Message):
    user_id = message.from_user.id
    user_data = user_descriptions.get(user_id)
    if user_data:
        await message.reply(format_description(user_data), parse_mode="HTML")
    else:
        await message.reply("Ты ещё не заполнял описание. Напиши боту в ЛС.")

@dp.message(lambda message: message.text.lower().startswith("описание @"))
async def handle_target_description(message: Message):
    target_username = message.text[len("описание @"):].strip()
    found = None
    for desc in user_descriptions.values():
        if desc["username"].lstrip("@") == target_username:
            found = desc
            break
    if found:
        await message.reply(format_description(found), parse_mode="HTML")
    else:
        await message.reply("Пользователь не заполнял описание или имя указано неверно.")

def format_description(data):
    return (
        f"<b>Описание:</b>\n"
        f"<b>Ник PUBG:</b> <code>{data['pubg_nick']}</code>\n"
        f"<b>ID PUBG:</b> <code>{data['pubg_id']}</code>\n"
        f"<b>Возраст:</b> {data['age']}\n"
        f"<b>Город:</b> {data['city']}\n"
        f"<b>Telegram:</b> {data['username']}"
    )

# Обработчик для вебхука
async def on_webhook(request):
    json_str = await request.json()
    update = types.Update(**json_str)
    await dp.process_update(update)
    return web.Response()

# Устанавливаем вебхук
async def on_start():
    webhook_url = os.getenv("WEBHOOK_URL")  # URL вебхука для Vercel
    await bot.set_webhook(webhook_url)

# Создаем приложение и запускаем сервер
app = web.Application()
app.router.add_post('/webhook', on_webhook)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_start())  # Устанавливаем вебхук
    web.run_app(app, host="0.0.0.0", port=8080)
