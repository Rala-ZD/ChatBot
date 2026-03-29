from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    editing_age = State()
    editing_gender = State()
    editing_nickname = State()
    editing_preferred_gender = State()
    editing_interests = State()

