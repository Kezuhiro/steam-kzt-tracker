from aiogram.fsm.state import State, StatesGroup

# --- СОСТОЯНИЯ FSM ---
class BotStates(StatesGroup):
    waiting_for_profile = State()
    waiting_for_game = State()