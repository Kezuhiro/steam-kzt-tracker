import re
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core import database as db
from core import steam_api
from bot.keyboards import main_menu, track_all_kb, tracked_games_kb, settings_kb
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

    if discounted_games:
        response_text += "🔥 <b>Игры по скидке:</b>\n"
        for game in discounted_games:
            url = f"https://store.steampowered.com/app/{game['id']}"
            name_link = f"<a href='{url}'>{game['name']}</a>"
            price_str = f"<s>{game['initial']}</s> <b>{game['price']} ₸</b> (-{game['discount']}%)"
            
            response_text += f"🔻 {name_link} — {price_str}\n"
        response_text += "\n"

    if regular_games:
        response_text += "📁 <b>Без скидки:</b>\n"
        for game in regular_games:
            url = f"https://store.steampowered.com/app/{game['id']}"
            name_link = f"<a href='{url}'>{game['name']}</a>"
            
            if game['price'] > 0:
                price_str = f"<b>{game['price']} ₸</b>"
            elif game['price'] == 0 and game['initial'] == 0 and not game.get('subs'):
                price_str = "<i>Нет цены</i>"
            else:
                price_str = "<b>Бесплатно</b>"
                
            response_text += f"🔹 {name_link} — {price_str}\n"

    if len(response_text) > 4000:
        response_text = response_text[:4000] + "\n\n<i>...И еще много игр, которые не влезли. Нажми кнопку ниже, чтобы начать их отслеживать.</i>"

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

    # Сохраняем в БД 
    await db.save_tracked_game(
        int(app_id), 
        game_info["name"], 
        game_info["price"], 
        game_info["initial"], 
        game_info["discount_pct"],
        game_info["header_image"],
        game_info["genres"],
        str(game_info["metacritic"])
    )
    await db.link_user_game(message.from_user.id, int(app_id))

    # ФОРМИРУЕМ ЦЕНУ
    if game_info["discount_pct"] > 0:
        price_str = f"<s>{game_info['initial']} ₸</s> <b>{game_info['price']} ₸</b> (-{game_info['discount_pct']}%) 🔥"
    elif game_info["price"] == 0:
        price_str = "<b>Бесплатно</b>"
    else:
        price_str = f"<b>{game_info['price']} ₸</b>"

    caption = (
        f"🎮 <b>{game_info['name']}</b>\n\n"
        f"🎭 Жанры: <i>{game_info['genres']}</i>\n"
        f"⭐ Рейтинг Metacritic: <b>{game_info['metacritic']}</b>\n\n"
        f"💰 Цена: {price_str}\n\n"
        f"✅ <i>Добавлено в мониторинг</i>"
    )

    steam_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Открыть в Steam", url=f"https://store.steampowered.com/app/{app_id}")]
    ])

    try:
        await message.answer_photo(
            photo=game_info["header_image"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=steam_kb
        )
    except Exception as e:
        await message.answer(caption, parse_mode="HTML", reply_markup=steam_kb)

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


        await db.save_tracked_game(app_id, name, price, initial, discount, header_image, genres, metacritic)
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