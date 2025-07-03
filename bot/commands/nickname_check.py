from discord import app_commands
from bot.bot_instance import tree, GUILD_ID
import re

nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")

@tree.command(name="검사", description="닉네임 검사", guild=discord.Object(id=GUILD_ID))
async def nickname_check(interaction: app_commands.Interaction):
    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        nick = member.nick or member.name
        parts = nick.split("/")
        if len(parts) != 3 or not nickname_pattern.fullmatch("/".join(p.strip() for p in parts)):
            count += 1
            try:
                await interaction.channel.send(f"{member.mention} 닉네임 형식이 올바르지 않아요.")
            except:
                pass
    await interaction.followup.send(f"🔍 검사 완료: {count}명 문제 있음", ephemeral=True)
