import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET

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
    """Асинхронный воркер для получения деталей одной игры"""
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
                        
                        # --- НОВЫЕ ПОЛЯ ---
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
        # Ограничиваем до 5 одновременных запросов
        sem = asyncio.Semaphore(5) 
        
        # Создаем пул задач и запускаем их параллельно
        tasks = [fetch_game_details(appid, session, sem, games_data) for appid in app_ids]
        await asyncio.gather(*tasks)
            
        return games_data

async def fetch_prices_for_watcher(app_ids: list):
    """Массовая проверка цен для Watcher'а."""
    games_data = {}
    sem = asyncio.Semaphore(5) # Все те же 5 одновременных запросов
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # Запускаем таски параллельно
        tasks = [fetch_game_details(appid, session, sem, games_data) for appid in app_ids]
        await asyncio.gather(*tasks)
            
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
                    
                    # 1. Цены
                    price_overview = game_data.get("price_overview")
                    price = initial = discount = 0
                    if price_overview:
                        price = price_overview.get("final", 0) // 100
                        initial = price_overview.get("initial", 0) // 100
                        discount = price_overview.get("discount_percent", 0)
                    
                    # 2. Картинка (если API не вернул, ставим стандартную заглушку Steam)
                    header_image = game_data.get("header_image", f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg")
                    
                    # 3. Жанры (превращаем список словарей в строку через запятую)
                    genres_list = game_data.get("genres", [])
                    genres = ", ".join([g.get("description") for g in genres_list]) if genres_list else "Не указано"
                    
                    # 4. Metacritic
                    metacritic = game_data.get("metacritic", {}).get("score", "Нет оценки")
                        
                    return {
                        "name": game_data.get("name"),
                        "price": price,
                        "initial": initial,
                        "discount_pct": discount,
                        "header_image": header_image,
                        "genres": genres,
                        "metacritic": metacritic
                    }
    return None

async def fetch_freebies():
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=10"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KZT_Steam_Bot/1.0"}
    
    freebies = []
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    for post in posts:
                        p_data = post["data"]
                        title = p_data.get("title", "")
                        flair = p_data.get("link_flair_text", "")
                        post_url = p_data.get("url", "")
                        
                        # ФИЛЬТР: Только [Steam], не Expired, и СТРОГО домен магазина Steam
                        if "[Steam]" in title and flair != "Expired" and flair != "Discussion":
                            if "store.steampowered.com" in post_url:
                                freebies.append({
                                    "id": p_data["id"],
                                    "title": title.replace("[Steam]", "").strip(),
                                    "url": post_url,
                                    "reddit_url": f"https://www.reddit.com{p_data['permalink']}"
                                })
                except Exception as e:
                    logging.error(f"Ошибка парсинга Reddit: {e}")
    return freebies