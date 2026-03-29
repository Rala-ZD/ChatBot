from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    awaiting_consent = State()
    awaiting_age = State()
    awaiting_gender = State()
    awaiting_nickname = State()
    awaiting_preferred_gender = State()
    awaiting_interests = State()
    awaiting_confirmation = State()

