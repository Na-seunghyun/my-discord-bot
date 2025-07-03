
from bot.bot_instance import tree
from discord import Interaction, app_commands
import random
import discord
from bot.utils.constants import GUILD_ID

class TeamMoveView(discord.ui.View):
    def __init__(self, teams, empty_channels):
        super().__init__(timeout=None)
        self.teams = teams
        self.empty_channels = empty_channels
        self.moved = False

    @discord.ui.button(label="🚀 팀 이동 시작", style=discord.ButtonStyle.green)
    async def move(self, interaction: Interaction, button: discord.ui.Button):
        if self.moved:
            await interaction.response.send_message("이미 이동 완료됨", ephemeral=True)
            return
        for team, channel in zip(self.teams[1:], self.empty_channels):
            for member in team:
                try:
                    await member.move_to(channel)
                except:
                    pass
        self.moved = True
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

@tree.command(name="팀짜기", description="음성 채널 팀 나누기", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(team_size="팀당 인원 수")
@app_commands.choices(team_size=[
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
    app_commands.Choice(name="4", value=4),
])
async def 팀짜기(interaction: Interaction, team_size: app_commands.Choice[int]):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    members = [m for m in vc.members if not m.bot]
    random.shuffle(members)
    teams = [members[i:i + team_size.value] for i in range(0, len(members), team_size.value)]

    guild = interaction.guild
    empty_channels = [ch for ch in guild.voice_channels if ch.name.startswith("일반") and len(ch.members) == 0 and ch != vc]

    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message("❌ 빈 채널 부족", ephemeral=True)
        return

    msg = f"🎲 팀 나누기 완료\n\n**팀 1 (현재 채널):** {', '.join(m.display_name for m in teams[0])}\n"
    for idx, (team, ch) in enumerate(zip(teams[1:], empty_channels), start=2):
        msg += f"**팀 {idx} ({ch.name}):** {', '.join(m.display_name for m in team)}\n"

    await interaction.response.send_message(msg, view=TeamMoveView(teams, empty_channels))
