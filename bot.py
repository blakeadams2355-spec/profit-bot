import asyncio
import logging
from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BufferedInputFile, FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Dict, Any, Awaitable

from config import BOT_TOKEN, ADMIN_ID
import database as db
import reports
import keyboards as kb
from images_config import get_image_path, image_exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

scheduler = AsyncIOScheduler()

CURRENCY_SYMBOLS = {'RUB': '₽', 'USD': '$'}
CURRENCY_NAMES = {'RUB': 'Рубли', 'USD': 'Доллары'}


# ==================== MIDDLEWARE ====================

class AdminOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: Message, data: Dict[str, Any]) -> Any:
        if event.from_user.id != ADMIN_ID:
            await event.answer("⛔ Доступ запрещён")
            return
        return await handler(event, data)


class AdminOnlyCallbackMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: CallbackQuery, data: Dict[str, Any]) -> Any:
        if event.from_user.id != ADMIN_ID:
            await event.answer("⛔ Доступ запрещён", show_alert=True)
            return
        return await handler(event, data)


router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


# ==================== СОСТОЯНИЯ ====================

class AddTransaction(StatesGroup):
    waiting_for_amount = State()
    waiting_for_comment = State()
    waiting_for_date = State()


class CustomPeriod(StatesGroup):
    waiting_for_start_date = State()
    waiting_for_end_date = State()


class ComparePeriods(StatesGroup):
    waiting_for_period1_start = State()
    waiting_for_period1_end = State()
    waiting_for_period2_start = State()
    waiting_for_period2_end = State()


class SettingsState(StatesGroup):
    waiting_for_daily_time = State()
    waiting_for_weekly_time = State()
    waiting_for_exchange_rate = State()


# ==================== ХЕЛПЕРЫ ====================

def format_number(num: float) -> str:
    return f"{num:,.2f}".replace(",", " ")


def get_rate() -> float:
    return float(db.get_setting("usd_rub_rate", "100.0"))


def get_period_dates(period: str) -> tuple:
    today = date.today()

    periods = {
        "today": (today, today),
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "week": (today - timedelta(days=today.weekday()), today),
        "month": (today.replace(day=1), today),
        "year": (today.replace(month=1, day=1), today),
        "all": (None, None),
    }

    if period in periods:
        return periods[period]

    year = today.year
    quarters = {
        "q1": (date(year, 1, 1), date(year, 3, 31)),
        "q2": (date(year, 4, 1), date(year, 6, 30)),
        "q3": (date(year, 7, 1), date(year, 9, 30)),
        "q4": (date(year, 10, 1), date(year, 12, 31)),
    }
    if period in quarters:
        return quarters[period]

    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    if period in months:
        month = months[period]
        start = date(year, month, 1)
        end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return start, end

    return None, None


