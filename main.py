import logging
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from sheets import SheetsClient, SheetsError

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
EDITOR_CHAT_ID: int = int(os.environ["EDITOR_CHAT_ID"])
OWNER_CHAT_ID: int = int(os.environ["OWNER_CHAT_ID"])
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

sheets_client = SheetsClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_message(tasks: list) -> tuple[str, InlineKeyboardMarkup | None]:
    """Build message text + inline keyboard from a list of tasks."""
    tz = pytz.timezone(TIMEZONE)
    today_str = datetime.now(tz).strftime("%d.%m.%Y")

    text = f"🎬 *Задания на {today_str}*\n\n"
    keyboard: list[list[InlineKeyboardButton]] = []

    for i, (row_idx, task) in enumerate(tasks[:2], start=1):
        collection  = task["collection"]  or "—"
        description = task["description"] or "—"
        platform    = task["platform"]    or "—"
        status      = task["status"]      or "—"

        text += (
            f"*Видео {i}*\n"
            f"📦 Коллекция: {collection}\n"
            f"📝 {description}\n"
            f"📱 Платформа: {platform}\n"
            f"🔄 Статус: {status}\n\n"
        )

        if status not in ("Готово", "Выложено"):
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Готово видео {i}",
                    callback_data=f"done|{row_idx}|{i}",
                )
            ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    return text.strip(), reply_markup


# ---------------------------------------------------------------------------
# Core send function (used by scheduler AND /today)
# ---------------------------------------------------------------------------

async def send_daily_tasks(bot, chat_id: int) -> None:
    try:
        tasks = sheets_client.get_tasks_for_today()
    except SheetsError as e:
        logger.error("Sheets error: %s", e)
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Не удалось загрузить задания из Google Sheets. Попробуйте позже.",
        )
        return

    if not tasks:
        tz = pytz.timezone(TIMEZONE)
        today_str = datetime.now(tz).strftime("%d.%m.%Y")
        await bot.send_message(
            chat_id=chat_id,
            text=f"📅 На {today_str} задач нет. Хорошего дня!",
        )
        return

    text, reply_markup = _build_message(tasks)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Привет\\!* Я помогаю отслеживать монтаж видео для бренда\\.\n\n"
        "📋 *Как работать:*\n"
        "• Каждое утро в *9:00* я пришлю задания на день\n"
        "• Смонтировал видео — нажми «Готово», владелец получит уведомление\n\n"
        "⌨️ *Команды:*\n"
        "/today — задания на сегодня\n"
        "/status — статистика за текущий месяц"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_daily_tasks(context.bot, update.effective_chat.id)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        stats = sheets_client.get_month_status()
    except SheetsError as e:
        logger.error("Sheets error: %s", e)
        await update.message.reply_text(
            "⚠️ Не удалось загрузить статистику из Google Sheets."
        )
        return

    tz = pytz.timezone(TIMEZONE)
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }
    now = datetime.now(tz)
    month_str = f"{month_names[now.month]} {now.year}"

    text = (
        f"📊 *Статистика за {month_str}*\n\n"
        f"🔄 В монтаже: {stats['in_progress']}\n"
        f"✅ Готово: {stats['done']}\n"
        f"📤 Выложено: {stats['published']}\n"
        f"─────────────\n"
        f"📌 Всего: {stats['total']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Callback handler (inline button press)
# ---------------------------------------------------------------------------

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    if len(parts) != 3:
        return

    _, row_idx_str, video_num = parts
    try:
        row_idx = int(row_idx_str)
    except ValueError:
        return

    try:
        task = sheets_client.mark_as_done(row_idx)
    except SheetsError as e:
        logger.error("Failed to update status: %s", e)
        await query.answer(
            "⚠️ Ошибка обновления статуса. Попробуйте ещё раз.",
            show_alert=True,
        )
        return

    # Remove the pressed button from the keyboard
    if query.message.reply_markup:
        new_rows = [
            row
            for row in query.message.reply_markup.inline_keyboard
            if not any(btn.callback_data == query.data for btn in row)
        ]
        new_markup = InlineKeyboardMarkup(new_rows) if new_rows else None
        try:
            await query.edit_message_reply_markup(reply_markup=new_markup)
        except Exception:
            pass  # Message too old to edit — not critical

    await query.message.reply_text(
        f"✅ Видео {video_num} отмечено как *Готово*!",
        parse_mode="Markdown",
    )

    # Notify the owner
    tz = pytz.timezone(TIMEZONE)
    today_str = datetime.now(tz).strftime("%d.%m.%Y")

    owner_text = (
        f"✅ *Видео готово к выкладке!*\n\n"
        f"📅 Дата: {task['date'] or today_str}\n"
        f"🎬 Видео {video_num} из дневного задания\n"
        f"📦 Коллекция: {task['collection'] or '—'}\n"
        f"📝 {task['description'] or '—'}\n"
        f"📱 Платформа: {task['platform'] or '—'}"
    )
    await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=owner_text,
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Scheduler lifecycle hooks
# ---------------------------------------------------------------------------

async def _post_init(application: Application) -> None:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_daily_tasks,
        trigger="cron",
        hour=9,
        minute=0,
        args=[application.bot, EDITOR_CHAT_ID],
        id="daily_tasks",
        replace_existing=True,
    )
    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started — daily tasks at 09:00 %s", TIMEZONE)


async def _post_shutdown(application: Application) -> None:
    scheduler: AsyncIOScheduler | None = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Python 3.14 no longer implicitly creates an event loop
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("today",  today_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback, pattern=r"^done\|"))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
