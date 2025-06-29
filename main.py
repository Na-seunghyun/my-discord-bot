from keep_alive import keep_alive  # ✅ 추가: Koyeb 헬스체크용 Flask 서버 실행

import discord
from discord.ext import commands
from discord import app_commands
import re
import os
import random
import asyncio

# 디스코드 서버 ID
GUILD_ID = 1309433603331198977

# 봇 설정
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True  # 음성 상태 변화를 받기 위해 필요

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")

# 자동 퇴장 태스크 관리용 딕셔너리 (user_id: asyncio.Task)
auto_disconnect_tasks = {}

async def auto_disconnect_after_timeout(user: discord.Member, channel: discord.VoiceChannel, timeout=1200):
    await asyncio.sleep(timeout)  # 20분 대기 (1800초)

    # 유저가 아직 음성채널에 있고, 채널이 동일한지 체크
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            print(f"{user} 님이 {channel} 채널에서 30분 무동작으로 강제 퇴장 처리됨")
            # 태스크 딕셔너리에서 제거
            auto_disconnect_tasks.pop(user.id, None)
        except Exception as e:
            print(f"강제 퇴장 실패: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    # 음성 채널 이동(또는 연결 해제)이 발생했을 때
    if member.id in auto_disconnect_tasks:
        # 기존 자동퇴장 태스크 취소
        task = auto_disconnect_tasks.pop(member.id)
        task.cancel()
        print(f"{member} 님의 자동퇴장 타이머가 취소되었습니다.")

@bot.event
async def on_voice_state_update(member, before, after):
    # 봇은 무시
    if member.bot:
        return

    # 대기방에 새롭게 들어간 경우만 감지
    if after.channel and after.channel.name == "대기방":
        if not before.channel or before.channel != after.channel:
            # 자유채팅방 찾기
            guild = member.guild
            text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(
                    f"{member.mention} 나도 게임을 하고싶어! "
                    f"나를 끼워주지 않으면 토끼록끼가 모든 음성채널을 폭파합니다. 💥🐰"
                )


@tree.command(name="검사", description="서버 전체 닉네임을 검사합니다.", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in guild.members:
        if member.bot:
            continue
        raw_nickname = member.nick or member.name
        parts = raw_nickname.split("/")
        if len(parts) != 3:
            valid = False
            cleaned_nickname = raw_nickname
        else:
            clean_parts = [p.strip().replace(" ", "") for p in parts]
            cleaned_nickname = "/".join(clean_parts)
            valid = bool(nickname_pattern.fullmatch(cleaned_nickname))

        if not valid:
            try:
                await interaction.channel.send(
                    f"{member.mention} 님, 별명 형식이 올바르지 않습니다.\n"
                    f"이름 / 아이디 / 년생 형식으로 변경해주세요."
                )
            except Exception as e:
                print(f"메시지 전송 실패: {e}")
            count += 1

    await interaction.followup.send(
        f"🔍 닉네임 검사 완료! 총 {count}명의 별명이 규칙에 맞지 않습니다.\n"
        f"🐰 토끼록끼님 명령에 복종합니다.",
        ephemeral=True,
    )

@tree.command(name="소환", description="다른 음성 채널에 있는 유저들을 토끼록끼의 엄청난 파워로 현재 채널로 모두 이동시킵니다.", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    guild = interaction.guild
    user_channel = interaction.user.voice.channel if interaction.user.voice else None

    if not user_channel:
        await interaction.response.send_message("❌ 먼저 음성 채널에 접속해주세요!", ephemeral=True)
        return

    exclude_channel_name = "밥좀묵겠습니다"
    moved_count = 0

    for vc in guild.voice_channels:
        if vc.name == exclude_channel_name or vc == user_channel:
            continue

        for member in vc.members:
            if not member.bot:
                try:
                    await member.move_to(user_channel)
                    moved_count += 1
                except Exception as e:
                    print(f"{member} 이동 실패: {e}")

    await interaction.response.send_message(f"📣 {moved_count}명을 {user_channel.name} 채널로 토끼롞끼의 강력한 힘으로 소환했습니다!")

class TeamMoveView(discord.ui.View):
    def __init__(self, teams, empty_channels, origin_channel):
        super().__init__(timeout=None)
        self.teams = teams
        self.empty_channels = empty_channels
        self.origin_channel = origin_channel
        self.moved = False  # ✅ 중복 이동 방지 플래그

    @discord.ui.button(label="✅ 팀 이동 시작", style=discord.ButtonStyle.green)
    async def move_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.moved:
            await interaction.response.send_message("⚠️ 이미 팀 이동이 완료되었습니다.", ephemeral=True)
            return

        for team, channel in zip(self.teams[1:], self.empty_channels):
            for member in team:
                try:
                    await member.move_to(channel)
                except Exception as e:
                    print(f"{member} 이동 실패: {e}")

        self.moved = True
        button.disabled = True
        await interaction.response.edit_message(content="🚀 토끼록끼의 엄청난 속도로 팀 이동 완료! 버튼은 한번만 사용할 수 있지롱.", view=self)
        self.stop()

@tree.command(name="팀짜기", description="음성 채널 멤버를 팀당 인원수로 나누고 이동 버튼을 제공합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(team_size="팀당 인원수 (2, 3, 4 중 선택)")
@app_commands.choices(team_size=[
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
    app_commands.Choice(name="4", value=4),
])
async def 팀짜기(interaction: discord.Interaction, team_size: app_commands.Choice[int]):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버 내에서만 사용할 수 있습니다.", ephemeral=True)
        return

    voice_state = interaction.user.voice
    if not voice_state or not voice_state.channel:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가야 합니다.", ephemeral=True)
        return

    origin_channel = voice_state.channel
    members = [m for m in origin_channel.members if not m.bot]

    if len(members) < 2:
        await interaction.response.send_message("❌ 팀을 나누기 위해서는 최소 2명이 필요합니다.", ephemeral=True)
        return

    random.shuffle(members)
    team_size_value = team_size.value
    teams = [members[i:i + team_size_value] for i in range(0, len(members), team_size_value)]

    voice_channel_names = [f"일반{i}" for i in range(1, 17)]
    target_channels = [discord.utils.get(guild.voice_channels, name=name) for name in voice_channel_names]
    target_channels = [ch for ch in target_channels if ch is not None]
    empty_channels = [ch for ch in target_channels if len(ch.members) == 0 and ch != origin_channel]

    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message(
            f"❌ 빈 음성 채널이 부족합니다! 필요한 채널: {len(teams) - 1}, 비어있는 채널: {len(empty_channels)}",
            ephemeral=True
        )
        return

    msg = f"🎲 팀 나누기 완료! 팀당 {team_size_value}명 기준입니다.\n\n"
    msg += f"**팀 1 (현재 채널 {origin_channel.name}):** {', '.join(m.mention for m in teams[0])}\n"
    for idx, (team, channel) in enumerate(zip(teams[1:], empty_channels), start=2):
        mentions = ", ".join(m.mention for m in team)
        msg += f"**팀 {idx} (예정 채널 {channel.name}):** {mentions}\n"
    msg += "\n📌 아래 버튼을 클릭하면 팀별로 음성 채널로 이동됩니다."

    view = TeamMoveView(teams=teams, empty_channels=empty_channels, origin_channel=origin_channel)
    await interaction.response.send_message(msg, view=view)

# --- 여기에 /밥 명령어 추가 ---

@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동합니다.", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if not user.voice or not user.voice.channel:
        await interaction.response.send_message("❌ 먼저 음성 채널에 접속해주세요!", ephemeral=True)
        return

    target_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")

    if not target_channel:
        await interaction.response.send_message("❌ '밥좀묵겠습니다' 음성채널을 찾을 수 없습니다.", ephemeral=True)
        return

    if not text_channel:
        await interaction.response.send_message("❌ '자유채팅방' 텍스트채널을 찾을 수 없습니다.", ephemeral=True)
        return

    try:
        # 음성 채널 이동
        await user.move_to(target_channel)
        await interaction.response.send_message(f"🍚 '{target_channel.name}' 채널로 이동했습니다! 20분 후 토끼록끼의 강력한 파워로 자동 퇴장된다!.", ephemeral=True)

        # 즉시 경고 메시지 전송
        await text_channel.send(f"{user.mention}님, 20분 동안 밥을 먹지 못하면 토끼록끼의 강력한 염력으로 강제퇴장 당할 수 있습니다.")

        # 기존 자동퇴장 타이머가 있다면 취소
        if user.id in auto_disconnect_tasks:
            auto_disconnect_tasks[user.id].cancel()

        # 새 타이머 등록
        task = asyncio.create_task(auto_disconnect_after_timeout(user, target_channel, timeout=1200))
        auto_disconnect_tasks[user.id] = task

    except Exception as e:
        await interaction.response.send_message(f"❌ 채널 이동에 실패했습니다: {e}", ephemeral=True)


# ▶️ keep_alive를 먼저 실행
keep_alive()  # ✅ Koyeb 헬스체크를 위한 웹 서버 실행

# ▶️ 디스코드 봇 실행
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 설정되지 않았습니다.")
