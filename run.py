import os
import re
import time
import json
import random
import asyncio
import logging
import aiohttp
import aiosqlite
from pydub import AudioSegment
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Filter
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, FSInputFile, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import BigInteger, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy import func
from rev_ai import apiclient
from moviepy.editor import VideoFileClip

ADMINS = [7281169403]
API_TOKEN = '7658777452:AAHUmMy3ROkwhmJpXlzZb3p2H5HRRcoWv5c'
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
tokens = ['02j2kY_UvdoL7WjGdXSyQ9MqLr9A-4oGoR6Z2JZt6BUh91471ctMr1FUD7oWGI-Kahzhoq6VZ7ZpLf4vLI4dyxYvvbHec', '02LIXJoYtq24oWGQ_-8Outb3c9C9kuOZZOF-Eg99NmlZ_-IDT5_8p0PI9OSq6_GtqSenZz0tlwSXcAYFWuS51L8O6lMBg', '02R1KhYQKOHOdva1jgHlN7qZuYFPqDpxDyaH033WYIBxJbbi4cUks79ipMe1tnbAQuyahN-LfmlsL3yAx1CinJiP5d3Ro']

# Создаем папки, если они не существуют
os.makedirs(os.path.dirname(db_path), exist_ok=True)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
ogg_path = os.path.join(DATA_DIR, 'add.ogg')
db_path = os.path.join(DATA_DIR, 'db')



# Создаем файл базы данных, если он не существует
if not os.path.exists(db_path):
    with open(db_path, 'w'):
        pass

DATABASE_URL = f'sqlite+aiosqlite:///{db_path}'

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine)


class AdminProtect(Filter):
    def __init__(self):
        self.admins = ADMINS

    async def __call__(self, message: Message):
        return message.from_user.id in self.admins


class Newsletter(StatesGroup):
    message = State()


class Add_tokens(StatesGroup):
    message = State()


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(default='Noname')
    time: Mapped[int] = mapped_column(default=100000)


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_user(tg_id, username):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            session.add(User(tg_id=tg_id, username=username))
        else:
            await session.execute(update(User).where(User.tg_id == tg_id).values(username=username))
        await session.commit()


async def add_usage(tg_id, usage):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user is None:
            return True # Или создай нового пользователя

        if user.time < usage:
            return True

        user.time -= usage
        await session.commit()


async def add_banned_user(tg_id):
    async with async_session() as session:
        await session.execute(update(User).where(User.tg_id == tg_id).values(username=User.username + '_BAN'))
        await session.commit()


async def get_users():
    async with async_session() as session:
        users = await session.scalars(select(User))
        return users
    

def get_duration_pydub(file_path):
    audio = AudioSegment.from_file(file_path)
    return int(len(audio) / 1000.0)


@dp.message(Command('start'))
async def start(message: Message):
    await message.answer(
        'Нет Telegram premium🚀? Не беда! Просто Отправь мне аудио или видео(кружочек) для перевода в текстовый вариант 📝 😉')
    #  reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text='Мой канал', url='https://t.me/bots884')).as_markup())
    await create_user(message.from_user.id, str(message.from_user.username))


@dp.message(AdminProtect(), Command('newsletter'))
async def admin(message: Message, state: FSMContext):
    await state.set_state(Newsletter.message)
    await message.answer('Отправь сообщение для рассылки')


@dp.message(AdminProtect(), Newsletter.message)
async def get_admin(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state is None or current_state != Newsletter.message:
        await message.answer('Сначала начни рассылку, используя команду /newsletter')
        return

    users = await get_users()
    i = 0
    for user in users:
        try:
            await bot.send_message(chat_id=user.tg_id, text=message.text)
        except:
            i += 1
            # await delete_banned_user(user.tg_id)
            if user.username[-3:] != 'BAN':
                await add_banned_user(user.tg_id)
    await message.answer(f'Рассылка завершена. Пользователей, заблокировавших бота: {i}')
    await state.clear()


@dp.message(AdminProtect(), Command('users'))
async def how_many(message: Message, bot: Bot):
    async with async_session() as session:
        # Количество пользователей в базе данных
        count_users = await session.scalar(select(func.count(User.id)))
        count_users_ban = await session.scalar(
            select(func.count(User.id)).where(User.username.ilike('%BAN%'))
        )
    await message.answer(
        f'Количество активных пользователей: \n\nКоличество пользователей в базе данных: {count_users}\n Заблоктровали бота: {count_users_ban}\n\n Итого: {count_users - count_users_ban}')


@dp.message(AdminProtect(), Command('tokens'))
async def get_tokens(message: Message):
    await message.answer('Токены для работы с RevAI:\n\n' + str(tokens), 
                         reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text='Добавить токен', callback_data='add_token')).row(InlineKeyboardButton(text='Изменить массив полностью', callback_data='edit_tokens')).as_markup())


@dp.message(AdminProtect(), F.text == 'Стоп')
async def stop_adding_tokens(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f'Токены добавлены. Текущий список: {tokens}', reply_markup=ReplyKeyboardRemove())


