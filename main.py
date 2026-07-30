#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZHOVIKA Personal Assistant — Backend API
=========================================
FastAPI backend for online features:
- Data sync
- AI chat (OpenAI/Claude integration)
- Instagram API
- Telegram Bot webhook
- Push notifications
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env
load_dotenv()

# ── Models ──
class ChatMessage(BaseModel):
    text: str
    user_id: str
    context: Optional[List[Dict]] = None

class SyncData(BaseModel):
    user_id: str
    tasks: List[Dict] = []
    notes: List[Dict] = []
    reminders: List[Dict] = []
    expenses: List[Dict] = []
    exercises: List[Dict] = []
    study: List[Dict] = []

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
    # Startup
    print("🚀 ZHOVIKA Backend started")
    yield
    # Shutdown
    print("👋 ZHOVIKA Backend stopped")

app = FastAPI(
    title="ZHOVIKA Personal Assistant API",
    description="Backend API for ZHOVIKA PWA and Telegram Bot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory storage (use Redis/DB in production) ──
users_data = {}
scheduled_posts = []

# ── AI Chat Endpoint ──
@app.post("/api/chat")
async def chat_endpoint(msg: ChatMessage):
    """Process AI chat message. Integrates with OpenAI or local model."""

    # Simple rule-based responses (fallback)
    text = msg.text.lower()

    responses = {
        "سلام": "سلام! چطور می‌تونم کمکتون کنم؟",
        "خوبی": "ممنون، خوبم! شما چطورید؟",
        "وظیفه": "می‌تونید وظایف رو توی اپلیکیشن مدیریت کنید. امروز چندتا کار دارید؟",
        "بودجه": "برای مدیریت هزینه‌ها به بخش بودجه اپلیکیشن برید.",
        "ورزش": "برنامه ورزشی امروز: ۳۰ دقیقه پیاده‌روی + ۲۰ اسکوات + ۱۵ شنا",
        "درس": "تکنیک پومودورو رو امتحان کنید: ۲۵ دقیقه تمرکز، ۵ دقیقه استراحت",
        "یادآوری": "یادآوری جدید می‌خواید تنظیم کنم؟",
        "اینستاگرام": "برای پست گذاشتن، حالت آنلاین رو فعال کنید و به بخش شبکه‌های اجتماعی برید.",
        "تلگرام": "ربات تلگرام ZHOVIKA فعاله! می‌تونید پیام broadcast کنید.",
    }

    response_text = "متوجه شدم! می‌تونید جزئیات بیشتری بدید یا از منوی اپلیکیشن استفاده کنید."
    for key, resp in responses.items():
        if key in text:
            response_text = resp
            break

    # Try OpenAI if API key available
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(text) > 5:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are ZHOVIKA, a helpful Persian personal assistant. Respond in Persian (Farsi). Be concise and friendly."},
                            {"role": "user", "content": msg.text}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.7
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response_text = data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI error: {e}")

    return {"response": response_text, "timestamp": datetime.now().isoformat()}

# ── Sync Endpoint ──
@app.post("/api/sync")
async def sync_endpoint(data: SyncData):
    """Sync user data between devices."""
    users_data[data.user_id] = {
        "tasks": data.tasks,
        "notes": data.notes,
        "reminders": data.reminders,
        "expenses": data.expenses,
        "exercises": data.exercises,
        "study": data.study,
        "last_sync": datetime.now().isoformat()
    }
    return {"status": "synced", "timestamp": datetime.now().isoformat()}

@app.get("/api/sync/{user_id}")
async def get_sync(user_id: str):
    """Get synced data for user."""
    if user_id not in users_data:
        raise HTTPException(status_code=404, detail="No data found")
    return users_data[user_id]

# ── Instagram Endpoints ──
@app.post("/api/instagram/post")
async def instagram_post(post: IGPost):
    """Schedule or post to Instagram."""
    # This would integrate with Instagram Graph API
    # For now, return mock response

    ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not ig_token:
        return {"status": "mock", "message": "Instagram API token not configured. Post saved for manual upload."}

    scheduled_posts.append({
        "platform": "instagram",
        "type": "post",
        "caption": post.caption,
        "schedule_time": post.schedule_time,
        "created": datetime.now().isoformat()
    })

    return {
        "status": "scheduled" if post.schedule_time else "posted",
        "post_id": f"ig_{len(scheduled_posts)}",
        "message": "Post processed successfully"
    }

@app.post("/api/instagram/story")
async def instagram_story(image: UploadFile = File(...), text: str = Form("")):
    """Upload story to Instagram."""
    return {"status": "mock", "message": "Story upload endpoint (requires Instagram API)"}

# ── Telegram Endpoints ──
@app.post("/api/telegram/send")
async def telegram_send(msg: TGMessage, background_tasks: BackgroundTasks):
    """Send message via Telegram Bot."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return {"status": "error", "message": "Telegram bot token not configured"}

    if msg.schedule_time:
        scheduled_posts.append({
            "platform": "telegram",
            "type": "message",
            "text": msg.text,
            "channel_id": msg.channel_id,
            "schedule_time": msg.schedule_time,
            "pin": msg.pin,
            "silent": msg.silent
        })
        return {"status": "scheduled", "message": "Message scheduled"}

    # Send immediately
    background_tasks.add_task(send_telegram_message, bot_token, msg)
    return {"status": "sent", "message": "Message sent to Telegram"}

async def send_telegram_message(bot_token: str, msg: TGMessage):
    """Actually send message to Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": msg.channel_id,
        "text": msg.text,
        "parse_mode": "HTML",
        "disable_notification": msg.silent
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if msg.pin and result.get("ok"):
                    # Pin the message
                    pin_url = f"https://api.telegram.org/bot{bot_token}/pinChatMessage"
                    await session.post(pin_url, json={
                        "chat_id": msg.channel_id,
                        "message_id": result["result"]["message_id"],
                        "disable_notification": msg.silent
                    })
    except Exception as e:
        print(f"Telegram send error: {e}")

# ── Reminder Endpoints ──
@app.post("/api/reminders")
async def create_reminder(reminder: ReminderCreate):
    """Create a server-side reminder with push notification."""
    # Store reminder and schedule push notification
    reminder_data = {
        "user_id": reminder.user_id,
        "text": reminder.text,
        "time": reminder.time,
        "repeat": reminder.repeat,
        "created": datetime.now().isoformat()
    }

    # In production, use Celery/APScheduler for scheduling
    return {"status": "created", "reminder": reminder_data}

# ── Health Check ──
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.now().isoformat()}

# ── Main ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
