from discord import app_commands
from bot.bot_instance import tree, GUILD_ID

@tree.command(name="소환", description="모두 소환", guild=discord.Object(id=GUILD_ID))
async def summon(interaction: app_commands.Interaction):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 들어가주세요!", ephemeral=True)
        return

    moved = 0
    for other_vc in interaction.guild