@dp.callback_query(AdminProtect(), F.data == 'add_token')
async def add_tokens(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Add_tokens.message)
    await callback.message.answer('Отправляй токены по одному!')


@dp.message(AdminProtect(), Add_tokens.message)
async def add_token(message: Message, state: FSMContext):
    global tokens
    tokens.append(message.text)
    await message.answer('Токен добавлен! Можешь отправить еще', reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Стоп')]], resize_keyboard=True))


@dp.message(AdminProtect(), F.text.startswith('[') & F.text.endswith(']'))
async def full_edit_tokens(message: Message):
    global tokens
    tokens = [t.strip().strip("'").strip('"') for t in message.text[1:-1].split(',')]
    await message.answer(f'Токены обновлены. Текущий список: {tokens}')


@dp.message(AdminProtect(), Command('get_db'))
async def get_db(message: Message, bot: Bot):
    database = FSInputFile(
        os.path.abspath(db_path),
        filename='db.sqlite3'
    )
    await message.answer_document(database)


async def download_file(session: aiohttp.ClientSession, file_url: str, id_file: str, file_extension: str):
    async with session.get(file_url) as response:
        with open(f'../data/{id_file}.{file_extension}', 'wb') as file:
            file.write(await response.read())


def transcribe_file(token: str, id_file: str, duration: int) -> str:
    global tokens
    if duration < 3:
        main_audio = AudioSegment.from_file(f'../data/{id_file}.ogg')
        add_audio = AudioSegment.from_file(ogg_path)
        combined = main_audio + add_audio
        combined.export(f'../data/{id_file}.ogg', format='ogg')
    client = apiclient.RevAiAPIClient(token)
    job_options = {'language': 'ru'}
    job = client.submit_job_local_file(f'../data/{id_file}.ogg', **job_options)
    while True:
        job_details = client.get_job_details(job.id)
        if job_details.status == 'transcribed':
            transcript_text = client.get_transcript_text(job.id)
            os.remove(f'../data/{id_file}.ogg')
            transcript_text = re.sub(r'Speaker \d+\s+', '', transcript_text)
            return transcript_text
        if job_details.status == 'failed':
            for tok in tokens:
                if tok == token:
                    tokens.remove(tok)
                    for i in tokens:
                        if len(i) > 2:
                            new_token = i
                    return f'new_{tok}; tokens={tokens}'


async def download_and_transcribe(bot: Bot, file_id: str, token: str, id_file: str, file_extension: str) -> str:
    file_info = await bot.get_file(file_id)
    file_path = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}'

    async with aiohttp.ClientSession() as session:
        await download_file(session, file_path, id_file, file_extension)

    if file_extension == 'mp4':
        video = VideoFileClip(f'../data/{id_file}.mp4')
        video.audio.write_audiofile(f'../data/{id_file}.ogg')
        video.close()
        os.remove(f'../data/{id_file}.mp4')
    duration = get_duration_pydub(f'../data/{id_file}.ogg')
    if await add_usage(id_file[:10], duration):
        await bot.send_message(chat_id='7281169403', text=f'Пользователь {id_file[:11]} превысил лимит времени на аудио')
        return 'Ты превысил лимит времени на аудио, попробуй позже или напиши администратору бота'
    transcript_text = await asyncio.to_thread(transcribe_file, token, id_file, duration)
    if transcript_text[:3] == 'new':
        await bot.send_message(chat_id='7281169403', text=transcript_text)
        transcript_text = 'Извини, сменился токен в приложении(бывает редко, тебе просто не повезло). Отправь заново свое аудио и я его уже точно обработаю)'

    return transcript_text


@dp.message(F.voice)
async def handle_audio_message(message: Message, bot: Bot):
    global tokens
    for i in tokens:
        if len(i) > 2:
            token = i
    await message.answer('Уже обрабатываю, подожди немного...')
    await create_user(message.from_user.id, str(message.from_user.username))
    num_file = str(message.from_user.id) + str(random.randint(1, 999999))
    voice_file_id = message.voice.file_id
    try:
        transcript_text = await download_and_transcribe(bot, voice_file_id, token, str(num_file), 'ogg')
        if len(transcript_text)<4096:
            await message.reply(transcript_text)
        else:
            for i in range(int(len(transcript_text)//4096)+1):
                await message.answer(transcript_text[i*4096:(i+1)*4096])
    except TelegramBadRequest:
        await message.reply('Текст в этом аудио отсутствует')


@dp.message(F.video_note)
async def handle_video_message(message: Message):
    global tokens
    for i in tokens:
        if len(i) > 2:
            token = i
    await message.answer('Уже обрабатываю, подожди немного...')
    video_file_id = message.video_note.file_id
    num_file = str(message.from_user.id) + str(random.randint(1, 999999))
    try:
        transcript_text = await download_and_transcribe(bot, video_file_id, token, num_file, 'mp4')
        await message.reply(transcript_text)
    except TelegramBadRequest:
        await message.reply('Текст в этом аудио отсутствует')


async def main():
    await async_main()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
