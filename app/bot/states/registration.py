from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    age = State()
    gender = State()
    nickname = State()
    preferred_gender = State()
    interests = State()
    consent = State()


class ProfileEditStates(StatesGroup):
    age = State()
    gender = State()
    nickname = State()
    preferred_gender = State()
    interests = State()
