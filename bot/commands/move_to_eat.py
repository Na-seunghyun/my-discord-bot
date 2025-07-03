from discord import app_commands
from discord.ext import commands
import asyncio
from bot.bot_instance import bot, tree

auto_disconnect_tasks = {}  # bot/events.py에 선언된 것과 공유할 필요 있음. 공유를 위해 별도 모듈로 분리하거나 인스턴스 공유 필요.

@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동", guild=bot.guilds[0])
async def move_to_eat(interaction: commands.Interaction):
    user = interaction.user
    guild = interaction.guild
    vc = guild.voice_channels
    eat_channel = next((ch for ch in vc if ch.name == "밥좀묵겠습니다"), None)

    if not eat_channel:
        await interaction.response.send_message("❌ 채널 없음", ephemeral=True)
        return

    try:
        await user.move_to(eat_channel)
        await interaction.response.send_message("🍚 밥 채널로 이동 완료", ephemeral=True)
        # 자동퇴장 타이머 시작
        task = asyncio.create_task(auto_disconnect_after_timeout(user, eat_channel, timeout=1200))
        auto_disconnect_tasks[user.id] = task
    except Exception:
        await interaction.response.send_message("❌ 이동 실패", ephemeral=True)


async def auto_disconnect_after_timeout(user, channel, timeout=1200):
    # 함수 본문은 bot/events.py의 동일 함수와 통일 필요
    pass