async def send_menu_with_image(target, section: str, caption: str,
                               reply_markup, parse_mode: str = "Markdown"):
    image_path = get_image_path(section)

    if image_path and Path(image_path).exists():
        photo = FSInputFile(image_path)
        return await target.answer_photo(photo, caption=caption,
                                         reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        return await target.answer(caption, reply_markup=reply_markup, parse_mode=parse_mode)


async def edit_or_send_menu(callback: CallbackQuery, section: str, caption: str,
                            reply_markup, parse_mode: str = "Markdown"):
    try:
        await callback.message.delete()
    except:
        pass

    image_path = get_image_path(section)

    if image_path and Path(image_path).exists():
        photo = FSInputFile(image_path)
        await callback.message.answer_photo(photo, caption=caption,
                                            reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await callback.message.answer(caption, reply_markup=reply_markup, parse_mode=parse_mode)


def format_stats_message(stats: dict, period_name: str = "Выбранный период") -> str:
    if stats['total_count'] == 0:
        return f"📊 *{period_name}*\n\n❌ Нет данных за этот период"

    msg = f"📊 *{period_name}*\n"
    msg += f"_(курс: 1$ = {stats['rate']:.2f}₽)_\n\n"
    msg += f"📦 *Сделок:* {stats['total_count']}\n\n"
    msg += f"💰 *В рублях:*\n"
    msg += f"├ Итого: *{format_number(stats['total_rub'])}* ₽\n"
    msg += f"└ Средний чек: {format_number(stats['avg_rub'])} ₽\n\n"
    msg += f"💵 *В долларах:*\n"
    msg += f"├ Итого: *{format_number(stats['total_usd'])}* $\n"
    msg += f"└ Средний чек: {format_number(stats['avg_usd'])} $"

    return msg


# ==================== КОМАНДЫ ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await send_menu_with_image(
        message, "main_menu",
        "👋 *Привет!*\n\nВыбери действие:",
        kb.main_menu_keyboard()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await send_menu_with_image(message, "main_menu", "📱 *Главное меню*", kb.main_menu_keyboard())


# ==================== ИСПРАВЛЕНИЕ 1: УБРАНО БЫСТРОЕ ДОБАВЛЕНИЕ ====================
# Закомментирован обработчик quick_add - теперь сделки добавляются только через кнопку

# @router.message(F.text.regexp(r'^[\d\s.,]+[₽$рРуУдД]?$|^[₽$]?[\d\s.,]+$'))
# async def quick_add(message: Message, state: FSMContext):
#     """Быстрое добавление: 1500 / 1500р / 100$"""
#     ... (убрано)


# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_send_menu(callback, "main_menu", "📱 *Главное меню*", kb.main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_send_menu(callback, "main_menu", "❌ Отменено\n\n📱 *Главное меню*", kb.main_menu_keyboard())
    await callback.answer()


# ==================== ДОБАВЛЕНИЕ СДЕЛКИ ====================

@router.callback_query(F.data == "add_transaction")
async def add_transaction_start(callback: CallbackQuery, state: FSMContext):
    default_currency = db.get_setting("default_currency", "RUB")
    symbol = CURRENCY_SYMBOLS[default_currency]

    await state.set_state(AddTransaction.waiting_for_amount)
    await edit_or_send_menu(
        callback, "add_deal",
        f"➕ *Добавление сделки*\n\n"
        f"Введи сумму:\n"
        f"• `1500` → {symbol} (по умолчанию)\n"
        f"• `1500р` → ₽\n"
        f"• `100$` → $",
        kb.cancel_keyboard()
    )
    await callback.answer()


@router.message(AddTransaction.waiting_for_amount)
async def add_amount(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    currency = None
    if any(c in text for c in ['₽', 'р', 'у']):
        currency = 'RUB'
    elif any(c in text for c in ['$', 'д']):
        currency = 'USD'

    amount_text = ''.join(c for c in text if c.isdigit() or c in '.,')

    try:
        amount = float(amount_text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма > 0", reply_markup=kb.cancel_keyboard())
            return

        if not currency:
            currency = db.get_setting("default_currency", "RUB")

        await state.update_data(amount=amount, currency=currency)
        await state.set_state(AddTransaction.waiting_for_comment)

        symbol = CURRENCY_SYMBOLS[currency]
        await message.answer(
            f"💰 *{format_number(amount)} {symbol}*\n\nКомментарий?",
            reply_markup=kb.skip_keyboard("comment"),
            parse_mode="Markdown"
        )
    except:
        await message.answer("❌ Неверный формат", reply_markup=kb.cancel_keyboard())


@router.callback_query(F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment=None)
    await state.set_state(AddTransaction.waiting_for_date)
    await callback.message.edit_text(
        "📅 Дата (ДД.ММ.ГГГГ) или пропустить для сегодня:",
        reply_markup=kb.skip_keyboard("date")
    )
    await callback.answer()


@router.message(AddTransaction.waiting_for_comment)
async def add_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(AddTransaction.waiting_for_date)
    await message.answer("📅 Дата (ДД.ММ.ГГГГ)?", reply_markup=kb.skip_keyboard("date"))


@router.callback_query(F.data == "skip_date")
async def skip_date(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rate = get_rate()

    t_id = db.add_transaction(data['amount'], data['currency'], data.get('comment'))
    symbol = CURRENCY_SYMBOLS[data['currency']]

    if data['currency'] == 'RUB':
        in_rub, in_usd = data['amount'], data['amount'] / rate
    else:
        in_usd, in_rub = data['amount'], data['amount'] * rate

    await state.clear()
    await edit_or_send_menu(
        callback, "main_menu",
        f"✅ *Сделка #{t_id}*\n\n"
        f"💰 {format_number(data['amount'])} {symbol}\n"
        f"💱 {format_number(in_rub)} ₽ / {format_number(in_usd)} $\n"
        f"📅 {date.today().strftime('%d.%m.%Y')}",
        kb.main_menu_keyboard()
    )
    await callback.answer()


@router.message(AddTransaction.waiting_for_date)
async def add_date(message: Message, state: FSMContext):
    try:
        t_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.skip_keyboard("date"))
        return

    data = await state.get_data()
    rate = get_rate()

    t_id = db.add_transaction(data['amount'], data['currency'], data.get('comment'), t_date)
    symbol = CURRENCY_SYMBOLS[data['currency']]

    if data['currency'] == 'RUB':
        in_rub, in_usd = data['amount'], data['amount'] / rate
    else:
        in_usd, in_rub = data['amount'], data['amount'] * rate

    await state.clear()
    await message.answer(
        f"✅ *Сделка #{t_id}*\n\n"
        f"💰 {format_number(data['amount'])} {symbol}\n"
        f"💱 {format_number(in_rub)} ₽ / {format_number(in_usd)} $\n"
        f"📅 {t_date.strftime('%d.%m.%Y')}",
        reply_markup=kb.main_menu_keyboard(),
        parse_mode="Markdown"
    )


# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "stats_menu")
async def stats_menu(callback: CallbackQuery):
    await edit_or_send_menu(callback, "stats", "📊 *Статистика*\n\nВыбери период:", kb.stats_period_keyboard())
    await callback.answer()


@router.callback_query(F.data.regexp(r"stats_(today|yesterday|week|month|year|all)$"))
async def show_stats(callback: CallbackQuery):
    period = callback.data.split("_")[1]

    period_names = {
        "today": "Сегодня", "yesterday": "Вчера", "week": "Неделя",
        "month": "Месяц", "year": "Год", "all": "Всё время"
    }

    start_date, end_date = get_period_dates(period)
    rate = get_rate()
    stats = db.get_combined_stats(start_date, end_date, rate)

    msg = format_stats_message(stats, period_names[period])

    await callback.message.edit_caption(caption=msg, reply_markup=kb.stats_period_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "stats_custom")
async def stats_custom(callback: CallbackQuery, state: FSMContext):
    await state.update_data(action="stats")
    await callback.message.edit_caption(
        caption="📅 *Выбери период:*",
        reply_markup=kb.date_preset_keyboard("period"),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== АНАЛИТИКА ====================

@router.callback_query(F.data == "analytics_menu")
async def analytics_menu(callback: CallbackQuery):
    await edit_or_send_menu(callback, "analytics", "📈 *Аналитика*", kb.analytics_keyboard())
    await callback.answer()


@router.callback_query(F.data == "analytics_full")
async def analytics_full(callback: CallbackQuery):
    rate = get_rate()

    all_stats = db.get_combined_stats(rate=rate)
    today_stats = db.get_combined_stats(*get_period_dates("today"), rate)
    week_stats = db.get_combined_stats(*get_period_dates("week"), rate)
    month_stats = db.get_combined_stats(*get_period_dates("month"), rate)

    msg = f"📈 *Полная аналитика*\n_(курс: 1$ = {rate:.2f}₽)_\n\n"

    msg += f"📊 *Всего:*\n"
    msg += f"├ {format_number(all_stats['total_rub'])} ₽\n"
    msg += f"├ {format_number(all_stats['total_usd'])} $\n"
    msg += f"└ {all_stats['total_count']} сделок\n\n"

    msg += f"📅 *Сегодня:* {format_number(today_stats['total_rub'])} ₽\n"
    msg += f"📆 *Неделя:* {format_number(week_stats['total_rub'])} ₽\n"
    msg += f"📆 *Месяц:* {format_number(month_stats['total_rub'])} ₽"

    await callback.message.edit_caption(caption=msg, reply_markup=kb.analytics_keyboard(), parse_mode="Markdown")
    await callback.answer()


# ==================== ИСПРАВЛЕНИЕ 3: ДОБАВЛЕН ОБРАБОТЧИК СРАВНЕНИЯ ПЕРИОДОВ ====================

@router.callback_query(F.data == "analytics_compare")
async def analytics_compare(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ComparePeriods.waiting_for_period1_start)
    await callback.message.edit_caption(
        caption="🔄 *Сравнение периодов*\n\n"
                "Введи дату *начала первого* периода (ДД.ММ.ГГГГ):",
        reply_markup=kb.cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ComparePeriods.waiting_for_period1_start)
async def compare_period1_start(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(period1_start=d)
        await state.set_state(ComparePeriods.waiting_for_period1_end)
        await message.answer(
            f"✅ Начало: {d.strftime('%d.%m.%Y')}\n\n"
            "Введи дату *конца первого* периода:",
            reply_markup=kb.cancel_keyboard(),
            parse_mode="Markdown"
        )
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


@router.message(ComparePeriods.waiting_for_period1_end)
async def compare_period1_end(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(period1_end=d)
        await state.set_state(ComparePeriods.waiting_for_period2_start)
        await message.answer(
            f"✅ Первый период сохранён\n\n"
            "Введи дату *начала второго* периода:",
            reply_markup=kb.cancel_keyboard(),
            parse_mode="Markdown"
        )
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


@router.message(ComparePeriods.waiting_for_period2_start)
async def compare_period2_start(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(period2_start=d)
        await state.set_state(ComparePeriods.waiting_for_period2_end)
        await message.answer(
            f"✅ Начало: {d.strftime('%d.%m.%Y')}\n\n"
            "Введи дату *конца второго* периода:",
            reply_markup=kb.cancel_keyboard(),
            parse_mode="Markdown"
        )
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


@router.message(ComparePeriods.waiting_for_period2_end)
async def compare_period2_end(message: Message, state: FSMContext):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        data = await state.get_data()
        await state.clear()

        rate = get_rate()

        stats1 = db.get_combined_stats(data['period1_start'], data['period1_end'], rate)
        stats2 = db.get_combined_stats(data['period2_start'], d, rate)

        # Расчёт изменений
        if stats2['total_rub'] > 0:
            change_rub = ((stats1['total_rub'] - stats2['total_rub']) / stats2['total_rub']) * 100
        else:
            change_rub = 100 if stats1['total_rub'] > 0 else 0

        if stats2['total_count'] > 0:
            change_count = ((stats1['total_count'] - stats2['total_count']) / stats2['total_count']) * 100
        else:
            change_count = 100 if stats1['total_count'] > 0 else 0

        change_rub_sign = "📈" if change_rub >= 0 else "📉"
        change_count_sign = "📈" if change_count >= 0 else "📉"

        p1_str = f"{data['period1_start'].strftime('%d.%m')} - {data['period1_end'].strftime('%d.%m.%Y')}"
        p2_str = f"{data['period2_start'].strftime('%d.%m')} - {d.strftime('%d.%m.%Y')}"

        msg = f"🔄 *Сравнение периодов*\n\n"
        msg += f"📅 *Период 1:* {p1_str}\n"
        msg += f"├ {format_number(stats1['total_rub'])} ₽\n"
        msg += f"└ {stats1['total_count']} сделок\n\n"
        msg += f"📅 *Период 2:* {p2_str}\n"
        msg += f"├ {format_number(stats2['total_rub'])} ₽\n"
        msg += f"└ {stats2['total_count']} сделок\n\n"
        msg += f"*Изменение:*\n"
        msg += f"{change_rub_sign} Выручка: {change_rub:+.1f}%\n"
        msg += f"{change_count_sign} Сделки: {change_count:+.1f}%"

        await message.answer(msg, reply_markup=kb.analytics_keyboard(), parse_mode="Markdown")
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


@router.callback_query(F.data == "analytics_dynamics")
async def analytics_dynamics(callback: CallbackQuery):
    rate = get_rate()
    monthly = db.get_combined_monthly_stats(rate)

    if len(monthly) < 1:
        await callback.answer("Недостаточно данных", show_alert=True)
        return

    msg = f"📈 *Динамика по месяцам*\n\n"

    for i, m in enumerate(monthly[-6:]):
        month_name = datetime.strptime(m['month'], '%Y-%m').strftime('%b %Y')
        msg += f"📅 *{month_name}:*\n"
        msg += f"├ {format_number(m['total_rub'])} ₽\n"
        msg += f"└ {format_number(m['total_usd'])} $\n\n"

    await callback.message.edit_caption(caption=msg, reply_markup=kb.analytics_keyboard(), parse_mode="Markdown")
    await callback.answer()


# ==================== ГРАФИКИ ====================

@router.callback_query(F.data == "charts_menu")
async def charts_menu(callback: CallbackQuery):
    await edit_or_send_menu(callback, "charts", "📉 *Графики*", kb.charts_keyboard())
    await callback.answer()


@router.callback_query(F.data.regexp(r"chart_(daily_week|daily_month|monthly)$"))
async def show_chart(callback: CallbackQuery):
    chart_type = callback.data.replace("chart_", "")
    rate = get_rate()
    today = date.today()

    await callback.answer("⏳ Генерирую...")

    if chart_type == "daily_week":
        start, end = today - timedelta(days=7), today
        c_type = "daily"
    elif chart_type == "daily_month":
        start, end = today - timedelta(days=30), today
        c_type = "daily"
    else:
        start, end = None, None
        c_type = "monthly"

    chart_buf = reports.generate_chart(start, end, c_type, rate)

    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer_photo(
        BufferedInputFile(chart_buf.read(), "chart.png"),
        caption="📉 *График доходов*",
        reply_markup=kb.charts_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "chart_custom")
async def chart_custom(callback: CallbackQuery, state: FSMContext):
    await state.update_data(action="chart")
    await callback.message.edit_caption(
        caption="📅 *Период для графика:*",
        reply_markup=kb.date_preset_keyboard("chartperiod"),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ЭКСПОРТ ====================

@router.callback_query(F.data == "export_menu")
async def export_menu(callback: CallbackQuery):
    await edit_or_send_menu(callback, "export", "📁 *Экспорт*\n\nВыбери формат:", kb.export_keyboard())
    await callback.answer()


@router.callback_query(F.data.regexp(r"export_(excel|pdf|both)$"))
async def export_format(callback: CallbackQuery):
    fmt = callback.data.replace("export_", "")
    await callback.message.edit_caption(
        caption="📅 *Период для экспорта:*",
        reply_markup=kb.export_period_keyboard(fmt),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"export_(excel|pdf|both)_(month|year|all)$"))
async def do_export(callback: CallbackQuery):
    parts = callback.data.split("_")
    fmt, period = parts[1], parts[2]

    await callback.answer("⏳ Генерирую...")

    start_date, end_date = get_period_dates(period)
    rate = get_rate()

    files = []
    try:
        if fmt in ("excel", "both"):
            buf = reports.generate_excel_report(start_date, end_date, rate)
            files.append(BufferedInputFile(buf.read(), f"report.xlsx"))
        if fmt in ("pdf", "both"):
            buf = reports.generate_pdf_report(start_date, end_date, rate)
            files.append(BufferedInputFile(buf.read(), f"report.pdf"))

        for f in files:
            await callback.message.answer_document(f)

        await callback.message.answer("✅ Готово!", reply_markup=kb.main_menu_keyboard())
    except Exception as e:
        logger.error(f"Export error: {e}")
        await callback.message.answer(f"❌ Ошибка экспорта: {e}", reply_markup=kb.main_menu_keyboard())


# ==================== КОНВЕРТЕР ====================

@router.callback_query(F.data == "converter_menu")
async def converter_menu(callback: CallbackQuery):
    rate = get_rate()

    msg = f"💱 *Конвертер*\n\n"
    msg += f"Курс: *1$ = {rate:.2f}₽*\n\n"
    msg += f"Примеры:\n"
    msg += f"• 1 000 ₽ = {1000 / rate:.2f} $\n"
    msg += f"• 100 $ = {100 * rate:,.0f} ₽\n"
    msg += f"• 10 000 ₽ = {10000 / rate:.2f} $\n"
    msg += f"• 1 000 $ = {1000 * rate:,.0f} ₽"

    await edit_or_send_menu(callback, "converter", msg, kb.converter_keyboard())
    await callback.answer()


# ==================== НАСТРОЙКИ ====================

@router.callback_query(F.data == "settings_menu")
async def settings_menu(callback: CallbackQuery):
    daily = db.get_setting("daily_reminder", "false") == "true"
    weekly = db.get_setting("weekly_reminder", "false") == "true"
    curr = db.get_setting("default_currency", "RUB")
    rate = get_rate()

    curr_name = "₽" if curr == "RUB" else "$"

    msg = f"⚙️ *Настройки*\n\n"
    msg += f"💵 Валюта: *{curr_name}*\n"
    msg += f"💱 Курс: *1$ = {rate:.2f}₽*\n\n"
    msg += f"📅 Ежедневный: {'✅' if daily else '❌'}\n"
    msg += f"📆 Еженедельный: {'✅' if weekly else '❌'}"

    await edit_or_send_menu(callback, "settings", msg, kb.settings_menu_keyboard(daily, weekly, curr))
    await callback.answer()


@router.callback_query(F.data == "settings_default_currency")
async def settings_currency(callback: CallbackQuery):
    curr = db.get_setting("default_currency", "RUB")
    await callback.message.edit_caption(
        caption="💵 *Валюта по умолчанию*\n\nДля быстрого ввода без указания валюты:",
        reply_markup=kb.currency_select_keyboard(curr),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_currency_"))
async def set_currency(callback: CallbackQuery):
    currency = callback.data.split("_")[-1]
    db.set_setting("default_currency", currency)
    await callback.answer(f"Валюта: {'₽' if currency == 'RUB' else '$'}", show_alert=True)
    await settings_menu(callback)


@router.callback_query(F.data == "settings_exchange_rate")
async def settings_rate(callback: CallbackQuery, state: FSMContext):
    rate = get_rate()
    await state.set_state(SettingsState.waiting_for_exchange_rate)
    await callback.message.edit_caption(
        caption=f"💱 *Курс USD/RUB*\n\nТекущий: 1$ = {rate:.2f}₽\n\nВведи новый:",
        reply_markup=kb.cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(SettingsState.waiting_for_exchange_rate)
async def set_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(",", "."))
        if rate <= 0:
            raise ValueError()
        db.set_setting("usd_rub_rate", str(rate))
        await state.clear()
        await message.answer(f"✅ Курс: 1$ = {rate:.2f}₽", reply_markup=kb.main_menu_keyboard())
    except:
        await message.answer("❌ Введи число > 0", reply_markup=kb.cancel_keyboard())


@router.callback_query(F.data == "settings_daily_toggle")
async def toggle_daily(callback: CallbackQuery):
    curr = db.get_setting("daily_reminder", "false")
    new = "false" if curr == "true" else "true"
    db.set_setting("daily_reminder", new)
    await callback.answer(f"{'Включено' if new == 'true' else 'Выключено'}")
    await settings_menu(callback)


@router.callback_query(F.data == "settings_weekly_toggle")
async def toggle_weekly(callback: CallbackQuery):
    curr = db.get_setting("weekly_reminder", "false")
    new = "false" if curr == "true" else "true"
    db.set_setting("weekly_reminder", new)
    await callback.answer(f"{'Включено' if new == 'true' else 'Выключено'}")
    await settings_menu(callback)


@router.callback_query(F.data == "delete_last")
async def delete_last(callback: CallbackQuery):
    last = db.get_last_transaction()
    if not last:
        await callback.answer("Нет сделок", show_alert=True)
        return

    symbol = CURRENCY_SYMBOLS.get(last['currency'], '?')
    await callback.message.edit_caption(
        caption=f"🗑 *Удалить?*\n\n{format_number(last['amount'])} {symbol}\n{last['transaction_date']}",
        reply_markup=kb.confirm_keyboard("delete_last"),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_delete_last")
async def confirm_delete(callback: CallbackQuery):
    last = db.get_last_transaction()
    if last:
        db.delete_transaction(last['id'])
    await callback.answer("Удалено")
    await settings_menu(callback)


# ==================== ПРЕСЕТЫ ДАТ ====================

@router.callback_query(
    F.data.regexp(r"(period|chartperiod)_(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|q1|q2|q3|q4)$"))
async def handle_period_preset(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    action, period = parts[0], parts[1]

    start_date, end_date = get_period_dates(period)
    rate = get_rate()

    if action == "period":
        stats = db.get_combined_stats(start_date, end_date, rate)
        msg = format_stats_message(stats, f"{start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}")
        await callback.message.edit_caption(caption=msg, reply_markup=kb.date_preset_keyboard("period"),
                                            parse_mode="Markdown")
    else:
        await callback.answer("⏳ Генерирую...")
        chart_buf = reports.generate_chart(start_date, end_date, 'daily', rate)
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer_photo(
            BufferedInputFile(chart_buf.read(), "chart.png"),
            caption="📉 *График*",
            reply_markup=kb.charts_keyboard(),
            parse_mode="Markdown"
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"(period|chartperiod)_manual$"))
async def manual_period(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[0]
    await state.update_data(action=action)
    await state.set_state(CustomPeriod.waiting_for_start_date)
    await callback.message.edit_caption(
        caption="📅 Введи дату *начала* (ДД.ММ.ГГГГ):",
        reply_markup=kb.cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(CustomPeriod.waiting_for_start_date)
async def manual_start(message: Message, state: FSMContext):
    try:
        start = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(start_date=start)
        await state.set_state(CustomPeriod.waiting_for_end_date)
        await message.answer(f"✅ Начало: {start.strftime('%d.%m.%Y')}\n\nДата *конца*:",
                             reply_markup=kb.cancel_keyboard(), parse_mode="Markdown")
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


@router.message(CustomPeriod.waiting_for_end_date)
async def manual_end(message: Message, state: FSMContext):
    try:
        end = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        data = await state.get_data()
        start = data['start_date']
        action = data.get('action', 'period')
        rate = get_rate()

        await state.clear()

        if action == "period":
            stats = db.get_combined_stats(start, end, rate)
            msg = format_stats_message(stats, f"{start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}")
            await message.answer(msg, reply_markup=kb.main_menu_keyboard(), parse_mode="Markdown")
        else:
            chart_buf = reports.generate_chart(start, end, 'daily', rate)
            await message.answer_photo(
                BufferedInputFile(chart_buf.read(), "chart.png"),
                caption="📉 *График*",
                reply_markup=kb.main_menu_keyboard(),
                parse_mode="Markdown"
            )
    except:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=kb.cancel_keyboard())


# ==================== ЗАПУСК ====================

async def main():
    db.init_db()
    scheduler.start()
    logger.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())