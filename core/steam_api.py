import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
import re
import urllib.parse
import feedparser

async def resolve_steam_id(steam_type: str, steam_val: str, session: aiohttp.ClientSession) -> str:
    if steam_type == 'profiles':
        return steam_val
    
    xml_url = f"https://steamcommunity.com/id/{steam_val}/?xml=1"
    async with session.get(xml_url) as resp:
        if resp.status == 200:
            xml_data = await resp.text()
            try:
                root = ET.fromstring(xml_data)
                steam_id64 = root.find('steamID64')
                if steam_id64 is not None:
                    return steam_id64.text
            except Exception as e:
                logging.error(f"Ошибка парсинга XML: {e}")
    return None

async def fetch_game_details(appid: int, session: aiohttp.ClientSession, sem: asyncio.Semaphore, games_data: dict):
    async with sem:
        details_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=kz&l=russian"
        async with session.get(details_url) as details_resp:
            if details_resp.status == 200:
                try:
                    details_json = await details_resp.json(content_type=None)
                    if not details_json:
                        return
                    
                    info = details_json.get(str(appid), {})
                    if info and info.get("success"):
                        game_data = info["data"]
                        price_overview = game_data.get("price_overview")
                        
                        header_image = game_data.get("header_image", f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg")
                        genres_list = game_data.get("genres", [])
                        genres = ", ".join([g.get("description") for g in genres_list]) if genres_list else "Не указано"
                        metacritic = game_data.get("metacritic", {}).get("score", "Нет оценки")
                        
                        games_data[str(appid)] = {
                            "name": game_data.get("name", "Неизвестно"),
                            "header_image": header_image,
                            "genres": genres,
                            "metacritic": metacritic,
                            "subs": [{
                                "price": price_overview.get("final"),
                                "initial": price_overview.get("initial"),
                                "discount_pct": price_overview.get("discount_percent")
                            }] if price_overview else []
                        }
                except Exception as e:
                    logging.error(f"Ошибка парсинга appid {appid}: {e}")
            else:
                logging.error(f"Steam вернул {details_resp.status} для {appid}")
        
        await asyncio.sleep(0.1)


async def fetch_wishlist(steam_type: str, steam_val: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        steam_id64 = await resolve_steam_id(steam_type, steam_val, session)
        
        if not steam_id64:
            logging.error("Не удалось определить steam_id64")
            return None
            
        wishlist_url = f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={steam_id64}"
        async with session.get(wishlist_url) as resp:
            if resp.status != 200:
                return None
            
            data = await resp.json()
            items = data.get("response", {}).get("items", [])
            
            if not items:
                return {} 
                
            app_ids = [item["appid"] for item in items]
            
        games_data = {}
        sem = asyncio.Semaphore(5) 
        
        tasks = [fetch_game_details(appid, session, sem, games_data) for appid in app_ids]
        await asyncio.gather(*tasks)
            
        return games_data

async def fetch_prices_for_watcher(app_ids: list) -> dict:
    """
    Безопасно и последовательно обновляет цены для списка игр из вишлистов,
    защищая IP от блокировок Steam во время плановых проверок.
    """
    games_data = {}
    if not app_ids:
        return games_data
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KZT_Steam_Bot/1.0",
        "Accept": "application/json",
    }
    
    logging.info(f"🔄 Watcher начинает плановое обновление цен для {len(app_ids)} игр...")
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for idx, appid in enumerate(app_ids, 1):
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=kz&l=russian"
            
            while True:
                try:
                    async with session.get(url) as resp:
                        # Защита: если во время проверки цен Стим моргнул лимитом
                        if resp.status == 429 or resp.status == 403:
                            logging.warning(f"🛑 Watcher поймал {resp.status} на игре {appid}. Пауза 45 сек...")
                            await asyncio.sleep(45)
                            continue # Повторяем запрос к этой же игре
                            
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if data and data.get(str(appid), {}).get("success"):
                                game_data = data[str(appid)]["data"]
                                price_overview = game_data.get("price_overview")
                                
                                genres_list = game_data.get("genres", [])
                                genres = ", ".join([g.get("description") for g in genres_list]) if genres_list else "Не указано"
                                
                                games_data[str(appid)] = {
                                    "name": game_data.get("name", "Неизвестно"),
                                    "header_image": game_data.get("header_image", ""),
                                    "genres": genres,
                                    "metacritic": game_data.get("metacritic", {}).get("score", "Нет оценки"),
                                    "subs": [{
                                        "price": price_overview.get("final"),
                                        "initial": price_overview.get("initial"),
                                        "discount_pct": price_overview.get("discount_percent")
                                    }] if price_overview else []
                                }
                            break # Успешно обработали, выходим из while True
                            
                except Exception as e:
                    logging.error(f"Ошибка Watcher на appid {appid}: {e}. Повтор через 5 сек...")
                    await asyncio.sleep(5)
                    continue
            
            # Микро-пауза между запросами в штатном режиме
            await asyncio.sleep(1.5)
            
    logging.info("✅ Watcher успешно собрал актуальные цены!")       
    return games_data

async def fetch_single_game(appid: str):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=kz&l=russian"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if data and data.get(appid, {}).get("success"):
                    game_data = data[appid]["data"]
                    
                    price_overview = game_data.get("price_overview")
                    price = initial = discount = 0
                    if price_overview:
                        price = price_overview.get("final", 0) // 100
                        initial = price_overview.get("initial", 0) // 100
                        discount = price_overview.get("discount_percent", 0)
                    
                    header_image = game_data.get("header_image", "")
                    
                    genres_list = game_data.get("genres", [])
                    genres = ", ".join([g.get("description") for g in genres_list]) if genres_list else "Не указано"
                    
                    metacritic = str(game_data.get("metacritic", {}).get("score", "Нет оценки"))
                    
                    short_desc = game_data.get("short_description", "Описание отсутствует.")
                    req_html = game_data.get("pc_requirements", {}).get("minimum", "Не указаны.")
                    clean_reqs = " ".join(re.sub(r'<[^>]+>', ' ', req_html).split())
                    
                    categories_list = game_data.get("categories", [])
                    categories = ", ".join([c.get("description") for c in categories_list]) if categories_list else "Не указано"

                    release_year = None
                    release_info = game_data.get("release_date", {})
                    if not release_info.get("coming_soon"):
                        date_str = release_info.get("date", "")
                        year_match = re.search(r'\b(\d{4})\b', date_str)
                        if year_match:
                            release_year = int(year_match.group(1))
                        
                    return {
                        "name": game_data.get("name"),
                        "price": price,
                        "initial": initial,
                        "discount_pct": discount,
                        "header_image": header_image,
                        "genres": genres,
                        "metacritic": metacritic,
                        "short_description": short_desc,
                        "pc_requirements": clean_reqs,
                        "categories": categories,
                        "release_year": release_year
                    }
    return None

async def fetch_freebies():
    # Открытый RSS-канал сабреддита FreeGameFindings
    url = "https://www.reddit.com/r/FreeGameFindings/new/.rss"
    
    # Маскируемся под стандартный RSS-ридер
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FeedReader/1.0"}
    
    freebies = []
    
    # Делаем запрос через asyncio, чтобы не блокировать поток
    try:
        import aiohttp
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    rss_text = await resp.text()
                    
                    # Парсим XML-структуру RSS
                    feed = feedparser.parse(rss_text)
                    
                    for entry in feed.entries:
                        title = entry.get("title", "")
                        post_url = entry.get("link", "")
                        # В RSS id поста обычно лежит в entry.id (например, 't3_12xyz')
                        post_id = entry.get("id", "").split("_")[-1] 
                        
                        # Ищем заветный тег [Steam] в заголовке
                        if "[Steam]" in title:
                            freebies.append({
                                "id": post_id,
                                "title": title.replace("[Steam]", "").strip(),
                                "url": post_url,  # Ссылка на раздачу
                                "reddit_url": entry.get("comments", post_url)  # Ссылка на обсуждение
                            })
                else:
                    logging.warning(f"⚠️ Reddit RSS отклонил запрос. Статус: {resp.status}")
                    
    except Exception as e:
        logging.error(f"Ошибка парсинга Reddit RSS: {e}")
        
    return freebies

async def fetch_top_appids_from_steamspy(page: int = 0) -> list[int]:
    """
    Получает около 1000 популярных AppID с одной страницы SteamSpy
    """
    url = f"https://steamspy.com/api.php?request=all&page={page}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    # Исправлено: убрали дублирующийся resp
                    data = await resp.json(content_type=None)
                    if not data:
                        return []
                    # Извлекаем все ключи (они же appid) и переводим в int
                    app_ids = [int(appid) for appid in data.keys() if appid.isdigit()]
                    logging.info(f"📊 SteamSpy <https://steamspy.com> отдал {len(app_ids)} игр со страницы {page}.")
                    return app_ids
                else:
                    logging.error(f"SteamSpy вернул ошибку HTTP {resp.status}")
        except Exception as e:
            # Выводим реальный текст ошибки e, чтобы понимать, что пошло не так
            logging.error(f"Ошибка при запросе к SteamSpy: {e}", exc_info=True)
    return []


async def fetch_and_save_single_game(appid: int, session: aiohttp.ClientSession, db) -> int:
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=kz&l=russian"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if data and data.get(str(appid), {}).get("success"):
                    game_data = data[str(appid)]["data"]
                    
                    # [Твой существующий код парсинга цен, жанров, картинок и метакритика...]
                    price = initial = discount = 0
                    if game_data.get("is_free") == True:
                        price = initial = discount = 0
                    elif "price_overview" in game_data:
                        price_overview = game_data["price_overview"]
                        price = (price_overview.get("final") or 0) // 100
                        initial = (price_overview.get("initial") or 0) // 100
                        discount = price_overview.get("discount_percent") or 0

                    header_image = game_data.get("header_image", "")
                    genres_list = game_data.get("genres", [])
                    genres = ", ".join([g.get("description") for g in genres_list]) if genres_list else "Не указано"
                    
                    metacritic_obj = game_data.get("metacritic")
                    metacritic = str(metacritic_obj.get("score")) if metacritic_obj else "Нет оценки"
                    
                    short_desc = game_data.get("short_description", "Описание отсутствует.")
                    req_html = game_data.get("pc_requirements", {}).get("minimum", "Не указаны.")
                    clean_reqs = " ".join(re.sub(r'<[^>]+>', ' ', req_html).split())
                    
                    categories_list = game_data.get("categories", [])
                    categories = ", ".join([c.get("description") for c in categories_list]) if categories_list else "Не указано"

                    # 🔥 ПАРСИНГ ГОДА РЕЛИЗА
                    release_year = None
                    release_info = game_data.get("release_date", {})
                    
                    # Проверяем, что игра вообще вышла (coming_soon == False)
                    if not release_info.get("coming_soon"):
                        date_str = release_info.get("date", "")
                        # Ищем 4 цифры подряд (год)
                        year_match = re.search(r'\b(\d{4})\b', date_str)
                        if year_match:
                            release_year = int(year_match.group(1))

                    # Передаем всё в СУБД
                    await db.save_tracked_game(
                        app_id=int(appid),
                        name=game_data.get("name"),
                        last_price=price,
                        initial_price=initial,
                        discount_pct=discount,
                        header_image=header_image,
                        genres=genres,
                        metacritic=metacritic,
                        short_description=short_desc,
                        pc_requirements=clean_reqs,
                        categories=categories,
                        release_year=release_year  # Передали в метод базы
                    )
                return 200
            return resp.status
    except Exception as e:
        logging.error(f"Ошибка сети на appid {appid}: {e}")
        return 500

async def seed_top_games_to_db():
    """
    Массовый парсер. Обновляет некорректные нулевые цены в базе данных чанками.
    """
    from core import database as db

    all_top_appids = await fetch_top_appids_from_steamspy(page=0)
    if not all_top_appids:
        logging.error("Не удалось собрать пул AppID из SteamSpy. Отмена.")
        return

    # ВРЕМЕННО: Комментируем фильтр существующих, чтобы скрипт прошелся по базе 
    # и перезаписал нулевые цены на нормальные KZT!
    app_ids_to_parse = all_top_appids 
    total_to_parse = len(app_ids_to_parse)

    logging.info(f"⏳ Перезапуск исправления цен. Будет обновлено: {total_to_parse} игр.")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KZT_Steam_Bot/1.0"}
    chunk_size = 5 
    
    async with aiohttp.ClientSession(headers=headers) as session:
        i = 0
        while i < len(app_ids_to_parse):
            chunk = app_ids_to_parse[i:i + chunk_size]
            
            tasks = [fetch_and_save_single_game(appid, session, db) for appid in chunk]
            statuses = await asyncio.gather(*tasks)
            
            if 429 in statuses or 403 in statuses:
                logging.warning("🛑 Стим кинул лимит (429/403). Остужаем IP 60 секунд...")
                await asyncio.sleep(60)
                continue 
            
            i += chunk_size
            if i % 20 == 0:
                logging.info(f"📦 Исправлено цен в БД: {min(i, total_to_parse)}/{total_to_parse} игр.")
            
            await asyncio.sleep(2.0)

    logging.info("✅ База данных успешно пересобрана. Все цены в KZT и бесплатные игры приведены к норме!")

async def find_and_parse_missing_game(game_name: str) -> bool:
    """
    Ищет игру в магазине Steam по названию, находит её AppID 
    и автоматически парсит её в базу данных PostgreSQL.
    """
    # 1. Локальный импорт БД, чтобы избежать NameError и цикличных импортов
    from core import database as db
    
    # 2. Безопасное кодирование названия (Dead Space -> Dead%20Space)
    safe_game_name = urllib.parse.quote(game_name)
    search_url = f"https://store.steampowered.com/api/storesearch/?term={safe_game_name}&l=russian&cc=kz"
    
    headers = {"User-Agent": "Mozilla/5.0 KZT_Steam_Bot/1.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url) as resp:
                if resp.status == 200:
                    search_data = await resp.json()
                    items = search_data.get("items", [])
                    if not items:
                        return False 
                    
                    best_match = items[0]
                    appid = best_match.get("id")
                    
                    status = await fetch_and_save_single_game(appid, session, db)
                    return status == 200
        except Exception as e:
            logging.error(f"Ошибка при On-Demand парсинге игры '{game_name}': {e}")
            return False
    return False