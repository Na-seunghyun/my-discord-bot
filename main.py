from keep_alive import keep_alive

import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import os
import random
import asyncio
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GUILD_ID = 1309433603331198977
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")
auto_disconnect_tasks = {}
voice_join_times = {}  # user_id: join_time


# 자동 퇴장
async def auto_disconnect_after_timeout(user: discord.Member, channel: discord.VoiceChannel, timeout=1200):
    await asyncio.sleep(timeout)
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            text_channel = discord.utils.get(user.guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 20분 지나서 자동 퇴장당했어요. 🍚")
        except Exception as e:
            print(f"오류: {e}")
    auto_disconnect_tasks.pop(user.id, None)


def sql_escape(s):
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

streaming_members = set()

@bot.event
async def on_voice_state_update(member, before, after):
    global streaming_members

    print(f"Voice state update - member: {member}, before: {before.channel if before else None}, after: {after.channel if after else None}")
    if member.bot:
        return
        
    # 자동 퇴장 타이머 제거
    if member.id in auto_disconnect_tasks:
        auto_disconnect_tasks[member.id].cancel()
        auto_disconnect_tasks.pop(member.id, None)

    # 대기방(예: "대기방") 입장 시 메시지 보내기
    if (before.channel != after.channel) and (after.channel is not None):
        if after.channel.name == "대기방":
            text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{member.mention} 나도 게임하고싶어! 나 도 끼 워 줘!")

    # 입장 기록
    if before.channel is None and after.channel is not None:
        voice_join_times[member.id] = datetime.now(timezone.utc)

    # 퇴장 기록
    elif before.channel is not None and after.channel is None:
        join_time = voice_join_times.pop(member.id, None)
        if join_time:
            left_time = datetime.now(timezone.utc)
            duration = int((left_time - join_time).total_seconds())

            user_id = str(member.id)
            username = member.display_name
            joined_at = join_time.isoformat()
            left_at = left_time.isoformat()

            data = {
                "user_id": user_id,
                "username": username,
                "joined_at": joined_at,
                "left_at": left_at,
                "duration_sec": duration,
            }

            try:
                response = supabase.table("voice_activity").insert(data).execute()
                if response.data:
                    print("✅ DB 저장 성공")
                else:
                    print("⚠️ DB 저장 실패: 응답에 데이터 없음")
            except Exception as e:
                print(f"❌ Supabase 예외 발생: {e}")
       
    # ——— 방송 시작/종료 알림 처리 ———

    # 방송 시작 감지 (False -> True)
    if not before.self_stream and after.self_stream and after.channel is not None:
        if member.id not in streaming_members:
            streaming_members.add(member.id)
            text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
            if text_channel:
                embed = discord.Embed(
                    title="📺 방송 시작 알림!",
                    description=f"{member.mention} 님이 `{after.channel.name}` 채널에서 방송을 시작했어요!\n👀 모두 구경하러 가보세요!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="Go Live 활성화됨")
                await text_channel.send(embed=embed)

    # 방송 종료 감지 (True -> False)
    if before.self_stream and not after.self_stream:
        if member.id in streaming_members:
            streaming_members.remove(member.id)
        # 방송 종료 알림 메시지는 보내지 않습니다!



@tasks.loop(minutes=30)
async def check_voice_channels_for_streaming():
    for guild in bot.guilds:
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
        if not text_channel:
            continue

        for vc in guild.voice_channels:
            if vc.name in MONITORED_CHANNEL_NAMES and vc.members:
                non_bot_members = [m for m in vc.members if not m.bot]
                if not any(m.voice and m.voice.self_stream for m in non_bot_members):
                    mentions = " ".join(m.mention for m in non_bot_members)

                    embed = discord.Embed(
                        title="🚨 방송 꺼짐 감지",
                        description=f"`{vc.name}` 채널에 사람이 있지만 **Go Live 방송이 꺼져 있습니다.**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="현재 인원", value=f"{len(non_bot_members)}명", inline=True)
                    embed.add_field(name="라이브 상태", value="❌ 없음", inline=True)
                    embed.set_footer(text="실수로 꺼졌다면 다시 방송을 켜주세요! 🎥")

                    await text_channel.send(content=mentions, embed=embed)



# ✅ 슬래시 명령어: 검사
@tree.command(name="검사", description="닉네임 검사", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        parts = (member.nick or member.name).split("/")
        if len(parts) != 3 or not nickname_pattern.fullmatch("/".join(p.strip() for p in parts)):
            count += 1
            try:
                await interaction.channel.send(f"{member.mention} 닉네임 형식이 올바르지 않아요.")
            except:
                pass
    await interaction.followup.send(f"🔍 검사 완료: {count}명 문제 있음", ephemeral=True)


# ✅ 슬래시 명령어: 소환
@tree.command(name="소환", description="모두 소환", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 들어가주세요!", ephemeral=True)
        return

    moved = 0
    for other_vc in interaction.guild.voice_channels:
        if other_vc == vc:
            continue
        for member in other_vc.members:
            if not member.bot:
                try:
                    await member.move_to(vc)
                    moved += 1
                except:
                    pass
    await interaction.response.send_message(f"📢 {moved}명 소환 완료!")


# ✅ 슬래시 명령어: 팀짜기
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
async def 팀짜기(interaction: discord.Interaction, team_size: app_commands.Choice[int]):
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

    await interaction.response.send_message(msg, view=TeamMoveView(teams, empty_channels, vc))


# ✅ 슬래시 명령어: 밥
@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: discord.Interaction):
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


# ——— 여기부터 추가 ———
def format_duration(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)  # 86400초 = 1일
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}일")
    if hours > 0 or days > 0:
        parts.append(f"{hours}시간")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}분")
    parts.append(f"{seconds}초")

    return " ".join(parts)


from discord.ui import View, button

class VoiceTopButton(View):
    def __init__(self):
        super().__init__(timeout=180)  # 뷰 타임아웃 3분

    @button(label="접속시간랭킹 보기", style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: discord.Interaction, button: discord.ui.Button):
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
                print("⚠️ 편집할 메시지를 찾을 수 없습니다.")

            await interaction.followup.send(msg, ephemeral=False)

        except Exception as e:
            await interaction.followup.send(f"❗ 오류 발생: {e}", ephemeral=False)





@tree.command(name="접속시간랭킹", description="음성 접속시간 Top 10", guild=discord.Object(id=GUILD_ID))
async def 접속시간랭킹(interaction: discord.Interaction):
    # 1) 즉시 defer — followup 으로 버튼 메시지 전송 준비
    await interaction.response.defer(ephemeral=True)
    # 2) 버튼 메시지는 followup.send 로
    await interaction.followup.send(
        "버튼을 눌러 음성 접속시간 랭킹을 확인하세요.",
        view=VoiceTopButton(),
        ephemeral=True
    )









@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    check_voice_channels_for_streaming.start()
    print(f"✅ 봇 로그인: {bot.user}")


keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
