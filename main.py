#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZHOVIKA Personal Assistant — Backend API v2.0
==============================================
FastAPI backend with powerful AI, smart planning, and language learning.
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ── Models ──
class ChatMessage(BaseModel):
    text: str
    user_id: str
    context: Optional[List[Dict]] = None
    intent: Optional[str] = None

class PlanRequest(BaseModel):
    user_id: str
    category: str  # workout, study, language, tasks
    details: Dict[str, Any]
    confirm: bool = False

class WorkoutPlan(BaseModel):
    user_id: str
    weight: float
    height: float
    age: int
    gender: str
    equipment: List[str]
    goal: str
    level: str

class StudyPlan(BaseModel):
    user_id: str
    subject: str
    hours_per_day: int
    duration_days: int
    goal: str

class LanguageRequest(BaseModel):
    user_id: str
    language: str
    level: str
    action: str  # lesson, conversation, translate, grammar
    message: Optional[str] = None

class SyncData(BaseModel):
    user_id: str
    tasks: List[Dict] = []
    notes: List[Dict] = []
    reminders: List[Dict] = []
    expenses: List[Dict] = []
    exercises: List[Dict] = []
    study: List[Dict] = []
    language: List[Dict] = []

class IGPost(BaseModel):
    caption: str
    image_url: Optional[str] = None
    hashtags: Optional[str] = None
    schedule_time: Optional[str] = None

class TGMessage(BaseModel):
    text: str
    channel_id: str
    pin: bool = False
    silent: bool = False
    schedule_time: Optional[str] = None

class ReminderCreate(BaseModel):
    user_id: str
    text: str
    time: str
    repeat: str = "once"

# ── FastAPI App ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 ZHOVIKA Backend v2.0 started")
    yield
    print("👋 ZHOVIKA Backend stopped")

