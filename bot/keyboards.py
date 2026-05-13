from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню (нижние кнопки)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Проверить вишлист"), KeyboardButton(text="🎁 Текущие раздачи")],
        [KeyboardButton(text="➕ Добавить игру вручную"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🔗 Привязать профиль")]
    ],
    resize_keyboard=True
)

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