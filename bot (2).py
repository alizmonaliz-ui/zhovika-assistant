#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZHOVIKA Telegram Bot
====================
Personal assistant bot for Telegram.
Commands:
    /start — شروع
    /tasks — مدیریت وظایف
    /notes — یادداشت‌ها
    /remind — یادآوری
    /budget — بودجه
    /exercise — ورزش
    /study — مطالعه
    /chat — چت با AI
    /help — راهنما
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set!")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ── User Data (use DB in production) ──
user_data = {}

# ── Keyboards ──
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ وظایف", callback_data="menu:tasks")
    builder.button(text="📝 یادداشت", callback_data="menu:notes")
    builder.button(text="⏰ یادآوری", callback_data="menu:reminders")
    builder.button(text="💰 بودجه", callback_data="menu:budget")
    builder.button(text="💪 ورزش", callback_data="menu:exercise")
    builder.button(text="📚 مطالعه", callback_data="menu:study")
    builder.button(text="🤖 چت با AI", callback_data="menu:chat")
    builder.button(text="📱 اپلیکیشن", url="https://your-domain.com")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

# ── Handlers ──
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = str(message.from_user.id)
    user_data[user_id] = user_data.get(user_id, {"tasks": [], "notes": [], "reminders": []})

    await message.answer(
        f"🖤 <b>سلام {message.from_user.first_name}!</b>\n\n"
        "به ربات ZHOVIKA خوش اومدی.\n"
        "من دستیار شخصی همه‌کاره‌ات هستم!\n\n"
        "✅ وظایف رو مدیریت کن\n"
        "📝 یادداشت بردار\n"
        "⏰ یادآوری تنظیم کن\n"
        "💰 هزینه‌ها رو پیگیری کن\n"
        "💪 ورزش رو Track کن\n"
        "📚 درس بخون\n"
        "🤖 با AI چت کن\n\n"
        "از منوی زیر شروع کن:",
        reply_markup=main_menu()
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>راهنمای ZHOVIKA Bot</b>\n\n"
        "<b>دستورات:</b>\n"
        "/start — شروع\n"
        "/tasks — لیست وظایف\n"
        "/addtask [متن] — افزودن وظیفه\n"
        "/notes — یادداشت‌ها\n"
        "/remind [ساعت] [متن] — یادآوری\n"
        "/budget — خلاصه بودجه\n"
        "/exercise — ورزش امروز\n"
        "/study — مطالعه\n"
        "/chat [متن] — چت با AI\n"
        "/help — این راهنما\n\n"
        "یا از منوی شیشه‌ای استفاده کن 👇",
        reply_markup=main_menu()
    )

@dp.message(Command("tasks"))
async def cmd_tasks(message: Message):
    user_id = str(message.from_user.id)
    tasks = user_data.get(user_id, {}).get("tasks", [])
    pending = [t for t in tasks if not t.get("done")]

    if not pending:
        await message.answer("🎉 همه وظایف انجام شده!", reply_markup=main_menu())
        return

    text = "✅ <b>وظایف شما:</b>\n\n"
    for i, task in enumerate(pending, 1):
        text += f"{i}. {task['text']}\n"

    builder = InlineKeyboardBuilder()
    for i, task in enumerate(pending):
        builder.button(text=f"✓ {i+1}", callback_data=f"task:done:{i}")
    builder.button(text="➕ وظیفه جدید", callback_data="task:add")
    builder.adjust(5, 1)

    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(Command("addtask"))
