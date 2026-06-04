# core/database.py
import logging
import asyncpg
from .config import DATABASE_URL

# Глобальный пул соединений. Будет переиспользоваться во всех функциях.
pool: asyncpg.Pool | None = None

async def init_db():
    global pool
    logging.info("⏳ Подключение к PostgreSQL...")
    pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id BIGINT PRIMARY KEY,
                steam_type TEXT NOT NULL,
                steam_val TEXT NOT NULL,
                wants_freebies INTEGER DEFAULT 1
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tracked_games (
                app_id BIGINT PRIMARY KEY,
                name TEXT,
                last_price BIGINT,
                initial_price BIGINT,
                discount_pct INTEGER,
                header_image TEXT,
                genres TEXT,
                metacritic TEXT,
                short_description TEXT,  
                pc_requirements TEXT,    
                categories TEXT,
                release_year INTEGER
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_games (
                tg_id BIGINT,
                app_id BIGINT,
                PRIMARY KEY (tg_id, app_id),
                FOREIGN KEY (tg_id) REFERENCES users (tg_id) ON DELETE CASCADE,
                FOREIGN KEY (app_id) REFERENCES tracked_games (app_id) ON DELETE CASCADE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sent_freebies (
                post_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT
            )
        ''')
    logging.info("✅ PostgreSQL успешно инициализирован.")

# --- ФУНКЦИИ ДЛЯ USERS ---
async def save_user(tg_id: int, steam_type: str, steam_val: str):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (tg_id, steam_type, steam_val) 
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id) DO UPDATE SET 
                steam_type = EXCLUDED.steam_type,
                steam_val = EXCLUDED.steam_val
        ''', tg_id, steam_type, steam_val)

async def get_user(tg_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT steam_type, steam_val FROM users WHERE tg_id = $1', tg_id)
        return (row['steam_type'], row['steam_val']) if row else None

# --- ФУНКЦИИ ДЛЯ ПОДПИСОК (TRACKING) ---
async def save_tracked_game(app_id: int, name: str, last_price: int, initial_price: int, discount_pct: int, 
                            header_image: str, genres: str, metacritic: str, 
                            short_description: str, pc_requirements: str, categories: str, release_year: int | None):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO tracked_games (
                app_id, name, last_price, initial_price, discount_pct, 
                header_image, genres, metacritic, short_description, pc_requirements, categories, release_year
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (app_id) DO UPDATE SET
                name=EXCLUDED.name,
                last_price=EXCLUDED.last_price,
                initial_price=EXCLUDED.initial_price,
                discount_pct=EXCLUDED.discount_pct,
                header_image=EXCLUDED.header_image,
                genres=EXCLUDED.genres,
                metacritic=EXCLUDED.metacritic,
                short_description=EXCLUDED.short_description,
                pc_requirements=EXCLUDED.pc_requirements,
                categories=EXCLUDED.categories,
                release_year=EXCLUDED.release_year
        ''', app_id, name, last_price, initial_price, discount_pct, header_image, genres, metacritic, short_description, pc_requirements, categories, release_year)

async def link_user_game(tg_id: int, app_id: int):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_games (tg_id, app_id) 
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        ''', tg_id, app_id)

async def get_users_tracking_game(app_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT tg_id FROM user_games WHERE app_id = $1', app_id)
        return [row['tg_id'] for row in rows]
        
async def get_user_tracked_games(tg_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT g.app_id, g.name 
            FROM tracked_games g
            JOIN user_games ug ON g.app_id = ug.app_id
            WHERE ug.tg_id = $1
        ''', tg_id)
        return [(row['app_id'], row['name']) for row in rows]

async def untrack_game(tg_id: int, app_id: int):
    async with pool.acquire() as conn:
        await conn.execute('DELETE FROM user_games WHERE tg_id = $1 AND app_id = $2', tg_id, app_id)

async def get_all_tracked_games():
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT app_id, name, last_price, initial_price, discount_pct, header_image, genres, metacritic FROM tracked_games')
        return [(r['app_id'], r['name'], r['last_price'], r['initial_price'], r['discount_pct'], r['header_image'], r['genres'], r['metacritic']) for r in rows]
    
async def get_all_users():
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT tg_id FROM users')
        return [row['tg_id'] for row in rows]

async def is_freebie_sent(post_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT 1 FROM sent_freebies WHERE post_id = $1', post_id)
        return row is not None

async def mark_freebie_sent(post_id: str, title: str, url: str):
    async with pool.acquire() as conn:
        await conn.execute('INSERT INTO sent_freebies (post_id, title, url) VALUES ($1, $2, $3)', post_id, title, url)

async def get_users_for_freebies():
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT tg_id FROM users WHERE wants_freebies = 1')
        return [row['tg_id'] for row in rows]

async def toggle_freebies_setting(tg_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT wants_freebies FROM users WHERE tg_id = $1', tg_id)
        if row:
            new_status = 0 if row['wants_freebies'] == 1 else 1
            await conn.execute('UPDATE users SET wants_freebies = $1 WHERE tg_id = $2', new_status, tg_id)
            return new_status
    return None

async def get_user_settings(tg_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT wants_freebies FROM users WHERE tg_id = $1', tg_id)
        return (row['wants_freebies'],) if row else None
    
async def get_games_by_ai_filters(genre: str | None, max_price: int | None, multiplayer: bool | None):
    async with pool.acquire() as conn:
        query = "SELECT app_id, name, last_price, initial_price, discount_pct, genres, metacritic, short_description, pc_requirements, categories, release_year FROM tracked_games WHERE 1=1"
        params = []
        param_idx = 1

        if genre:
            # ILIKE в Postgres работает без учета регистра
            query += f" AND genres ILIKE ${param_idx}"
            params.append(f"%{genre}%")
            param_idx += 1

        if max_price is not None:
            query += f" AND last_price <= ${param_idx}"
            params.append(max_price)
            param_idx += 1

        if multiplayer:
                    query += " AND (genres ILIKE '%Multiplayer%' OR categories ILIKE '%Multi-player%' OR categories ILIKE '%Совместная игра%' OR categories ILIKE '%Кооператив%')"

        query += " ORDER BY discount_pct DESC, last_price ASC LIMIT 10"

        rows = await conn.fetch(query, *params)
        
        games = []
        for row in rows:
            games.append({
                "app_id": row['app_id'],
                "name": row['name'],
                "last_price": row['last_price'],
                "initial_price": row['initial_price'],
                "discount_pct": row['discount_pct'],
                "header_image": row['header_image'],
                "genres": row['genres'],
                "release_year": row['release_year']
            })
        return games


async def get_user_tracked_games_detailed(tg_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT g.app_id, g.name, g.last_price, g.initial_price, g.discount_pct, g.genres
            FROM tracked_games g
            JOIN user_games ug ON g.app_id = ug.app_id
            WHERE ug.tg_id = $1
        ''', tg_id)
        
        games = []
        for row in rows:
            games.append({
                "app_id": row['app_id'],
                "name": row['name'],
                "price": row['last_price'],
                "initial": row['initial_price'],
                "discount_pct": row['discount_pct'],
                "genres": row['genres']
            })
        return games

async def get_tracked_games_count() -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT COUNT(*) FROM tracked_games')
        return row['count'] if row else 0
        
async def get_games_for_ai_analysis(max_price: int = None, only_discounted: bool = False, limit: int = 40):
    async with pool.acquire() as conn:
        query = "SELECT app_id, name, last_price, initial_price, discount_pct, genres, metacritic, short_description, pc_requirements, categories, release_year FROM tracked_games WHERE 1=1"
        params = []
        param_idx = 1
        
        if only_discounted:
            query += " AND discount_pct > 0"
            
        if max_price is not None:
            query += f" AND last_price <= ${param_idx}"
            params.append(max_price)
            param_idx += 1
            
        # COALESCE и NULLIF — безопасный каст строк в INT в Postgres
        query += f" ORDER BY COALESCE(NULLIF(metacritic, 'Нет оценки')::INTEGER, 0) DESC, discount_pct DESC LIMIT ${param_idx}"
        params.append(limit)
        
        rows = await conn.fetch(query, *params)
        
        games = []
        for row in rows:
            games.append({
                "id": row['app_id'],
                "title": row['name'],
                "current_price_kzt": row['last_price'],
                "original_price_kzt": row['initial_price'],
                "discount_percent": row['discount_pct'],
                "genres": row['genres'],
                "rating_metacritic": row['metacritic'],
                "description": row['short_description'],
                "requirements": row['pc_requirements'],
                "features": row['categories'],
                "release_year": row['release_year']
            })
        return games
    
async def get_game_by_name(name: str):
    """Ищет игру в базе по названию (по частичному совпадению)"""
    async with pool.acquire() as conn:
        # Оборачиваем имя в %, чтобы искать "содержит текст"
        return await conn.fetchrow('SELECT * FROM tracked_games WHERE name ILIKE $1', f'%{name}%')

async def get_game_by_id(app_id: int):
    """Ищет игру в базе по AppID"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM tracked_games WHERE app_id = $1', app_id)