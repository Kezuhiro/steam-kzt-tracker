from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню (нижние кнопки)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Проверить вишлист"), KeyboardButton(text="🎁 Текущие раздачи")],
        [KeyboardButton(text="🤖 AI Игровой Скаут")], # <-- Единая точка входа для AI
        [KeyboardButton(text="🔗 Привязать профиль"), KeyboardButton(text="⚙️ Настройки")]
    ],
    resize_keyboard=True
)

ai_scout_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎭 Поиск по вайбу/настроению", callback_data="ai_mode_vibes")],
    [InlineKeyboardButton(text="🧩 Найти игру по описанию механик", callback_data="ai_mode_desc")],
    [InlineKeyboardButton(text="⚔️ Сравнительный Баттл игр", callback_data="ai_mode_compare")]
])

# Инлайн-кнопка под карточкой игры (Идея 1: Анализ отзывов через LLM)
def game_card_kb(app_id: int, url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Открыть в Steam", url=url)],
        [InlineKeyboardButton(text="📋 🤖 Анализ отзывов ИИ", callback_data=f"ai_reviews_{app_id}")] # <-- Новая кнопка
    ])

# Остальные твои функции без изменений...
def settings_kb(wants_freebies: int):
    freebies_text = "🔕 Выкл. уведомления о раздачах" if wants_freebies == 1 else "🔔 Вкл. уведомления о раздачах"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои отслеживаемые игры", callback_data="show_tracked_games")],
        [InlineKeyboardButton(text=freebies_text, callback_data="toggle_freebies")]
    ])

def track_all_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Отслеживать весь вишлист", callback_data="track_wishlist")]
    ])

def tracked_games_kb(games):
    builder = []
    for app_id, name in games:
        builder.append([InlineKeyboardButton(text=f"❌ Удалить: {name}", callback_data=f"untrack_{app_id}")])
    return InlineKeyboardMarkup(inline_keyboard=builder)