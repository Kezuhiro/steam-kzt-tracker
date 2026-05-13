import asyncio
import logging
from aiogram import Bot
from . import database as db
from . import steam_api
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def start_watcher(bot: Bot, interval_hours: float = 4):
    logging.info(f"👁️ Watcher запущен! Проверка каждые {interval_hours} ч.")
    await asyncio.sleep(10)
    
    while True:
        try:
            await check_discounts(bot)
        except Exception as e:
            logging.error(f"Ошибка в Watcher: {e}")
        
        # Засыпаем (переводим часы в секунды)
        await asyncio.sleep(interval_hours * 3600)

async def check_discounts(bot: Bot):
    logging.info("🔄 Watcher начал проверку цен...")
    
    tracked_games = await db.get_all_tracked_games()
    if not tracked_games:
        return

    app_ids = [game[0] for game in tracked_games]
    actual_prices = await steam_api.fetch_prices_for_watcher(app_ids)
    
    for game in tracked_games:
        app_id, name, db_last_price, db_initial, db_discount, db_image, db_genres, db_meta = game
        str_app_id = str(app_id)
        
        if str_app_id not in actual_prices:
            continue 
        
        game_info = actual_prices[str_app_id]
        subs = game_info.get("subs", [])
        
        actual_image = game_info.get("header_image", db_image)
        actual_genres = game_info.get("genres", db_genres)
        actual_meta = str(game_info.get("metacritic", db_meta))
        
        if not subs:
            continue
            
        actual_price = subs[0].get("price", 0) // 100
        actual_initial = subs[0].get("initial", 0) // 100
        actual_discount = subs[0].get("discount_pct", 0)

        # Сравниваем цены
        if actual_discount > db_discount or (actual_price < db_last_price and actual_price > 0):
            logging.info(f"🔥 СКИДКА! {name} стоила {db_last_price}, теперь {actual_price}")
            
            users = await db.get_users_tracking_game(app_id)
            
            # --- ФОРМИРУЕМ КАРТОЧКУ УВЕДОМЛЕНИЯ ---
            caption = (
                f"🔥 <b>СКИДКА НА ИГРУ ИЗ ВИШЛИСТА!</b> 🔥\n\n"
                f"🎮 <b>{name}</b>\n"
                f"🎭 Жанры: <i>{actual_genres}</i>\n"
                f"⭐ Metacritic: <b>{actual_meta}</b>\n\n"
                f"💰 Старая цена: <s>{db_last_price} ₸</s>\n"
                f"🎁 Новая цена: <b>{actual_price} ₸</b> (-{actual_discount}%)\n"
            )
            
            steam_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Купить в Steam", url=f"https://store.steampowered.com/app/{app_id}")]
            ])
            
            # Рассылаем фото всем подписанным
            for tg_id in users:
                try:
                    await bot.send_photo(
                        chat_id=tg_id, 
                        photo=actual_image, 
                        caption=caption, 
                        parse_mode="HTML", 
                        reply_markup=steam_kb
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление {tg_id}: {e}")
            
        if actual_price != db_last_price or actual_discount != db_discount or actual_image != db_image:
            await db.save_tracked_game(app_id, name, actual_price, actual_initial, actual_discount, actual_image, actual_genres, actual_meta)
            
    logging.info("✅ Watcher завершил цикл проверки.")

async def start_freebies_watcher(bot: Bot, interval_hours: float = 1.0):
    """Отдельный цикл проверки бесплатных раздач (раз в час)."""
    logging.info(f"🎁 Freebies Watcher запущен! Проверка каждые {interval_hours} ч.")
    await asyncio.sleep(5) 
    
    while True:
        try:
            await check_freebies(bot)
        except Exception as e:
            logging.error(f"Ошибка в Freebies Watcher: {e}")
        
        await asyncio.sleep(interval_hours * 3600)

async def check_freebies(bot: Bot):
    logging.info("🔎 Проверка свежих раздач 100% скидок...")
    freebies = await steam_api.fetch_freebies()
    
    if not freebies:
        return

    users = await db.get_users_for_freebies()
    if not users:
        return
        
    for freebie in freebies:
        post_id = freebie["id"]
        
        # Если уже отправляли эту игру пропускаем
        if await db.is_freebie_sent(post_id):
            continue
            
        logging.info(f"🎁 НАЙДЕНА РАЗДАЧА: {freebie['title']}")
        
        text = (
            f"🎁 <b>БЕСПЛАТНАЯ РАЗДАЧА В STEAM!</b> 🎁\n\n"
            f"Найдена игра со 100% скидкой:\n"
            f"🔹 <b>{freebie['title']}</b>\n\n"
            f"Успей забрать на аккаунт!\n"
            f"<i>(Иногда раздачи требуют перехода по ссылке, а не просто кнопки в Steam)</i>"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👉 Забрать игру", url=freebie['url'])],
            [InlineKeyboardButton(text="💬 Пост на Reddit", url=freebie['reddit_url'])]
        ])
        
        # Рассылаем всем пользователям
        for tg_id in users:
            try:
                await bot.send_message(tg_id, text, parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                logging.error(f"Не удалось отправить раздачу пользователю {tg_id}: {e}")
        
        # Помечаем как отправленное, чтобы не спамить
        await db.mark_freebie_sent(post_id, freebie["title"], freebie["url"])
        await asyncio.sleep(0.5) 