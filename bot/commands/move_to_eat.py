
from bot.bot_instance import tree
from discord import Interaction
import discord
import asyncio
from bot.utils.constants import GUILD_ID
from bot.utils.timers import auto_disconnect_after_timeout, auto_disconnect_tasks

@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: Interaction):
    user = interaction.user
    guild = interaction.guild
    vc = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
    if not vc:
        await interaction.response.send_message("❌ 채널 없음", ephemeral=True)
        return
    try:
        await user.move_to(vc)
        await interaction.response.send_message("🍚 밥 채널로 이동 완료", ephemeral=True)

        task = asyncio.create_task(auto_disconnect_after_timeout(user, vc, timeout=1200))
        auto_disconnect_tasks[user.id] = task
    except:
        await interaction.response.send_message("❌ 이동 실패", ephemeral=True)
