
from bot.bot_instance import tree
from discord import Interaction
from discord.ui import View, button
from bot.utils.db import supabase
from bot.utils.formatters import format_duration
from bot.utils.constants import GUILD_ID

class VoiceTopButton(View):
    def __init__(self):
        super().__init__(timeout=180)

    @button(label="접속시간랭킹 보기", style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: Interaction, button):
        await interaction.response.defer(ephemeral=False)
        try:
            response = supabase.rpc("get_top_voice_activity", {}).execute()
            if not hasattr(response, "data") or response.data is None:
                await interaction.followup.send("❌ Supabase 응답 오류 또는 데이터 없음", ephemeral=False)
                return

            data = response.data
            if not data:
                await interaction.followup.send("😥 기록된 접속 시간이 없습니다.", ephemeral=False)
                return

            msg = "🎤 음성 접속시간 Top 10\n"
            for rank, info in enumerate(data, 1):
                time_str = format_duration(info['total_duration'])
                msg += f"{rank}. {info['username']} — {time_str}\n"

            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except discord.errors.NotFound:
                pass

            await interaction.followup.send(msg, ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"❗ 오류 발생: {e}", ephemeral=False)

@tree.command(name="접속시간랭킹", description="음성 접속시간 Top 10", guild=discord.Object(id=GUILD_ID))
async def 접속시간랭킹(interaction: Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(
        "버튼을 눌러 음성 접속시간 랭킹을 확인하세요.",
        view=VoiceTopButton(),
        ephemeral=True
    )
