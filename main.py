from keep_alive import keep_alive

import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import os
import random
import asyncio

# 디스코드 서버 ID
GUILD_ID = 1309433603331198977
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")
auto_disconnect_tasks = {}

# 자동 퇴장 타이머 함수 (로그 추가)
async def auto_disconnect_after_timeout(user: discord.Member, channel: discord.VoiceChannel, timeout=1200):
    print(f"[자동퇴장 타이머 시작] {user}님, {timeout}초 후 자동퇴장 대기중...")
    await asyncio.sleep(timeout)
    print(f"[자동퇴장 타이머 종료] {user}님 퇴장 시도")
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            print(f"{user} 님이 {channel.name}에서 자동 퇴장 처리됨")

            guild = user.guild
            text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 결국 20분 동안 밥을 먹지 못해 강제 퇴장 당했습니다. 😢")

        except Exception as e:
            print(f"강제 퇴장 실패: {e}")
        finally:
            auto_disconnect_tasks.pop(user.id, None)
    else:
        print(f"{user} 님이 이미 채널을 떠났거나 다른 채널에 있습니다.")
        auto_disconnect_tasks.pop(user.id, None)

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    check_voice_channels_for_streaming.start()
    print(f"✅ 봇 로그인 완료: {bot.user} | 슬래시 명령어 동기화 완료")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if member.id in auto_disconnect_tasks:
        task = auto_disconnect_tasks.pop(member.id)
        task.cancel()
        print(f"{member.name}님의 자동퇴장 타이머가 취소되었습니다.")

    # 대기방 입장 알림
    if after.channel and after.channel.name == "대기방":
        if not before.channel or before.channel.id != after.channel.id:
            text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(
                    f"{member.mention} 나도 게임을 하고싶어! 나를 끼워주지 않으면 토끼록끼가 모든 음성채널을 폭파합니다. 💥🐰"
                )

    # 방송 종료 감지 (같은 채널에서 방송만 꺼졌을 때)
    was_streaming = before.self_stream
    is_streaming = after.self_stream
    same_channel = before.channel == after.channel and after.channel is not None

    if was_streaming and not is_streaming and same_channel:
        text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
        if text_channel:
            embed = discord.Embed(
                title="📴 방송 종료 감지!",
                description=f"{member.mention} 님이 `{after.channel.name}` 채널에서 방송을 종료했어요.\n혹시 실수로 끄셨나요? 🎥 다시 켜주세요!",
                color=discord.Color.orange()
            )
            embed.add_field(name="채널명", value=after.channel.name, inline=True)
            embed.add_field(name="방송 상태", value="❌ 꺼짐", inline=True)
            await text_channel.send(content=member.mention, embed=embed)

@tasks.loop(minutes=10)
async def check_voice_channels_for_streaming():
    for guild in bot.guilds:
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
        if not text_channel:
            continue

        for vc in guild.voice_channels:
            if vc.name in MONITORED_CHANNEL_NAMES and vc.members:
                if not any(m.voice and m.voice.self_stream for m in vc.members if not m.bot):
                    embed = discord.Embed(
                        title="🚨 방송 꺼짐 감지",
                        description=f"`{vc.name}` 채널에 사람이 있지만 Go Live 방송이 꺼져 있습니다.",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="현재 인원", value=f"{len(vc.members)}명", inline=True)
                    embed.add_field(name="라이브 상태", value="❌ 없음", inline=True)
                    mentions = " ".join(m.mention for m in vc.members if not m.bot)
                    await text_channel.send(content=mentions, embed=embed)

# ✅ 기존 명령어 및 이벤트 핸들러들 그대로 유지
# 검사, 소환, 팀짜기, 밥 이동 등 기존 코드 아래에 이어서 추가

