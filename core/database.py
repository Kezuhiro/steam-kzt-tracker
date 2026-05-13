import aiosqlite
from .config import DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                steam_type TEXT NOT NULL,
                steam_val TEXT NOT NULL,
                wants_freebies INTEGER DEFAULT 1
            )
        ''')
        
        # ДОБАВЛЕНЫ: header_image, genres, metacritic
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tracked_games (
                app_id INTEGER PRIMARY KEY,
                name TEXT,
                last_price INTEGER,
                initial_price INTEGER,
                discount_pct INTEGER,
                header_image TEXT,
                genres TEXT,
                metacritic TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_games (
                tg_id INTEGER,
                app_id INTEGER,
                PRIMARY KEY (tg_id, app_id),
                FOREIGN KEY (tg_id) REFERENCES users (tg_id),
                FOREIGN KEY (app_id) REFERENCES tracked_games (app_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS sent_freebies (
                post_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT
            )
        ''')
        await db.commit()

# --- ФУНКЦИИ ДЛЯ USERS ---
async def save_user(tg_id: int, steam_type: str, steam_val: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT OR REPLACE INTO users (tg_id, steam_type, steam_val) VALUES (?, ?, ?)',
            (tg_id, steam_type, steam_val)
        )
        await db.commit()

async def get_user(tg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT steam_type, steam_val FROM users WHERE tg_id = ?', (tg_id,)) as cursor:
            return await cursor.fetchone()

# --- ФУНКЦИИ ДЛЯ ПОДПИСОК (TRACKING) ---
async def save_tracked_game(app_id: int, name: str, last_price: int, initial_price: int, discount_pct: int, header_image: str, genres: str, metacritic: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO tracked_games (app_id, name, last_price, initial_price, discount_pct, header_image, genres, metacritic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(app_id) DO UPDATE SET
                name=excluded.name,
                last_price=excluded.last_price,
                initial_price=excluded.initial_price,
                discount_pct=excluded.discount_pct,
                header_image=excluded.header_image,
                genres=excluded.genres,
                metacritic=excluded.metacritic
        ''', (app_id, name, last_price, initial_price, discount_pct, header_image, genres, metacritic))
        await db.commit()

async def link_user_game(tg_id: int, app_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR IGNORE INTO user_games (tg_id, app_id) VALUES (?, ?)', (tg_id, app_id))
        await db.commit()


async def get_all_tracked_games():
    """Получает все игры, за которыми кто-то следит."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT app_id, name, last_price, initial_price, discount_pct FROM tracked_games') as cursor:
            return await cursor.fetchall()

async def get_users_tracking_game(app_id: int):
    """Получает tg_id всех пользователей, подписанных на конкретную игру."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT tg_id FROM user_games WHERE app_id = ?', (app_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
        
async def get_user_tracked_games(tg_id: int):
    """Получает список игр, которые отслеживает конкретный пользователь."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT g.app_id, g.name 
            FROM tracked_games g
            JOIN user_games ug ON g.app_id = ug.app_id
            WHERE ug.tg_id = ?
        ''', (tg_id,)) as cursor:
            return await cursor.fetchall()

async def untrack_game(tg_id: int, app_id: int):
    """Удаляет привязку игры к пользователю."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM user_games WHERE tg_id = ? AND app_id = ?', (tg_id, app_id))
        await db.commit()

async def get_all_tracked_games():
    """Получает все игры, за которыми кто-то следит."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Добавлены новые колонки в SELECT
        async with db.execute('SELECT app_id, name, last_price, initial_price, discount_pct, header_image, genres, metacritic FROM tracked_games') as cursor:
            return await cursor.fetchall()
    
async def get_all_users():
    """Получает tg_id всех зарегистрированных пользователей для глобальной рассылки."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT tg_id FROM users') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def is_freebie_sent(post_id: str):
    """Проверяет, отправляли ли мы уже эту раздачу."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT 1 FROM sent_freebies WHERE post_id = ?', (post_id,)) as cursor:
            return await cursor.fetchone() is not None

async def mark_freebie_sent(post_id: str, title: str, url: str):
    """Записывает раздачу в базу, чтобы не отправить её повторно."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO sent_freebies (post_id, title, url) VALUES (?, ?, ?)', (post_id, title, url))
        await db.commit()

async def get_users_for_freebies():
    """Получает тех, кто НЕ отключал уведомления о раздачах."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT tg_id FROM users WHERE wants_freebies = 1') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def toggle_freebies_setting(tg_id: int):
    """Переключает статус уведомлений (Вкл/Выкл)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT wants_freebies FROM users WHERE tg_id = ?', (tg_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_status = 0 if row[0] == 1 else 1
                await db.execute('UPDATE users SET wants_freebies = ? WHERE tg_id = ?', (new_status, tg_id))
                await db.commit()
                return new_status
    return None

async def get_user_settings(tg_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT wants_freebies FROM users WHERE tg_id = ?', (tg_id,)) as cursor:
            return await cursor.fetchone()