app = FastAPI(
    title="ZHOVIKA Personal Assistant API v2",
    description="Powerful backend for ZHOVIKA with AI planning & language learning",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory storage ──
users_data = {}
scheduled_posts = []
conversations = {}

# ── AI Configuration ──
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

SYSTEM_PROMPT = """شما ZHOVIKA هستید، یک دستیار شخصی فارسی‌زبان بسیار توانمند.
همیشه به فارسی پاسخ بده مگر کاربر زبان دیگه‌ای بخواد. صمیمی، مختصر و کاربردی باش.

توانایی‌های تو:
- مدیریت وظایف و برنامه‌ریزی روزانه
- طراحی برنامه ورزشی شخصی‌سازی‌شده بر اساس قد، وزن، هدف و امکانات کاربر
- طراحی برنامه مطالعاتی روزبه‌روز با تکنیک پومودورو
- آموزش زبان (واژگان، گرامر، تمرین) در سطوح A1 تا C2، با تعیین سطح واقعی قبل از شروع
- مکالمه آزاد و مشاوره عمومی

قوانین مهم:
1. اگر کاربر اطلاعات کافی برای ساخت یک برنامه (ورزشی/مطالعاتی/وظیفه) نداده، اول سوال بپرس. هیچ‌وقت بدون اطلاعات کافی ابزار را صدا نزن.
2. وقتی اطلاعات کافی داری، از ابزار مناسب (create_task / create_workout_plan / create_study_plan) استفاده کن تا یک پیشنهاد ساختاریافته بسازی. این پیشنهاد قبل از اضافه‌شدن به برنامه، به کاربر برای تایید نشان داده می‌شود — پس لازم نیست بگویی "به بخش X اضافه شد"، چون هنوز تایید نگرفته‌ای.
3. در متن پاسخ عادی خودت، خلاصه‌ای دوستانه از چیزی که پیشنهاد می‌کنی بنویس؛ جزئیات کامل را در ابزار قرار بده.
4. در هر پیام فقط از ابزارهایی استفاده کن که واقعاً به درخواست فعلی مربوط است.

پروتکل آموزش زبان (خیلی مهم):
5. اگر کاربر می‌خواهد یک زبان جدید یاد بگیرد و سطح فعلی‌اش (A1 تا C2) را صریحاً نگفته، هرگز مستقیم درس نساز.
   اول از ابزار start_placement_test استفاده کن و ۶ تا ۸ سوال چهارگزینه‌ای با سختی فزاینده
   (از خیلی ساده A1 تا نسبتاً سخت B2/C1) در همان زبان بساز تا سطح واقعی‌اش مشخص شود.
6. بعد از اینکه نتیجه‌ی آزمون به‌صورت خلاصه (تعداد سوال درست از کل) در پیام بعدی کاربر آمد،
   بر اساس درصد پاسخ درست سطح را تخمین بزن (مثلاً: زیر ۳۰٪ → A1، ۳۰-۵۰٪ → A2، ۵۰-۷۰٪ → B1،
   ۷۰-۸۵٪ → B2، بالای ۸۵٪ → C1) و همان لحظه با ابزار create_language_lesson اولین درس را
   دقیقاً متناسب با همان سطح بساز — بدون اینکه دوباره از کاربر سطحش را بپرسی.
7. اگر کاربر خودش صریحاً سطحش را گفت (مثلاً "B1 هستم" یا "متوسط دارم")، نیازی به آزمون نیست؛
   مستقیم برو سراغ create_language_lesson با همان سطح.
"""

TOOLS = [
    {
        "name": "create_task",
        "description": "یک وظیفه ساده به لیست کارهای کاربر اضافه کن (وقتی کاربر یک کار مشخص و ساده می‌خواهد، نه یک برنامه چندروزه).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "متن وظیفه، با یک ایموجی مناسب در ابتدا"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "when": {"type": "string", "enum": ["today", "tomorrow"], "description": "پیش‌فرض today"}
            },
            "required": ["text", "priority"]
        }
    },
    {
        "name": "create_workout_plan",
        "description": "یک برنامه ورزشی شخصی‌سازی‌شده بساز. فقط وقتی صدا بزن که حداقل سطح و هدف کاربر (یا وزن/قد/وسایل در دسترس) مشخص باشد.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
                "goal": {"type": "string", "description": "مثلا کاهش وزن، عضله‌سازی، تناسب اندام"},
                "bmi_note": {"type": "string", "description": "در صورت وجود قد و وزن، یادداشت کوتاه درباره BMI"},
                "exercises": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "duration": {"type": "integer", "description": "دقیقه"},
                            "calories": {"type": "integer"},
                            "sets": {"type": "string", "description": "مثلا '3×12' یا خالی برای تمرین‌های زمان‌محور"}
                        },
                        "required": ["name", "duration"]
                    }
                }
            },
            "required": ["level", "goal", "exercises"]
        }
    },
    {
        "name": "create_study_plan",
        "description": "یک برنامه مطالعاتی چندروزه با تقسیم موضوعات و پومودورو بساز. فقط وقتی صدا بزن که درس/موضوع و مدت‌زمان مشخص باشد.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "hours_per_day": {"type": "number"},
                "days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "integer"},
                            "topic": {"type": "string"},
                            "pomodoros": {"type": "integer"}
                        },
                        "required": ["day", "topic"]
                    }
                }
            },
            "required": ["subject", "hours_per_day", "days"]
        }
    },
    {
        "name": "start_placement_test",
        "description": "یک آزمون کوتاه تعیین سطح (۶ تا ۸ سوال چهارگزینه‌ای با سختی فزاینده) برای یک زبان بساز، وقتی کاربر سطح خودش را نگفته است.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "answer": {"type": "string"},
                            "difficulty": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1"]}
                        },
                        "required": ["q", "options", "answer", "difficulty"]
                    }
                }
            },
            "required": ["language", "questions"]
        }
    },
    {
        "name": "create_language_lesson",
        "description": "یک درس زبان کامل (واژگان + گرامر + تمرین) بساز. فقط وقتی صدا بزن که زبان و سطح مشخص باشد.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "level": {"type": "string", "description": "A1 تا C2"},
                "title": {"type": "string"},
                "vocabulary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "word": {"type": "string"},
                            "meaning": {"type": "string"},
                            "example": {"type": "string"}
                        },
                        "required": ["word", "meaning"]
                    }
                },
                "grammar": {"type": "string"},
                "exercise": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "answer": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["language", "level", "vocabulary"]
        }
    }
]