# 명령어: 검사
@tree.command(name="검사", description="서버 전체 닉네임을 검사합니다.", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용 가능합니다.", ephemeral=True)
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
        else:
            clean_parts = [p.strip().replace(" ", "") for p in parts]
            cleaned_nickname = "/".join(clean_parts)
            valid = bool(nickname_pattern.fullmatch(cleaned_nickname))

        if not valid:
            try:
                await interaction.channel.send(
                    f"{member.mention} 님, 별명 형식이 올바르지 않습니다.\n이름 / 아이디 / 년생 형식으로 변경해주세요."
                )
            except:
                pass
            count += 1

    await interaction.followup.send(f"🔍 닉네임 검사 완료: {count}명 오류", ephemeral=True)

# 명령어: 소환
@tree.command(name="소환", description="모든 유저를 현재 음성 채널로 소환합니다.", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    user_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not user_channel:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    if user_channel.name in ["대기방", "밥좀묵겠습니다", "게스트방", "클랜훈련소"]:
        await interaction.response.send_message("❌ 이 채널에서는 소환 명령어를 사용할 수 없습니다.", ephemeral=True)
        return

    guild = interaction.guild
    moved = 0
    for vc in guild.voice_channels:
        if vc == user_channel or vc.name in ["밥좀묵겠습니다", "대기방", "게스트방", "클랜훈련소"]:
            continue
        for member in vc.members:
            if not member.bot:
                try:
                    await member.move_to(user_channel)
                    moved += 1
                except:
                    pass

    await interaction.response.send_message(f"📢 총 {moved}명을 소환했습니다!")

# 명령어: 팀짜기
class TeamMoveView(discord.ui.View):
    def __init__(self, teams, empty_channels, origin_channel):
        super().__init__(timeout=None)
        self.teams = teams
        self.empty_channels = empty_channels
        self.origin_channel = origin_channel
        self.moved = False

    @discord.ui.button(label="🚀 팀 이동 시작", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.moved:
            await interaction.response.send_message("⚠️ 이미 이동 완료됨", ephemeral=True)
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

@tree.command(name="팀짜기", description="팀을 나누고 버튼으로 이동시킵니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(team_size="팀당 인원수 선택")
@app_commands.choices(team_size=[
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
    app_commands.Choice(name="4", value=4),
])
async def 팀짜기(interaction: discord.Interaction, team_size: app_commands.Choice[int]):
    user_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not user_channel:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    members = [m for m in user_channel.members if not m.bot]
    if len(members) < 2:
        await interaction.response.send_message("❌ 최소 2명 필요!", ephemeral=True)
        return

    random.shuffle(members)
    teams = [members[i:i + team_size.value] for i in range(0, len(members), team_size.value)]

    guild = interaction.guild
    candidate_channels = [discord.utils.get(guild.voice_channels, name=f"일반{i}") for i in range(1, 17)]
    empty_channels = [ch for ch in candidate_channels if ch and len(ch.members) == 0 and ch != user_channel]

    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message("❌ 빈 채널 부족!", ephemeral=True)
        return

    msg = f"🎲 **팀 나누기 완료! 팀당 {team_size.value}명**\n\n"
    msg += f"**팀 1 (현재 채널):** {', '.join(f'`{m.display_name}`' for m in teams[0])}\n"
    for idx, (team, channel) in enumerate(zip(teams[1:], empty_channels), start=2):
        mentions = ", ".join(f"`{m.display_name}`" for m in team)
        msg += f"**팀 {idx} ({channel.name}):** {mentions}\n"   
    msg += "✅ **아래 버튼을 눌러 팀 이동을 시작하세요!**\n\n"
    view = TeamMoveView(teams, empty_channels, user_channel)
    await interaction.response.send_message(msg, view=view)

# 명령어: 밥 이동
@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동합니다.", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
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
        await user.move_to(target_channel)
        await interaction.response.send_message(
            f"🍚 '{target_channel.name}' 채널로 이동했습니다! 20분 후 당신은 자동 퇴장처리 됩니다.",
            ephemeral=True
        )
        await text_channel.send(f"{user.mention}님, 20분 동안 밥을 먹지 못하면 토끼록끼의 강력한 염력으로 강제퇴장 당할 수 있습니다.")

        if user.id in auto_disconnect_tasks:
            auto_disconnect_tasks[user.id].cancel()
            print(f"[타이머 취소] 기존 {user}님의 자동퇴장 타이머가 취소되었습니다.")

        task = asyncio.create_task(auto_disconnect_after_timeout(user, target_channel, timeout=1200))
        auto_disconnect_tasks[user.id] = task
        print(f"[타이머 등록] {user}님 자동퇴장 타이머가 등록되었습니다.")

    except Exception as e:
        try:
            await interaction.response.send_message(f"❌ 채널 이동에 실패했습니다: {e}", ephemeral=True)
        except Exception as send_error:
            print(f"에러 발생, 응답 전송 실패: {send_error}")
        print(f"채널 이동 실패: {e}")

keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
