from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить сделку", callback_data="add_transaction")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats_menu"),
        InlineKeyboardButton(text="📈 Аналитика", callback_data="analytics_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📉 Графики", callback_data="charts_menu"),
        InlineKeyboardButton(text="📁 Экспорт", callback_data="export_menu")
    )
    builder.row(
        InlineKeyboardButton(text="💱 Конвертер", callback_data="converter_menu"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu")
    )
    
    return builder.as_markup()


def stats_period_keyboard() -> InlineKeyboardMarkup:
    """Выбор периода статистики (без выбора валюты)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="stats_today"),
        InlineKeyboardButton(text="📅 Вчера", callback_data="stats_yesterday")
    )
    builder.row(
        InlineKeyboardButton(text="📆 Неделя", callback_data="stats_week"),
        InlineKeyboardButton(text="📆 Месяц", callback_data="stats_month")
    )
    builder.row(
        InlineKeyboardButton(text="📆 Год", callback_data="stats_year"),
        InlineKeyboardButton(text="🗓 Всё время", callback_data="stats_all")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Свой период", callback_data="stats_custom")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def analytics_keyboard() -> InlineKeyboardMarkup:
    """Меню аналитики"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Полная аналитика", callback_data="analytics_full")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Сравнить периоды", callback_data="analytics_compare")
    )
    builder.row(
        InlineKeyboardButton(text="📈 Динамика роста", callback_data="analytics_dynamics")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def charts_keyboard() -> InlineKeyboardMarkup:
    """Меню графиков"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 По дням (неделя)", callback_data="chart_daily_week"),
        InlineKeyboardButton(text="📅 По дням (месяц)", callback_data="chart_daily_month")
    )
    builder.row(
        InlineKeyboardButton(text="📆 По месяцам", callback_data="chart_monthly")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Свой период", callback_data="chart_custom")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def export_keyboard() -> InlineKeyboardMarkup:
    """Меню экспорта"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📗 Excel", callback_data="export_excel"),
        InlineKeyboardButton(text="📕 PDF", callback_data="export_pdf")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Оба формата", callback_data="export_both")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def export_period_keyboard(format_type: str) -> InlineKeyboardMarkup:
    """Выбор периода для экспорта"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📆 Этот месяц", callback_data=f"export_{format_type}_month"),
        InlineKeyboardButton(text="📆 Этот год", callback_data=f"export_{format_type}_year")
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Всё время", callback_data=f"export_{format_type}_all")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Свой период", callback_data=f"export_{format_type}_custom")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="export_menu")
    )
    
    return builder.as_markup()


def settings_menu_keyboard(daily_enabled: bool, weekly_enabled: bool, 
                           default_currency: str = "RUB") -> InlineKeyboardMarkup:
    """Меню настроек"""
    builder = InlineKeyboardBuilder()
    
    daily_status = "✅" if daily_enabled else "❌"
    weekly_status = "✅" if weekly_enabled else "❌"
    curr_symbol = "₽" if default_currency == "RUB" else "$"
    
    builder.row(
        InlineKeyboardButton(
            text=f"💵 Валюта по умолчанию: {curr_symbol}", 
            callback_data="settings_default_currency"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💱 Курс USD/RUB", 
            callback_data="settings_exchange_rate"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{daily_status} Ежедневный отчёт", 
            callback_data="settings_daily_toggle"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⏰ Время ежедневного", 
            callback_data="settings_daily_time"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{weekly_status} Еженедельный отчёт", 
            callback_data="settings_weekly_toggle"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📅 День и время еженедельного", 
            callback_data="settings_weekly_config"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить последнюю сделку", callback_data="delete_last")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def currency_select_keyboard(current: str = "RUB") -> InlineKeyboardMarkup:
    """Выбор валюты по умолчанию"""
    builder = InlineKeyboardBuilder()
    
    rub_mark = "✅ " if current == "RUB" else ""
    usd_mark = "✅ " if current == "USD" else ""
    
    builder.row(
        InlineKeyboardButton(text=f"{rub_mark}🇷🇺 Рубли (₽)", callback_data="set_currency_RUB"),
        InlineKeyboardButton(text=f"{usd_mark}🇺🇸 Доллары ($)", callback_data="set_currency_USD")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="settings_menu")
    )
    
    return builder.as_markup()


def weekday_keyboard() -> InlineKeyboardMarkup:
    """Выбор дня недели"""
    builder = InlineKeyboardBuilder()
    
    days = [
        ("Пн", "monday"), ("Вт", "tuesday"), ("Ср", "wednesday"),
        ("Чт", "thursday"), ("Пт", "friday"), ("Сб", "saturday"), ("Вс", "sunday")
    ]
    
    builder.row(*[
        InlineKeyboardButton(text=d[0], callback_data=f"weekday_{d[1]}")
        for d in days[:4]
    ])
    builder.row(*[
        InlineKeyboardButton(text=d[0], callback_data=f"weekday_{d[1]}")
        for d in days[4:]
    ])
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="settings_menu")
    )
    
    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Подтверждение действия"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_action")
    )
    
    return builder.as_markup()


def back_keyboard(callback: str = "main_menu") -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=callback)
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
    )
    return builder.as_markup()


def skip_keyboard(action: str) -> InlineKeyboardMarkup:
    """Кнопка пропустить"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{action}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
    )
    return builder.as_markup()


def date_preset_keyboard(action: str) -> InlineKeyboardMarkup:
    """Пресеты дат для быстрого выбора"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 Январь", callback_data=f"{action}_jan"),
        InlineKeyboardButton(text="📅 Февраль", callback_data=f"{action}_feb"),
        InlineKeyboardButton(text="📅 Март", callback_data=f"{action}_mar")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Апрель", callback_data=f"{action}_apr"),
        InlineKeyboardButton(text="📅 Май", callback_data=f"{action}_may"),
        InlineKeyboardButton(text="📅 Июнь", callback_data=f"{action}_jun")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Июль", callback_data=f"{action}_jul"),
        InlineKeyboardButton(text="📅 Август", callback_data=f"{action}_aug"),
        InlineKeyboardButton(text="📅 Сентябрь", callback_data=f"{action}_sep")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Октябрь", callback_data=f"{action}_oct"),
        InlineKeyboardButton(text="📅 Ноябрь", callback_data=f"{action}_nov"),
        InlineKeyboardButton(text="📅 Декабрь", callback_data=f"{action}_dec")
    )
    builder.row(
        InlineKeyboardButton(text="Q1 (Янв-Март)", callback_data=f"{action}_q1"),
        InlineKeyboardButton(text="Q2 (Апр-Июнь)", callback_data=f"{action}_q2")
    )
    builder.row(
        InlineKeyboardButton(text="Q3 (Июль-Сент)", callback_data=f"{action}_q3"),
        InlineKeyboardButton(text="Q4 (Окт-Дек)", callback_data=f"{action}_q4")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{action}_manual")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def converter_keyboard() -> InlineKeyboardMarkup:
    """Меню конвертера"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💱 Изменить курс", callback_data="settings_exchange_rate")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()
