from aiogram.fsm.state import State, StatesGroup


class ReportStates(StatesGroup):
    reason = State()
    note = State()
