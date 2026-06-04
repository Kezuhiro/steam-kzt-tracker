import re
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.ai_service import ai_service
from core import database as db
from core import steam_api
from bot.keyboards import main_menu, track_all_kb, tracked_games_kb, settings_kb, game_card_kb, ai_scout_kb
from core.config import STEAM_LINK_RE
from bot.states import BotStates

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    welcome_text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"🔹 Бот для отслеживания <b>Steam KZT</b>. Помогу тебе:\n"
        f"🔹 Экономить на играх, отслеживая скидки в тенге KZT\n"
        f"🔹 Не пропускать 100% раздачи (халяву) в Steam\n"
        f"🔹 Следить за ценами на скины и кейсы\n\n"
        f"С чего начнем?"
    )
    
    await message.answer(welcome_text, reply_markup=main_menu, parse_mode="HTML")

# --- 1. ПРИВЯЗКА ПРОФИЛЯ ---
@router.message(F.text == "🔗 Привязать профиль")
async def ask_profile(message: types.Message, state: FSMContext):
    instruction_text = (
        "🔗 <b>Привязка аккаунта Steam</b>\n\n"
        "Отправь мне ссылку на свой профиль. Это нужно, чтобы я мог автоматически подтянуть твой вишлист.\n\n"
        "<b>Примеры ссылок:</b>\n"
        "• <code>https://steamcommunity.com/id/nickname/</code>\n"
        "• <code>https://steamcommunity.com/profiles/7656119.../</code>\n\n"
        "⚠️ <b>Важно:</b> Твой профиль и «Сведения об играх» должны быть <u>Открытыми</u> в настройках приватности Steam, иначе я ничего не увижу."
    )
    
    await message.answer(instruction_text, parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_profile)

@router.message(BotStates.waiting_for_profile, F.text.regexp(STEAM_LINK_RE))
async def save_profile(message: types.Message, state: FSMContext):
    match = STEAM_LINK_RE.search(message.text)
    steam_type, steam_val = match.group(1), match.group(2)
    
    await db.save_user(message.from_user.id, steam_type, steam_val)
    await message.answer("Профиль привязан.", reply_markup=main_menu)
    await state.clear()

# --- 2. ПРОВЕРКА ВИШЛИСТА ---
@router.message(F.text == "📥 Проверить вишлист")
async def check_wishlist(message: types.Message):
    user_data = await db.get_user(message.from_user.id)
    if not user_data:
        await message.answer("🔗 Привяжи профиль Steam в главном меню, чтобы я мог найти твои игры.")
        return

    msg = await message.answer("⏳ Стягиваю данные из Steam, подожди немного...")
    
    data = await steam_api.fetch_wishlist(user_data[0], user_data[1])

    if not data:
        await msg.edit_text("📭 Твой вишлист пуст или скрыт настройками приватности.")
        return
    games = []
    for game_id, info in data.items():
        name = info.get('name', 'Неизвестно')
        subs = info.get('subs', [])
        
        price = initial = discount = 0
        if subs:
            price = subs[0].get('price', 0) // 100
            initial = subs[0].get('initial', 0) // 100
            discount = subs[0].get('discount_pct', 0)
            
        games.append({
            'id': game_id,
            'name': name,
            'price': price,
            'initial': initial,
            'discount': discount
        })

    games.sort(key=lambda x: (-x['discount'], x['price']))
    discounted_games = [g for g in games if g['discount'] > 0]
    regular_games = [g for g in games if g['discount'] == 0]

    response_text = "📋 <b>Твой вишлист:</b>\n\n"
    limit_reached = False

    if discounted_games:
        response_text += "🔥 <b>Игры по скидке:</b>\n"
        for game in discounted_games:
            # 🔥 Проверка лимита ДО добавления новой строки (~3900 символов с запасом)
            if len(response_text) > 3900:
                limit_reached = True
                break
                
            url = f"https://store.steampowered.com/app/{game['id']}"
            name_link = f"<a href='{url}'>{game['name']}</a>"
            price_str = f"<s>{game['initial']}</s> <b>{game['price']} ₸</b> (-{game['discount']}%)"
            response_text += f"🔻 {name_link} — {price_str}\n"
        response_text += "\n"

    if regular_games and not limit_reached:
        response_text += "📁 <b>Без скидки:</b>\n"
        for game in regular_games:
            if len(response_text) > 3900:
                limit_reached = True
                break
                
            url = f"https://store.steampowered.com/app/{game['id']}"
            name_link = f"<a href='{url}'>{game['name']}</a>"
            
            if game['price'] > 0:
                price_str = f"<b>{game['price']} ₸</b>"
            elif game['price'] == 0 and game['initial'] == 0 and not game.get('subs'):
                price_str = "<i>Нет цены</i>"
            else:
                price_str = "<b>Бесплатно</b>"
                
            response_text += f"🔹 {name_link} — {price_str}\n"

    # 🔥 Если лимит превышен, добавляем красивую плашку. Строку при этом НЕ РЕЖЕМ!
    if limit_reached:
        response_text += "\n\n<i>...И еще много игр, которые не влезли. Нажми кнопку ниже, чтобы начать их отслеживать.</i>"

    await msg.delete()
    await message.answer(response_text, parse_mode="HTML", reply_markup=track_all_kb(), disable_web_page_preview=True)