async def call_claude(messages: List[Dict]) -> Optional[Dict]:
    if not CLAUDE_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": CLAUDE_MODEL,
                "max_tokens": 1500,
                "system": SYSTEM_PROMPT,
                "messages": messages,
                "tools": TOOLS
            }
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"Claude API error {resp.status}: {await resp.text()}")
        return None
    except Exception as e:
        print(f"Claude error: {e}")
        return None

async def call_openai_fallback(messages: List[Dict]) -> Optional[Dict]:
    """Plain-text fallback (no tool calling) when Claude is unavailable."""
    if not OPENAI_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            oa_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
                {"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else json.dumps(m["content"], ensure_ascii=False)}
                for m in messages
            ]
            payload = {
                "model": "gpt-4o-mini",
                "messages": oa_messages,
                "max_tokens": 1000,
                "temperature": 0.7
            }
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"].get("content", "")
                    return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}
        return None
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None

# Map Claude tool names -> pending_action type used by the frontend
TOOL_TYPE_MAP = {
    "create_task": "task",
    "create_workout_plan": "workout",
    "create_study_plan": "study",
    "create_language_lesson": "language",
    "start_placement_test": "placement_test",
}

# ── Enhanced AI Chat ──
@app.post("/api/chat")
async def chat_endpoint(msg: ChatMessage):
    """Real AI chat: sends full conversation to Claude with tool definitions,
    and turns any tool_use blocks into structured pending_actions that the
    frontend shows as a confirm/reject card before touching any local data.
    """

    user_id = msg.user_id
    if user_id not in conversations:
        conversations[user_id] = []

    # msg.context lets the frontend replay recent chat history so the
    # assistant has real memory of the conversation, not just the last line.
    history = msg.context or conversations[user_id]
    messages = [{"role": h["role"], "content": h["content"]} for h in history if h.get("content")]
    messages.append({"role": "user", "content": msg.text})
    messages = messages[-20:]

    api_response = await call_claude(messages)
    model_used = "claude"

    if not api_response:
        api_response = await call_openai_fallback(messages)
        model_used = "gpt-4o-mini"

    if not api_response:
        # No AI key configured / both providers unreachable.
        reply = enhanced_fallback(msg.text)
        conversations[user_id].append({"role": "user", "content": msg.text})
        conversations[user_id].append({"role": "assistant", "content": reply})
        return {"response": reply, "pending_actions": [], "actions": [], "timestamp": datetime.now().isoformat(), "model": "local"}

    content_blocks = api_response.get("content", [])
    text_parts = [b["text"] for b in content_blocks if b.get("type") == "text" and b.get("text")]
    reply_text = "\n".join(text_parts).strip()

    pending_actions = []
    for block in content_blocks:
        if block.get("type") == "tool_use":
            tool_name = block.get("name")
            action_type = TOOL_TYPE_MAP.get(tool_name)
            if action_type:
                pending_actions.append({
                    "id": block.get("id"),
                    "type": action_type,
                    "tool": tool_name,
                    "payload": block.get("input", {})
                })

    if not reply_text and pending_actions:
        reply_text = "این پیشنهاد رو آماده کردم — نگاهش کن و اگه خوبه تایید کن تا اضافه بشه 👇"
    if not reply_text:
        reply_text = "متوجه شدم، بیشتر توضیح بده تا دقیق‌تر کمک کنم."

    conversations[user_id].append({"role": "user", "content": msg.text})
    conversations[user_id].append({"role": "assistant", "content": reply_text})
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]

    return {
        "response": reply_text,
        "pending_actions": pending_actions,
        "actions": [{"type": a["type"], "extracted": True} for a in pending_actions],  # legacy field, kept for compatibility
        "timestamp": datetime.now().isoformat(),
        "model": model_used
    }

