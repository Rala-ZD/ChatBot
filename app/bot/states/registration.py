from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    awaiting_consent = State()
    awaiting_age = State()
    awaiting_gender = State()
    awaiting_region = State()
    awaiting_interests = State()

