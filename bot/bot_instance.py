import os
from discord.ext import commands
from discord import app_commands
from keep_alive import keep_alive

import discord

# 봇 초기화, 싱글톤 역할, 토큰 실행 함수 포함

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

GUILD_ID = 1309433603331198977

# Supabase 초기화 코드 (env에서 불러오기)
from supabase import create_client, Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_bot():
    keep_alive()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
