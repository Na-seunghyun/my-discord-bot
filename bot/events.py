from bot.bot_instance import bot, tree
import discord
import asyncio
from datetime import datetime, timezone, timedelta
from bot.utils.db import supabase
from bot.utils.constants import MONITORED_CHANNEL_NAMES
from bot.utils.timers import auto_disconnect_after_timeout, auto_disconnect_tasks

streaming_members = set()
waiting_room_message_cache = {}
voice_activity_cache = {}
voice_join_times = {}
channel_last_empty = {}
all_empty_since = None
notified_after_empty = False

@bot.event
async def on_ready():
    guild = discord.Object(id=YOUR_GUILD_ID)  # constants로 옮기세요
    await tree.sync(guild=guild)
    print(f"✅ 봇 로그인: {bot.user}")

@bot.event
async def on_voice_state_update(member, before, after):
    # 이벤트 로직 전체 여기에 넣으세요.
    # 자동퇴장 타이머 관리, 배그 모니터링, 방송 시작/종료 알림, DB 저장 등
    pass