def enhanced_fallback(text: str) -> str:
    """Much smarter fallback responses."""
    t = text.lower()

    # Workout planning
    if any(w in t for w in ["ورزش", "تمرین", "بدنسازی", "fitness", "workout"]):
        return """💪 می‌خوای برنامه ورزشی شخصی‌سازی شده بسازم؟

لطفاً این اطلاعات رو بده:
• وزن و قد
• سن و جنسیت
• هدف (کاهش وزن/عضله‌سازی/تناسب اندام)
• سطح (مبتدی/متوسط/پیشرفته)
• وسایل در دسترس (دمبل/کش/هیچ)

با این اطلاعات یه برنامه کامل هفتگی می‌چینم که خودش به بخش ورزش و وظایف اضافه بشه! 🎯"""

    # Language learning
    if any(w in t for w in ["زبان", "انگلیسی", "فرانسه", "آلمانی", "language", "duolingo", "درس زبان"]):
        return """🌍 عالیه! می‌خوای یه زبان جدید یاد بگیری؟

زبان‌های پشتیبانی شده:
🇺🇸 انگلیسی | 🇫🇷 فرانسوی | 🇩🇪 آلمانی | 🇪🇸 اسپانیایی | 🇮🇹 ایتالیایی | 🇯🇵 ژاپنی

می‌تونم برات:
• 📚 درس‌های سطح‌بندی شده بسازم
• 🗣️ مکالمه واقعی با AI تمرین کنی
• 📝 لغت و گرامر تدریس کنم
• 🎯 آزمون تعاملی بگیرم

کدوم زبان و چه سطحی؟ (A1 مبتدی تا C2 پیشرفته)"""

    # Study planning
    if any(w in t for w in ["درس", "مطالعه", "کنکور", "امتحان", "study", "پومودورو"]):
        return """📚 می‌خوای برنامه مطالعاتی بچینم؟

می‌تونم برات:
• 📅 تقسیم‌بندی موضوعات روی روزها
• ⏱️ تایمر پومودورو تنظیم کنم
• ✅ وظایف روزانه درسی اضافه کنم
• 📊 پیشرفتت رو Track کنم

چه درسی و چند ساعت در روز می‌خوای بخونی؟"""

    # Task planning
    if any(w in t for w in ["وظیفه", "کار", "تسک", "task", "برنامه ریزی", "plan"]):
        return """✅ می‌خوام برات برنامه‌ریزی کنم!

می‌تونم:
• 📋 لیست وظایف امروز/هفته بسازم
• ⏰ یادآوری تنظیم کنم
• 📅 به تقویم اضافه کنم
• 🎯 اولویت‌بندی کنم

چه کاری داری؟ بگو خودم همه‌چی رو بچینم و به بخش‌های مربوطه اضافه کنم! 🚀"""

    # Calendar
    if any(w in t for w in ["تقویم", "رویداد", "calendar", "تاریخ", "event"]):
        return "📅 تقویم شمسی کاملاً فعال شده! می‌تونی روی هر روز کلیک کنی و رویداد/وظیفه اون روز رو ببینی. همچنین می‌تونی رویداد جدید اضافه کنی."

    # Budget
    if any(w in t for w in ["بودجه", "پول", "هزینه", "budget", "خرج"]):
        return "💰 برای مدیریت مالی، به بخش 'بیشتر > بودجه' برو. می‌تونی هزینه‌ها رو دسته‌بندی کنی، محدودیت ماهانه تعیین کنی و نمودار مصرف ببینی."

    # Greeting
    if any(w in t for w in ["سلام", "خوبی", "حالت", "چطوری", "hi", "hello"]):
        return f"""سلام! 👋 من ZHOVIKA هستم، دستیار شخصی هوشمندت.

امروز چطور می‌تونم کمکت کنم؟

🎯 قابلیت‌های من:
• ✅ مدیریت وظایف هوشمند
• 💪 برنامه‌ریزی ورزشی شخصی‌سازی شده
• 📚 برنامه مطالعاتی + پومودورو
• 🌍 آموزش زبان (بهتر از دولینگو!)
• 💰 پیگیری بودجه
• 📅 تقویم شمسی کامل
• 📱 مدیریت شبکه‌های اجتماعی

کدوم بخش رو می‌خوای شروع کنی؟"""

    return "متوجه شدم! می‌تونی جزئیات بیشتری بدی یا از منوی پایین بخش مورد نظر رو انتخاب کن. من می‌تونم برات برنامه‌ریزی کنم، وظایف بسازم، تمرین بدم، یا هر کمک دیگه‌ای بکنم. 🎯"

