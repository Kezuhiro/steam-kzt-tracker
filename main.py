import asyncio
import logging
from aiogram import Bot, Dispatcher
from core.config import TOKEN
from core.database import init_db
from bot.handlers import router
from core.watcher import start_watcher, start_freebies_watcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    dp.include_router(router)
    
    await init_db()
    
    # Запускаем проверку вишлиста (раз в 4 часа)
    asyncio.create_task(start_watcher(bot, interval_hours=4))
    
    # Запускаем проверку бесплатных раздач (раз в 1 час)
    # Для теста можешь поставить interval_hours=0.005, чтобы бот сразу проверил Reddit
    asyncio.create_task(start_freebies_watcher(bot, interval_hours=1))
    
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())