# --- 3. ДОБАВЛЕНИЕ ИГРЫ ВРУЧНУЮ ---
@router.message(F.text == "➕ Добавить игру вручную")
async def ask_manual_game(message: types.Message, state: FSMContext):
    await message.answer("Отправь AppID игры (только цифры) или ссылку на неё в магазине.")
    await state.set_state(BotStates.waiting_for_game)

@router.message(BotStates.waiting_for_game)
async def process_manual_game(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    app_id_match = re.search(r'app/(\d+)', text)
    if app_id_match:
        app_id = app_id_match.group(1)
    elif text.isdigit():
        app_id = text
    else:
        await message.answer("Некорректный формат. Нужен AppID или ссылка.")
        return

    await message.answer("🔍 Проверяю игру...")
    game_info = await steam_api.fetch_single_game(app_id)
    
    if not game_info:
        await message.answer("❌ Игра не найдена или недоступна в регионе.")
        return

    # 🔥 ИСПРАВЛЕНО: Передаем все 12 аргументов в новую БД
    await db.save_tracked_game(
        app_id=int(app_id), 
        name=game_info.get("name", "Неизвестно"), 
        last_price=game_info.get("price", 0), 
        initial_price=game_info.get("initial", 0), 
        discount_pct=game_info.get("discount_pct", 0),
        header_image=game_info.get("header_image", ""),
        genres=game_info.get("genres", "Не указано"),
        metacritic=str(game_info.get("metacritic", "Нет оценки")),
        short_description=game_info.get("short_description", "Описание отсутствует"),
        pc_requirements=game_info.get("pc_requirements", "Не указаны"),
        categories=game_info.get("categories", "Не указано"),
        release_year=game_info.get("release_year", None)
    )
    await db.link_user_game(message.from_user.id, int(app_id))

    if game_info.get("discount_pct", 0) > 0:
        price_str = f"<s>{game_info.get('initial', 0)} ₸</s> <b>{game_info.get('price', 0)} ₸</b> (-{game_info.get('discount_pct', 0)}%) 🔥"
    elif game_info.get("price", 0) == 0:
        price_str = "<b>Бесплатно</b>"
    else:
        price_str = f"<b>{game_info.get('price', 0)} ₸</b>"

    caption = (
        f"🎮 <b>{game_info.get('name', 'Неизвестно')}</b>\n\n"
        f"🎭 Жанры: <i>{game_info.get('genres', 'Не указано')}</i>\n"
        f"⭐ Рейтинг Metacritic: <b>{game_info.get('metacritic', 'Нет оценки')}</b>\n\n"
        f"💰 Цена: {price_str}\n\n"
        f"✅ <i>Добавлено в мониторинг</i>"
    )

    steam_url = f"https://store.steampowered.com/app/{app_id}"
    kb = game_card_kb(int(app_id), steam_url)

    try:
        await message.answer_photo(photo=game_info.get("header_image"), caption=caption, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await message.answer(caption, parse_mode="HTML", reply_markup=kb)

    await state.clear()


@router.callback_query(F.data.startswith("untrack_"))
async def process_untrack(callback: types.CallbackQuery):
    app_id = int(callback.data.split("_")[1])
    await db.untrack_game(callback.from_user.id, app_id)
    

    games = await db.get_user_tracked_games(callback.from_user.id)
    if not games:
        await callback.message.edit_text("Список отслеживания пуст.")
    else:
        await callback.message.edit_reply_markup(reply_markup=tracked_games_kb(games))
        
    await callback.answer("Удалено из мониторинга.")

# Обработка массовой подписки из вишлиста
@router.callback_query(F.data == "track_wishlist")
async def process_track_wishlist(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🔄 Синхронизирую вишлист с БД...")
    
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        return

    data = await steam_api.fetch_wishlist(user_data[0], user_data[1])

    if not data:
        await callback.message.answer("❌ Ошибка при синхронизации.")
        return

    for app_id_str, info in data.items():
        app_id = int(app_id_str)
        name = info.get('name', 'Неизвестно')
        header_image = info.get('header_image', '')
        genres = info.get('genres', 'Не указано')
        metacritic = str(info.get('metacritic', 'Нет оценки'))
        
        subs = info.get('subs', [])
        price = initial = discount = 0

        if subs:
            price = subs[0].get('price', 0) // 100
            initial = subs[0].get('initial', 0) // 100
            discount = subs[0].get('discount_pct', 0)

        # Вытаскиваем новые поля (если fetch_wishlist их отдает, иначе дефолты)
        short_desc = info.get('short_description', 'Описание отсутствует')
        pc_reqs = info.get('pc_requirements', 'Не указаны')
        categories = info.get('categories', 'Не указано')
        release_year = info.get('release_year', None)

        # 🔥 ИСПРАВЛЕНО: Передаем 12 аргументов
        await db.save_tracked_game(
            app_id=app_id, 
            name=name, 
            last_price=price, 
            initial_price=initial, 
            discount_pct=discount, 
            header_image=header_image, 
            genres=genres, 
            metacritic=metacritic,
            short_description=short_desc,
            pc_requirements=pc_reqs,
            categories=categories,
            release_year=release_year
        )
        await db.link_user_game(callback.from_user.id, app_id)

    await callback.message.answer("✅ Твой вишлист успешно добавлен в систему мониторинга!")
    await callback.answer()
# --- ПРОСМОТР РАЗДАЧ ВРУЧНУЮ ---
@router.message(F.text == "🎁 Текущие раздачи")
async def manual_check_freebies(message: types.Message):
    await message.answer("🔍 Ищу актуальные раздачи со 100% скидкой в Steam...")
    freebies = await steam_api.fetch_freebies()
    
    if not freebies:
        await message.answer("😔 Прямо сейчас чистых раздач в Steam нет. Попробуй позже!")
        return

    for freebie in freebies:
        text = (
            f"🎁 <b>БЕСПЛАТНО В STEAM</b>\n"
            f"🔹 <b>{freebie['title']}</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👉 Забрать игру", url=freebie['url'])]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

# --- МЕНЮ НАСТРОЕК ---
@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    user_settings = await db.get_user_settings(message.from_user.id)
    if not user_settings:
        await message.answer("❌ Сначала привяжи профиль в главном меню.")
        return
        
    wants_freebies = user_settings[0]

    tracked_games = await db.get_user_tracked_games(message.from_user.id)
    games_count = len(tracked_games)
    
    freebies_status = "✅ Включены" if wants_freebies == 1 else "❌ Выключены"
    
    settings_text = (
        "⚙️ <b>Центр управления</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ Игр в мониторинге: <code>{games_count}</code>\n"
        f"└ Регион цен: <b>Казахстан (₸)</b>\n\n"
        f"🔔 <b>Уведомления:</b>\n"
        f"└ Раздачи 100% скидок: <b>{freebies_status}</b>\n\n"
        "Используй кнопки ниже, чтобы изменить настройки или очистить список отслеживания."
    )
    
    await message.answer(
        settings_text, 
        parse_mode="HTML", 
        reply_markup=settings_kb(wants_freebies)
    )

# --- ОБРАБОТКА КНОПОК НАСТРОЕК ---
@router.callback_query(F.data == "toggle_freebies")
async def process_toggle_freebies(callback: types.CallbackQuery):
    new_status = await db.toggle_freebies_setting(callback.from_user.id)
    if new_status is not None:
        await callback.message.edit_reply_markup(reply_markup=settings_kb(new_status))
        status_text = "включены 🔔" if new_status == 1 else "выключены 🔕"
        await callback.answer(f"Уведомления о раздачах {status_text}!")

@router.callback_query(F.data == "show_tracked_games")
async def process_show_tracked(callback: types.CallbackQuery):
    games = await db.get_user_tracked_games(callback.from_user.id)
    if not games:
        await callback.message.answer("Ты пока ничего не отслеживаешь.")
    else:
        await callback.message.answer(
            "Твои подписки. Нажми, чтобы удалить:",
            reply_markup=tracked_games_kb(games)
        )
    await callback.answer()

# 1. Главная точка входа — переключаем на инлайн-меню режимов
@router.message(F.text == "🤖 AI Игровой Скаут")
async def cmd_ai_scout_menu(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        "🧠 <b>Добро пожаловать в ИИ-Центр управления базой Steam!</b>\n\n"
        "Я подключен напрямую к аналитической базе данных PostgreSQL.\n"
        "Выбери интеллектуальный режим, который тебе нужен:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=ai_scout_kb)

# 2. Обработка кликов по инлайн-кнопкам ИИ режимов
@router.callback_query(F.data.startswith("ai_mode_"))
async def process_ai_mode_choice(callback: types.CallbackQuery, state: FSMContext):
    mode = callback.data.split("_")[2]
    await callback.answer()
    
    if mode == "vibes":
        await state.set_state(BotStates.ai_vibes_waiting)
        await callback.message.answer(
            "🎭 <b>Режим: Поиск по вайбу и атмосфере</b>\n\n"
            "Напиши свои пожелания. Ты можешь указывать желаемый бюджет или требовать скидку прямо в тексте!\n"
            "<i>Пример: 'хочу сложный космический выживач до 4000 тенге со скидкой' или 'что-то фановое под музыку'</i>",
            parse_mode="HTML"
        )
    elif mode == "desc":
        await state.set_state(BotStates.ai_desc_waiting)
        await callback.message.answer(
            "🧩 <b>Режим: Детектив (Поиск по описанию)</b>\n\n"
            "Опиши геймплей, механики или сюжет игры, название которой ты забыл.\n"
            "<i>Пример: 'игра где ты просыпаешься на острове, рубишь деревья, строишь дома и там есть зомби ночю'</i>",
            parse_mode="HTML"
        )
    elif mode == "compare":
        await state.set_state(BotStates.ai_compare_waiting)
        await callback.message.answer(
            "⚔️ <b>Режим: Баттл и сравнение игр</b>\n\n"
            "Напиши названия двух или трех игр из топ чартов, и я сравню их ценность, скидки и геймплей.\n"
            "<i>Пример: 'Что лучше купить: Witcher 3 или Cyberpunk 2077?'</i>",
            parse_mode="HTML"
        )

# 3. Универсальный внутренний обработчик для текстовых стейтов ИИ
async def execute_hybrid_rag_search(message: types.Message, state: FSMContext, mode: str):
    user_prompt = message.text.strip()
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    max_price = None
    price_match = re.search(r'(?:до|бюджет|цена|дешевле)\s*(\d+)|(\d+)\s*(?:тенге|kzt|кзт|тг)', user_prompt, re.IGNORECASE)
    if price_match:
        price_str = price_match.group(1) or price_match.group(2)
        if price_str:
            max_price = int(price_str)

    status_msg = await message.answer("🤖 ИИ подбирает подходящие тайтлы и пишет рецензию...")

    # 🔥 ТЕПЕРЬ ЭТО СЛОВАРЬ: {"Имя Игры": "Почему подходит"}
    suggested_games_dict = await ai_service.think_game_titles(user_prompt)
    
    if not suggested_games_dict:
        await status_msg.edit_text("❌ ИИ не смог подобрать игры. Попробуй переформулировать запрос!")
        await state.clear()
        return

    await status_msg.edit_text("⏳ Игры выбраны! Подтягиваю точные цены из Steam...")

    ready_games = []

    # 3. ЦИКЛ ОН-ДЕМАНД ПАРСИНГА С СОХРАНЕНИЕМ РЕЦЕНЗИИ
    for title, reason in suggested_games_dict.items():
        game_row = await db.get_game_by_name(title)
        
        if not game_row:
            success = await steam_api.find_and_parse_missing_game(title)
            if success:
                game_row = await db.get_game_by_name(title)
        
        if game_row:
            # Превращаем строку БД в словарь, чтобы добавить туда мнение ИИ
            game_dict = dict(game_row)
            game_dict['ai_reason'] = reason
            ready_games.append(game_dict)

    if not ready_games:
        await status_msg.edit_text("📭 Не удалось найти точные данные по предложенным ИИ играм в Steam.")
        await state.clear()
        return

    # 4. АЛГОРИТМ ФИЛЬТРАЦИИ ПО БЮДЖЕТУ
    final_selection = []
    
    if max_price is not None:
        in_budget_games = [g for g in ready_games if g['last_price'] <= max_price]
        if in_budget_games:
            final_selection = in_budget_games
            response_header = f"🎯 <b>Игры, идеально подходящие под твой бюджет (до {max_price} ₸):</b>\n\n"
        else:
            ready_games.sort(key=lambda x: x['last_price'] - max_price)
            final_selection = ready_games[:2]
            response_header = f"⚠️ <b>В лимит {max_price} ₸ ничего не нашлось, но вот варианты с минимальной переплатой:</b>\n\n"
    else:
        final_selection = ready_games[:3]
        response_header = "🎮 <b>Вот отличные игры под твой запрос:</b>\n\n"

    # 5. КРАСИВЫЙ СБОР ФИНАЛЬНОГО HTML-ОТВЕТА
    response_text = response_header
    
    for game in final_selection:
        if game['discount_pct'] > 0:
            price_str = f"<s>{game['initial_price']} ₸</s> <b>{game['last_price']} ₸</b> (-{game['discount_pct']}%) 🔥"
        elif game['last_price'] == 0:
            price_str = "<b>Бесплатно (Free to Play)</b>"
        else:
            price_str = f"<b>{game['last_price']} ₸</b>"

        release_year_str = str(game['release_year']) if game['release_year'] else "Год неизвестен"
        
        # 🔥 ДОБАВЛЕНО ПОЛЕ 'Почему подходит'
        response_text += (
            f"🔹 <b>{game['name']} ({release_year_str})</b>\n"
            f"💬 <i>Почему подходит:</i> {game['ai_reason']}\n"
            f"🎭 Жанры: <i>{game['genres']}</i>\n"
            f"⭐ Metacritic: <b>{game['metacritic']}</b>\n"
            f"💰 Цена: {price_str}\n"
            f"📝 Подробнее: <a href='https://store.steampowered.com/app/{game['app_id']}'>Ссылка в Steam</a>\n"
            f"-----------------------------------\n\n"
        )

    await status_msg.delete()
    await message.answer(response_text, parse_mode="HTML", reply_markup=main_menu, disable_web_page_preview=True)
    await state.clear()

# Маппинг стейтов на выполнение
@router.message(BotStates.ai_vibes_waiting)
async def process_vibes_mode(message: types.Message, state: FSMContext):
    await execute_hybrid_rag_search(message, state, "vibes")

@router.message(BotStates.ai_desc_waiting)
async def process_desc_mode(message: types.Message, state: FSMContext):
    await execute_hybrid_rag_search(message, state, "desc")

@router.message(BotStates.ai_compare_waiting)
async def process_compare_mode(message: types.Message, state: FSMContext):
    await execute_hybrid_rag_search(message, state, "compare")

# Заглушка, чтобы обычный случайный текст вне стейтов не триггерил ИИ хаотично
@router.message(F.text & ~F.text.startswith('/'))
async def default_text_fallback(message: types.Message):
    await message.answer(
        "💡 Используй кнопки меню для управления ботом.\n"
        "Если ты хочешь запустить умный ИИ-поиск по описанию или вайбу, нажми кнопку <b>🤖 AI Игровой Скаут</b>.",
        parse_mode="HTML"
    )