# ── Smart Planning Endpoints ──
@app.post("/api/plan/workout")
async def plan_workout(plan: WorkoutPlan):
    """Generate personalized workout plan."""

    bmi = plan.weight / ((plan.height/100) ** 2)

    # Generate plan based on stats
    if plan.level == "beginner":
        exercises = [
            {"name": "پیاده‌روی سریع", "duration": 30, "calories": 150, "sets": None},
            {"name": "اسکوات", "duration": 10, "calories": 50, "sets": "3×10"},
            {"name": "شنا سوئدی", "duration": 5, "calories": 30, "sets": "3×5"},
            {"name": "پلانک", "duration": 5, "calories": 20, "sets": "3×20 ثانیه"},
        ]
    elif plan.level == "intermediate":
        exercises = [
            {"name": "دویدن آهسته", "duration": 30, "calories": 300, "sets": None},
            {"name": "اسکوات با دمبل", "duration": 15, "calories": 100, "sets": "4×12"},
            {"name": "شنا", "duration": 10, "calories": 60, "sets": "3×15"},
            {"name": "لانگ", "duration": 10, "calories": 80, "sets": "3×12 هر پا"},
            {"name": "پلانک", "duration": 5, "calories": 30, "sets": "3×45 ثانیه"},
        ]
    else:
        exercises = [
            {"name": "دویدن تناوبی", "duration": 30, "calories": 400, "sets": None},
            {"name": "اسکوات پرشی", "duration": 15, "calories": 150, "sets": "4×15"},
            {"name": "شنا الماس", "duration": 10, "calories": 100, "sets": "4×12"},
            {"name": "ددلیفت", "duration": 15, "calories": 120, "sets": "4×8"},
            {"name": "بورپی", "duration": 10, "calories": 150, "sets": "3×10"},
        ]

    weekly_schedule = {
        "شنبه": "بالا تنه + کاردیو",
        "یکشنبه": "پایین تنه",
        "دوشنبه": "استراحت/یوگا",
        "سه‌شنبه": "کاردیو",
        "چهارشنبه": "بالا تنه",
        "پنجشنبه": "پایین تنه + شکم",
        "جمعه": "استراحت فعال (پیاده‌روی)"
    }

    return {
        "status": "success",
        "bmi": round(bmi, 1),
        "plan": {
            "daily_exercises": exercises,
            "weekly_schedule": weekly_schedule,
            "tips": [
                "قبل از تمرین ۱۰ دقیقه گرم کن",
                "بعد از تمرین ۵ دقیقه سرد کن",
                "آب کافی بنوش (حداقل ۲ لیتر)"
            ]
        },
        "tasks_to_create": [
            {"text": f"💪 تمرین امروز: {exercises[0]['name']}", "priority": "high"}
        ]
    }

@app.post("/api/plan/study")
async def plan_study(plan: StudyPlan):
    """Generate study plan."""
    total_hours = plan.hours_per_day * plan.duration_days

    # Create daily breakdown
    schedule = []
    for day in range(plan.duration_days):
        schedule.append({
            "day": day + 1,
            "topics": [f"موضوع {day+1}"],
            "hours": plan.hours_per_day,
            "pomodoros": plan.hours_per_day * 2  # 2 pomodoros per hour
        })

    return {
        "status": "success",
        "total_hours": total_hours,
        "schedule": schedule,
        "tasks_to_create": [
            {"text": f"📚 مطالعه {plan.subject} - روز ۱", "priority": "medium"}
        ]
    }

