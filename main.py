import asyncio
import logging
from aiogram import Bot, Dispatcher
from core.config import TOKEN
from core.database import init_db
from bot.handlers import router
from core.watcher import start_watcher, start_freebies_watcher
# 🔥 Не забываем импортировать наш парсер
from core.steam_api import seed_top_games_to_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    dp.include_router(router)
    
    logging.info("⏳ Ожидание запуска СУБД PostgreSQL...")
    await asyncio.sleep(4)
    
    # 1. Инициализируем пул и таблицы асинхронного Postgres (asyncpg)
    await init_db()
    

    # asyncio.create_task(seed_top_games_to_db())
    
    # 3. Настраиваем воркеры (наш отложенный запуск watcher, чтобы не мешать парсеру)
    async def delayed_watcher():
        logging.info("⏳ Воркер цен (Watcher) уходит в режим ожидания на 10 минут, чтобы не мешать первичному парсингу...")
        await asyncio.sleep(600) 
        await start_watcher(bot, interval_hours=4)

    asyncio.create_task(delayed_watcher())
    
    # Запускаем проверку бесплатных раздач (она дёргает Reddit, Стим не трогает)
    asyncio.create_task(start_freebies_watcher(bot, interval_hours=1))
    
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())