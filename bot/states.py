from aiogram.fsm.state import State, StatesGroup

# --- СОСТОЯНИЯ FSM ---
class BotStates(StatesGroup):
    waiting_for_profile = State()
    waiting_for_game = State()
    waiting_for_budget = State()
    ai_vibes_waiting = State()    # ждем описание настроения
    ai_desc_waiting = State()     # ждем описание геймплея
    ai_compare_waiting = State()  # ждем названия двух игр