# ── Language Learning Endpoints ──
@app.post("/api/language/lesson")
async def language_lesson(req: LanguageRequest):
    """Generate language lesson."""

    lessons = {
        "english": {
            "A1": {
                "title": "مقدماتی: معرفی خود",
                "vocabulary": [
                    {"word": "Hello", "meaning": "سلام", "example": "Hello, my name is..."},
                    {"word": "Good morning", "meaning": "صبح بخیر", "example": "Good morning! How are you?"},
                    {"word": "Thank you", "meaning": "ممنون", "example": "Thank you very much!"},
                    {"word": "Please", "meaning": "لطفاً", "example": "Please, help me."},
                    {"word": "Friend", "meaning": "دوست", "example": "She is my friend."}
                ],
                "grammar": "فعل 'to be' در حال ساده: I am, You are, He/She is",
                "exercise": [
                    {"q": "I ___ a student.", "options": ["am", "is", "are"], "answer": "am"},
                    {"q": "She ___ my sister.", "options": ["am", "is", "are"], "answer": "is"}
                ]
            },
            "B1": {
                "title": "متوسط: گذشته ساده",
                "vocabulary": [
                    {"word": "Yesterday", "meaning": "دیروز", "example": "I went there yesterday."},
                    {"word": "Experience", "meaning": "تجربه", "example": "It was a great experience."},
                    {"word": "Journey", "meaning": "سفر", "example": "The journey was long."}
                ],
                "grammar": "گذشته ساده: افعال منظم با +ed و افعال نامنظم",
                "exercise": [
                    {"q": "I ___ (go) to school yesterday.", "options": ["goed", "went", "gone"], "answer": "went"},
                    {"q": "She ___ (watch) a movie last night.", "options": ["watched", "watch", "watching"], "answer": "watched"}
                ]
            }
        },
        "french": {
            "A1": {
                "title": "Français débutant: Présentation",
                "vocabulary": [
                    {"word": "Bonjour", "meaning": "سلام/صبح بخیر", "example": "Bonjour! Comment allez-vous?"},
                    {"word": "Merci", "meaning": "ممنون", "example": "Merci beaucoup!"},
                    {"word": "Ami", "meaning": "دوست", "example": "C'est mon ami."}
                ],
                "grammar": "فعل être (بودن): Je suis, Tu es, Il/Elle est",
                "exercise": [
                    {"q": "Je ___ français.", "options": ["suis", "es", "est"], "answer": "suis"},
                    {"q": "Il ___ professeur.", "options": ["suis", "es", "est"], "answer": "est"}
                ]
            }
        },
        "german": {
            "A1": {
                "title": "Deutsch Anfänger: Vorstellung",
                "vocabulary": [
                    {"word": "Hallo", "meaning": "سلام", "example": "Hallo! Wie geht's?"},
                    {"word": "Danke", "meaning": "ممنون", "example": "Danke schön!"},
                    {"word": "Freund", "meaning": "دوست", "example": "Das ist mein Freund."}
                ],
                "grammar": "فعل sein: Ich bin, Du bist, Er/Sie ist",
                "exercise": [
                    {"q": "Ich ___ müde.", "options": ["bin", "bist", "ist"], "answer": "bin"},
                    {"q": "Du ___ nett.", "options": ["bin", "bist", "ist"], "answer": "bist"}
                ]
            }
        }
    }

    lang_data = lessons.get(req.language, lessons["english"])
    level_data = lang_data.get(req.level, lang_data["A1"])

    return {
        "status": "success",
        "language": req.language,
        "level": req.level,
        "lesson": level_data,
        "xp_reward": 50,
        "next_lesson": f"{req.language}_{req.level}_2"
    }