async def cmd_addtask(message: Message):
    text = message.text.replace("/addtask", "").strip()
    if not text:
        await message.answer("❌ لطفاً بعد از /addtask متن وظیفه را بنویسید\nمثال: /addtask کتاب خواندن")
        return

    user_id = str(message.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {"tasks": [], "notes": [], "reminders": []}

    user_data[user_id]["tasks"].append({"text": text, "done": False, "created": datetime.now().isoformat()})
    await message.answer(f"✅ وظیفه اضافه شد:\n<code>{text}</code>", reply_markup=main_menu())

@dp.message(Command("chat"))
async def cmd_chat(message: Message):
    text = message.text.replace("/chat", "").strip()
    if not text:
        await message.answer("🤖 لطفاً بعد از /chat سوال خود را بنویسید")
        return

    # Simple AI response
    responses = {
        "سلام": "سلام! چطور می‌تونم کمکتون کنم؟",
        "خوبی": "ممنون! شما چطورید؟",
        "وظیفه": "می‌تونید با /tasks وظایف رو ببینید یا با /addtask اضافه کنید.",
        "ورزش": "برنامه امروز: ۳۰ دقیقه پیاده‌روی + ۲۰ اسکوات + ۱۵ شنا 💪",
    }

    response = "متوجه شدم! برای جزئیات بیشتر از منوی اصلی استفاده کنید."
    for key, resp in responses.items():
        if key in text:
            response = resp
            break

    # Try backend AI
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/api/chat",
                json={"text": text, "user_id": str(message.from_user.id)},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", response)
    except:
        pass

    await message.answer(f"🤖 <b>AI:</b>\n{response}", reply_markup=main_menu())

@dp.message(Command("remind"))
async def cmd_remind(message: Message):
    parts = message.text.replace("/remind", "").strip().split(" ", 1)
    if len(parts) < 2:
        await message.answer("⏰ فرمت: /remind [ساعت] [متن]\nمثال: /remind 08:00 بیدار شو!")
        return

    time_str, remind_text = parts[0], parts[1]
    user_id = str(message.from_user.id)

    if user_id not in user_data:
        user_data[user_id] = {"tasks": [], "notes": [], "reminders": []}

    user_data[user_id]["reminders"].append({
        "time": time_str,
        "text": remind_text,
        "active": True
    })

    await message.answer(
        f"⏰ <b>یادآوری تنظیم شد:</b>\n"
        f"زمان: {time_str}\n"
        f"متن: {remind_text}",
        reply_markup=main_menu()
    )

@dp.message(Command("budget"))
async def cmd_budget(message: Message):
    await message.answer(
        "💰 <b>بودجه شما</b>\n\n"
        "برای ثبت هزینه از فرمت زیر استفاده کنید:\n"
        "/expense [مبلغ] [دسته] [عنوان]\n"
        "مثال: /expense 50000 غذا ناهار\n\n"
        "دسته‌ها: غذا، حمل‌ونقل، خرید، قبوض، سایر",
        reply_markup=main_menu()
    )

@dp.message(Command("expense"))
async def cmd_expense(message: Message):
    parts = message.text.replace("/expense", "").strip().split(" ", 2)
    if len(parts) < 2:
        await message.answer("❌ فرمت: /expense [مبلغ] [دسته] [عنوان]")
        return

    amount = parts[0]
    category = parts[1] if len(parts) > 1 else "سایر"
    title = parts[2] if len(parts) > 2 else "بدون عنوان"

    await message.answer(
        f"💰 <b>هزینه ثبت شد:</b>\n"
        f"مبلغ: {amount} تومان\n"
        f"دسته: {category}\n"
        f"عنوان: {title}",
        reply_markup=main_menu()
    )

@dp.message(Command("exercise"))
async def cmd_exercise(message: Message):
    await message.answer(
        "💪 <b>برنامه ورزشی امروز:</b>\n\n"
        "1️⃣ پیاده‌روی سریع — ۳۰ دقیقه\n"
        "2️⃣ اسکوات — ۳ ست × ۱۵\n"
        "3️⃣ شنا — ۳ ست × ۱۰\n"
        "4️⃣ پلانک — ۳ ست × ۳۰ ثانیه\n"
        "5️⃣ کشش — ۱۰ دقیقه\n\n"
        "برای ثبت تمرین: /addex [نام] [دقیقه] [کالری]",
        reply_markup=main_menu()
    )

@dp.message(Command("study"))
async def cmd_study(message: Message):
    await message.answer(
        "📚 <b>تکنیک پومودورو:</b>\n\n"
        "🍅 ۲۵ دقیقه تمرکز\n"
        "☕ ۵ دقیقه استراحت\n"
        "🔄 بعد از ۴ پومودورو: ۱۵ دقیقه استراحت\n\n"
        "برای شروع تایمر از اپلیکیشن استفاده کنید!",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data.startswith("menu:"))
async def on_menu(callback: CallbackQuery):
    menu = callback.data.split(":")[1]
    commands = {
        "tasks": "/tasks", "notes": "/notes", "reminders": "/remind",
        "budget": "/budget", "exercise": "/exercise", "study": "/study",
        "chat": "/chat سلام"
    }
    await callback.answer()
    if menu in commands:
        # Simulate command
        msg = types.Message(
            message_id=callback.message.message_id,
            date=datetime.now(),
            chat=callback.message.chat,
            text=commands[menu]
        )
        msg._bot = bot
        # Route to appropriate handler
        if menu == "tasks":
            await cmd_tasks(msg)
        elif menu == "budget":
            await cmd_budget(msg)
        elif menu == "exercise":
            await cmd_exercise(msg)
        elif menu == "study":
            await cmd_study(msg)
        elif menu == "chat":
            await cmd_chat(msg)

@dp.message()
async def handle_text(message: Message):
    """Handle any other messages."""
    await message.answer(
        "🤔 دستور نامشخص!\n"
        "از /help برای راهنما استفاده کنید یا منوی زیر:",
        reply_markup=main_menu()
    )

# ── Main ──
async def main():
    print("🤖 ZHOVIKA Telegram Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
