import os
import discord
from discord.ext import commands
from bot import events  # 이벤트 등록
from bot.commands import check_nickname, summon, team_split, move_to_eat, voice_ranking  # 명령어 임포트
from bot.utils.constants import INTENTS

bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree

def run_bot():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