@app.post("/api/language/conversation")
async def language_conversation(req: LanguageRequest):
    """AI conversation practice."""

    scenarios = {
        "english": [
            {"role": "system", "text": "You are a friendly English teacher. Have a natural conversation. Correct mistakes gently."},
            {"role": "ai", "text": "Hi there! 👋 Let's practice English. How was your day? Tell me about something interesting you did recently!"}
        ],
        "french": [
            {"role": "system", "text": "You are a friendly French teacher. Have a natural conversation in French."},
            {"role": "ai", "text": "Bonjour! 😊 Parlons français! Comment s'appelle-tu? D'où viens-tu?"}
        ],
        "german": [
            {"role": "system", "text": "You are a friendly German teacher. Have a natural conversation in German."},
            {"role": "ai", "text": "Hallo! 👋 Lass uns Deutsch üben! Wie heißt du? Wo wohnst du?"}
        ]
    }

    scenario = scenarios.get(req.language, scenarios["english"])

    if req.message:
        # Continue conversation with AI (plain chat, no tools needed here)
        messages = [{"role": "user", "content": req.message}]
        api_resp = await call_claude(messages) or await call_openai_fallback(messages)
        if api_resp:
            texts = [b["text"] for b in api_resp.get("content", []) if b.get("type") == "text"]
            reply = "\n".join(texts).strip() or f"Great! Keep practicing! You said: '{req.message}'. Let's continue! 🎯"
        else:
            reply = f"Great! Keep practicing! You said: '{req.message}'. Let's continue! 🎯"
    else:
        reply = scenario[1]["text"]

    return {
        "status": "success",
        "language": req.language,
        "ai_message": reply,
        "corrections": [],
        "xp_reward": 20
    }

# ── Sync Endpoints ──
@app.post("/api/sync")
async def sync_endpoint(data: SyncData):
    users_data[data.user_id] = {
        "tasks": data.tasks,
        "notes": data.notes,
        "reminders": data.reminders,
        "expenses": data.expenses,
        "exercises": data.exercises,
        "study": data.study,
        "language": data.language,
        "last_sync": datetime.now().isoformat()
    }
    return {"status": "synced", "timestamp": datetime.now().isoformat()}

@app.get("/api/sync/{user_id}")
async def get_sync(user_id: str):
    if user_id not in users_data:
        raise HTTPException(status_code=404, detail="No data found")
    return users_data[user_id]

# ── Instagram & Telegram ──
@app.post("/api/instagram/post")
async def instagram_post(post: IGPost):
    ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not ig_token:
        return {"status": "mock", "message": "Instagram API token not configured"}
    scheduled_posts.append({
        "platform": "instagram", "type": "post",
        "caption": post.caption, "schedule_time": post.schedule_time,
        "created": datetime.now().isoformat()
    })
    return {"status": "scheduled" if post.schedule_time else "posted", "post_id": f"ig_{len(scheduled_posts)}"}

@app.post("/api/telegram/send")
async def telegram_send(msg: TGMessage, background_tasks: BackgroundTasks):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return {"status": "error", "message": "Telegram bot token not configured"}
    if msg.schedule_time:
        scheduled_posts.append({"platform": "telegram", "type": "message", "text": msg.text, "channel_id": msg.channel_id, "schedule_time": msg.schedule_time})
        return {"status": "scheduled"}
    background_tasks.add_task(send_tg_message, bot_token, msg)
    return {"status": "sent"}

async def send_tg_message(bot_token: str, msg: TGMessage):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": msg.channel_id, "text": msg.text, "parse_mode": "HTML", "disable_notification": msg.silent}) as resp:
                result = await resp.json()
                if msg.pin and result.get("ok"):
                    await session.post(f"https://api.telegram.org/bot{bot_token}/pinChatMessage", json={"chat_id": msg.channel_id, "message_id": result["result"]["message_id"]})
    except Exception as e:
        print(f"TG error: {e}")

# ── Reminders ──
@app.post("/api/reminders")
async def create_reminder(reminder: ReminderCreate):
    return {"status": "created", "reminder": reminder.dict(), "created": datetime.now().isoformat()}

# ── Health ──
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "ai_available": bool(OPENAI_KEY or CLAUDE_KEY), "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
