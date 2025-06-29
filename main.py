import discord
from discord.ext import commands
from discord import app_commands
import re
import os
import random

# 디스코드 서버 ID
GUILD_ID = 1309433603331198977

# 봇 설정
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# 닉네임 정규식 패턴
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")


@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    # 전역 명령어 삭제
    tree.clear_commands(guild=None)
    await tree.sync(guild=None)
    print("❎ 전역 명령어 삭제 요청 완료")

    # 길드 명령어 등록
    await tree.sync(guild=guild)
    print(f"✅ 봇 로그인 완료: {bot.user} | 길드 슬래시 명령어 동기화 완료")


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

        print(f"DEBUG 검사중: '{raw_nickname}' -> '{cleaned_nickname}' 유효: {valid}")

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


@tree.command(name="팀짜기", description="음성 채널 멤버를 팀당 인원수로 나누고 빈 채널로 이동", guild=discord.Object(id=GUILD_ID))
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

    team_size_value = team_size.value
    random.shuffle(members)

    # 팀 나누기
    teams = []
    for i in range(0, len(members), team_size_value):
        teams.append(members[i:i + team_size_value])

    # "일반1" ~ "일반16" 음성 채널 리스트 찾기
    voice_channel_names = [f"일반{i}" for i in range(1, 17)]
    target_channels = []
    for name in voice_channel_names:
        ch = discord.utils.get(guild.voice_channels, name=name)
        if ch:
            target_channels.append(ch)

    # 빈 채널 리스트 만들기 (이미 인원이 있는 채널 제외)
    empty_channels = [ch for ch in target_channels if len(ch.members) == 0]

    # 호출 채널(origin_channel)은 빈 채널에서 제외
    if origin_channel in empty_channels:
        empty_channels.remove(origin_channel)

    # 이동할 팀(팀 2부터) 수와 빈 채널 수 비교
    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message(
            f"❌ 빈 음성 채널이 부족합니다! 필요한 채널: {len(teams) - 1}, 비어있는 채널: {len(empty_channels)}",
            ephemeral=True
        )
        return

    # 팀 1은 이동 안 함, 팀 2부터 빈 채널에 차례대로 이동
    for team, channel in zip(teams[1:], empty_channels):
        for member in team:
            try:
                await member.move_to(channel)
            except Exception as e:
                print(f"{member} 이동 실패: {e}")

    # 결과 메시지 작성
    msg = f"🎲 팀 나누기 및 음성 채널 이동 완료! (팀당 {team_size_value}명 기준)\n\n"
    # 팀1은 호출 채널에 그대로
    mentions_team1 = ", ".join(m.mention for m in teams[0])
    msg += f"**팀 1 (기존 채널 {origin_channel.name}):** {mentions_team1}\n"

    # 팀 2부터 이동 채널 명시
    for idx, (team, channel) in enumerate(zip(teams[1:], empty_channels), start=2):
        mentions = ", ".join(m.mention for m in team)
        msg += f"**팀 {idx} ({channel.name}):** {mentions}\n"

    msg += "\n❤️ 오덕봇을 사랑해주세요. 이 영광을 토끼록끼에게 바칩니다."

    await interaction.response.send_message(msg, ephemeral=False)


# ▶️ 디스코드 봇 실행
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 설정되지 않았습니다.")
