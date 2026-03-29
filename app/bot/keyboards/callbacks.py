from aiogram.filters.callback_data import CallbackData


class RegistrationCallback(CallbackData, prefix="reg"):
    action: str
    value: str | None = None


class ProfileCallback(CallbackData, prefix="profile"):
    field: str


class ReportCallback(CallbackData, prefix="report"):
    action: str
    value: str | None = None
